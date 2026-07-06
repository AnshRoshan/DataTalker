# agents/sql_retry.py
from llm.gemini import generate_sql_or_response_with_gemini
from typing import Dict, Any


class SQLRetryAgent:
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyzes failed SQL execution and attempts to generate improved SQL.
        This agent is called when the initial SQL execution returns no results or fails.
        """
        print(
            "[SQLRetryAgent] received state:",
            {k: v for k, v in state.items() if k not in ["detailed_schema", "results"]},
        )
        
        question = state.get("question", "")
        schema_description = state.get("schema_description")
        db_dialect = state.get("db_dialect", "sqlite")
        previous_sql = state.get("sql", "")
        previous_results = state.get("results", [])
        retry_count = state.get("retry_count", 0)
        
        # Limit retry attempts
        max_retries = 2
        if retry_count >= max_retries:
            print(f"[SQLRetryAgent] Maximum retry attempts ({max_retries}) reached.")
            state["error"] = f"Unable to generate working SQL after {max_retries} attempts."
            state["sql_needed"] = False
            return state
        
        # Increment retry count
        state["retry_count"] = retry_count + 1
        
        # Analyze the failure
        failure_context = self._analyze_failure(previous_sql, previous_results, question)
        
        # Create enhanced prompt with failure context
        enhanced_schema = f"{schema_description}\n\n{failure_context}"
        
        print(f"[SQLRetryAgent] Retry attempt {retry_count + 1}/{max_retries} for {db_dialect}...")
        print(f"[SQLRetryAgent] Previous SQL failed: {previous_sql}")
        
        # Call the LLM function with enhanced context
        llm_result = generate_sql_or_response_with_gemini(
            schema=enhanced_schema, question=question, db_dialect=db_dialect
        )
        
        print(f"[SQLRetryAgent] Retry LLM Result: {llm_result}")
        
        # Process the LLM result
        if "sql" in llm_result:
            print("[SQLRetryAgent] New SQL generated on retry.")
            state["sql"] = llm_result["sql"]
            state["sql_needed"] = True
            state.pop("error", None)
            # Store previous attempt for learning
            state["previous_sql_attempts"] = state.get("previous_sql_attempts", []) + [previous_sql]
        elif "response" in llm_result:
            print("[SQLRetryAgent] Direct response generated on retry.")
            state["results"] = llm_result["response"]
            state["sql_needed"] = False
            state.pop("error", None)
        elif "error" in llm_result:
            print(f"[SQLRetryAgent] Error from LLM on retry: {llm_result['error']}")
            state["error"] = f"LLM Error on retry {retry_count + 1}: {llm_result['error']}"
            state["sql_needed"] = False
        else:
            print("[SQLRetryAgent] Unexpected result format from LLM on retry.")
            state["error"] = f"Unexpected result format from LLM on retry attempt {retry_count + 1}."
            state["sql_needed"] = False
        
        return state
    
    def _analyze_failure(self, previous_sql: str, previous_results: Any, question: str) -> str:
        """
        Analyzes why the previous SQL failed and provides context for retry.
        """
        failure_analysis = "\n--- PREVIOUS ATTEMPT ANALYSIS ---\n"
        
        if isinstance(previous_results, list) and len(previous_results) == 0:
            failure_analysis += "ISSUE: Previous query returned 0 rows.\n"
            failure_analysis += f"FAILED SQL: {previous_sql}\n"
            
            # Analyze common failure patterns
            if "'Department Name'" in previous_sql or '"Department Name"' in previous_sql:
                failure_analysis += "PROBLEM: Query used placeholder 'Department Name' instead of actual department name.\n"
                failure_analysis += "SOLUTION: Use actual department names from the schema or remove department filter.\n"
            
            if "WHERE" in previous_sql.upper():
                failure_analysis += "PROBLEM: WHERE clause may be too restrictive or using non-existent values.\n"
                failure_analysis += "SOLUTION: Try removing or relaxing WHERE conditions, or use actual values from the database.\n"
            
            if "=" in previous_sql and ("'" in previous_sql or '"' in previous_sql):
                failure_analysis += "PROBLEM: Exact string matching may be failing due to case sensitivity or non-existent values.\n"
                failure_analysis += "SOLUTION: Use LIKE with wildcards, ILIKE for case-insensitive matching, or remove string filters.\n"
        
        elif previous_results is None:
            failure_analysis += "ISSUE: Previous query execution failed completely.\n"
            failure_analysis += f"FAILED SQL: {previous_sql}\n"
            failure_analysis += "SOLUTION: Check for syntax errors, invalid table/column names, or permission issues.\n"
        
        failure_analysis += "\nINSTRUCTIONS FOR RETRY:\n"
        failure_analysis += "1. Generate a simpler, more general query that is likely to return results\n"
        failure_analysis += "2. Avoid hardcoded string values unless you're certain they exist\n"
        failure_analysis += "3. Use broader conditions or remove restrictive WHERE clauses entirely\n"
        failure_analysis += "4. Focus on the core data requested in the question\n"
        failure_analysis += "5. If the question asks for specific entities, first query to see what entities exist\n"
        failure_analysis += "6. Consider using LIKE with wildcards instead of exact matches\n"
        failure_analysis += "7. Try removing JOIN conditions if they might be too restrictive\n"
        failure_analysis += "8. Generate multiple queries to explore available data first\n"
        failure_analysis += "\nSUGGESTED ALTERNATIVE APPROACHES:\n"
        
        if "department" in question.lower():
            failure_analysis += "- First query available departments: SELECT name FROM departments;\n"
            failure_analysis += "- Then show all appointments: SELECT * FROM appointments LIMIT 10;\n"
            failure_analysis += "- Or combine: SELECT name FROM departments; SELECT * FROM appointments LIMIT 10;\n"
        
        if "patient" in question.lower() and ("name" in question.lower() or "'" in question):
            failure_analysis += "- First show available patient names: SELECT name FROM patients;\n"
            failure_analysis += "- Use LIKE for partial matching: WHERE name LIKE '%John%';\n"
            failure_analysis += "- Or show all patients: SELECT * FROM patients;\n"
        
        if "appointment" in question.lower():
            failure_analysis += "- Show all appointments: SELECT * FROM appointments;\n"
            failure_analysis += "- Show appointments with patient/doctor info: SELECT a.*, p.name as patient_name, d.name as doctor_name FROM appointments a JOIN patients p ON a.patient_id = p.patient_id JOIN doctors d ON a.doctor_id = d.doctor_id;\n"
        
        failure_analysis += "--- END ANALYSIS ---\n"
        
        return failure_analysis