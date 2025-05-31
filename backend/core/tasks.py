"""
Background Task System using Celery

Provides asynchronous task processing for heavy operations like
large queries, schema analysis, and data exports.
"""

import asyncio
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from enum import Enum

from celery import Celery, Task
from celery.result import AsyncResult
from celery.signals import task_prerun, task_postrun, task_failure
import redis
from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from pydantic import BaseModel

from .config import get_settings
from .monitoring import get_logger, track_performance
from .database import DatabaseManager

logger = get_logger(__name__)
settings = get_settings()

class TaskStatus(str, Enum):
    """Task status enumeration"""
    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    REVOKED = "revoked"

class TaskPriority(str, Enum):
    """Task priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class TaskResult(BaseModel):
    """Task result model"""
    task_id: str
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    progress: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    user_id: Optional[int] = None

class AsyncTask(Task):
    """Custom Celery task with async support and error handling"""
    
    def __call__(self, *args, **kwargs):
        """Override to handle async functions"""
        try:
            # If the task function is async, run it in event loop
            if asyncio.iscoroutinefunction(self.run):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self.run(*args, **kwargs))
                finally:
                    loop.close()
            else:
                return self.run(*args, **kwargs)
        except Exception as e:
            logger.error(f"Task {self.name} failed: {str(e)}", exc_info=True)
            raise

# Create Celery app
celery_app = Celery(
    "talktodb_tasks",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
    include=["core.tasks"]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.celery.task_time_limit,
    task_soft_time_limit=settings.celery.task_soft_time_limit,
    worker_prefetch_multiplier=settings.celery.worker_prefetch_multiplier,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_compression="gzip",
    result_compression="gzip",
    result_expires=3600,  # 1 hour
    task_routes={
        "core.tasks.execute_large_query": {"queue": "query_queue"},
        "core.tasks.analyze_schema": {"queue": "analysis_queue"},
        "core.tasks.export_data": {"queue": "export_queue"},
        "core.tasks.generate_llm_response": {"queue": "llm_queue"},
    }
)

class TaskManager:
    """Manages background tasks and their lifecycle"""
    
    def __init__(self):
        self.redis_client = None
        self.db_engine = None
    
    async def init(self):
        """Initialize task manager"""
        try:
            # Initialize Redis connection
            self.redis_client = redis.from_url(
                settings.cache.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            
            # Initialize database engine for task storage
            self.db_engine = create_async_engine(
                settings.database.get_url(),
                pool_size=5,
                max_overflow=10
            )
            
            logger.info("Task manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize task manager: {e}")
            raise
    
    async def submit_task(
        self,
        task_name: str,
        args: tuple = (),
        kwargs: dict = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        user_id: Optional[int] = None,
        eta: Optional[datetime] = None,
        countdown: Optional[int] = None
    ) -> str:
        """Submit a task for background execution"""
        kwargs = kwargs or {}
        
        try:
            # Add metadata
            kwargs["user_id"] = user_id
            kwargs["submitted_at"] = datetime.utcnow().isoformat()
            
            # Configure task options
            task_options = {
                "priority": self._get_priority_value(priority),
                "retry": True,
                "retry_policy": {
                    "max_retries": 3,
                    "interval_start": 0,
                    "interval_step": 0.2,
                    "interval_max": 0.2,
                }
            }
            
            if eta:
                task_options["eta"] = eta
            elif countdown:
                task_options["countdown"] = countdown
            
            # Submit task
            result = celery_app.send_task(
                task_name,
                args=args,
                kwargs=kwargs,
                **task_options
            )
            
            # Store task metadata
            await self._store_task_metadata(result.id, task_name, user_id, priority)
            
            logger.info(
                f"Task submitted: {task_name}",
                extra={
                    "task_id": result.id,
                    "user_id": user_id,
                    "priority": priority.value
                }
            )
            
            return result.id
            
        except Exception as e:
            logger.error(f"Failed to submit task {task_name}: {e}")
            raise
    
    async def get_task_result(self, task_id: str) -> TaskResult:
        """Get task result and status"""
        try:
            result = AsyncResult(task_id, app=celery_app)
            
            # Get task metadata
            metadata = await self._get_task_metadata(task_id)
            
            task_result = TaskResult(
                task_id=task_id,
                status=TaskStatus(result.status.lower()),
                user_id=metadata.get("user_id")
            )
            
            if result.successful():
                task_result.result = result.result
                task_result.completed_at = datetime.utcnow()
            elif result.failed():
                task_result.error = str(result.result) if result.result else "Unknown error"
                task_result.traceback = result.traceback
            
            # Get progress if available
            if hasattr(result, "info") and isinstance(result.info, dict):
                task_result.progress = result.info.get("progress")
            
            return task_result
            
        except Exception as e:
            logger.error(f"Failed to get task result for {task_id}: {e}")
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILURE,
                error=str(e)
            )
    
    async def cancel_task(self, task_id: str, user_id: Optional[int] = None) -> bool:
        """Cancel a running task"""
        try:
            # Check if user has permission to cancel this task
            if user_id:
                metadata = await self._get_task_metadata(task_id)
                if metadata.get("user_id") != user_id:
                    logger.warning(
                        f"User {user_id} attempted to cancel task {task_id} belonging to user {metadata.get('user_id')}"
                    )
                    return False
            
            # Cancel the task
            celery_app.control.revoke(task_id, terminate=True)
            
            # Update metadata
            await self._update_task_status(task_id, TaskStatus.REVOKED)
            
            logger.info(f"Task cancelled: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {e}")
            return False
    
    async def get_user_tasks(
        self,
        user_id: int,
        status: Optional[TaskStatus] = None,
        limit: int = 50
    ) -> List[TaskResult]:
        """Get tasks for a specific user"""
        try:
            tasks = []
            
            # Get task IDs from Redis
            pattern = f"task_metadata:{user_id}:*"
            task_keys = await self.redis_client.keys(pattern)
            
            for key in task_keys[:limit]:
                task_id = key.split(":")[-1]
                task_result = await self.get_task_result(task_id)
                
                if status is None or task_result.status == status:
                    tasks.append(task_result)
            
            return sorted(tasks, key=lambda x: x.started_at or datetime.min, reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to get user tasks for {user_id}: {e}")
            return []
    
    async def cleanup_completed_tasks(self, older_than_hours: int = 24):
        """Clean up completed tasks older than specified hours"""
        try:
            cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
            
            # Get all task metadata keys
            pattern = "task_metadata:*"
            keys = await self.redis_client.keys(pattern)
            
            cleaned = 0
            for key in keys:
                metadata = await self.redis_client.hgetall(key)
                if metadata.get("completed_at"):
                    completed_at = datetime.fromisoformat(metadata["completed_at"])
                    if completed_at < cutoff:
                        await self.redis_client.delete(key)
                        cleaned += 1
            
            logger.info(f"Cleaned up {cleaned} old task records")
            
        except Exception as e:
            logger.error(f"Failed to cleanup tasks: {e}")
    
    def _get_priority_value(self, priority: TaskPriority) -> int:
        """Convert priority enum to numeric value"""
        priority_map = {
            TaskPriority.LOW: 1,
            TaskPriority.NORMAL: 5,
            TaskPriority.HIGH: 8,
            TaskPriority.URGENT: 10
        }
        return priority_map.get(priority, 5)
    
    async def _store_task_metadata(
        self,
        task_id: str,
        task_name: str,
        user_id: Optional[int],
        priority: TaskPriority
    ):
        """Store task metadata in Redis"""
        if not self.redis_client:
            return
        
        try:
            metadata = {
                "task_name": task_name,
                "user_id": user_id or 0,
                "priority": priority.value,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Store with multiple keys for different lookup patterns
            await self.redis_client.hset(f"task_metadata:{task_id}", mapping=metadata)
            
            if user_id:
                await self.redis_client.hset(f"task_metadata:{user_id}:{task_id}", mapping=metadata)
            
            # Set expiration
            await self.redis_client.expire(f"task_metadata:{task_id}", 86400)  # 24 hours
            
        except Exception as e:
            logger.error(f"Failed to store task metadata: {e}")
    
    async def _get_task_metadata(self, task_id: str) -> Dict[str, Any]:
        """Get task metadata from Redis"""
        if not self.redis_client:
            return {}
        
        try:
            metadata = await self.redis_client.hgetall(f"task_metadata:{task_id}")
            return metadata
        except Exception as e:
            logger.error(f"Failed to get task metadata: {e}")
            return {}
    
    async def _update_task_status(self, task_id: str, status: TaskStatus):
        """Update task status in metadata"""
        if not self.redis_client:
            return
        
        try:
            await self.redis_client.hset(
                f"task_metadata:{task_id}",
                "status",
                status.value
            )
            
            if status in [TaskStatus.SUCCESS, TaskStatus.FAILURE, TaskStatus.REVOKED]:
                await self.redis_client.hset(
                    f"task_metadata:{task_id}",
                    "completed_at",
                    datetime.utcnow().isoformat()
                )
                
        except Exception as e:
            logger.error(f"Failed to update task status: {e}")

# Global task manager instance
task_manager = TaskManager()

# Celery signal handlers
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Handle task start"""
    logger.info(f"Task started: {task.name}", extra={"task_id": task_id})

@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
    """Handle task completion"""
    logger.info(f"Task completed: {task.name}", extra={
        "task_id": task_id,
        "state": state
    })

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """Handle task failure"""
    logger.error(f"Task failed: {sender.name}", extra={
        "task_id": task_id,
        "exception": str(exception),
        "traceback": traceback
    })

# Utility functions
async def submit_task(
    task_name: str,
    args: tuple = (),
    kwargs: dict = None,
    priority: TaskPriority = TaskPriority.NORMAL,
    user_id: Optional[int] = None
) -> str:
    """Utility function to submit a task"""
    return await task_manager.submit_task(task_name, args, kwargs, priority, user_id)

async def get_task_result(task_id: str) -> TaskResult:
    """Utility function to get task result"""
    return await task_manager.get_task_result(task_id)

async def cancel_task(task_id: str, user_id: Optional[int] = None) -> bool:
    """Utility function to cancel a task"""
    return await task_manager.cancel_task(task_id, user_id)
