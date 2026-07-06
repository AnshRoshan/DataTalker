# PostgreSQL Support

This API now supports both SQLite and PostgreSQL databases. For PostgreSQL, the system connects directly to your database without downloading any files.

## Usage

### PostgreSQL Connection String Format

You can use either the `db_connection_string` or `db_url` parameter with the following format:

```
postgresql://username:password@hostname:port/database_name
```

**Parameter Options:**
- `db_connection_string` - Explicitly for database connection strings
- `db_url` - Can be either a database connection string OR a file download URL (for SQLite)

### Example Connection Strings

```bash
# Local PostgreSQL
postgresql://postgres:password@localhost:5432/hospital_db

# Remote PostgreSQL (like Neon, AWS RDS, etc.)
postgresql://user:pass@host.region.provider.com:5432/dbname

# With SSL (recommended for production)
postgresql://user:pass@host:5432/dbname?sslmode=require
```

### API Endpoints

#### Extract Schema
```bash
# Using db_connection_string parameter
curl -X POST 'http://localhost:8000/schema/' \
  -F 'db_connection_string=postgresql://user:pass@host:5432/dbname'

# Using db_url parameter (alternative)
curl -X POST 'http://localhost:8000/schema/' \
  -F 'db_url=postgresql://user:pass@host:5432/dbname'
```

#### Chat with Database
```bash
# Using db_connection_string parameter
curl -X POST 'http://localhost:8000/chat/' \
  -F 'question=How many patients are in the hospital?' \
  -F 'db_connection_string=postgresql://user:pass@host:5432/dbname'

# Using db_url parameter (alternative)
curl -X POST 'http://localhost:8000/chat/' \
  -F 'question=How many patients are in the hospital?' \
  -F 'db_url=postgresql://user:pass@host:5432/dbname'
```

## Features

- **Direct Connection**: No file downloads required for PostgreSQL
- **Schema Caching**: Automatically caches database schema for faster subsequent queries
- **Security**: Uses SQLAlchemy with parameterized queries to prevent SQL injection
- **Error Handling**: Comprehensive error handling for connection and query issues

## Supported Database Types

| Database | Connection Method | Example |
|----------|------------------|---------|
| SQLite | File upload | Upload .db/.sqlite/.sqlite3 files |
| SQLite | Local path | `sqlite:///path/to/database.db` |
| SQLite | Remote URL | Downloads and caches locally |
| PostgreSQL | Connection string | `postgresql://user:pass@host:port/db` |

## Environment Variables

For security, you can also use environment variables in your connection string:

```bash
export DB_USER="your_username"
export DB_PASS="your_password"
export DB_HOST="your_host"
export DB_NAME="your_database"

# Then use:
postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:5432/${DB_NAME}
```

## Dependencies

The following PostgreSQL drivers are included:
- `asyncpg` - For async PostgreSQL operations
- `psycopg2-binary` - For SQLAlchemy PostgreSQL support

## Troubleshooting

### Connection Issues
- Ensure your PostgreSQL server is accessible from the API server
- Check firewall settings and network connectivity
- Verify credentials and database name
- For cloud databases, ensure SSL settings are correct

### Performance
- Schema extraction may take longer for large databases
- Results are cached to improve subsequent query performance
- Consider using connection pooling for high-traffic scenarios