import json
import os
import requests
from dotenv import load_dotenv
import re

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise Exception("Missing Gemini API key. Add it to your .env file.")


def generate_sql_or_response_with_gemini(schema, question):
    system_instruction = (
        "You are an expert SQL assistant for database queries. Your role is to analyze user questions and determine the appropriate response.\n\n"
        "## DECISION LOGIC:\n"
        "1. **SQL REQUIRED**: If the question asks for specific data, statistics, or information that requires querying the database\n"
        "2. **DIRECT RESPONSE**: If the question is about general concepts, definitions, or can be answered without database access\n\n"
        "## DATABASE CONTEXT:\n"
        "You are working with SQLite databases that may contain various tables with relationships.\n"
        "Always consider table relationships, foreign keys, and data types when generating SQL.\n\n"
        "## RESPONSE FORMATS:\n"
        '- For SQL queries: {"sql": "<your optimized SQL query>"}\n'
        '- For direct answers: {"response": "<your natural language response>"}\n\n'
        "## SQL BEST PRACTICES:\n"
        "- Use proper JOIN syntax for related tables\n"
        "- Include appropriate WHERE clauses for filtering\n"
        "- Use aggregate functions (COUNT, SUM, AVG) when needed\n"
        "- Order results logically (ORDER BY)\n"
        "- Limit results when appropriate\n"
        "- Use table aliases for readability\n"
        "- Write SINGLE SQL statements only (no multiple statements separated by semicolons)\n"
        "- Use proper syntax: SELECT * FROM table_name (not SELECT _FROM)\n"
        "- Ensure all SQL is valid SQLite syntax\n\n"
        "## TABLE INFORMATION GUIDELINES:\n"
        "When schema is provided, analyze:\n"
        "- Table names and their purposes\n"
        "- Column names and data types\n"
        "- Primary and foreign key relationships\n"
        "- Potential data patterns\n\n"
        "CRITICAL: Return ONLY valid JSON. No markdown, explanations, or formatting."
    )

    prompt_text = (
        f"{system_instruction}\n\n" f"Schema: {schema}\n\n" f"Question: {question}"
    )

    payload = {"contents": [{"role": "user", "parts": [{"text": prompt_text}]}]}

    response = requests.post(
        url="https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
        headers={"Content-Type": "application/json"},
        params={"key": GEMINI_API_KEY},
        json=payload,
    )

    if response.status_code == 200:
        if not response.text.strip():
            raise Exception("Gemini Response Error: Empty response.")

        try:
            content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            content = re.sub(r"^```(json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)

            return json.loads(content)
        except json.JSONDecodeError:
            raise Exception("Gemini did not return valid JSON. Response: " + content)
        except Exception as e:
            raise Exception(f"Gemini Response Error: {e}")
    else:
        raise Exception(f"Gemini API Error: {response.status_code} - {response.text}")


def format_answer(question, result):
    system_instruction = (
        "You are an expert data analyst that formats database query results into clear, human-readable responses.\n\n"
        "## YOUR ROLE:\n"
        "Transform raw database results into meaningful, well-structured answers that directly address the user's question.\n\n"
        "## FORMATTING GUIDELINES:\n"
        "1. **Direct Answers**: Start with a clear, direct response to the question\n"
        "2. **Data Presentation**: Present data in logical, easy-to-read format\n"
        "3. **Context**: Provide relevant context and insights when appropriate\n"
        "4. **Numbers**: Format numbers clearly (use commas for thousands, appropriate decimal places)\n"
        "5. **Tables**: When multiple records, suggest tabular format for frontend display\n\n"
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
    response = requests.post(
        url="https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
        headers={"Content-Type": "application/json"},
        params={"key": GEMINI_API_KEY},
        json=payload,
    )

    if response.status_code == 200:
        try:
            content = response.json()["candidates"][0]["content"]["parts"][0][
                "text"
            ].strip()
            # Clean up any markdown formatting
            content = re.sub(r"^```(json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)

            # Parse JSON response
            parsed_response = json.loads(content)
            return parsed_response
        except json.JSONDecodeError:
            # Fallback to plain text if JSON parsing fails
            return {"answer": content, "follow_up_questions": []}
        except KeyError:
            raise Exception("Unexpected Gemini API response format.")
    else:
        raise Exception(f"Gemini API Error: {response.status_code} - {response.text}")