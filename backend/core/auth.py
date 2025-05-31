"""
Authentication Service

Handles user authentication, registration, session management,
and user operations for the TalkToData application.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import secrets

from fastapi import HTTPException, status
from sqlalchemy import select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from .database import get_database_manager
from .security import (
    User, UserSession, UserRole, LoginRequest, LoginResponse,
    security_manager, TokenData
)
from .monitoring import get_logger, track_performance
from .config import get_settings

logger = get_logger(__name__)
settings = get_settings()

class AuthenticationError(Exception):
    """Custom authentication error"""
    pass

class AuthService:
    """Authentication service for user management"""
    
    def __init__(self):
        self.db_manager = get_database_manager()
        
    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: UserRole = UserRole.VIEWER
    ) -> User:
        """Create a new user"""
        with track_performance("auth.create_user"):
            async with self.db_manager.get_session() as session:
                try:
                    # Hash password
                    hashed_password = security_manager.hash_password(password)
                    
                    # Create user
                    user = User(
                        username=username,
                        email=email,
                        hashed_password=hashed_password,
                        role=role.value,
                        created_at=datetime.utcnow()
                    )
                    
                    session.add(user)
                    await session.commit()
                    await session.refresh(user)
                    
                    logger.info(
                        "User created successfully",
                        extra={
                            "user_id": user.id,
                            "username": username,
                            "email": email,
                            "role": role.value
                        }
                    )
                    
                    return user
                    
                except IntegrityError as e:
                    await session.rollback()
                    if "username" in str(e):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Username already exists"
                        )
                    elif "email" in str(e):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Email already exists"
                        )
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="User creation failed"
                        )
    
    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user with username and password"""
        with track_performance("auth.authenticate_user"):
            async with self.db_manager.get_session() as session:
                # Get user by username
                query = select(User).where(
                    and_(User.username == username, User.is_active == True)
                )
                result = await session.execute(query)
                user = result.scalar_one_or_none()
                
                if not user:
                    logger.warning(
                        "Authentication failed - user not found",
                        extra={"username": username}
                    )
                    return None
                
                # Verify password
                if not security_manager.verify_password(password, user.hashed_password):
                    logger.warning(
                        "Authentication failed - invalid password",
                        extra={"username": username, "user_id": user.id}
                    )
                    return None
                
                # Update last login
                await session.execute(
                    update(User)
                    .where(User.id == user.id)
                    .values(last_login=datetime.utcnow())
                )
                await session.commit()
                
                logger.info(
                    "User authenticated successfully",
                    extra={
                        "username": username,
                        "user_id": user.id,
                        "role": user.role
                    }
                )
                
                return user
    
    async def login(self, login_request: LoginRequest, ip_address: str, user_agent: str) -> LoginResponse:
        """Login a user and create session"""
        with track_performance("auth.login"):
            # Authenticate user
            user = await self.authenticate_user(login_request.username, login_request.password)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid username or password"
                )
            
            # Create session
            session_token = await self.create_session(user.id, ip_address, user_agent)
            
            # Create JWT token
            user_data = {
                "username": user.username,
                "user_id": user.id,
                "role": user.role,
                "session_token": session_token
            }
            
            access_token = security_manager.create_access_token(user_data)
            
            return LoginResponse(
                access_token=access_token,
                expires_in=settings.security.access_token_expire_minutes * 60,
                user={
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "is_active": user.is_active
                }
            )
    
    async def create_session(self, user_id: int, ip_address: str, user_agent: str) -> str:
        """Create a new user session"""
        with track_performance("auth.create_session"):
            async with self.db_manager.get_session() as session:
                # Generate session token
                session_token = secrets.token_urlsafe(32)
                
                # Create session record
                user_session = UserSession(
                    user_id=user_id,
                    session_token=session_token,
                    expires_at=datetime.utcnow() + timedelta(
                        minutes=settings.security.session_expire_minutes
                    ),
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
                session.add(user_session)
                await session.commit()
                
                # Clean up old sessions
                await self.cleanup_expired_sessions(user_id, session)
                
                return session_token
    
    async def validate_session(self, session_token: str) -> Optional[UserSession]:
        """Validate a session token"""
        with track_performance("auth.validate_session"):
            async with self.db_manager.get_session() as session:
                query = select(UserSession).where(
                    and_(
                        UserSession.session_token == session_token,
                        UserSession.expires_at > datetime.utcnow()
                    )
                )
                result = await session.execute(query)
                user_session = result.scalar_one_or_none()
                
                if user_session:
                    # Update last accessed time
                    await session.execute(
                        update(UserSession)
                        .where(UserSession.id == user_session.id)
                        .values(last_accessed=datetime.utcnow())
                    )
                    await session.commit()
                
                return user_session
    
    async def logout(self, session_token: str) -> bool:
        """Logout a user by invalidating session"""
        with track_performance("auth.logout"):
            async with self.db_manager.get_session() as session:
                result = await session.execute(
                    delete(UserSession).where(UserSession.session_token == session_token)
                )
                await session.commit()
                
                success = result.rowcount > 0
                
                if success:
                    logger.info(
                        "User logged out successfully",
                        extra={"session_token": session_token[:8] + "..."}
                    )
                
                return success
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        with track_performance("auth.get_user_by_id"):
            async with self.db_manager.get_session() as session:
                query = select(User).where(User.id == user_id)
                result = await session.execute(query)
                return result.scalar_one_or_none()
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        with track_performance("auth.get_user_by_username"):
            async with self.db_manager.get_session() as session:
                query = select(User).where(User.username == username)
                result = await session.execute(query)
                return result.scalar_one_or_none()
    
    async def update_user_role(self, user_id: int, new_role: UserRole) -> bool:
        """Update user role"""
        with track_performance("auth.update_user_role"):
            async with self.db_manager.get_session() as session:
                result = await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(role=new_role.value)
                )
                await session.commit()
                
                success = result.rowcount > 0
                
                if success:
                    logger.info(
                        "User role updated",
                        extra={
                            "user_id": user_id,
                            "new_role": new_role.value
                        }
                    )
                
                return success
    
    async def deactivate_user(self, user_id: int) -> bool:
        """Deactivate a user"""
        with track_performance("auth.deactivate_user"):
            async with self.db_manager.get_session() as session:
                # Deactivate user
                result = await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(is_active=False)
                )
                
                # Invalidate all sessions
                await session.execute(
                    delete(UserSession).where(UserSession.user_id == user_id)
                )
                
                await session.commit()
                
                success = result.rowcount > 0
                
                if success:
                    logger.info(
                        "User deactivated",
                        extra={"user_id": user_id}
                    )
                
                return success
    
    async def change_password(self, user_id: int, current_password: str, new_password: str) -> bool:
        """Change user password"""
        with track_performance("auth.change_password"):
            async with self.db_manager.get_session() as session:
                # Get user
                query = select(User).where(User.id == user_id)
                result = await session.execute(query)
                user = result.scalar_one_or_none()
                
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found"
                    )
                
                # Verify current password
                if not security_manager.verify_password(current_password, user.hashed_password):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Current password is incorrect"
                    )
                
                # Hash new password
                new_hashed_password = security_manager.hash_password(new_password)
                
                # Update password
                await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(hashed_password=new_hashed_password)
                )
                
                # Invalidate all other sessions for security
                await session.execute(
                    delete(UserSession).where(UserSession.user_id == user_id)
                )
                
                await session.commit()
                
                logger.info(
                    "Password changed successfully",
                    extra={"user_id": user_id}
                )
                
                return True
    
    async def cleanup_expired_sessions(self, user_id: Optional[int] = None, session: Optional[AsyncSession] = None):
        """Clean up expired sessions"""
        with track_performance("auth.cleanup_expired_sessions"):
            use_session = session or self.db_manager.get_session()
            
            async with use_session as s:
                query = delete(UserSession).where(UserSession.expires_at < datetime.utcnow())
                
                if user_id:
                    query = query.where(UserSession.user_id == user_id)
                
                result = await s.execute(query)
                
                if not session:  # Only commit if we created the session
                    await s.commit()
                
                if result.rowcount > 0:
                    logger.info(
                        "Cleaned up expired sessions",
                        extra={
                            "sessions_removed": result.rowcount,
                            "user_id": user_id
                        }
                    )
    
    async def get_user_sessions(self, user_id: int) -> List[UserSession]:
        """Get active sessions for a user"""
        with track_performance("auth.get_user_sessions"):
            async with self.db_manager.get_session() as session:
                query = select(UserSession).where(
                    and_(
                        UserSession.user_id == user_id,
                        UserSession.expires_at > datetime.utcnow()
                    )
                ).order_by(UserSession.last_accessed.desc())
                
                result = await session.execute(query)
                return result.scalars().all()
    
    async def get_all_users(self, skip: int = 0, limit: int = 100) -> Tuple[List[User], int]:
        """Get all users with pagination"""
        with track_performance("auth.get_all_users"):
            async with self.db_manager.get_session() as session:
                # Get total count
                count_query = select(User).where(User.is_active == True)
                count_result = await session.execute(count_query)
                total = len(count_result.scalars().all())
                
                # Get users with pagination
                query = select(User).where(User.is_active == True).offset(skip).limit(limit)
                result = await session.execute(query)
                users = result.scalars().all()
                
                return users, total

# Global auth service instance
auth_service = AuthService()

# Utility functions
async def create_user(username: str, email: str, password: str, role: UserRole = UserRole.VIEWER) -> User:
    """Utility function to create a user"""
    return await auth_service.create_user(username, email, password, role)

async def authenticate_user(username: str, password: str) -> Optional[User]:
    """Utility function to authenticate a user"""
    return await auth_service.authenticate_user(username, password)

async def login_user(login_request: LoginRequest, ip_address: str, user_agent: str) -> LoginResponse:
    """Utility function to login a user"""
    return await auth_service.login(login_request, ip_address, user_agent)

async def logout_user(session_token: str) -> bool:
    """Utility function to logout a user"""
    return await auth_service.logout(session_token)
