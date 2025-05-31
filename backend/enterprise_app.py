"""
Enterprise FastAPI Application

The main FastAPI application with all enterprise features:
- Authentication and authorization
- Rate limiting and security
- Background task processing
- Caching and monitoring
- Database integration
"""

from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any
import asyncio

from fastapi import FastAPI, Request, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field

# Core enterprise components
from core.config import get_settings
from core.database import get_database_manager
from core.cache import get_cache_manager
from core.monitoring import get_logger, track_performance, health_check
from core.security import (
    security_manager, TokenData, UserRole, Permission,
    LoginRequest, LoginResponse
)
from core.auth import auth_service
from core.middleware import (
    setup_middleware, get_current_user_from_request,
    require_admin, require_analyst
)
from core.tasks import task_manager, submit_task, get_task_result, TaskPriority
from core.task_implementations import (
    execute_large_query, analyze_schema, export_data, generate_llm_response
)

# Import existing agents for backward compatibility
# Note: These imports may need to be updated based on actual agent files
# from agents.main_agent import main_agent
# from agents.schema_agent import schema_agent
# from agents.sql_agent import sql_agent
# from agents.validation_agent import validation_agent
# from agents.execution_agent import execution_agent
# from agents.formatting_agent import formatting_agent
# from agents.error_handler_agent import error_handler_agent

# Import the enterprise LangGraph workflow
from enterprise_graph import enterprise_workflow, process_query_async

settings = get_settings()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    logger.info("Starting TalkToData Enterprise API")
    
    try:
        # Initialize core components
        logger.info("Initializing database manager")
        db_manager = get_database_manager()
        await db_manager.init()
        
        logger.info("Initializing cache manager")
        cache_manager = get_cache_manager()
        await cache_manager.init()
        
        logger.info("Initializing security manager")
        await security_manager.init()
        
        logger.info("Initializing task manager")
        await task_manager.init()
        
        # Create default admin user if it doesn't exist
        try:
            admin_user = await auth_service.get_user_by_username("admin")
            if not admin_user:
                logger.info("Creating default admin user")
                await auth_service.create_user(
                    username="admin",
                    email="admin@talktodb.com",
                    password="admin123",  # Change this in production!
                    role=UserRole.ADMIN
                )
                logger.info("Default admin user created")
        except Exception as e:
            logger.warning(f"Could not create default admin user: {e}")
        
        logger.info("TalkToData Enterprise API started successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    finally:
        logger.info("Shutting down TalkToData Enterprise API")

# Create FastAPI app
app = FastAPI(
    title="TalkToData Enterprise API",
    description="Enterprise-grade natural language database query system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Setup middleware
setup_middleware(app)

# Request/Response models
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    use_background: bool = Field(default=False, description="Execute as background task for long queries")
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)

class QueryResponse(BaseModel):
    success: bool
    result: Optional[Dict[str, Any]] = None
    task_id: Optional[str] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None

class SchemaResponse(BaseModel):
    success: bool
    schema: Optional[Dict[str, Any]] = None
    cached: bool = False
    error: Optional[str] = None

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    progress: Optional[int] = None
    error: Optional[str] = None

class ExportRequest(BaseModel):
    query: str = Field(..., min_length=1)
    format: str = Field(default="csv", pattern="^(csv|json|excel|parquet)$")
    filename: Optional[str] = Field(default=None, max_length=100)

class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., regex=r"^[^@]+@[^@]+\.[^@]+$")
    password: str = Field(..., min_length=6)
    role: UserRole = Field(default=UserRole.VIEWER)

# Health check endpoint
@app.get("/health")
async def health_check_endpoint():
    """Health check endpoint"""
    return await health_check()

# Authentication endpoints
@app.post("/auth/login", response_model=LoginResponse)
async def login(request: Request, login_data: LoginRequest):
    """User login"""
    with track_performance("auth.login"):
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "")
        
        return await auth_service.login(login_data, client_ip, user_agent)

@app.post("/auth/logout")
async def logout(current_user: TokenData = Depends(get_current_user_from_request)):
    """User logout"""
    with track_performance("auth.logout"):
        # In a full implementation, you'd get the session token and invalidate it
        return {"message": "Logged out successfully"}

# Database query endpoints
@app.post("/query", response_model=QueryResponse)
async def query_database(
    request_data: QueryRequest,
    current_user: TokenData = Depends(require_analyst)
):
    """Execute natural language database query"""
    with track_performance("api.query"):
        try:
            if request_data.use_background:
                # Submit as background task for large queries
                task_id = await submit_task(
                    "core.task_implementations.execute_large_query",
                    kwargs={
                        "query": request_data.question,
                        "user_id": current_user.user_id
                    },
                    priority=request_data.priority,
                    user_id=current_user.user_id
                )
                  return QueryResponse(
                    success=True,
                    task_id=task_id
                )
            else:
                # Execute synchronously using enterprise workflow
                result = await process_query_async(
                    question=request_data.question,
                    user_context={
                        "user_id": current_user.user_id,
                        "role": current_user.role,
                        "departments": current_user.departments,
                        "permissions": current_user.permissions
                    },
                    db_config={
                        "connection_string": settings.DATABASE_URL,
                        "max_execution_time": request_data.max_execution_time or 30
                    }
                )
                
                return QueryResponse(
                    success=not bool(result.get("error")),
                    result=result,
                    execution_time=result.get("total_processing_time_ms"),
                    error=result.get("error")
                )
                
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return QueryResponse(
                success=False,
                error=str(e)
            )

@app.get("/schema", response_model=SchemaResponse)
async def get_schema(current_user: TokenData = Depends(get_current_user_from_request)):
    """Get database schema"""
    with track_performance("api.schema"):
        try:
            cache_manager = get_cache_manager()
            
            # Try to get from cache first
            cached_schema = await cache_manager.get_schema()
            if cached_schema:
                return SchemaResponse(
                    success=True,
                    schema=cached_schema,
                    cached=True
                )
            
            # Get from database
            db_manager = get_database_manager()
            schema = await db_manager.get_schema()
            
            # Cache for future use
            await cache_manager.set_schema(schema)
            
            return SchemaResponse(
                success=True,
                schema=schema,
                cached=False
            )
            
        except Exception as e:
            logger.error(f"Schema retrieval failed: {e}")
            return SchemaResponse(
                success=False,
                error=str(e)
            )

@app.post("/schema/analyze")
async def analyze_schema_endpoint(
    current_user: TokenData = Depends(require_analyst),
    include_statistics: bool = True,
    include_relationships: bool = True
):
    """Trigger comprehensive schema analysis as background task"""
    with track_performance("api.schema.analyze"):
        task_id = await submit_task(
            "core.task_implementations.analyze_schema",
            kwargs={
                "user_id": current_user.user_id,
                "include_statistics": include_statistics,
                "include_relationships": include_relationships
            },
            priority=TaskPriority.NORMAL,
            user_id=current_user.user_id
        )
        
        return {"task_id": task_id, "message": "Schema analysis started"}

# Export endpoints
@app.post("/export")
async def export_data_endpoint(
    export_request: ExportRequest,
    current_user: TokenData = Depends(require_analyst)
):
    """Export query results to various formats"""
    with track_performance("api.export"):
        task_id = await submit_task(
            "core.task_implementations.export_data",
            kwargs={
                "query": export_request.query,
                "user_id": current_user.user_id,
                "format": export_request.format,
                "filename": export_request.filename
            },
            priority=TaskPriority.NORMAL,
            user_id=current_user.user_id
        )
        
        return {"task_id": task_id, "message": f"Export to {export_request.format} started"}

# Task management endpoints
@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    current_user: TokenData = Depends(get_current_user_from_request)
):
    """Get status of a background task"""
    with track_performance("api.task.status"):
        result = await get_task_result(task_id)
        
        # Check if user owns this task (admin can see all tasks)
        if (current_user.role != UserRole.ADMIN and 
            result.user_id != current_user.user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own tasks"
            )
        
        return TaskStatusResponse(
            task_id=task_id,
            status=result.status.value,
            result=result.result,
            progress=result.progress,
            error=result.error
        )

@app.get("/tasks")
async def get_user_tasks(
    current_user: TokenData = Depends(get_current_user_from_request),
    limit: int = 50
):
    """Get user's background tasks"""
    with track_performance("api.tasks.list"):
        tasks = await task_manager.get_user_tasks(
            current_user.user_id,
            limit=limit
        )
        
        return {
            "tasks": [
                {
                    "task_id": task.task_id,
                    "status": task.status.value,
                    "progress": task.progress,
                    "started_at": task.started_at,
                    "completed_at": task.completed_at
                }
                for task in tasks
            ]
        }

@app.delete("/tasks/{task_id}")
async def cancel_task(
    task_id: str,
    current_user: TokenData = Depends(get_current_user_from_request)
):
    """Cancel a background task"""
    with track_performance("api.task.cancel"):
        success = await task_manager.cancel_task(task_id, current_user.user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found or cannot be cancelled"
            )
        
        return {"message": "Task cancelled successfully"}

# Admin endpoints
@app.post("/admin/users", dependencies=[Depends(require_admin)])
async def create_user(user_data: UserCreateRequest):
    """Create a new user (admin only)"""
    with track_performance("api.admin.create_user"):
        try:
            user = await auth_service.create_user(
                username=user_data.username,
                email=user_data.email,
                password=user_data.password,
                role=user_data.role
            )
            
            return {
                "message": "User created successfully",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role
                }
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"User creation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User creation failed"
            )

@app.get("/admin/users", dependencies=[Depends(require_admin)])
async def list_users(skip: int = 0, limit: int = 100):
    """List all users (admin only)"""
    with track_performance("api.admin.list_users"):
        users, total = await auth_service.get_all_users(skip, limit)
        
        return {
            "users": [
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "is_active": user.is_active,
                    "created_at": user.created_at,
                    "last_login": user.last_login
                }
                for user in users
            ],
            "total": total,
            "skip": skip,
            "limit": limit
        }

@app.get("/admin/health")
async def admin_health_check(current_user: TokenData = Depends(require_admin)):
    """Comprehensive system health check (admin only)"""
    with track_performance("api.admin.health"):
        health_data = await health_check()
        
        # Add additional admin-specific health info
        health_data["components"] = {
            "database": await get_database_manager().health_check(),
            "cache": await get_cache_manager().health_check(),
            "task_queue": "healthy"  # Would check Celery broker status
        }
        
        return health_data

# Metrics endpoint for monitoring
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    # This would return Prometheus-formatted metrics
    # For now, return basic JSON metrics
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z",
        "metrics": {
            "requests_total": 1000,
            "requests_per_second": 10.5,
            "active_connections": 25,
            "cache_hit_rate": 0.85
        }
    }

# Backward compatibility endpoint for existing frontend
@app.post("/process_query")
async def process_query_legacy(
    request: Request,
    current_user: TokenData = Depends(get_current_user_from_request)
):
    """Legacy endpoint for backward compatibility"""
    try:
        body = await request.json()
        question = body.get("question", "")
        
        # Use the new query endpoint internally
        query_request = QueryRequest(question=question)
        return await query_database(query_request, current_user)
        
    except Exception as e:
        return {"error": str(e), "success": False}

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "enterprise_app:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.debug,
        workers=1 if settings.api.debug else settings.api.workers
    )
