"""
FastAPI Middleware Layer

Provides security middleware, rate limiting, CORS handling,
request/response processing, and performance monitoring for the TalkToData API.
"""

import time
import uuid
from typing import Dict, Optional, Any, Callable
import json

from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
import asyncio

from .monitoring import get_logger, track_performance, correlation_id_var
from .security import security_manager, TokenData
from .config import get_settings

logger = get_logger(__name__)
settings = get_settings()

class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for authentication and authorization"""
    
    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.public_paths = {
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/auth/login",
            "/auth/register"
        }
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request through security middleware"""
        path = request.url.path
        
        # Skip security for public paths
        if path in self.public_paths or path.startswith("/static"):
            return await call_next(request)
        
        # Extract and validate JWT token
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required"}
            )
        
        try:
            token = authorization.split(" ")[1]
            token_data = security_manager.jwt_manager.verify_token(token)
            
            # Add user context to request
            request.state.current_user = token_data
            
            # Log authenticated request
            logger.info(
                "Authenticated request",
                extra={
                    "user_id": token_data.user_id,
                    "username": token_data.username,
                    "role": token_data.role.value,
                    "path": path,
                    "method": request.method
                }
            )
            
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail}
            )
        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"}
            )
        
        return await call_next(request)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""
    
    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.bypass_paths = {"/health", "/metrics"}
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request through rate limiting middleware"""
        path = request.url.path
        
        # Skip rate limiting for specific paths
        if path in self.bypass_paths:
            return await call_next(request)
        
        try:
            # Get user ID if authenticated
            user_id = None
            if hasattr(request.state, "current_user"):
                user_id = request.state.current_user.user_id
            
            # Check rate limit
            await security_manager.check_rate_limit(request, user_id)
            
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail},
                headers=e.headers or {}
            )
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Continue on rate limiting errors
        
        return await call_next(request)

class RequestTrackerMiddleware(BaseHTTPMiddleware):
    """Request tracking and performance monitoring middleware"""
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Track request performance and add correlation ID"""
        start_time = time.time()
        correlation_id = str(uuid.uuid4())
        
        # Set correlation ID in context
        correlation_id_var.set(correlation_id)
        
        # Add correlation ID to request
        request.state.correlation_id = correlation_id
        
        # Log request start
        logger.info(
            "Request started",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params),
                "user_agent": request.headers.get("user-agent"),
                "client_ip": request.client.host
            }
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Add headers
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
            
            # Log request completion
            logger.info(
                "Request completed",
                extra={
                    "duration_ms": duration * 1000,
                    "status_code": response.status_code,
                    "response_size": response.headers.get("content-length", 0)
                }
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            
            logger.error(
                "Request failed",
                extra={
                    "duration_ms": duration * 1000,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            
            # Return error response
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error", "correlation_id": correlation_id},
                headers={"X-Correlation-ID": correlation_id}
            )

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Global error handling middleware"""
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Handle errors and exceptions"""
        try:
            return await call_next(request)
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
            
            logger.error(
                "Unhandled exception",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "path": request.url.path,
                    "method": request.method
                },
                exc_info=True
            )
            
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal server error",
                    "correlation_id": correlation_id
                },
                headers={"X-Correlation-ID": correlation_id}
            )

class ResponseFormatterMiddleware(BaseHTTPMiddleware):
    """Response formatting and standardization middleware"""
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Format API responses consistently"""
        response = await call_next(request)
        
        # Skip formatting for non-JSON responses
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            return response
        
        # Skip formatting for specific paths
        if request.url.path in {"/docs", "/redoc", "/openapi.json"}:
            return response
        
        # Add standard headers
        response.headers["X-API-Version"] = "1.0"
        response.headers["X-Powered-By"] = "TalkToData"
        
        return response

def setup_cors(app: FastAPI) -> None:
    """Setup CORS middleware"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "X-Response-Time", "X-API-Version"]
    )

def setup_middleware(app: FastAPI) -> None:
    """Setup all middleware for the FastAPI application"""
    
    # Add middleware in reverse order (last added is executed first)
    
    # Response formatting (outermost)
    app.add_middleware(ResponseFormatterMiddleware)
    
    # Error handling
    app.add_middleware(ErrorHandlerMiddleware)
    
    # Request tracking and performance monitoring
    app.add_middleware(RequestTrackerMiddleware)
    
    # Rate limiting
    app.add_middleware(RateLimitMiddleware)
    
    # Security (authentication/authorization)
    app.add_middleware(SecurityMiddleware)
    
    # CORS (innermost, after security)
    setup_cors(app)
    
    logger.info("Middleware setup completed")

class MiddlewareUtils:
    """Utility functions for middleware operations"""
    
    @staticmethod
    def get_current_user(request: Request) -> Optional[TokenData]:
        """Get current user from request state"""
        return getattr(request.state, "current_user", None)
    
    @staticmethod
    def get_correlation_id(request: Request) -> Optional[str]:
        """Get correlation ID from request state"""
        return getattr(request.state, "correlation_id", None)
    
    @staticmethod
    def is_authenticated(request: Request) -> bool:
        """Check if request is authenticated"""
        return hasattr(request.state, "current_user")
    
    @staticmethod
    def require_permission(request: Request, permission: str) -> bool:
        """Check if current user has required permission"""
        current_user = MiddlewareUtils.get_current_user(request)
        if not current_user:
            return False
        return permission in [p.value for p in current_user.permissions]

# Dependency functions for FastAPI
async def get_current_user_from_request(request: Request) -> TokenData:
    """FastAPI dependency to get current user"""
    current_user = MiddlewareUtils.get_current_user(request)
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return current_user

async def require_admin(request: Request) -> TokenData:
    """FastAPI dependency to require admin role"""
    current_user = await get_current_user_from_request(request)
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    return current_user

async def require_analyst(request: Request) -> TokenData:
    """FastAPI dependency to require analyst role or higher"""
    current_user = await get_current_user_from_request(request)
    if current_user.role.value not in ["admin", "analyst"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analyst role or higher required"
        )
    return current_user
