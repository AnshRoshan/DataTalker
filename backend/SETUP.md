# TalkToData Setup Guide

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.13 or higher
- Gemini API key from Google AI Studio

### 2. Installation Steps

```bash
# Navigate to project directory
cd TalkToData

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env file and add your GEMINI_API_KEY
```

### 3. Running the Application

**Option A: Full Stack (Recommended)**
```bash
# Terminal 1: Start FastAPI backend
uvicorn main:fastapi_app --reload --port 8000

# Terminal 2: Start Streamlit frontend
streamlit run streamlit.py
```

**Option B: API Only**
```bash
# Start only the FastAPI backend
uvicorn main:fastapi_app --reload --port 8000
# Access API docs at: http://localhost:8000/docs
```

### 4. Access Points
- **Web Interface**: http://localhost:8501
- **API Documentation**: http://localhost:8000/docs
- **API Endpoint**: http://localhost:8000/chat/

## 🗄️ Database Requirements

### Supported Formats
- SQLite (.db files)
- Local file upload
- Remote URL access

### Sample Database
The project includes sample databases in the `extra/database/` directory:
- `sample.db` - Basic users and orders tables
- `schema.sql` - Database creation script

### Creating Your Own Database
```sql
-- Example table structure
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    created_at DATE DEFAULT CURRENT_DATE
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    product TEXT NOT NULL,
    amount REAL,
    order_date DATE DEFAULT CURRENT_DATE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

## 🔧 Configuration Options

### Environment Variables
- `GEMINI_API_KEY`: Required for AI functionality
- `DEBUG_MODE`: Enable detailed logging (optional)
- `MAX_QUERY_RESULTS`: Limit query result size (optional)

### API Configuration
The FastAPI backend supports:
- File uploads (multipart/form-data)
- URL-based database access
- CORS for frontend integration

### Frontend Features
- Interactive chat interface
- Example query suggestions
- Table result visualization
- Column analysis and statistics
- Database schema information

## 📊 Usage Examples

### Natural Language Queries
```
"Show me all users"
"What's the total revenue?"
"Find orders from last month"
"Who are the top customers?"
"Calculate average order value"
```

### API Usage
```bash
curl -X POST "http://localhost:8000/chat/" \
  -F "question=Show me all users" \
  -F "db_file=@path/to/your/database.db"
```

## 🛠️ Development

### Project Structure
```
TalkToData/
├── agents/           # AI agent implementations
├── llm/             # LLM integration (Gemini)
├── extra/           # Sample data and utilities
├── main.py          # FastAPI application
├── main_graph.py    # LangGraph workflow
├── streamlit.py     # Frontend interface
└── requirements.txt # Dependencies
```

### Adding New Agents
1. Create agent class in `agents/` directory
2. Implement `__call__` method with state parameter
3. Add agent to workflow in `main_graph.py`
4. Update conditional edges as needed

### Customizing LLM Behavior
Edit `llm/gemini.py` to:
- Modify system instructions
- Adjust response formatting
- Add new AI capabilities
- Change model parameters

## 🔍 Troubleshooting

### Common Issues

**1. Missing API Key**
```
Error: Missing Gemini API key
Solution: Add GEMINI_API_KEY to .env file
```

**2. Database Connection Failed**
```
Error: Schema extraction failed
Solution: Ensure .db file is valid SQLite database
```

**3. Port Already in Use**
```
Error: Address already in use
Solution: Use different port: uvicorn main:fastapi_app --port 8001
```

**4. Module Import Errors**
```
Error: No module named 'langgraph'
Solution: pip install -r requirements.txt
```

### Performance Tips
- Use indexed columns for better query performance
- Limit result sets for large databases
- Consider database optimization for complex queries
- Monitor API rate limits for Gemini AI

### Security Considerations
- Validate all SQL queries before execution
- Sanitize user inputs
- Use environment variables for sensitive data
- Implement proper error handling

## 📈 Advanced Features

### Custom Database Schemas
The system automatically detects:
- Table structures and relationships
- Primary and foreign keys
- Column data types and constraints
- Row counts and statistics

### Query Optimization
- Automatic JOIN detection
- Efficient WHERE clause generation
- Result limiting and pagination
- Index usage recommendations

### Error Recovery
- Fallback responses for invalid queries
- Graceful handling of database errors
- User-friendly error messages
- Retry mechanisms for API failures