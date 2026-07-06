# agents/answer.py
from llm.gemini import format_answer
from typing import Dict, Any, List, Optional


class AnswerFormatterAgent:
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formats the final response to the user.
        If an error occurred previously, it presents the error message.
        If results exist, it calls the LLM to format them into a natural language answer.
        """
        # Log state selectively
        print(
            "[AnswerFormatterAgent] received state:",
            {
                k: v
                for k, v in state.items()
                if k not in ["detailed_schema", "schema_description", "results"]
            },
        )

        question: str = state.get("question", "your question")
        results: List[Dict[str, Any]] | str | None = state.get(
            "results"
        )  # Can be list of dicts (SQL results) or string (direct LLM response)
        error_message: Optional[str] = state.get("error")
        sql_executed: bool = state.get("sql_executed", False)
        sql_query: Optional[str] = state.get("sql")  # Get the executed SQL if available

        final_answer: str = ""
        follow_up_questions: List[str] = []

        if error_message:
            # If an error was explicitly set in the state, prioritize showing it.
            print(
                f"[AnswerFormatterAgent] An error occurred in a previous step: {error_message}"
            )
            final_answer = f"I encountered an error: {error_message}"
            # Optionally add context like the original question
            # final_answer = f"Sorry, I couldn't process your question 	{question}	 due to an error: {error_message}"
        elif sql_executed:
            # SQL was executed, format the results (which could be an empty list)
            if results is None:
                # Should ideally not happen if sql_executed is True and no error, but handle defensively
                print(
                    "[AnswerFormatterAgent] Warning: SQL executed but results are None and no error reported."
                )
                final_answer = "The query was executed, but no results were returned or an unexpected issue occurred."
            else:
                print(
                    f"[AnswerFormatterAgent] Formatting results from executed SQL: {results}"
                )
                try:
                    # Add the executed SQL to the context for the formatter LLM
                    context_for_formatter = {
                        "executed_sql": sql_query,
                        "query_results": results,
                    }
                    print(
                        f"[AnswerFormatterAgent] Calling format_answer LLM with question: {question} and context."
                    )
                    formatted_response = format_answer(question, context_for_formatter)
                    print(
                        f"[AnswerFormatterAgent] format_answer LLM returned: {formatted_response}"
                    )

                    if (
                        isinstance(formatted_response, dict)
                        and "answer" in formatted_response
                    ):
                        final_answer = formatted_response.get(
                            "answer", "Could not format the results."
                        )
                        follow_up_questions = formatted_response.get(
                            "follow_up_questions", []
                        )
                    else:
                        # Handle cases where formatter LLM failed or returned unexpected format
                        print(
                            "[AnswerFormatterAgent] Warning: Formatter LLM did not return expected dict format."
                        )
                        final_answer = f"Successfully executed query. Results: {results}"  # Fallback to showing raw results
                        if (
                            isinstance(formatted_response, dict)
                            and "error" in formatted_response
                        ):
                            final_answer += (
                                f" (Formatter Error: {formatted_response["error"]})"
                            )
                        elif not isinstance(formatted_response, dict):
                            final_answer += (
                                f" (Formatter returned non-dict: {formatted_response})"
                            )

                except Exception as e:
                    print(
                        f"[AnswerFormatterAgent] Error calling format_answer LLM: {e}"
                    )
                    final_answer = f"Successfully executed query, but failed to format the answer nicely. Raw results: {results}"  # Fallback
        elif isinstance(results, str):
            # If results is a string, it's likely a direct response from SQLWriterAgent
            print(
                f"[AnswerFormatterAgent] Using direct response from previous step: {results}"
            )
            final_answer = results
            # Optionally, call formatter LLM even for direct responses to get follow-up questions
            # try:
            #     formatted_response = format_answer(question, {"direct_response": results})
            #     follow_up_questions = formatted_response.get("follow_up_questions", [])
            # except Exception as e:
            #     print(f"[AnswerFormatterAgent] Error calling format_answer for direct response: {e}")
        else:
            # Default case if no error, no SQL execution, and no direct response string
            print("[AnswerFormatterAgent] No results, error, or direct response found.")
            final_answer = "I was unable to find an answer or generate a query for your request. Please try rephrasing."

        print(f"[AnswerFormatterAgent] Final Answer: {final_answer}")
        print(
            f"[AnswerFormatterAgent] Final Follow-up Questions: {follow_up_questions}"
        )

        # Clean up state before finishing? Optional.
        # state.pop("results", None)
        # state.pop("error", None)

        # Return the final state for the graph termination
        return {
            **state,
            "answer": final_answer,
            "follow_up_questions": follow_up_questions,
        }
