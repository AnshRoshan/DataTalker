# core/schema_retrieval.py
"""Large-schema retrieval (relevance pruning): when a schema has more tables
than the prompt budget (DATATALKER_MAX_PROMPT_TABLES, 0 = unlimited), send only
the tables most relevant to the question instead of the whole schema.

Scoring is deterministic: token overlap between question words and table/column
names (case-insensitive, snake_case split, stopwords dropped), with a bonus for
semantic-YAML synonyms when a semantic file is configured. Selected tables are
always extended with direct FK neighbors (1 hop, bounded) so joins stay
discoverable. The graph model comes from core.schema_graph (derived, not stored).
"""
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from core.schema_graph import build_schema_graph, neighbors_of
from core.settings import get_settings

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "in", "into", "is", "it", "list", "many", "me", "much", "of", "on", "or",
    "per", "please", "show", "than", "that", "the", "their", "them", "then",
    "there", "these", "they", "this", "those", "to", "top", "up", "us", "use",
    "was", "were", "what", "when", "where", "which", "who", "whose", "why",
    "will", "with", "would", "you", "your", "do", "does", "did", "can",
    "could", "should", "give", "get", "tell", "all", "each", "every", "any",
    "number", "count", "total", "average", "avg", "sum", "most", "least",
}

_WORD_SPLIT = re.compile(r"[^0-9a-z_]+")


def question_tokens(question: str) -> Set[str]:
    """Lowercased question words split on non-word chars, stopwords dropped."""
    words = [w for w in _WORD_SPLIT.split(str(question).lower()) if w]
    return {w for w in words if w not in _STOPWORDS}


def _name_tokens(name: str) -> Set[str]:
    return {t for t in re.split(r"[_\s]+", str(name).lower()) if t}


def _semantic_synonyms() -> Dict[str, List[str]]:
    """table -> synonyms from the semantic YAML (empty without a config)."""
    try:
        from core.semantic import load_semantic

        model = load_semantic()
        if not model:
            return {}
        return {
            str(name): list(spec.get("synonyms") or [])
            for name, spec in model.get("tables", {}).items()
        }
    except Exception:
        logger.debug("semantic layer unavailable for retrieval scoring", exc_info=True)
        return {}


def score_table(table: Dict[str, Any], q_tokens: Set[str],
                synonyms: Dict[str, List[str]]) -> float:
    """Relevance of one detailed_schema table entry to the question tokens."""
    name = str(table.get("table_name", ""))
    name_words = _name_tokens(name)
    # Bonus: semantic synonyms for this table that appear in the question.
    synonym_hit = 0.0
    for syn in synonyms.get(name, []):
        if _name_tokens(syn) & q_tokens:
            synonym_hit += 2.0
            break
    score = 2.0 * len(name_words & q_tokens) + synonym_hit
    for col in table.get("columns", []):
        col_words = _name_tokens(col.get("name", ""))
        score += 1.0 * len(col_words & q_tokens)
    return score


def select_relevant_tables(
    detailed_schema: List[Dict[str, Any]],
    question: str,
    max_tables: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """Prune detailed_schema to the top-K tables most relevant to the question.

    Returns (pruned_detailed_schema, pruning_note). The note is "" when no
    pruning happened; otherwise it is a short prompt fragment telling the model
    the schema was narrowed (so it knows more tables exist).
    """
    if max_tables is None:
        max_tables = get_settings().max_prompt_tables
    if not max_tables or max_tables <= 0 or len(detailed_schema) <= max_tables:
        return detailed_schema, ""

    q_tokens = question_tokens(question)
    synonyms = _semantic_synonyms()
    graph = build_schema_graph(detailed_schema)

    scored = sorted(
        detailed_schema,
        key=lambda t: (-score_table(t, q_tokens, synonyms), str(t.get("table_name"))),
    )
    selected = [str(t.get("table_name")) for t in scored[:max_tables]]
    selected_set = set(selected)

    # Always include direct FK neighbors (1 hop) of selected tables, bounded so
    # the prompt budget stays meaningful.
    neighbor_cap = max_tables // 2
    for name in selected:
        if len(selected_set) >= max_tables + neighbor_cap:
            break
        for neighbor in sorted(neighbors_of(graph, name)):
            if len(selected_set) >= max_tables + neighbor_cap:
                break
            selected_set.add(neighbor)

    pruned = [t for t in detailed_schema if str(t.get("table_name")) in selected_set]

    note = (
        f"NOTE: The schema was pruned to the {len(pruned)} tables most relevant to "
        f"the question; {len(detailed_schema)} tables exist in this database. "
        "If the question seems to need a table not listed, say so in the answer.\n"
    )
    logger.debug(
        "schema pruned %d -> %d tables; selected: %s",
        len(detailed_schema), len(pruned), sorted(selected_set),
    )
    return pruned, note
