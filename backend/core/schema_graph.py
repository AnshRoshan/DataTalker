# core/schema_graph.py
"""Schema graph model: tables as nodes, foreign keys (and inferred joins) as edges.

Derived on demand from the cached `detailed_schema` structure (see
agents/schema.py) — nothing is persisted. Shapes:

    detailed_schema = [
        {"table_name": "patients",
         "columns": [{"name": "patient_id", "type": "INTEGER", "primary_key": True,
                      "nullable": False, ...}, ...],
         "foreign_keys": [{"constrained_columns": ["patient_id"],
                           "referred_table": "orders",
                           "referred_columns": ["customer_id"], ...}], ...]

    graph = {"nodes": [{"id": "patients", "name": "patients",
                        "columns": [{"name", "type", "primary_key", "foreign_keys"}]}],
             "edges": [{"source", "target", "label", "inferred"}]}

Edges: explicit FKs from reflection are trusted as-is; for databases without
declared FKs, likely join paths are inferred by matching column-name patterns
(`<table>_id` -> table `table`/`tables`, plus exact-name matches), capped per
table to keep noise down. Inference is deterministic (sorted iteration).
"""
import logging
import re
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Cap on inferred (non-FK) edges contributed by any single table.
MAX_INFERRED_PER_TABLE = 3

_SNAKE_SPLIT = re.compile(r"[_\s]+")


def _tokens(name: str) -> List[str]:
    """Lowercased name split on underscores (snake_case -> words)."""
    return [t for t in _SNAKE_SPLIT.split(str(name).strip().lower()) if t]


def _singular(word: str) -> str:
    """Crude singular form ('addresses' -> 'addresse' is fine — both sides of
    the comparison are normalized the same way, so precision doesn't matter)."""
    if word.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"
    if word.endswith("ses") and len(word) > 3:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _norm(name: str) -> str:
    """Singularized, de-underscored normalization ('order_items' -> 'orderitem')."""
    return "".join(_singular(t) for t in _tokens(name))


def _add_edge(edges: List[Dict[str, Any]], seen: Set[tuple], source: str, target: str,
              label: str, inferred: bool) -> None:
    key = (source, target, label)
    if key in seen or source == target:
        return
    seen.add(key)
    edges.append({"source": source, "target": target, "label": label, "inferred": inferred})


def _infer_joins(detailed_schema: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Infer likely FK edges for schemas without declared foreign keys.

    Heuristics, in priority order per candidate column:
    1. `<something>_id` column -> table `something` (singular/plural normalized)
       whose primary key is `id`/`something_id`/`<something>_id`-ish.
    2. Exact normalized table-name match: column named like another table.
    At most MAX_INFERRED_PER_TABLE edges per source table; deterministic order.
    """
    tables = [t.get("table_name") for t in detailed_schema if t.get("table_name")]
    norm_to_table: Dict[str, str] = {}
    for name in tables:
        norm_to_table.setdefault(_norm(name), name)

    pk_names: Dict[str, Set[str]] = {}
    col_names: Dict[str, Set[str]] = {}
    for t in detailed_schema:
        name = t.get("table_name")
        cols = {c.get("name") for c in t.get("columns", []) if c.get("name")}
        col_names[name] = cols
        pk_names[name] = {c.get("name") for c in t.get("columns", []) if c.get("primary_key")}

    inferred: List[Dict[str, Any]] = []
    seen: Set[tuple] = set()
    for t in sorted(detailed_schema, key=lambda x: str(x.get("table_name"))):
        source = str(t.get("table_name"))
        added = 0
        for col in sorted(t.get("columns", []), key=lambda c: str(c.get("name"))):
            if added >= MAX_INFERRED_PER_TABLE:
                break
            col_name = str(col.get("name", ""))
            target = None
            if col_name.endswith("_id"):
                stem = col_name[:-3]
                target = norm_to_table.get(_norm(stem))
                if target is None and stem.endswith("_"):
                    target = norm_to_table.get(_norm(stem.rstrip("_")))
                if target is None:
                    # Suffix fallback for compound table names: `record_id` ->
                    # `medical_records` (normalized table name ends with the stem).
                    # Deterministic: shortest matching table name wins.
                    stem_norm = _norm(stem)
                    if stem_norm:
                        cands = [
                            name
                            for name in tables
                            if name != source
                            and pk_names.get(name)
                            and _norm(name).endswith(stem_norm)
                        ]
                        if cands:
                            target = min(cands, key=lambda n: (len(n), n))
            else:
                target = norm_to_table.get(_norm(col_name))
            if not target or target == source:
                continue
            # Require plausible key alignment: the referenced table has a pk
            # (any) and this column is not itself that table's unrelated field.
            if not pk_names.get(target):
                continue
            label = f"{source}.{col_name} = {target}.{sorted(pk_names[target])[0]}"
            _add_edge(inferred, seen, source, target, label, inferred=True)
            added += 1
    return inferred


def build_schema_graph(detailed_schema: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the graph (nodes + edges) from a reflected detailed_schema."""
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    seen_edges: Set[tuple] = set()

    for t in detailed_schema:
        name = t.get("table_name")
        if not name:
            continue
        fk_cols: Dict[str, List[Dict[str, Any]]] = {}
        for fk in t.get("foreign_keys", []) or []:
            constrained = fk.get("constrained_columns") or []
            for col in constrained:
                fk_cols.setdefault(str(col), []).append({
                    "table": fk.get("referred_table"),
                    "columns": [str(c) for c in (fk.get("referred_columns") or [])],
                })
        columns = [
            {
                "name": c.get("name"),
                "type": str(c.get("type", "")),
                "primary_key": bool(c.get("primary_key")),
                "nullable": bool(c.get("nullable", True)),
                "foreign_keys": fk_cols.get(str(c.get("name")), []),
            }
            for c in t.get("columns", []) if c.get("name")
        ]
        nodes.append({"id": name, "name": name, "columns": columns})

        for fk in t.get("foreign_keys", []) or []:
            target = fk.get("referred_table")
            if not target:
                continue
            label = (
                f"{name}.{', '.join(str(c) for c in fk.get('constrained_columns') or [])}"
                f" = {target}.{', '.join(str(c) for c in fk.get('referred_columns') or [])}"
            )
            _add_edge(edges, seen_edges, name, target, label, inferred=False)

    # Inferred joins only where no explicit edge already connects the pair.
    explicit_pairs = {(e["source"], e["target"]) for e in edges}
    for cand in _infer_joins(detailed_schema):
        if (cand["source"], cand["target"]) not in explicit_pairs:
            _add_edge(edges, seen_edges, cand["source"], cand["target"], cand["label"], inferred=True)

    logger.debug("schema graph: %d nodes, %d edges", len(nodes), len(edges))
    return {"nodes": nodes, "edges": edges}


def neighbors_of(graph: Dict[str, Any], table: str) -> Set[str]:
    """Direct neighbors of a table (both directions)."""
    out: Set[str] = set()
    for e in graph.get("edges", []):
        if e["source"] == table:
            out.add(e["target"])
        elif e["target"] == table:
            out.add(e["source"])
    return out


def subgraph(graph: Dict[str, Any], table_names: Set[str]) -> Dict[str, Any]:
    """Restrict the graph to the given tables; edges must have both endpoints in."""
    names = set(table_names)
    return {
        "nodes": [n for n in graph["nodes"] if n["id"] in names],
        "edges": [e for e in graph["edges"] if e["source"] in names and e["target"] in names],
    }


def to_prompt_text(graph: Dict[str, Any]) -> str:
    """Compact LLM-friendly rendering of a (sub)graph."""
    nodes = graph.get("nodes", [])
    if not nodes:
        return ""
    lines = ["TABLE RELATIONSHIPS:"]
    for node in nodes:
        name = node["name"]
        cols = node.get("columns", [])
        pk = [c["name"] for c in cols if c.get("primary_key")]
        col_summary = ", ".join(
            f"{c['name']}{' (PK)' if c.get('primary_key') else ''}" for c in cols
        )
        line = f"- {name}: {col_summary}" if col_summary else f"- {name}"
        if pk:
            line += f" | primary key: {', '.join(pk)}"
        links = [
            e for e in graph.get("edges", [])
            if e["source"] == name or e["target"] == name
        ]
        for e in links:
            other = e["target"] if e["source"] == name else e["source"]
            marker = "" if not e.get("inferred") else " (inferred join)"
            line += f"\n  -> joins to {other} via {e['label']}{marker}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def relationships_text(graph: Dict[str, Any]) -> str:
    """One line per edge summarizing how tables connect ("" when none)."""
    edges = graph.get("edges", [])
    if not edges:
        return ""
    lines = ["HOW TABLES CONNECT (use these join conditions):"]
    for e in edges:
        marker = " (inferred)" if e.get("inferred") else ""
        lines.append(f"- {e['label']}{marker}")
    return "\n".join(lines) + "\n"
