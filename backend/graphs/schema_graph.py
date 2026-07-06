# graphs/schema_graph.py
"""Schema extraction graph using LangGraph."""

from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, List, Dict, Any, Literal

# Import agent classes
from agents.schema import SchemaAgent

class SchemaState(TypedDict):
    db_uri: str
    db_dialect: Literal["sqlite", "postgresql"]
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

print("[SchemaGraph] Schema extraction graph compiled successfully.")