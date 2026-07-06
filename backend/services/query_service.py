# services/query_service.py
"""Query processing service."""

from typing import Dict, Any, Optional
from fastapi import HTTPException

from graphs.query_graph import query_app


class QueryService:
    """Service for handling query processing."""
    
    @staticmethod
    def process_query(
        question: str,
        db_uri: str,
        db_dialect: str,
        schema_data: Dict[str, Any],
        db_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a natural language question against the database."""
        
        if not question.strip():
            raise HTTPException(status_code=400, detail="Question cannot be empty")
        
        # Prepare state for query processing
        query_state = {
            "question": question,
            "db_path": db_path,
            "db_uri": db_uri,
            "db_dialect": db_dialect,
            "detailed_schema": schema_data.get("detailed_schema"),
            "schema_description": schema_data.get("schema_description"),
        }

        try:
            # Process with Query Graph
            result_state = query_app.invoke(query_state)
            
            # Prepare response data
            response_data = {
                "answer": result_state.get("answer", "No answer generated."),
                "sql": result_state.get("sql", ""),
                "results": result_state.get("results", []),
                "follow_up_questions": result_state.get("follow_up_questions", []),
            }

            # Handle different result types
            if isinstance(response_data["results"], str):
                # If results is a string (error message), convert to empty list
                response_data["results"] = []
            elif not isinstance(response_data["results"], list):
                # If results is not a list, convert to empty list
                response_data["results"] = []

            return response_data
            
        except Exception as e:
            print(f"[QueryService] error processing query: {e!r}")
            raise HTTPException(status_code=500, detail="Failed to process the query.")