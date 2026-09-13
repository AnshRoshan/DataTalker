# graphs/schema_graph.py
"""Schema extraction graph using LangGraph."""

import logging

from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, List, Dict, Any

# Import agent classes
from agents.schema import SchemaAgent

logger = logging.getLogger(__name__)


class SchemaState(TypedDict):
    db_uri: str
    db_dialect: str  # sqlite | postgresql | mysql (see core/dialects.py)
    db_path: Optional[str]
    include_tables: Optional[List[str]]
    schema: Optional[Dict[str, List[str]]]
    detailed_schema: Optional[List[Dict[str, Any]]]
    schema_description: Optional[str]
    error: Optional[str]

# Instantiate agents
schema_agent = SchemaAgent()

# Define the schema extraction graph
schema_graph_builder = StateGraph(SchemaState)

# Add nodes - for schema extraction, we only need the schema agent
schema_graph_builder.add_node("schema_node", schema_agent)

# Set entry point directly to schema extraction (skip user input validation)
schema_graph_builder.set_entry_point("schema_node")

# Add edges - schema node goes directly to END
schema_graph_builder.add_edge("schema_node", END)

# Compile the schema graph
schema_app = schema_graph_builder.compile()

logger.debug("Schema extraction graph compiled.")