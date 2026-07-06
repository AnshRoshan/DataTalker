# agents/fallback.py
from typing import Dict, Any


class FallbackAgent:
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles cases where SQL validation fails.
        Provides a user-friendly message explaining the issue.
        """
        print(
            "[FallbackAgent] received state:",
            {k: v for k, v in state.items() if k != "detailed_schema"},
        )

        # Get information from the state
        user_question = state.get("question", "your question")
        # Use the reason provided by the validator
        reason = state.get(
            "validation_reason", "The generated SQL query was deemed unsafe or invalid."
        )
        unsafe_sql = state.get(
            "unsafe_sql_attempt"
        )  # Get the unsafe SQL if validator stored it

        # Construct a user-friendly response
        response = (
            f"⚠️ I encountered an issue processing your request regarding: 	{user_question}	\n\n"
            f"**Reason:** {reason}\n\n"
        )

        # Optionally include the problematic SQL for debugging (use with caution)
        # if unsafe_sql:
        #     response += f"Problematic SQL (for reference): `{unsafe_sql}`\n\n"

        response += "Please try rephrasing your question, ensuring it focuses on reading data rather than modifying it."

        print(f"[FallbackAgent] Generated fallback response: {response}")

        # Update state for the formatter/final output
        # Clear potentially confusing keys from previous steps
        state.pop("sql", None)
        state.pop("results", None)  # Clear any previous results
        state.pop("unsafe_sql_attempt", None)  # Don't need this anymore

        return {
            **state,
            "answer": response,  # Provide the final answer directly
            "sql_executed": False,  # Explicitly state SQL was not executed
            "error": reason,  # Keep the validation reason as the primary error for logging/debugging
        }
