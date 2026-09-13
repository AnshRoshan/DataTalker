# backend/test_schema_graph.py
# Assert-based self-check for core/schema_graph.py (FK edges, inferred joins,
# prompt rendering) against the bundled hospital.db fixture.
#   uv run --directory backend python test_schema_graph.py
import pathlib
import sqlite3

from core.schema_graph import (
    build_schema_graph,
    neighbors_of,
    relationships_text,
    subgraph,
    to_prompt_text,
)

BACKEND = pathlib.Path(__file__).resolve().parent
HOSPITAL = BACKEND / "hospital.db"


def reflect(db_path: pathlib.Path):
    """Minimal detailed_schema in the shape agents/schema.py produces."""
    con = sqlite3.connect(str(db_path))
    try:
        tables = [
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        detailed = []
        for t in tables:
            cols = [
                {"name": r[1], "type": r[2], "primary_key": bool(r[5]), "nullable": not r[3]}
                for r in con.execute(f"PRAGMA table_info('{t}')")
            ]
            fks = [
                {"constrained_columns": [r[3]], "referred_table": r[2], "referred_columns": [r[4]]}
                for r in con.execute(f"PRAGMA foreign_key_list('{t}')")
            ]
            detailed.append({"table_name": t, "columns": cols, "foreign_keys": fks})
        return detailed
    finally:
        con.close()


detailed = reflect(HOSPITAL)
assert len(detailed) == 7, len(detailed)

# --- explicit FK edges from reflection ---
graph = build_schema_graph(detailed)
assert len(graph["nodes"]) == 7
assert all(not e["inferred"] for e in graph["edges"]), graph["edges"]
explicit_pairs = {(e["source"], e["target"]) for e in graph["edges"]}
assert ("appointments", "patients") in explicit_pairs
assert ("appointments", "doctors") in explicit_pairs
assert ("doctors", "departments") in explicit_pairs
assert ("prescriptions", "medications") in explicit_pairs
assert ("patients", "appointments") not in explicit_pairs  # direction preserved

# --- neighbors (both directions) ---
assert "patients" in neighbors_of(graph, "appointments")
assert "appointments" in neighbors_of(graph, "patients")
assert neighbors_of(graph, "medications") == {"prescriptions"}

# --- inferred joins: strip declared FKs and the heuristics must recover paths ---
bare = [{**t, "foreign_keys": []} for t in detailed]
inferred_graph = build_schema_graph(bare)
inferred = [e for e in inferred_graph["edges"] if e["inferred"]]
assert inferred, "inferred joins must be produced without declared FKs"
inferred_pairs = {(e["source"], e["target"]) for e in inferred}
assert ("appointments", "patients") in inferred_pairs
assert ("appointments", "doctors") in inferred_pairs
assert ("medical_records", "patients") in inferred_pairs
assert ("doctors", "departments") in inferred_pairs
# deterministic: rebuilding yields identical edges
# inference is deterministic: rebuilding yields identical edges
assert build_schema_graph(bare)["edges"] == inferred_graph["edges"]
# every declared FK path is recoverable by name inference alone
assert explicit_pairs <= inferred_pairs

# --- subgraph restricts nodes and edges ---
sub = subgraph(graph, {"appointments", "patients", "medications"})
assert {n["id"] for n in sub["nodes"]} == {"appointments", "patients", "medications"}
assert all(e["source"] in {"appointments", "patients", "medications"}
           and e["target"] in {"appointments", "patients", "medications"} for e in sub["edges"])
assert not any(e["target"] == "medications" for e in sub["edges"])  # prescriptions dropped

# --- prompt rendering ---
prompt = to_prompt_text(graph)
assert "TABLE RELATIONSHIPS:" in prompt
assert "- appointments:" in prompt
assert "joins to patients via appointments.patient_id = patients.patient_id" in prompt
assert "(PK)" in prompt
iprompt = to_prompt_text(inferred_graph)
assert "joins to patients" in iprompt
assert "(inferred join)" in iprompt

rels = relationships_text(graph)
assert "HOW TABLES CONNECT" in rels
assert "appointments.patient_id = patients.patient_id" in rels
assert relationships_text({"nodes": [], "edges": []}) == ""

print("schema_graph: all assertions passed")
