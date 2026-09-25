# core/semantic.py
"""Semantic layer lite (EC-09): optional YAML file with table/column
descriptions and metric definitions, appended to the SQL-writer prompt.

Configured via DATATALKER_SEMANTIC_FILE, e.g.:
    tables:
      patients:
        description: "People admitted to the hospital"
        synonyms: ["person", "individual"]
        columns:
          admission_date: "Date the patient was admitted"
    metrics:
      active_patients:
        description: "Patients currently admitted"
        sql: "SELECT COUNT(*) FROM patients WHERE discharged_at IS NULL"

Invalid or missing file -> no extra context (""), never a hard failure.
Metric SQL is provided as *definition context* only — the model still writes a
single read-only SELECT, and the validator guards whatever it produces.
"""
import logging
from typing import Any, Dict, Optional

import yaml

from .settings import get_settings

logger = logging.getLogger(__name__)


def load_semantic() -> Optional[Dict[str, Any]]:
    """Load + validate the semantic model. None = not configured/unusable."""
    settings = get_settings()
    if not settings.semantic_file:
        return None
    path = settings.semantic_file_path
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        logger.warning("Semantic file %s could not be loaded: %s", path, e)
        return None
    if not isinstance(raw, dict):
        logger.warning("Semantic file %s must be a mapping; ignoring.", path)
        return None

    tables: Dict[str, Any] = {}
    for name, spec in (raw.get("tables") or {}).items():
        if not isinstance(spec, dict):
            continue
        tables[str(name)] = {
            "description": str(spec.get("description", "")),
            "synonyms": [str(s) for s in (spec.get("synonyms") or []) if isinstance(s, (str, int, float))],
            "columns": {str(c): str(d) for c, d in (spec.get("columns") or {}).items()
                        if isinstance(c, str) and isinstance(d, (str, int, float))},
        }

    metrics: Dict[str, Any] = {}
    for name, spec in (raw.get("metrics") or {}).items():
        if isinstance(spec, dict) and isinstance(spec.get("sql"), str) and spec["sql"].strip():
            metrics[str(name)] = {
                "description": str(spec.get("description", "")),
                "sql": spec["sql"].strip(),
            }

    return {"tables": tables, "metrics": metrics}


def semantic_context() -> str:
    """Render the semantic model as prompt context ("" when absent)."""
    model = load_semantic()
    if not model or not (model["tables"] or model["metrics"]):
        return ""

    lines = ["## SEMANTIC LAYER (business definitions):"]
    if model["tables"]:
        lines.append("Table/column meanings and alternate names (synonyms) you should recognize in questions:")
        for table, spec in model["tables"].items():
            synonyms = f" (also called: {', '.join(spec['synonyms'])})" if spec["synonyms"] else ""
            lines.append(f"- {table}{synonyms}: {spec['description']}" if spec["description"] else f"- {table}{synonyms}")
            for column, desc in spec["columns"].items():
                lines.append(f"    - {column}: {desc}")
    if model["metrics"]:
        lines.append("Predefined metrics (reference definitions — adapt them to the question, keep a single SELECT):")
        for name, spec in model["metrics"].items():
            lines.append(f"- {name}: {spec['description']}")
            lines.append(f"  Definition SQL: {spec['sql']}")
    return "\n".join(lines) + "\n"
