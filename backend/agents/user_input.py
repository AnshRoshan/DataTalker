# agents/user_input.py
from typing import Dict, Any


class UserInputAgent:
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes the initial input state, ensuring all necessary fields
        (question, db_uri, db_dialect, db_path) are present and passed forward.
        """
        question = state.get("question")
        db_uri = state.get("db_uri")
        db_dialect = state.get("db_dialect")
        db_path = state.get("db_path")  # Keep for mod time checks etc.

        print(f"[UserInputAgent] Received initial state:")
        print(f"  Question: {question}")
        print(f"  DB URI: {db_uri}")
        print(f"  DB Dialect: {db_dialect}")
        print(f"  DB Path: {db_path}")

        # Basic validation (more robust checks could be added)
        # For schema extraction, question is optional; for query processing, it's required
        if not db_uri or not db_dialect:
            error_message = "UserInputAgent Error: Missing essential initial state (db_uri or db_dialect)."
            print(error_message)
            # Return an error state immediately if critical info is missing
            # This might need adjustment based on how the graph handles early errors
            return {
                "error": error_message,
                "question": question,
                "db_uri": db_uri,
                "db_dialect": db_dialect,
                "db_path": db_path,
            }

        # If question is missing but we have db_uri and db_dialect, this might be schema-only extraction
        if not question:
            print(
                "[UserInputAgent] No question provided - assuming schema-only extraction"
            )

        # Pass along all necessary information
        return {
            "question": question,
            "db_uri": db_uri,
            "db_dialect": db_dialect,
            "db_path": db_path,
            "error": None,  # Initialize error as None
        }
