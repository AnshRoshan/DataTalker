# backend/test_retrieval.py
# Assert-based self-check for core/schema_retrieval.py: top-K selection,
# neighbor inclusion, and the pruning note — on a synthetic 100-table schema.
#   uv run --directory backend python test_retrieval.py
from core.schema_retrieval import (
    question_tokens,
    score_table,
    select_relevant_tables,
)
from core.settings import get_settings

# --- settings default ---
assert get_settings().max_prompt_tables == 25


def make_table(name, columns):
    return {
        "table_name": name,
        "columns": [{"name": c, "type": "TEXT", "primary_key": i == 0, "nullable": True}
                    for i, c in enumerate(columns)],
        "foreign_keys": [],
    }


def link(schema, source, source_col, target, target_col):
    for t in schema:
        if t["table_name"] == source:
            t["foreign_keys"].append({
                "constrained_columns": [source_col],
                "referred_table": target,
                "referred_columns": [target_col],
            })


# Synthetic schema: 100 tables, most of them irrelevant filler.
schema = [
    make_table("patients", ["patient_id", "name", "gender", "admission_date"]),
    make_table("patient_visits", ["visit_id", "patient_id", "visit_date", "ward"]),
    make_table("doctors", ["doctor_id", "name", "specialty"]),
    make_table("orders", ["order_id", "customer_id", "total"]),
    make_table("order_items", ["order_item_id", "order_id", "product_id", "quantity"]),
    make_table("products", ["product_id", "name", "price"]),
]
schema += [make_table(f"zfiller_{i:03d}", [f"zfiller_{i:03d}_id", "value", "note"])
           for i in range(94)]
link(schema, "patient_visits", "patient_id", "patients", "patient_id")
link(schema, "orders", "customer_id", "zfiller_001", "zfiller_001_id")
link(schema, "order_items", "order_id", "orders", "order_id")

# --- question tokenization ---
q = question_tokens("How many patients were admitted last month?")
assert "patients" in q and "admitted" in q
assert "how" not in q and "many" not in q and "the" not in q  # stopwords dropped

# --- scoring: name hit beats column-only hit; synonym bonus applies ---
filler = next(t for t in schema if t["table_name"] == "zfiller_042")
patients = next(t for t in schema if t["table_name"] == "patients")
assert score_table(patients, q, {}) > score_table(filler, q, {})
assert score_table(patients, question_tokens("person records"), {"patients": ["person"]}) > 0

# --- pruning: top-K + 1-hop FK neighbor, note appended, under budget untouched ---
pruned, note = select_relevant_tables(schema, "How many patients were admitted last month?",
                                      max_tables=5)
names = {t["table_name"] for t in pruned}
assert "patients" in names, names
assert "patient_visits" in names, "FK neighbor of a selected table must be included"
assert "zfiller_042" not in names
assert len(pruned) <= 5 + (5 // 2), len(pruned)  # bounded: K + neighbor cap
assert "pruned to the" in note and str(len(pruned)) in note and "100" in note, note
# original schema order preserved for kept tables
orig_order = [t["table_name"] for t in schema if t["table_name"] in names]
assert [t["table_name"] for t in pruned] == orig_order

# no pruning when the schema fits the budget
subset = schema[:5]
same, no_note = select_relevant_tables(subset, "anything", max_tables=25)
assert same is subset and no_note == ""
# max_tables=0 disables pruning entirely (unlimited)
same, no_note = select_relevant_tables(schema, "anything", max_tables=0)
assert same is schema and no_note == ""

print("retrieval: all assertions passed")
