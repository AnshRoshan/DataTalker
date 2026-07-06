# Talk to DB API - Architecture Documentation

## Overview

The Talk to DB API has been refactored into a clean, modular architecture that separates concerns and improves maintainability. The application allows users to chat with databases using natural language queries.

## Directory Structure

```
backend/
├── main.py                 # Main FastAPI application entry point
├── core/                   # Core utilities and configuration
│   ├── __init__.py
│   ├── config.py          # Configuration settings and constants
│   ├── database.py        # Database connection and validation utilities
│   ├── cache.py           # Schema caching functionality
│   └── file_handler.py    # File upload and download handling
├── api/                    # API layer
│   ├── __init__.py
│   ├── endpoints.py       # FastAPI route definitions
│   ├── models.py          # Pydantic models for requests/responses
│   └── dependencies.py    # FastAPI dependencies and input handlers
├── services/               # Business logic services
│   ├── __init__.py
│   ├── schema_service.py  # Schema extraction service
│   └── query_service.py   # Query processing service
├── graphs/                 # LangGraph workflow definitions
│   ├── __init__.py
│   ├── schema_graph.py    # Schema extraction graph
│   ├── query_graph.py     # Query processing graph
│   └── main_graph.py      # Comprehensive graph (schema + query)
├── agents/                 # Individual agent implementations
│   ├── user_input.py      # User input validation agent
│   ├── schema.py          # Schema extraction agent
│   ├── sql_writer.py      # SQL generation agent
│   ├── validator.py       # SQL validation agent
│   ├── db_executor.py     # Database execution agent
│   ├── answer.py          # Answer formatting agent
│   └── fallback.py        # Fallback handling agent
└── llm/                    # LLM integration
    └── gemini.py          # Gemini LLM integration
```

## Architecture Layers

### 1. Core Layer (`core/`)
Contains fundamental utilities and configuration:
- **config.py**: Centralized configuration and constants
- **database.py**: Database connection utilities, path validation, connection string parsing
- **cache.py**: Schema caching with expiration and management
- **file_handler.py**: File upload, download, and temporary file management

### 2. API Layer (`api/`)
Handles HTTP requests and responses:
- **endpoints.py**: FastAPI route definitions and request handling
- **models.py**: Pydantic models for request/response validation
- **dependencies.py**: Reusable FastAPI dependencies for database input processing

### 3. Services Layer (`services/`)
Contains business logic:
- **schema_service.py**: Orchestrates schema extraction and caching
- **query_service.py**: Handles natural language query processing

### 4. Graphs Layer (`graphs/`)
LangGraph workflow definitions:
- **schema_graph.py**: Simplified schema extraction workflow
- **query_graph.py**: Query processing workflow (SQL generation → validation → execution → formatting)
- **main_graph.py**: Comprehensive workflow combining schema extraction and query processing

### 5. Agents Layer (`agents/`)
Individual processing agents (unchanged from original structure):
- Each agent handles a specific step in the processing pipeline
- Agents are stateless and can be composed into different workflows

## Key Improvements

### 1. Separation of Concerns
- **Database handling** is isolated in `core/database.py`
- **Caching logic** is centralized in `core/cache.py`
- **File operations** are handled in `core/file_handler.py`
- **API logic** is separated from business logic

### 2. Modular Design
- Each module has a single responsibility
- Easy to test individual components
- Clear dependencies between modules

### 3. Configuration Management
- All configuration is centralized in `core/config.py`
- Easy to modify settings without touching business logic

### 4. Improved Graph Architecture
- **Schema graph** is simplified and doesn't require user input validation
- **Query graph** focuses only on query processing
- **Main graph** provides the full workflow when needed

### 5. Better Error Handling
- Consistent error handling across all layers
- Proper HTTP exception handling
- Resource cleanup (temporary files)

## API Endpoints

### POST `/chat/`
Main endpoint for natural language database queries.
- Automatically extracts and caches schema if needed
- Processes natural language questions
- Returns formatted answers with SQL and results

### POST `/schema/`
Dedicated endpoint for schema extraction and caching.
- Supports multiple input methods (file upload, local path, URL, connection string)
- Returns schema information and table list

### GET `/schema/cache`
View cached schema information.

### DELETE `/schema/cache`
Clear all cached schemas.

### GET `/health`
Health check endpoint.

### GET `/`
API information and documentation.

## Database Support

### SQLite
- Local file paths (absolute paths required)
- File uploads
- URL downloads
- Connection strings (`sqlite:///path/to/file.db`)

### PostgreSQL
- Connection strings (`postgresql://user:pass@host:port/dbname`)
- Direct remote database access

## Usage Examples

### Using Connection String
```bash
curl -X POST "http://localhost:8000/chat/" \
  -F "question=What tables are available?" \
  -F "db_connection_string=postgresql://user:pass@host:port/dbname"
```

### Using File Upload
```bash
curl -X POST "http://localhost:8000/chat/" \
  -F "question=Show me all users" \
  -F "db_file=@database.db"
```

### Using Local Path
```bash
curl -X POST "http://localhost:8000/chat/" \
  -F "question=Count all records" \
  -F "db_path=/absolute/path/to/database.db"
```

## Development

### Running the Application
```bash
cd backend
python main.py
```

### Testing Individual Components
```python
# Test schema service
from services.schema_service import SchemaService
schema_data = SchemaService.extract_and_cache_schema(
    "sqlite:///test.db", "sqlite", "/path/to/test.db"
)

# Test query service
from services.query_service import QueryService
result = QueryService.process_query(
    "Show all tables", "sqlite:///test.db", "sqlite", schema_data
)
```

### Adding New Features
1. **New database type**: Extend `core/database.py` and update configuration
2. **New input method**: Add to `api/dependencies.py`
3. **New processing step**: Create new agent and update relevant graph
4. **New endpoint**: Add to `api/endpoints.py` with appropriate model

## Migration from Old Structure

The old monolithic `main.py` has been preserved as `main_old.py`. The new structure maintains backward compatibility through:
- Symbolic links for graph files
- Same API endpoints and behavior
- Identical response formats

## Benefits of New Architecture

1. **Maintainability**: Clear separation makes code easier to understand and modify
2. **Testability**: Individual components can be tested in isolation
3. **Scalability**: Easy to add new features without affecting existing code
4. **Reusability**: Services and utilities can be reused across different contexts
5. **Configuration**: Centralized configuration management
6. **Error Handling**: Consistent error handling and resource cleanup