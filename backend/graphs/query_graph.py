# graphs/query_graph.py
"""Query processing graph using LangGraph."""

from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, List, Dict, Any, Literal

# Import agent classes
from agents.sql_writer import SQLWriterAgent
from agents.validator import ValidatorAgent
from agents.db_executor import DBExecutorAgent
from agents.answer import AnswerFormatterAgent
from agents.fallback import FallbackAgent
from agents.sql_retry import SQLRetryAgent


class QueryState(TypedDict):
    question: str
    db_uri: str
    db_dialect: Literal["sqlite", "postgresql"]
    db_path: Optional[str]
    include_tables: Optional[List[str]]
    schema: Optional[Dict[str, List[str]]]
    detailed_schema: Optional[List[Dict[str, Any]]]
    schema_description: Optional[str]
    sql: Optional[str]
    sql_needed: Optional[bool]
    is_safe: Optional[bool]
    validation_reason: Optional[str]
    unsafe_sql_attempt: Optional[str]
    results: Optional[List[Dict[str, Any]] | str]
    sql_executed: Optional[bool]
    affected_rows: Optional[int]
    answer: Optional[str]
    follow_up_questions: Optional[List[str]]
    error: Optional[str]
    retry_count: Optional[int]
    previous_sql_attempts: Optional[List[str]]


# Instantiate agents
sql_writer_agent = SQLWriterAgent()
validator_agent = ValidatorAgent()
db_executor_agent = DBExecutorAgent()
answer_formatter_agent = AnswerFormatterAgent()
fallback_agent = FallbackAgent()
sql_retry_agent = SQLRetryAgent()

# Define the query processing graph
query_graph_builder = StateGraph(QueryState)

# Add nodes for each agent
query_graph_builder.add_node("writer_node", sql_writer_agent)
query_graph_builder.add_node("validator_node", validator_agent)
query_graph_builder.add_node("executor_node", db_executor_agent)
query_graph_builder.add_node("fallback_node", fallback_agent)
query_graph_builder.add_node("formatter_node", answer_formatter_agent)
query_graph_builder.add_node("retry_node", sql_retry_agent)

# Set entry point to writer (schema is already available)
query_graph_builder.set_entry_point("writer_node")


# Define routing logic
def route_after_writer(state: QueryState):
    print("[QueryGraph] Routing after writer...")
    if state.get("error"):  # Check for LLM errors propagated by writer
        print("[QueryGraph] Writer error detected, routing to formatter.")
        return "formatter_node"
    elif state.get("sql_needed"):
        print("[QueryGraph] SQL needed, routing to validator.")
        return "validator_node"
    else:
        print("[QueryGraph] No SQL needed, routing to formatter.")
        return "formatter_node"


def route_after_validator(state: QueryState):
    print("[QueryGraph] Routing after validator...")
    if state.get("is_safe"):
        print("[QueryGraph] SQL is safe, routing to executor.")
        return "executor_node"
    else:
        print("[QueryGraph] SQL is unsafe, routing to fallback.")
        return "fallback_node"


def route_after_executor(state: QueryState):
    print("[QueryGraph] Routing after executor...")
    results = state.get("results", [])
    sql_executed = state.get("sql_executed", False)
    retry_count = state.get("retry_count")
    if retry_count is None:
        retry_count = 0

    # Check if execution was successful but returned no meaningful results
    should_retry = False

    if sql_executed and retry_count < 2:
        if isinstance(results, list):
            if len(results) == 0:
                # No results at all
                should_retry = True
            elif len(results) > 0 and isinstance(results[0], dict):
                # Check if it's multiple query results format
                if "statement_index" in results[0]:
                    # Multiple queries - check if all returned empty
                    total_rows = sum(stmt.get("row_count", 0) for stmt in results)
                    if total_rows == 0:
                        should_retry = True
                else:
                    # Single query format - already handled by len(results) == 0
                    pass

    if should_retry:
        print(
            "[QueryGraph] Execution successful but no meaningful results, routing to retry."
        )
        return "retry_node"
    else:
        print(
            "[QueryGraph] Execution complete or max retries reached, routing to formatter."
        )
        return "formatter_node"


# Add edges
query_graph_builder.add_conditional_edges("writer_node", route_after_writer)
query_graph_builder.add_conditional_edges("validator_node", route_after_validator)
query_graph_builder.add_conditional_edges("executor_node", route_after_executor)
query_graph_builder.add_conditional_edges(
    "retry_node", route_after_writer
)  # Retry goes back to writer routing
query_graph_builder.add_edge("fallback_node", "formatter_node")
query_graph_builder.add_edge("formatter_node", END)

# Compile the query graph
query_app = query_graph_builder.compile()

print("[QueryGraph] Query processing graph compiled successfully.")
