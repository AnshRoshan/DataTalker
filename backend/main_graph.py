from langgraph.graph import StateGraph
from agents.user_input import UserInputAgent
from agents.schema import SchemaAgent

from agents.sql_writer import SQLWriterAgent
from agents.validator import ValidatorAgent
from agents.db_executor import DBExecutorAgent
from agents.answer import AnswerFormatterAgent
from agents.fallback import FallbackAgent


user_input_agent = UserInputAgent()
schema=SchemaAgent()

writer=SQLWriterAgent()
validator=ValidatorAgent()
executor=DBExecutorAgent()
formatter=AnswerFormatterAgent()
fallback=FallbackAgent()
# ✅ 1. Define state schema
graph = StateGraph(state_schema=dict)

# ✅ 2. Add agent nodes (NOTE: no parentheses! pass the class/function itself)
graph.add_node("input", user_input_agent)
graph.add_node("schema", schema)

graph.add_node("writer", writer)
graph.add_node("validator", validator)
graph.add_node("executor", executor)
graph.add_node("formatter", formatter)
graph.add_node("fallback", fallback)

# ✅ 3. Add edges (correct API)
graph.set_entry_point("input")
graph.add_edge("input", "schema")
graph.add_conditional_edges(
    "schema",
    lambda state: "yes" if state.get("error") else "no",
    {"yes": "formatter", "no": "writer"}
)
graph.add_conditional_edges(
    "writer",
    lambda state: "yes" if state.get("sql_needed") else "no",
    {"yes": "validator", "no": "formatter"}
)
graph.add_conditional_edges(
    "validator",
    lambda state: "yes" if state.get("is_safe") else "no",
    {"yes": "executor", "no": "fallback"}
)
graph.add_edge("executor", "formatter")
graph.add_edge("fallback", "formatter")
graph.set_finish_point("formatter")
# agents/user_input.py
# agents/schema.py
# ✅ 4. Compile
app = graph.compile()

# ✅ 5. Run
 