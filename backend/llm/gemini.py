# llm/gemini.py
import json
import os
import requests
from dotenv import load_dotenv
import re
import time
from typing import Literal, Dict, Any

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise Exception("Missing Gemini API key. Add it to your .env file.")

# Configuration for retries
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2  # Simple fixed delay


def _get_system_instruction_for_sql(
    db_dialect: Literal["sqlite", "postgresql"] = "sqlite",
) -> str:
    """Generates the system instruction tailored to the specified SQL dialect."""

    dialect_specific_context = ""
    dialect_specific_practices = ""

    if db_dialect == "sqlite":
        dialect_specific_context = "You are working with SQLite databases."
        dialect_specific_practices = "- Ensure all SQL is valid SQLite syntax.\n"
    elif db_dialect == "postgresql":
        dialect_specific_context = "You are working with PostgreSQL databases."
        dialect_specific_practices = (
            "- Use standard SQL syntax compatible with PostgreSQL.\n"
            "- Pay attention to PostgreSQL-specific functions and data types if applicable.\n"
            "- Use double quotes for identifiers (table/column names) only if necessary (e.g., contains spaces or special characters), otherwise use standard unquoted names.\n"
            "- Use single quotes for string literals.\n"
            "- Ensure all SQL is valid PostgreSQL syntax.\n"
        )
    else:
        dialect_specific_context = (
            "You are working with a SQL database (defaulting to SQLite behavior)."
        )
        dialect_specific_practices = "- Ensure all SQL is valid SQLite syntax.\n"

    system_instruction = (
        f"You are an expert SQL assistant for database queries. Your role is to analyze user questions and determine the appropriate response based on the provided database schema.\n\n"
        f"## TARGET DATABASE DIALECT: {db_dialect.upper()}\n\n"
        "## DECISION LOGIC:\n"
        "1. **SQL REQUIRED**: If the question asks for specific data, statistics, or information that requires querying the database.\n"
        "2. **DIRECT RESPONSE**: If the question is about general concepts, definitions, or can be answered without database access.\n\n"
        "## DATABASE CONTEXT:\n"
        f"{dialect_specific_context} The database may contain various tables with relationships.\n"
        "Always consider table relationships, foreign keys, and data types when generating SQL.\n\n"
        "## RESPONSE FORMATS:\n"
        'For SQL queries: Return ONLY a JSON object like: {{"sql": "<your_optimized_sql_query>"}}\n'
        'For direct answers: Return ONLY a JSON object like: {{"response": "<your_natural_language_response>"}}\n\n'
        f"## SQL BEST PRACTICES (General & {db_dialect.upper()} Specific):\n"
        "- Analyze the schema carefully before writing any query.\n"
        "- Use proper JOIN syntax for related tables (prefer INNER JOIN, LEFT JOIN etc. over implicit joins).\n"
        "- Include appropriate WHERE clauses for filtering.\n"
        "- Use aggregate functions (COUNT, SUM, AVG, MIN, MAX) when needed.\n"
        "- Order results logically (ORDER BY).\n"
        "- Limit results when appropriate (e.g., LIMIT 10), unless the user asks for all data.\n"
        "- Use table aliases for readability, especially in joins (e.g., SELECT c.name FROM customers c ...).\n"
        "- Write valid SQL statements. Multiple statements can be separated by semicolons when needed.\n"
        "- Ensure column names and table names exactly match the provided schema.\n"
        f"{dialect_specific_practices}"
        "## TABLE INFORMATION GUIDELINES:\n"
        "When schema is provided, analyze:\n"
        "- Table names and their purposes\n"
        "- Column names and data types\n"
        "- Primary and foreign key relationships\n"
        "- Row counts (if provided) for context\n"
        "- Potential data patterns\n\n"
        "CRITICAL: Return ONLY valid JSON as specified in RESPONSE FORMATS. No markdown, explanations, comments, or any other text outside the JSON structure."
    )
    return system_instruction


def _parse_and_validate_gemini_response(response_text: str) -> Dict[str, Any]:
    """Parses the Gemini response text, validates structure, and returns result or error."""
    if not response_text:
        return {"error": "LLM returned an empty response.", "retryable": True}

    try:
        # Clean potential markdown fences
        content = re.sub(
            r"^```(?:json)?\\s*", "", response_text.strip(), flags=re.IGNORECASE
        )
        content = re.sub(r"\\s*```$", "", content)

        try:
            parsed_json = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract the first JSON object from the text using regex as fallback
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                try:
                    parsed_json = json.loads(match.group(0))
                except Exception:
                    return {
                        "error": "LLM did not return valid JSON, even after extracting JSON object.",
                        "retryable": True,
                        "raw_content": response_text,
                    }
            else:
                return {
                    "error": "LLM did not return valid JSON.",
                    "retryable": True,
                    "raw_content": response_text,
                }

        # Validate expected keys and types
        if (
            "sql" in parsed_json
            and isinstance(parsed_json["sql"], str)
            and parsed_json["sql"].strip()
        ):
            # Basic check for common invalid patterns (can be expanded)
            if "SELECT _FROM" in parsed_json["sql"]:  # Example invalid pattern
                return {
                    "error": "LLM generated potentially invalid SQL (e.g., SELECT _FROM).",
                    "retryable": True,
                    "raw_content": content,
                }
            return {"sql": parsed_json["sql"], "retryable": False}  # Success
        elif (
            "response" in parsed_json
            and isinstance(parsed_json["response"], str)
            and parsed_json["response"].strip()
        ):
            return {"response": parsed_json["response"], "retryable": False}  # Success
        else:
            # Missing keys or invalid types
            found_keys = (
                list(parsed_json.keys())
                if isinstance(parsed_json, dict)
                else str(type(parsed_json))
            )
            return {
                "error": f"LLM JSON response missing 'sql'/'response' key or has invalid type/empty value. Found keys/types: {found_keys}",
                "retryable": True,
                "raw_content": content,
            }

    except json.JSONDecodeError:
        # Treat non-JSON as a potential direct response, but mark as non-retryable unless empty
        # If the expectation is STRICTLY JSON, this could be marked retryable=True
        # For now, assume it might be a valid text answer that failed formatting.
        return {
            "error": "LLM did not return valid JSON.",
            "retryable": True,
            "raw_content": response_text,
        }
    except Exception as e:
        # Catch unexpected parsing errors
        return {
            "error": f"Unexpected error parsing LLM response: {e}",
            "retryable": True,
            "raw_content": response_text,
        }


def generate_sql_or_response_with_gemini(
    schema: str, question: str, db_dialect: Literal["sqlite", "postgresql"] = "sqlite"
) -> dict:
    """Generates SQL or a direct response using Gemini, with retries for recoverable errors."""

    system_instruction = _get_system_instruction_for_sql(db_dialect)
    prompt_text = (
        f"{system_instruction}\n\n"
        f"Schema:\n```\n{schema}\n```\n\n"
        f"Question: {question}"
    )
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt_text}]}]}

    last_error = None
    for attempt in range(MAX_RETRIES):
        print(
            f"[Gemini] Attempt {attempt + 1}/{MAX_RETRIES} for {db_dialect} query/response..."
        )

        try:
            response = requests.post(
                url="https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
                headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY},
                json=payload,
                timeout=60,  # Add a timeout
            )

            if response.status_code == 200:
                response_json = response.json()
                try:
                    # Extract the actual LLM text from the nested structure
                    response_text = response_json["candidates"][0]["content"]["parts"][
                        0
                    ]["text"].strip()
                except (KeyError, IndexError, TypeError) as e:
                    last_error = {
                        "error": f"Unexpected Gemini API response structure: {e}. Raw response: {response.text}",
                        "retryable": False,
                        "raw_content": response.text,
                    }
                    print(
                        f"[Gemini] Attempt {attempt + 1} failed: {last_error.get('error')}. Aborting retries."
                    )
                    return last_error

                # Parse and validate the response content
                parsed_result = _parse_and_validate_gemini_response(response_text)

                if "error" not in parsed_result:
                    print(f"[Gemini] Success on attempt {attempt + 1}.")
                    return parsed_result  # Return successful sql or response
                else:
                    last_error = parsed_result  # Store the error details
                    if parsed_result.get("retryable"):
                        print(
                            f"[Gemini] Attempt {attempt + 1} failed: {last_error.get('error')}. Retrying..."
                        )
                        time.sleep(
                            RETRY_DELAY_SECONDS * (attempt + 1)
                        )  # Simple backoff
                        continue  # Go to next attempt
                    else:
                        print(
                            f"[Gemini] Attempt {attempt + 1} failed with non-retryable error: {last_error.get('error')}. Aborting retries."
                        )
                        return {
                            "error": f"Non-retryable error after attempt {attempt + 1}: {last_error.get('error')}",
                            "raw_content": last_error.get("raw_content"),
                        }
            else:  # Handle API errors (non-200 status)
                last_error = {
                    "error": f"Gemini API Error: {response.status_code} - {response.text}",
                    "retryable": True,
                }
                print(
                    f"[Gemini] Attempt {attempt + 1} failed: {last_error.get('error')}. Retrying..."
                )
                time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
                continue  # Go to next attempt

        except requests.exceptions.RequestException as e:
            last_error = {
                "error": f"Network error connecting to Gemini API: {e}",
                "retryable": True,
            }
            print(
                f"[Gemini] Attempt {attempt + 1} failed: {last_error.get('error')}. Retrying..."
            )
            time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
            continue  # Go to next attempt
        except Exception as e:
            # Catch unexpected errors during the request/response cycle
            last_error = {
                "error": f"Unexpected error during Gemini call: {e}",
                "retryable": False,
            }  # Assume non-retryable
            print(
                f"[Gemini] Attempt {attempt + 1} failed with unexpected error: {last_error.get('error')}. Aborting retries."
            )
            return last_error  # Return the final unexpected error

    # If all retries fail, return the last recorded error
    print(f"[Gemini] All {MAX_RETRIES} attempts failed.")
    return (
        last_error
        if last_error
        else {"error": "All Gemini attempts failed without specific error details."}
    )


def format_answer(question, result):
    # This function can also benefit from retries, but keeping it simple for now.
    # Assume format_answer is less critical to retry or less prone to recoverable errors.
    system_instruction = (
        "You are an expert data analyst that formats database query results into clear, human-readable responses.\n\n"
        "## YOUR ROLE:\n"
        "Transform raw database results into meaningful, well-structured answers that directly address the user\\'s question.\n\n"
        "## FORMATTING GUIDELINES:\n"
        "1. **Direct Answers**: Start with a clear, direct response to the question\n"
        "2. **Data Presentation**: Present data in logical, easy-to-read format\n"
        "3. **Context**: Provide relevant context and insights when appropriate\n"
        "4. **Numbers**: Format numbers clearly (use commas for thousands, appropriate decimal places)\n"
        "5. **Tables**: When multiple records, suggest tabular format for frontend display\n"
        "6. **Multiple Queries**: When results come from multiple SQL statements, organize and present them clearly\n\n"
        "## RESPONSE FORMAT:\n"
        "Return a JSON object with the following structure:\n"
        "{\n"
        '  "answer": "<main answer to the question>",\n'
        '  "follow_up_questions": ["<question1>", "<question2>", ...]\n'
        "}\n\n"
        "## FOLLOW-UP QUESTION GUIDELINES:\n"
        "For database query results, include follow-up questions when:\n"
        "- The data shows interesting trends that warrant deeper investigation\n"
        "- The results are part of a larger analysis that could benefit from additional queries\n"
        "- The answer reveals anomalies or patterns that need explanation\n"
        "- The question was broad and could be refined for more specific insights\n\n"
        "For direct responses (non-database questions), include follow-up questions when:\n"
        "- The response introduces concepts that could be explored with database queries\n"
        "- The user might want to know about database capabilities or structure\n"
        "- The response could lead to practical database exploration\n\n"
        "Make follow-up questions specific to the actual context. If no relevant follow-up questions, use an empty array [].\n\n"
        "## EXAMPLES:\n"
        '- For counts: {"answer": "There are 25 users in the database.", "follow_up_questions": []}\n'
        '- For trends: {"answer": "Sales increased 15% this quarter.", "follow_up_questions": ["Which products drove the sales increase?", "How does this compare to last year?"]}\n'
        '- For multiple queries: {"answer": "Here are the results from your queries: Query 1 returned 5 patients, Query 2 returned 3 doctors, Query 3 showed 12 appointments.", "follow_up_questions": ["Show me details about specific patients", "What are the appointment times?"]}\n'
        '- For direct responses: {"answer": "I am an AI assistant for database queries.", "follow_up_questions": ["What tables are available in this database?", "Show me some sample data"]}\n\n'
        "CRITICAL: Return ONLY valid JSON. No markdown, explanations, or formatting."
    )

    prompt_text = (
        f"{system_instruction}\n\n"
        f"Original Question: {question}\n\n"
        f"Query Results: {result}\n\n"
        f"Task: Format the above results into a structured JSON response with the main answer and relevant follow-up questions."
    )
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt_text}]}]}

    try:
        response = requests.post(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent",
            headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY},
            json=payload,
            timeout=30,  # Shorter timeout for formatting
        )

        if response.status_code == 200:
            response_text = response.text.strip()
            if not response_text:
                print("[Gemini Formatter] Error: Received empty response.")
                return {
                    "answer": "Error: Received empty response from formatter.",
                    "follow_up_questions": [],
                }
            try:
                content = response.json()["candidates"][0]["content"]["parts"][0][
                    "text"
                ]
                content = re.sub(
                    r"^```(?:json)?\s*", "", content.strip(), flags=re.IGNORECASE
                )
                content = re.sub(r"\s*```$", "", content)
                parsed_response = json.loads(content)
                parsed_response["answer"] = parsed_response.get(
                    "answer", "Could not format answer."
                )
                parsed_response["follow_up_questions"] = parsed_response.get(
                    "follow_up_questions", []
                )
                return parsed_response
            except json.JSONDecodeError:
                print(
                    f"[Gemini Formatter] Error: Failed to decode JSON. Response: {content}"
                )
                return {"answer": content, "follow_up_questions": []}  # Fallback
            except (KeyError, IndexError, TypeError) as e:
                print(
                    f"[Gemini Formatter] Error: Unexpected API response structure or type error. Error: {e}. Response: {response_text}"
                )
                return {
                    "answer": f"Error processing formatter response: {e}",
                    "follow_up_questions": [],
                }
            except Exception as e:
                print(
                    f"[Gemini Formatter] Error: An unexpected error occurred. Error: {e}"
                )
                return {
                    "answer": f"Unexpected error formatting answer: {e}",
                    "follow_up_questions": [],
                }
        else:
            print(
                f"[Gemini Formatter] API Error: {response.status_code} - {response.text}"
            )
            return {
                "answer": f"Formatter API Error: {response.status_code}",
                "follow_up_questions": [],
            }
    except requests.exceptions.RequestException as e:
        print(f"[Gemini Formatter] Network error: {e}")
        return {
            "answer": f"Network error during formatting: {e}",
            "follow_up_questions": [],
        }
    except Exception as e:
        print(f"[Gemini Formatter] Unexpected error: {e}")
        return {
            "answer": f"Unexpected error during formatting call: {e}",
            "follow_up_questions": [],
        }
