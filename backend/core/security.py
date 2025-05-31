"""
Enterprise Security Layer

Provides JWT authentication, role-based access control, API rate limiting,
and security middleware for the TalkToData application.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Union
from enum import Enum
import json

import jwt
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from pydantic import BaseModel, Field
import redis.asyncio as redis
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from .config import get_settings
from .monitoring import get_logger, track_performance

logger = get_logger(__name__)
settings = get_settings()

# Security models
Base = declarative_base()

class UserRole(str, Enum):
    """User roles for role-based access control"""
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"
    
class Permission(str, Enum):
    """System permissions"""
    READ_SCHEMA = "read_schema"
    EXECUTE_QUERY = "execute_query"
    VIEW_RESULTS = "view_results"
    ADMIN_USERS = "admin_users"
    ADMIN_SYSTEM = "admin_system"

# Role-Permission mapping
ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    UserRole.VIEWER: {Permission.READ_SCHEMA, Permission.VIEW_RESULTS},
    UserRole.ANALYST: {Permission.READ_SCHEMA, Permission.EXECUTE_QUERY, Permission.VIEW_RESULTS},
    UserRole.ADMIN: {
        Permission.READ_SCHEMA,
        Permission.EXECUTE_QUERY,
        Permission.VIEW_RESULTS,
        Permission.ADMIN_USERS,
        Permission.ADMIN_SYSTEM
    }
}

class User(Base):
    """User model for database"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default=UserRole.VIEWER.value)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")

class UserSession(Base):
    """User session tracking"""
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_token = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    
    # Relationships
    user = relationship("User", back_populates="sessions")

# Pydantic models
class TokenData(BaseModel):
    """JWT token payload data"""
    username: str
    user_id: int
    role: UserRole
    permissions: List[Permission]
    exp: datetime
    iat: datetime
    jti: str  # JWT ID for token revocation

class LoginRequest(BaseModel):
    """Login request model"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

class LoginResponse(BaseModel):
    """Login response model"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Union[str, int, bool]]

class PasswordHasher:
    """Secure password hashing utilities"""
    
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    def hash_password(self, password: str) -> str:
        """Hash a password securely"""
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)

class JWTManager:
    """JWT token management"""
    
    def __init__(self):
        self.secret_key = settings.security.secret_key
        self.algorithm = settings.security.algorithm
        self.access_token_expire_minutes = settings.security.access_token_expire_minutes
        
    def create_access_token(self, user: Dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a new access token"""
        to_encode = user.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=self.access_token_expire_minutes)
        
        # Add standard JWT claims
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": secrets.token_urlsafe(32)  # Unique token ID for revocation
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> TokenData:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Extract token data
            username: str = payload.get("username")
            user_id: int = payload.get("user_id")
            role: str = payload.get("role")
            
            if username is None or user_id is None or role is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload"
                )
            
            # Convert role and get permissions
            user_role = UserRole(role)
            permissions = list(ROLE_PERMISSIONS.get(user_role, set()))
            
            return TokenData(
                username=username,
                user_id=user_id,
                role=user_role,
                permissions=permissions,
                exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
                iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
                jti=payload.get("jti", "")
            )
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )

class RateLimiter:
    """Redis-based rate limiting"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.default_limits = settings.security.rate_limit
    
    async def init_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.from_url(
                settings.cache.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Rate limiter Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis for rate limiting: {e}")
            self.redis_client = None
    
    async def is_allowed(self, key: str, limit: int, window: int) -> tuple[bool, Dict[str, int]]:
        """
        Check if request is allowed under rate limit
        
        Args:
            key: Unique identifier for rate limiting (e.g., user_id, ip_address)
            limit: Number of requests allowed
            window: Time window in seconds
            
        Returns:
            (is_allowed, {"remaining": int, "reset_time": int})
        """
        if not self.redis_client:
            # If Redis is not available, allow all requests
            logger.warning("Rate limiter Redis not available, allowing request")
            return True, {"remaining": limit - 1, "reset_time": window}
        
        try:
            current_time = int(datetime.now().timestamp())
            window_start = current_time - window
            
            # Use sliding window rate limiting
            pipe = self.redis_client.pipeline()
            
            # Remove expired entries
            await pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests
            current_count = await pipe.zcard(key)
            
            if current_count >= limit:
                # Calculate reset time
                oldest_request = await self.redis_client.zrange(key, 0, 0, withscores=True)
                reset_time = int(oldest_request[0][1]) + window if oldest_request else window
                
                return False, {
                    "remaining": 0,
                    "reset_time": reset_time - current_time
                }
            
            # Add current request
            await pipe.zadd(key, {str(secrets.token_urlsafe(8)): current_time})
            await pipe.expire(key, window)
            await pipe.execute()
            
            return True, {
                "remaining": limit - current_count - 1,
                "reset_time": window
            }
            
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # On error, allow the request
            return True, {"remaining": limit - 1, "reset_time": window}
    
    async def check_rate_limit(self, request: Request, user_id: Optional[int] = None) -> None:
        """Check rate limit for a request"""
        # Determine rate limit key and limits
        if user_id:
            key = f"rate_limit:user:{user_id}"
            limit = self.default_limits["per_user_per_minute"]
        else:
            # Use IP-based rate limiting for unauthenticated requests
            client_ip = request.client.host
            key = f"rate_limit:ip:{client_ip}"
            limit = self.default_limits["per_ip_per_minute"]
        
        is_allowed, info = await self.is_allowed(key, limit, 60)  # 60 seconds window
        
        if not is_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": str(info["remaining"]),
                    "X-RateLimit-Reset": str(info["reset_time"])
                }
            )

class SecurityManager:
    """Central security management"""
    
    def __init__(self):
        self.password_hasher = PasswordHasher()
        self.jwt_manager = JWTManager()
        self.rate_limiter = RateLimiter()
        self.bearer = HTTPBearer()
    
    async def init(self):
        """Initialize security components"""
        await self.rate_limiter.init_redis()
    
    def hash_password(self, password: str) -> str:
        """Hash a password"""
        return self.password_hasher.hash_password(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password"""
        return self.password_hasher.verify_password(plain_password, hashed_password)
    
    def create_access_token(self, user_data: Dict) -> str:
        """Create an access token"""
        return self.jwt_manager.create_access_token(user_data)
    
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials) -> TokenData:
        """Get current user from JWT token"""
        with track_performance("security.verify_token"):
            token_data = self.jwt_manager.verify_token(credentials.credentials)
            
            # Log authentication event
            logger.info(
                "User authenticated",
                extra={
                    "user_id": token_data.user_id,
                    "username": token_data.username,
                    "role": token_data.role.value
                }
            )
            
            return token_data
    
    def require_permission(self, required_permission: Permission):
        """Decorator to require specific permission"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                # Extract token data from kwargs or context
                token_data = kwargs.get("current_user")
                if not token_data or required_permission not in token_data.permissions:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission '{required_permission.value}' required"
                    )
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    async def check_rate_limit(self, request: Request, user_id: Optional[int] = None):
        """Check rate limits"""
        await self.rate_limiter.check_rate_limit(request, user_id)

# Global security manager instance
security_manager = SecurityManager()

# Security utilities
def get_password_hash(password: str) -> str:
    """Utility function to hash passwords"""
    return security_manager.hash_password(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Utility function to verify passwords"""
    return security_manager.verify_password(plain_password, hashed_password)

def create_access_token(user_data: Dict) -> str:
    """Utility function to create access tokens"""
    return security_manager.create_access_token(user_data)

async def get_current_user(credentials: HTTPAuthorizationCredentials = None) -> TokenData:
    """Dependency to get current authenticated user"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return await security_manager.get_current_user(credentials)

def require_permission(permission: Permission):
    """Decorator to require specific permissions"""
    return security_manager.require_permission(permission)

async def check_rate_limit(request: Request, user_id: Optional[int] = None):
    """Check rate limits for requests"""
    await security_manager.check_rate_limit(request, user_id)
