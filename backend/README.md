# TalkToData - Natural Language Database Query System

## 🎯 Project Overview

TalkToData is an intelligent database query system that allows users to interact with SQLite databases using natural language. The system uses LangGraph for orchestrating multiple AI agents and Gemini AI for natural language processing.

## 🏗️ Architecture

### Core Components

1. **FastAPI Backend** (`main.py`) - REST API server
2. **LangGraph Orchestration** (`main_graph.py`) - Agent workflow management
3. **Streamlit Frontend** (`streamlit.py`) - Web interface
4. **AI Agents** (`agents/`) - Specialized processing units
5. **LLM Integration** (`llm/gemini.py`) - Gemini AI integration

### Agent Workflow

```
User Input → Schema Analysis → SQL Generation → Validation → Execution → Answer Formatting
```

## 📊 Database Schema Information

### Sample Database Tables

#### Users Table
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Unique user identifier |
| name | TEXT | User's full name |
| email | TEXT | User's email address |
| created_at | DATE | Account creation date |

#### Orders Table
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Unique order identifier |
| user_id | INTEGER | Foreign key to users table |
| product | TEXT | Product name |
| amount | REAL | Order amount |
| order_date | DATE | Date of order |

### Sample Data
- **Users**: Alice, Bob, Charlie with respective emails and creation dates
- **Orders**: Linked to users with product information and amounts

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
- Gemini API Key

### Installation

1. **Clone and setup**:
```bash
cd TalkToData
pip install -r requirements.txt
```

2. **Environment Configuration**:
Create `.env` file:
```
GEMINI_API_KEY=your_gemini_api_key_here
```

3. **Run the application**:

**Backend (Terminal 1)**:
```bash
uvicorn main:fastapi_app --reload --port 8000
```

**Frontend (Terminal 2)**:
```bash
streamlit run streamlit.py
```

4. **Access the application**:
- Frontend: http://localhost:8501
- API: http://localhost:8000

## 💡 Usage Examples

### Natural Language Queries
- "Show me all users"
- "What is the total amount of orders?"
- "Who placed orders in 2024?"
- "Find users with gmail addresses"
- "What's the average order amount?"

### Database Upload Options
1. **File Upload**: Upload `.db` files directly
2. **URL Import**: Provide direct links to `.db` files

## 🔧 API Endpoints

### POST /chat/
**Parameters**:
- `question` (required): Natural language query
- `db_file` (optional): SQLite database file
- `db_url` (optional): URL to SQLite database

**Response**:
```json
{
  "answer": "Natural language response",
  "sql": "Generated SQL query",
  "results": [{"column": "value"}]
}
```

## 🧠 Agent Details

### 1. UserInputAgent
- Processes incoming user questions
- Validates input format

### 2. SchemaAgent
- Extracts database schema information
- Provides table and column details
- Handles connection errors

### 3. SQLWriterAgent
- Determines if SQL is needed
- Generates appropriate SQL queries
- Returns natural language responses for non-data questions

### 4. ValidatorAgent
- Validates SQL query safety
- Prevents harmful operations
- Ensures query correctness

### 5. DBExecutorAgent
- Executes validated SQL queries
- Returns structured results
- Handles database errors

### 6. AnswerFormatterAgent
- Formats responses for users
- Creates human-readable answers
- Handles table formatting

### 7. FallbackAgent
- Handles unsafe or invalid queries
- Provides alternative responses
- Error recovery

## 🛡️ Security Features

- SQL injection prevention
- Query validation
- Safe operation enforcement
- Error handling and recovery

## 📁 Project Structure

```
TalkToData/
├── agents/                 # AI agent implementations
│   ├── answer.py          # Answer formatting
│   ├── db_executor.py     # Database execution
│   ├── fallback.py        # Error handling
│   ├── schema.py          # Schema analysis
│   ├── sql_writer.py      # SQL generation
│   ├── user_input.py      # Input processing
│   └── validator.py       # Query validation
├── extra/                 # Additional utilities
│   ├── app.py            # Alternative app
│   ├── create_db.py      # Database creation
│   └── database/         # Sample databases
├── llm/                  # LLM integrations
│   └── gemini.py         # Gemini AI interface
├── main.py               # FastAPI application
├── main_graph.py         # LangGraph workflow
├── streamlit.py          # Frontend interface
├── requirements.txt      # Dependencies
└── pyproject.toml        # Project configuration
```

## 🔄 Workflow Process

1. **Input Processing**: User submits question and database
2. **Schema Extraction**: System analyzes database structure
3. **Intent Recognition**: Determines if SQL query is needed
4. **SQL Generation**: Creates appropriate database query
5. **Validation**: Ensures query safety and correctness
6. **Execution**: Runs query against database
7. **Formatting**: Presents results in user-friendly format

## 🎨 Features

- **Multi-format Support**: Upload files or provide URLs
- **Intelligent Routing**: Automatic SQL vs. natural language detection
- **Safety First**: Built-in query validation and sanitization
- **Rich Responses**: Tables, charts, and formatted text
- **Error Recovery**: Graceful handling of invalid queries
- **Chat History**: Persistent conversation tracking

## 🔧 Configuration

### Environment Variables
- `GEMINI_API_KEY`: Required for AI functionality

### Customization Options
- Database connection settings
- AI model parameters
- Response formatting preferences
- Security validation rules

## 📈 Performance Considerations

- Efficient schema caching
- Optimized query execution
- Minimal API calls
- Streamlined agent communication

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Implement changes
4. Add tests
5. Submit pull request

## 📄 License

This project is open source and available under the MIT License.