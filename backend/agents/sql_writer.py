# agents/sql_writer.py
from llm.service import generate_sql_or_response
from typing import Dict, Any


class SQLWriterAgent:
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates SQL query or a direct response based on the question and schema.
        Handles database dialect and potential errors from the LLM.
        """
        print(
            "[SQLWriterAgent] received state:",
            {k: v for k, v in state.items() if k != "detailed_schema"},
        )  # Avoid printing large schema
        question = state.get("question", "")
        schema_description = state.get(
            "schema_description"
        )  # Use the formatted description
        db_dialect = state.get(
            "db_dialect", "sqlite"
        )  # Get dialect from state, default to sqlite

        if not schema_description:
            print("[SQLWriterAgent] Error: No schema description available.")
            # Return state indicating no SQL needed and provide a result message
            # Avoid overwriting existing errors if present
            if "error" not in state or not state["error"]:
                state["error"] = (
                    "No database schema information available to generate SQL."
                )
            state["sql_needed"] = False
            return state

        # Call the LLM function, passing the dialect
        print(f"[SQLWriterAgent] Calling LLM for {db_dialect}...")
        llm_result = generate_sql_or_response(
            schema=schema_description, question=question, db_dialect=db_dialect
        )

        print(f"[SQLWriterAgent] LLM Result: {llm_result}")

        # Process the LLM result (which could be {'sql': ...}, {'response': ...}, or {'error': ...})
        if "sql" in llm_result:
            print("[SQLWriterAgent] SQL generated.")
            state["sql"] = llm_result["sql"]
            state["sql_needed"] = True
            state.pop(
                "error", None
            )  # Clear previous non-critical errors if SQL is generated
        elif "response" in llm_result:
            print("[SQLWriterAgent] Direct response generated.")
            # Pass the direct response to the formatter via the 'results' key (or a dedicated key if preferred)
            state["results"] = llm_result["response"]
            state["sql_needed"] = False
            state.pop("error", None)
        elif "error" in llm_result:
            print(f"[SQLWriterAgent] Error from LLM: {llm_result["error"]}")
            # Propagate the error from the LLM
            state["error"] = f"LLM Error: {llm_result["error"]}"
            # Decide the flow - maybe fallback or straight to formatter with error?
            # For now, setting sql_needed to False and letting graph handle error state.
            state["sql_needed"] = False
            # Keep the error in the state for downstream agents or conditional edges
        else:
            # Unexpected result format from LLM
            print("[SQLWriterAgent] Error: Unexpected result format from LLM.")
            state["error"] = (
                "Unexpected result format from LLM after SQL generation attempt."
            )
            state["sql_needed"] = False

        return state
