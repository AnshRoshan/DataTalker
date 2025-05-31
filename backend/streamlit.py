import streamlit as st
import requests
import pandas as pd

API_URL = "http://localhost:8000/chat/"

st.set_page_config(page_title="Chat with your DB", page_icon="🧠")
st.title("🧠 Chat with your SQLite DB")

# ------------------ SESSION STATE INIT ------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "db_method" not in st.session_state:
    st.session_state.db_method = "Upload File"

if "db_file" not in st.session_state:
    st.session_state.db_file = None

if "db_url" not in st.session_state:
    st.session_state.db_url = ""

# ------------------ SIDEBAR: DB SELECTION ------------------
st.sidebar.header("📁 Load your Database")
st.session_state.db_method = st.sidebar.radio(
    "Choose DB input method", ["Upload File", "Provide URL"]
)

if st.session_state.db_method == "Upload File":
    st.session_state.db_file = st.sidebar.file_uploader(
        "Upload a `.db` file", type=["db"]
    )
    st.session_state.db_url = ""
else:
    st.session_state.db_url = st.sidebar.text_input("Paste direct link to `.db` file")
    st.session_state.db_file = None

# ------------------ SIDEBAR: EXAMPLE QUERIES ------------------
st.sidebar.header("💡 Example Queries")
example_queries = [
    "Show me all users",
    "What is the total number of orders?",
    "Who are the top 5 customers by order amount?",
    "What's the average order value?",
    "Show orders from the last 30 days",
    "List all products ordered",
    "Find users with gmail addresses",
]

for query in example_queries:
    if st.sidebar.button(f"📝 {query}", key=f"example_{hash(query)}"):
        st.session_state.example_query = query

# ------------------ SIDEBAR: DATABASE INFO ------------------
if st.session_state.db_file or st.session_state.db_url:
    st.sidebar.header("🗄️ Database Info")
    st.sidebar.info(
        "Database loaded successfully! You can now ask questions about your data."
    )

    with st.sidebar.expander("📋 Sample Questions"):
        st.write(
            """
        **Data Exploration:**
        - "How many records are in each table?"
        - "What columns are available?"
        - "Show me a sample of the data"
        
        **Analytics:**
        - "What are the trends in the data?"
        - "Calculate totals and averages"
        - "Find top/bottom performers"
        
        **Filtering:**
        - "Show records from specific dates"
        - "Filter by specific criteria"
        - "Find records matching patterns"
        """
        )

# ------------------ MAIN CHAT INTERFACE ------------------
st.markdown("### 💬 Chat")

# Handle example query selection
if "example_query" in st.session_state:
    user_question = st.session_state.example_query
    del st.session_state.example_query
else:
    user_question = st.chat_input("Ask something about your database...")

if user_question:
    with st.spinner("Talking to your DB..."):
        # Send question and db to FastAPI
        files = (
            {"db_file": st.session_state.db_file} if st.session_state.db_file else {}
        )
        data = {"question": user_question}
        if st.session_state.db_url:
            data["db_url"] = st.session_state.db_url

        try:
            res = requests.post(API_URL, files=files, data=data)
            if res.status_code == 200:
                response = res.json()

                # Add to history
                st.session_state.chat_history.append(
                    {
                        "question": user_question,
                        "answer": response.get("answer", "No answer."),
                        "sql": response.get("sql"),
                        "results": response.get("results"),
                        "follow_up_questions": response.get("follow_up_questions", []),
                    }
                )
            else:
                st.error(f"❌ Error: {res.json().get('error', 'Unknown error')}")
        except Exception as e:
            st.error(f"❌ Backend error: {e}")

# ------------------ DISPLAY CHAT HISTORY ------------------
for chat in st.session_state.chat_history:
    with st.chat_message("user"):
        st.markdown(chat["question"])

    with st.chat_message("assistant"):
        st.markdown("**Answer:** " + chat["answer"])
        if chat.get("sql"):
            st.markdown("**SQL:**")
            st.code(chat["sql"], language="sql")

        results = chat.get("results")

        if isinstance(results, list) and all(isinstance(row, dict) for row in results):
            df = pd.DataFrame(results)
            if not df.empty:
                st.markdown("### 📊 Query Results")

                # Display summary information
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Rows", len(df))
                with col2:
                    st.metric("Columns", len(df.columns))
                with col3:
                    if df.select_dtypes(include=["number"]).empty:
                        st.metric("Data Types", "Text/Mixed")
                    else:
                        st.metric(
                            "Numeric Cols",
                            len(df.select_dtypes(include=["number"]).columns),
                        )

                # Display the data table
                st.dataframe(df, use_container_width=True)

                # Show column information
                with st.expander("📋 Column Details"):
                    for col in df.columns:
                        col_type = str(df[col].dtype)
                        null_count = df[col].isnull().sum()
                        unique_count = df[col].nunique()
                        st.write(
                            f"**{col}**: {col_type} | {unique_count} unique values | {null_count} null values"
                        )

            else:
                st.info("Query executed successfully but returned no rows.")
        else:
            st.warning("No tabular results to show.")

        # Display follow-up questions
        follow_up_questions = chat.get("follow_up_questions", [])
        if follow_up_questions:
            st.markdown("### 🤔 Follow-up Questions")
            st.markdown("*Click on any question to explore further:*")

            for i, question in enumerate(follow_up_questions):
                if st.button(
                    f"❓ {question}", key=f"followup_{hash(chat['question'])}_{i}"
                ):
                    st.session_state.followup_query = question

# Handle follow-up question selection
if "followup_query" in st.session_state:
    # Trigger a new query with the follow-up question
    user_question = st.session_state.followup_query
    del st.session_state.followup_query

    with st.spinner("Exploring follow-up question..."):
        # Send question and db to FastAPI
        files = (
            {"db_file": st.session_state.db_file} if st.session_state.db_file else {}
        )
        data = {"question": user_question}
        if st.session_state.db_url:
            data["db_url"] = st.session_state.db_url

        try:
            res = requests.post(API_URL, files=files, data=data)
            if res.status_code == 200:
                response = res.json()

                # Add to history
                st.session_state.chat_history.append(
                    {
                        "question": user_question,
                        "answer": response.get("answer", "No answer."),
                        "sql": response.get("sql"),
                        "results": response.get("results"),
                        "follow_up_questions": response.get("follow_up_questions", []),
                    }
                )
                st.rerun()  # Refresh to show the new conversation
            else:
                st.error(f"❌ Error: {res.json().get('error', 'Unknown error')}")
        except Exception as e:
            st.error(f"❌ Backend error: {e}")

# ------------------ FOOTER ------------------
