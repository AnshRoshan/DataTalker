"""
Enterprise Monitoring and Observability
Structured logging, metrics, and performance tracking
"""

import logging
import time
import json
import asyncio
import sys
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from functools import wraps
from contextvars import ContextVar
from dataclasses import dataclass, asdict
import uuid

from core.config import settings


# Context variables for request tracking
request_id_ctx: ContextVar[str] = ContextVar('request_id', default='')
user_id_ctx: ContextVar[str] = ContextVar('user_id', default='')


@dataclass
class PerformanceMetric:
    """Performance metric data structure"""
    operation: str
    duration: float
    success: bool
    timestamp: datetime
    request_id: str
    metadata: Dict[str, Any]


class StructuredLogger:
    """Enterprise structured logging with correlation IDs"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.setup_logger()
    
    def setup_logger(self):
        """Configure structured logging"""
        
        # Remove existing handlers
        self.logger.handlers.clear()
        
        # Set log level
        log_level = getattr(logging, settings.monitoring.LOG_LEVEL.upper())
        self.logger.setLevel(log_level)
        
        # Create handler
        handler = logging.StreamHandler(sys.stdout)
        
        # Set formatter based on configuration
        if settings.monitoring.LOG_FORMAT == "json":
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s'
            )
        
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # Prevent propagation to root logger
        self.logger.propagate = False
    
    def _add_context(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add context information to log entry"""
        context = {
            'request_id': request_id_ctx.get(''),
            'user_id': user_id_ctx.get(''),
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'talktodata',
            'environment': settings.app.ENVIRONMENT
        }
        
        if extra:
            context.update(extra)
        
        return context
    
    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log debug message with context"""
        self.logger.debug(message, extra=self._add_context(extra))
    
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log info message with context"""
        self.logger.info(message, extra=self._add_context(extra))
    
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log warning message with context"""
        self.logger.warning(message, extra=self._add_context(extra))
    
    def error(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log error message with context"""
        self.logger.error(message, extra=self._add_context(extra))
    
    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log critical message with context"""
        self.logger.critical(message, extra=self._add_context(extra))


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging"""
    
    def format(self, record):
        """Format log record as JSON"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields from context
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'service'):
            log_entry['service'] = record.service
        if hasattr(record, 'environment'):
            log_entry['environment'] = record.environment
        
        # Add any extra fields
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                              'filename', 'module', 'lineno', 'funcName', 'created', 
                              'msecs', 'relativeCreated', 'thread', 'threadName', 
                              'processName', 'process', 'stack_info', 'exc_info', 'exc_text']:
                    log_entry[key] = value
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, default=str)


class PerformanceTracker:
    """Performance tracking and metrics collection"""
    
    def __init__(self):
        self.metrics: Dict[str, list] = {}
        self.request_metrics: Dict[str, list] = {}
    
    def track_operation(self, operation: str, duration: float, success: bool = True, 
                       metadata: Optional[Dict[str, Any]] = None):
        """Track operation performance"""
        
        metric = PerformanceMetric(
            operation=operation,
            duration=duration,
            success=success,
            timestamp=datetime.utcnow(),
            request_id=request_id_ctx.get(''),
            metadata=metadata or {}
        )
        
        if operation not in self.metrics:
            self.metrics[operation] = []
        
        self.metrics[operation].append(metric)
        
        # Keep only last 1000 metrics per operation
        if len(self.metrics[operation]) > 1000:
            self.metrics[operation] = self.metrics[operation][-1000:]
    
    def get_operation_stats(self, operation: str) -> Dict[str, Any]:
        """Get statistics for a specific operation"""
        
        if operation not in self.metrics:
            return {"error": "Operation not found"}
        
        metrics = self.metrics[operation]
        durations = [m.duration for m in metrics]
        successes = [m.success for m in metrics]
        
        if not durations:
            return {"error": "No metrics available"}
        
        return {
            "operation": operation,
            "total_requests": len(durations),
            "success_rate": sum(successes) / len(successes) * 100,
            "avg_duration": sum(durations) / len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "p95_duration": self._percentile(durations, 95),
            "p99_duration": self._percentile(durations, 99),
            "recent_requests": len([m for m in metrics if 
                                  (datetime.utcnow() - m.timestamp).seconds < 300])
        }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all operations"""
        return {
            operation: self.get_operation_stats(operation)
            for operation in self.metrics.keys()
        }
    
    def _percentile(self, data: list, percentile: int) -> float:
        """Calculate percentile"""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]


class RequestTracker:
    """Track individual request performance and context"""
    
    def __init__(self):
        self.active_requests: Dict[str, Dict[str, Any]] = {}
    
    def start_request(self, endpoint: str, method: str = "POST") -> str:
        """Start tracking a new request"""
        request_id = str(uuid.uuid4())
        
        self.active_requests[request_id] = {
            "id": request_id,
            "endpoint": endpoint,
            "method": method,
            "start_time": time.time(),
            "operations": []
        }
        
        # Set context variable
        request_id_ctx.set(request_id)
        
        return request_id
    
    def add_operation(self, request_id: str, operation: str, duration: float, success: bool = True):
        """Add operation to request tracking"""
        if request_id in self.active_requests:
            self.active_requests[request_id]["operations"].append({
                "operation": operation,
                "duration": duration,
                "success": success,
                "timestamp": datetime.utcnow().isoformat()
            })
    
    def finish_request(self, request_id: str, success: bool = True, 
                      response_size: Optional[int] = None) -> Dict[str, Any]:
        """Finish request tracking and return summary"""
        
        if request_id not in self.active_requests:
            return {"error": "Request not found"}
        
        request_data = self.active_requests[request_id]
        total_duration = time.time() - request_data["start_time"]
        
        summary = {
            "request_id": request_id,
            "endpoint": request_data["endpoint"],
            "method": request_data["method"],
            "total_duration": total_duration,
            "success": success,
            "response_size": response_size,
            "operations_count": len(request_data["operations"]),
            "operations": request_data["operations"]
        }
        
        # Clean up
        del self.active_requests[request_id]
        
        return summary


# Global instances
performance_tracker = PerformanceTracker()
request_tracker = RequestTracker()


def get_logger(name: str) -> StructuredLogger:
    """Get structured logger instance"""
    return StructuredLogger(name)


def track_performance(operation: str, include_args: bool = False):
    """Decorator to track function performance"""
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                error = None
                metadata = {}
                
                if include_args:
                    metadata["args_count"] = len(args)
                    metadata["kwargs_keys"] = list(kwargs.keys())
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    error = str(e)
                    raise
                finally:
                    duration = time.time() - start_time
                    
                    if error:
                        metadata["error"] = error
                    
                    performance_tracker.track_operation(
                        operation=operation,
                        duration=duration,
                        success=success,
                        metadata=metadata
                    )
                    
                    # Add to current request if available
                    request_id = request_id_ctx.get('')
                    if request_id:
                        request_tracker.add_operation(request_id, operation, duration, success)
            
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                error = None
                metadata = {}
                
                if include_args:
                    metadata["args_count"] = len(args)
                    metadata["kwargs_keys"] = list(kwargs.keys())
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    error = str(e)
                    raise
                finally:
                    duration = time.time() - start_time
                    
                    if error:
                        metadata["error"] = error
                    
                    performance_tracker.track_operation(
                        operation=operation,
                        duration=duration,
                        success=success,
                        metadata=metadata
                    )
                    
                    # Add to current request if available
                    request_id = request_id_ctx.get('')
                    if request_id:
                        request_tracker.add_operation(request_id, operation, duration, success)
            
            return sync_wrapper
    
    return decorator


class HealthChecker:
    """System health checking and monitoring"""
    
    def __init__(self):
        self.health_checks: Dict[str, Callable] = {}
    
    def register_check(self, name: str, check_func: Callable):
        """Register a health check function"""
        self.health_checks[name] = check_func
    
    async def run_checks(self) -> Dict[str, Any]:
        """Run all registered health checks"""
        results = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {},
            "summary": {
                "total": len(self.health_checks),
                "healthy": 0,
                "unhealthy": 0,
                "degraded": 0
            }
        }
        
        overall_status = "healthy"
        
        for name, check_func in self.health_checks.items():
            try:
                if asyncio.iscoroutinefunction(check_func):
                    check_result = await check_func()
                else:
                    check_result = check_func()
                
                results["checks"][name] = check_result
                
                status = check_result.get("status", "unknown")
                results["summary"][status] = results["summary"].get(status, 0) + 1
                
                if status == "unhealthy":
                    overall_status = "unhealthy"
                elif status == "degraded" and overall_status != "unhealthy":
                    overall_status = "degraded"
                    
            except Exception as e:
                results["checks"][name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                results["summary"]["unhealthy"] += 1
                overall_status = "unhealthy"
        
        results["status"] = overall_status
        return results


# Global health checker
health_checker = HealthChecker()


def setup_monitoring():
    """Initialize monitoring system"""
    logger = get_logger(__name__)
    logger.info("Monitoring system initialized", extra={
        "log_level": settings.monitoring.LOG_LEVEL,
        "log_format": settings.monitoring.LOG_FORMAT,
        "metrics_enabled": settings.monitoring.ENABLE_METRICS
    })
