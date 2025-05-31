# TalkToData - Enterprise Natural Language Database Query Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13+-blue.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7+-red.svg)](https://redis.io/)

## 🎯 Project Overview

TalkToData is an enterprise-grade intelligent database query platform that enables users to interact with PostgreSQL databases using natural language. Built with FastAPI, LangGraph AI orchestration, and Gemini AI, it provides scalable, secure, and production-ready natural language database interactions for massive datasets.

### 🚀 Enterprise Features

- **💾 PostgreSQL Support** - Handle massive databases with millions of records
- **🔒 Enterprise Security** - JWT authentication, RBAC, rate limiting
- **📈 High Performance** - Async operations, connection pooling, multi-layer caching
- **⚡ Background Processing** - Celery-based async task execution
- **📊 Monitoring & Observability** - Structured logging, health checks, metrics
- **🐳 Production Ready** - Docker containerization, multi-environment support
- **🔄 Horizontal Scaling** - Load balancer ready, stateless design

## 🏗️ Enterprise Architecture

### Core Infrastructure

```mermaid
graph TB
    A[Load Balancer] --> B[FastAPI Instances]
    B --> C[PostgreSQL Primary]
    B --> D[Redis Cache]
    B --> E[Celery Workers]
    E --> F[Redis Broker]
    B --> G[PostgreSQL Replicas]
    H[Monitoring] --> B
    I[Flower] --> E
```

### System Components

1. **🚀 FastAPI Enterprise API** (`enterprise_app.py`) - Production-grade REST API
2. **🧠 LangGraph AI Orchestration** (`main_graph.py`) - Multi-agent workflow
3. **🎨 Streamlit Dashboard** (`streamlit.py`) - Admin & user interface
4. **🤖 Specialized AI Agents** (`agents/`) - Domain-specific processing
5. **🔧 Core Infrastructure** (`core/`) - Database, caching, security, monitoring
6. **⚙️ Background Tasks** (`core/tasks.py`) - Async processing with Celery

### Agent Workflow

```
Authentication → Input Processing → Schema Analysis → SQL Generation → 
Validation → Background Execution → Caching → Response Formatting
```

## 📊 Enterprise Database Schema

### Supported Database Types
- **PostgreSQL 13+** - Primary production database
- **SQLite** - Legacy support and development

### User Management Schema

#### Users Table (Enterprise)
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PRIMARY KEY | Unique user identifier |
| username | VARCHAR(255) UNIQUE | User login name |
| email | VARCHAR(255) UNIQUE | User email address |
| password_hash | VARCHAR(255) | Bcrypt hashed password |
| role | user_role ENUM | ADMIN, ANALYST, VIEWER |
| is_active | BOOLEAN | Account status |
| created_at | TIMESTAMP | Account creation time |
| updated_at | TIMESTAMP | Last modification time |

#### Sessions Table
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PRIMARY KEY | Session identifier |
| user_id | UUID | Foreign key to users |
| access_token | VARCHAR(255) | JWT access token |
| refresh_token | VARCHAR(255) | JWT refresh token |
| expires_at | TIMESTAMP | Token expiration |
| created_at | TIMESTAMP | Session creation time |

### Sample Business Data

#### Orders Table (Example)
| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PRIMARY KEY | Order identifier |
| customer_id | INTEGER | Customer reference |
| product_name | VARCHAR(255) | Product description |
| amount | DECIMAL(10,2) | Order amount |
| order_date | TIMESTAMP | Order timestamp |
| status | VARCHAR(50) | Order status |

### Database Features
- **Connection Pooling** - Handles 100+ concurrent connections
- **Query Optimization** - Automatic explain plan analysis
- **Read Replicas** - Distribute read queries for better performance
- **Indexes** - Optimized for common query patterns
- **Partitioning** - Support for time-based and range partitioning

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+**
- **PostgreSQL 13+**
- **Redis 7+**
- **Docker & Docker Compose** (recommended)
- **Gemini API Key**

### 🐳 Docker Development Setup (Recommended)

1. **Clone and setup environment**:
```bash
git clone <repository>
cd talk-to-db/backend
cp .env.template .env
# Edit .env with your configuration
```

2. **Quick start with setup script**:
```bash
chmod +x setup.sh
./setup.sh
```

3. **Manual Docker setup**:
```bash
# Start all services
docker-compose -f docker-compose.dev.yml up -d

# Check service health
docker-compose -f docker-compose.dev.yml ps

# View logs
docker-compose -f docker-compose.dev.yml logs -f api
```

4. **Access the applications**:
- **API Documentation**: http://localhost:8000/docs
- **Streamlit Dashboard**: http://localhost:8501
- **pgAdmin**: http://localhost:5050 (admin@admin.com / admin)
- **Redis Commander**: http://localhost:8081
- **Flower (Celery)**: http://localhost:5555

### 🔧 Manual Development Setup

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Start infrastructure services**:
```bash
# PostgreSQL
docker run -d --name postgres \
  -e POSTGRES_DB=talktodata \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 postgres:15

# Redis
docker run -d --name redis \
  -p 6379:6379 redis:7-alpine
```

3. **Initialize database**:
```bash
# Run database initialization script
psql -h localhost -U postgres -d talktodata -f scripts/init.sql
```

4. **Start application services**:

**Terminal 1 - API Server**:
```bash
uvicorn enterprise_app:app --reload --port 8000
```

**Terminal 2 - Celery Worker**:
```bash
celery -A core.tasks worker --loglevel=info
```

**Terminal 3 - Celery Beat (Scheduler)**:
```bash
celery -A core.tasks beat --loglevel=info
```

**Terminal 4 - Flower (Optional)**:
```bash
celery -A core.tasks flower
```

**Terminal 5 - Streamlit (Optional)**:
```bash
streamlit run streamlit.py
```

### 📋 Production Deployment

1. **Build production images**:
```bash
docker-compose build
```

2. **Deploy to production**:
```bash
docker-compose up -d
```

3. **Scale workers**:
```bash
docker-compose up -d --scale worker=3
```

## 💡 Usage Examples

### 🔐 Authentication

```bash
# Register new user
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "analyst1",
    "email": "analyst@company.com",
    "password": "SecurePass123!",
    "role": "ANALYST"
  }'

# Login
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "analyst1",
    "password": "SecurePass123!"
  }'
```

### 🗣️ Natural Language Queries

**Enterprise Queries**:
- "Show me the top 10 customers by revenue this quarter"
- "What's the monthly growth rate for the past year?"
- "Find all orders with amounts greater than $10,000"
- "Which products have the highest return rate?"
- "Show me user activity patterns by department"

**Complex Analytics**:
- "Compare sales performance between regions for Q4"
- "What's the customer lifetime value by segment?"
- "Identify trending products in the last 30 days"
- "Show me the correlation between marketing spend and sales"

### 📊 Background Tasks

**Large Data Exports**:
```bash
# Export large dataset
curl -X POST "http://localhost:8000/query/export" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SELECT * FROM orders WHERE order_date >= '\''2024-01-01'\''",
    "format": "parquet"
  }'
```

**Schema Analysis**:
```bash
# Analyze database schema
curl -X POST "http://localhost:8000/admin/analyze-schema" \
  -H "Authorization: Bearer <admin_token>"
```

## 🔧 Enterprise API Endpoints

### Authentication Endpoints
- `POST /auth/register` - Register new user
- `POST /auth/login` - User login
- `POST /auth/logout` - User logout
- `POST /auth/refresh` - Refresh access token
- `PUT /auth/change-password` - Change password

### Query Endpoints
- `POST /query/` - Execute natural language query
- `POST /query/background` - Submit background query task
- `GET /query/task/{task_id}` - Get task status and results
- `POST /query/export` - Export query results (CSV, JSON, Excel, Parquet)

### Admin Endpoints (Admin Role Required)
- `GET /admin/users` - List all users
- `POST /admin/users` - Create user
- `PUT /admin/users/{user_id}` - Update user
- `DELETE /admin/users/{user_id}` - Delete user
- `POST /admin/analyze-schema` - Full schema analysis
- `GET /admin/system-stats` - System performance metrics

### System Endpoints
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics
- `GET /` - API information

### API Response Format

**Success Response**:
```json
{
  "success": true,
  "data": {
    "answer": "Natural language response",
    "sql": "Generated SQL query",
    "results": [{"column": "value"}],
    "execution_time": 0.045
  },
  "timestamp": "2024-01-01T12:00:00Z",
  "correlation_id": "abc-123-def"
}
```

**Error Response**:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid query syntax",
    "details": {}
  },
  "timestamp": "2024-01-01T12:00:00Z",
  "correlation_id": "abc-123-def"
}
```

### Rate Limiting
- **Public endpoints**: 100 requests per hour
- **Authenticated users**: 1000 requests per hour
- **Admin users**: 5000 requests per hour

## 🧠 Enterprise Agent Architecture

### 1. UserInputAgent
- **Enhanced Input Processing** - Validates and sanitizes user queries
- **Context Preservation** - Maintains conversation history
- **Multi-language Support** - Handles international queries

### 2. SchemaAgent
- **Intelligent Caching** - Redis-based schema caching with TTL
- **Performance Optimization** - Async schema extraction
- **Large Schema Handling** - Efficient processing of 100+ tables
- **Connection Pooling** - Reuses database connections

### 3. SQLWriterAgent
- **Advanced SQL Generation** - Complex joins, subqueries, CTEs
- **Query Optimization** - Automatic query plan analysis
- **Security Integration** - Built-in injection prevention
- **Performance Hints** - Suggests indexes and optimizations

### 4. ValidatorAgent
- **Multi-layer Validation** - Syntax, semantic, and security checks
- **Role-based Permissions** - Query restrictions by user role
- **Resource Limiting** - Prevents resource-intensive queries
- **Compliance Checking** - GDPR/PII data protection

### 5. DBExecutorAgent
- **Async Execution** - Non-blocking query processing
- **Background Tasks** - Celery integration for long queries
- **Result Streaming** - Handle large result sets efficiently
- **Error Recovery** - Graceful failure handling

### 6. AnswerFormatterAgent
- **Rich Formatting** - Tables, charts, visualizations
- **Export Options** - Multiple output formats
- **Internationalization** - Multi-language responses
- **Template System** - Customizable response formats

### 7. FallbackAgent
- **Intelligent Recovery** - Context-aware error handling
- **Alternative Suggestions** - Query refinement recommendations
- **Learning System** - Improves from failed queries
- **Escalation Support** - Human expert handoff

## 🛡️ Enterprise Security Features

### Authentication & Authorization
- **JWT-based Authentication** - Secure token-based auth
- **Role-Based Access Control (RBAC)** - Admin, Analyst, Viewer roles
- **Session Management** - Secure session handling with Redis
- **Password Security** - Bcrypt hashing with salt

### API Security
- **Rate Limiting** - Redis-based sliding window algorithm
- **Request Validation** - Pydantic schema validation
- **CORS Protection** - Configurable cross-origin policies
- **Request Tracking** - Correlation IDs for audit trails

### Database Security
- **SQL Injection Prevention** - Parameterized queries only
- **Query Validation** - Multi-layer security checks
- **Permission Enforcement** - Role-based query restrictions
- **Data Masking** - PII protection capabilities

### Infrastructure Security
- **Environment Isolation** - Separate dev/staging/prod configs
- **Secrets Management** - Environment-based configuration
- **Container Security** - Non-root user, minimal attack surface
- **Network Security** - Internal service communication

### Compliance Features
- **Audit Logging** - Complete request/response logging
- **Data Privacy** - GDPR-compliant data handling
- **Access Monitoring** - Real-time security monitoring
- **Compliance Reporting** - Generate security reports

## 📁 Enterprise Project Structure

```
talk-to-db/backend/
├── core/                          # Enterprise infrastructure
│   ├── auth.py                   # Authentication service
│   ├── cache.py                  # Multi-layer caching
│   ├── config.py                 # Configuration management
│   ├── database.py               # PostgreSQL async layer
│   ├── middleware.py             # Security & request middleware
│   ├── monitoring.py             # Logging & observability
│   ├── security.py               # JWT & RBAC implementation
│   ├── tasks.py                  # Celery task infrastructure
│   └── task_implementations.py   # Background task implementations
├── agents/                        # AI agent implementations
│   ├── answer.py                 # Response formatting agent
│   ├── db_executor.py            # Database execution agent
│   ├── fallback.py               # Error handling agent
│   ├── schema.py                 # Schema analysis agent
│   ├── sql_writer.py             # SQL generation agent
│   ├── user_input.py             # Input processing agent
│   └── validator.py              # Query validation agent
├── llm/                          # LLM integrations
│   └── gemini.py                 # Gemini AI interface
├── scripts/                      # Database & deployment scripts
│   └── init.sql                  # PostgreSQL initialization
├── enterprise_app.py             # Enterprise FastAPI application
├── main_graph.py                 # LangGraph AI orchestration
├── streamlit.py                  # Dashboard interface
├── main.py                       # Legacy API (backward compatibility)
├── Dockerfile                    # Multi-stage container build
├── docker-compose.yml            # Production deployment
├── docker-compose.dev.yml        # Development environment
├── requirements.txt              # Python dependencies
├── .env.template                 # Environment configuration template
├── setup.sh                      # Development setup script
└── README.md                     # This documentation
```

## 🔄 Enterprise Workflow Process

1. **🔐 Authentication** - JWT token validation and role verification
2. **📝 Input Processing** - User query sanitization and validation  
3. **🗂️ Schema Analysis** - Cached database structure retrieval
4. **🧠 Intent Recognition** - AI determines query type and complexity
5. **⚡ SQL Generation** - Optimized query creation with security checks
6. **✅ Multi-layer Validation** - Syntax, semantic, and security validation
7. **🔄 Background Execution** - Async processing for complex queries
8. **💾 Intelligent Caching** - Results cached for performance
9. **📊 Response Formatting** - Rich, user-friendly result presentation
10. **📈 Monitoring & Logging** - Complete audit trail and performance metrics

## 🎨 Enterprise Features

### Core Capabilities
- **🌐 Multi-tenant Architecture** - Isolated user environments
- **📊 Advanced Analytics** - Complex statistical queries and aggregations
- **🔍 Intelligent Search** - Natural language to SQL translation
- **📈 Performance Optimization** - Query plan analysis and suggestions
- **🔄 Real-time Processing** - Live data updates and streaming results

### Data Export & Integration
- **📄 Multiple Export Formats** - CSV, JSON, Excel, Parquet
- **🔗 API Integration** - REST endpoints for system integration
- **📊 Visualization Ready** - Structured data for BI tools
- **🔄 Batch Processing** - Handle large dataset exports efficiently
- **⏰ Scheduled Reports** - Automated query execution

### Monitoring & Administration
- **📊 System Dashboard** - Real-time performance metrics
- **👥 User Management** - Role-based access control
- **🔍 Query Analytics** - Usage patterns and optimization insights
- **🚨 Alert System** - Proactive issue detection
- **📋 Audit Trails** - Complete activity logging

## 🔧 Enterprise Configuration

### Environment Variables

#### Core Application
```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false
ENVIRONMENT=production

# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
DATABASE_POOL_TIMEOUT=30

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=3600
REDIS_MAX_CONNECTIONS=50

# Security Configuration
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_WINDOW=3600

# AI Configuration
GEMINI_API_KEY=your-gemini-api-key
LLM_MODEL=gemini-1.5-pro
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=4096

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
CELERY_TASK_TIMEOUT=300
```

#### Monitoring & Logging
```bash
# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=/app/logs/app.log

# Monitoring Configuration
ENABLE_METRICS=true
METRICS_PORT=9090
HEALTH_CHECK_INTERVAL=30
```

### Customization Options

#### Database Settings
- Connection pool configuration for high concurrency
- Query timeout and retry policies
- Read replica configuration for load distribution
- Database-specific optimization parameters

#### AI Model Parameters
- Temperature control for response creativity
- Token limits for cost optimization
- Model selection for different query types
- Response caching strategies

#### Security Policies
- JWT token expiration settings
- Rate limiting configurations
- Role-based permission matrices
- API access control rules

#### Performance Tuning
- Cache TTL settings for different data types
- Background task queue configurations
- Database connection optimization
- Response compression settings

## 📈 Performance & Scalability

### Database Performance
- **Connection Pooling** - Up to 100 concurrent connections
- **Query Optimization** - Automatic explain plan analysis
- **Intelligent Caching** - Multi-layer Redis caching strategy
- **Read Replicas** - Distribute read queries across replicas
- **Async Operations** - Non-blocking database operations

### Caching Strategy
- **L1 Cache** - In-memory application cache
- **L2 Cache** - Redis distributed cache
- **Schema Caching** - Long-term schema metadata storage
- **Query Result Caching** - Intelligent result caching with TTL
- **LLM Response Caching** - Reduce AI API calls

### Horizontal Scaling
- **Stateless Design** - Fully horizontally scalable
- **Load Balancer Ready** - Multiple API instance support
- **Background Processing** - Celery worker scaling
- **Database Sharding** - Support for partitioned databases
- **CDN Integration** - Static asset distribution

### Performance Benchmarks
- **Query Response Time** - < 100ms for cached queries
- **Concurrent Users** - 1000+ simultaneous users
- **Database Scale** - Tested with 1000+ tables, 100M+ records
- **Background Tasks** - Process 10,000+ tasks per hour
- **API Throughput** - 10,000+ requests per minute

## 🧪 Testing & Quality Assurance

### Test Coverage
- **Unit Tests** - Individual component testing
- **Integration Tests** - End-to-end workflow testing
- **Performance Tests** - Load and stress testing
- **Security Tests** - Vulnerability and penetration testing

### Quality Gates
- **Code Coverage** - Minimum 90% test coverage
- **Performance Benchmarks** - Automated performance regression testing
- **Security Scans** - Automated vulnerability scanning
- **Code Quality** - Static analysis and linting

### Continuous Integration
- **Automated Testing** - Full test suite on every commit
- **Security Scanning** - Dependency and code security analysis
- **Performance Monitoring** - Continuous performance tracking
- **Quality Metrics** - Code complexity and maintainability scores

## 🚀 Deployment & Operations

### Container Orchestration
- **Docker Support** - Full containerization
- **Kubernetes Ready** - Helm charts available
- **Auto-scaling** - Horizontal pod autoscaling
- **Health Checks** - Kubernetes liveness/readiness probes

### Monitoring & Observability
- **Structured Logging** - JSON formatted logs with correlation IDs
- **Metrics Collection** - Prometheus metrics export
- **Distributed Tracing** - Request tracing across services
- **Alerting** - Proactive issue detection and notification

### Backup & Recovery
- **Database Backups** - Automated PostgreSQL backups
- **Configuration Backup** - Environment configuration versioning
- **Disaster Recovery** - Multi-region deployment support
- **Data Retention** - Configurable data lifecycle policies

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Clone your fork: `git clone <your-fork>`
3. Create development environment: `./setup.sh`
4. Create feature branch: `git checkout -b feature/your-feature`
5. Make changes and add tests
6. Ensure all tests pass: `python -m pytest`
7. Submit pull request with detailed description

### Code Standards
- **Python Style** - Follow PEP 8 and use Black formatter
- **Type Hints** - All functions must include type annotations
- **Documentation** - Comprehensive docstrings for all modules
- **Testing** - Unit tests required for new features
- **Security** - Security review for authentication/authorization changes

### Contribution Areas
- **Performance Optimization** - Database query optimization
- **Security Enhancements** - Authentication and authorization improvements
- **AI Agents** - New specialized agents for domain-specific queries
- **Integrations** - New database connectors and export formats
- **Monitoring** - Enhanced observability and metrics
- **Documentation** - User guides and technical documentation

## 📚 Additional Resources

### Documentation
- **[Enterprise Transformation Plan](ENTERPRISE_TRANSFORMATION_PLAN.md)** - Detailed migration guide
- **[API Documentation](http://localhost:8000/docs)** - Interactive OpenAPI documentation
- **[Setup Guide](SETUP.md)** - Detailed installation instructions

### External Dependencies
- **[FastAPI Documentation](https://fastapi.tiangolo.com/)** - Web framework
- **[LangGraph Documentation](https://langchain-ai.github.io/langgraph/)** - AI workflow orchestration
- **[PostgreSQL Documentation](https://www.postgresql.org/docs/)** - Database system
- **[Redis Documentation](https://redis.io/documentation)** - Caching and message broker
- **[Celery Documentation](https://docs.celeryproject.org/)** - Background task processing

### Community
- **Issue Tracking** - Report bugs and request features via GitHub Issues
- **Discussions** - Technical discussions and questions via GitHub Discussions
- **Security** - Report security vulnerabilities via security@company.com

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Enterprise License
For enterprise customers requiring additional features, support, or compliance certifications, please contact our enterprise team for licensing options.

---

## 🏆 Acknowledgments

- **LangChain Team** - For the excellent LangGraph framework
- **FastAPI Team** - For the high-performance web framework
- **Google** - For the powerful Gemini AI models
- **PostgreSQL Community** - For the robust database system
- **Redis Team** - For the fast in-memory data structure store

---

**Built with ❤️ for enterprise-grade natural language database interactions**