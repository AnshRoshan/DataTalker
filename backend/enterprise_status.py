"""
Enterprise Status Check and Health Monitoring

Comprehensive status checker for all enterprise components including
database, cache, background tasks, and API endpoints.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, List
import aiohttp
import asyncpg
import redis
import structlog

from core.config import get_settings
from core.database import get_database_manager
from core.cache import get_cache_manager

logger = structlog.get_logger(__name__)

class EnterpriseStatusChecker:
    """Comprehensive status checker for all enterprise components"""
    
    def __init__(self):
        self.settings = get_settings()
        self.status_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_health": "unknown",
            "components": {},
            "performance_metrics": {},
            "summary": {}
        }
    
    async def check_all_components(self) -> Dict[str, Any]:
        """Check the health of all enterprise components"""
        
        print("🔍 TalkToData Enterprise Health Check")
        print("=" * 50)
        
        # Check individual components
        await self._check_database()
        await self._check_cache()
        await self._check_api()
        await self._check_background_tasks()
        await self._check_file_system()
        await self._gather_performance_metrics()
        
        # Calculate overall health
        self._calculate_overall_health()
        
        # Generate summary
        self._generate_summary()
        
        return self.status_data
    
    async def _check_database(self):
        """Check PostgreSQL database connectivity and performance"""
        print("📊 Checking Database...")
        
        component_status = {
            "name": "PostgreSQL Database",
            "status": "unknown",
            "details": {},
            "metrics": {},
            "errors": []
        }
        
        try:
            db_manager = get_database_manager()
            
            # Test connection
            start_time = time.time()
            await db_manager.connect()
            connection_time = (time.time() - start_time) * 1000
            
            # Test query performance
            start_time = time.time()
            async with db_manager.get_connection() as conn:
                result = await conn.fetchval("SELECT 1")
                query_time = (time.time() - start_time) * 1000
                
                # Get database info
                db_version = await conn.fetchval("SELECT version()")
                db_size = await conn.fetchval(
                    "SELECT pg_size_pretty(pg_database_size(current_database()))"
                )
                connection_count = await conn.fetchval(
                    "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
                )
            
            component_status.update({
                "status": "healthy",
                "details": {
                    "version": db_version.split()[1] if db_version else "unknown",
                    "size": db_size,
                    "active_connections": connection_count,
                    "database_name": self.settings.DATABASE_NAME
                },
                "metrics": {
                    "connection_time_ms": round(connection_time, 2),
                    "query_time_ms": round(query_time, 2)
                }
            })
            
            print(f"  ✅ Database is healthy (connection: {connection_time:.1f}ms)")
            
        except Exception as e:
            component_status.update({
                "status": "unhealthy",
                "errors": [str(e)]
            })
            print(f"  ❌ Database check failed: {str(e)}")
        
        self.status_data["components"]["database"] = component_status
    
    async def _check_cache(self):
        """Check Redis cache connectivity and performance"""
        print("💾 Checking Cache...")
        
        component_status = {
            "name": "Redis Cache",
            "status": "unknown",
            "details": {},
            "metrics": {},
            "errors": []
        }
        
        try:
            cache_manager = get_cache_manager()
            
            # Test connection and performance
            start_time = time.time()
            await cache_manager.redis.ping()
            ping_time = (time.time() - start_time) * 1000
            
            # Test cache operations
            test_key = "health_check_test"
            start_time = time.time()
            await cache_manager.redis.set(test_key, "test_value", ex=60)
            set_time = (time.time() - start_time) * 1000
            
            start_time = time.time()
            value = await cache_manager.redis.get(test_key)
            get_time = (time.time() - start_time) * 1000
            
            await cache_manager.redis.delete(test_key)
            
            # Get Redis info
            redis_info = await cache_manager.redis.info()
            
            component_status.update({
                "status": "healthy",
                "details": {
                    "version": redis_info.get("redis_version", "unknown"),
                    "memory_used": redis_info.get("used_memory_human", "unknown"),
                    "connected_clients": redis_info.get("connected_clients", 0),
                    "total_commands": redis_info.get("total_commands_processed", 0)
                },
                "metrics": {
                    "ping_time_ms": round(ping_time, 2),
                    "set_time_ms": round(set_time, 2),
                    "get_time_ms": round(get_time, 2)
                }
            })
            
            print(f"  ✅ Cache is healthy (ping: {ping_time:.1f}ms)")
            
        except Exception as e:
            component_status.update({
                "status": "unhealthy",
                "errors": [str(e)]
            })
            print(f"  ❌ Cache check failed: {str(e)}")
        
        self.status_data["components"]["cache"] = component_status
    
    async def _check_api(self):
        """Check API endpoints and response times"""
        print("🌐 Checking API...")
        
        component_status = {
            "name": "FastAPI Application",
            "status": "unknown",
            "details": {},
            "metrics": {},
            "errors": []
        }
        
        try:
            base_url = f"http://localhost:{self.settings.API_PORT}"
            
            async with aiohttp.ClientSession() as session:
                # Check health endpoint
                start_time = time.time()
                async with session.get(f"{base_url}/health") as response:
                    health_time = (time.time() - start_time) * 1000
                    health_data = await response.json()
                
                # Check docs endpoint
                start_time = time.time()
                async with session.get(f"{base_url}/docs") as response:
                    docs_time = (time.time() - start_time) * 1000
                    docs_status = response.status
            
            component_status.update({
                "status": "healthy" if health_data.get("status") == "healthy" else "degraded",
                "details": {
                    "base_url": base_url,
                    "docs_available": docs_status == 200,
                    "health_data": health_data
                },
                "metrics": {
                    "health_endpoint_ms": round(health_time, 2),
                    "docs_endpoint_ms": round(docs_time, 2)
                }
            })
            
            print(f"  ✅ API is healthy (health: {health_time:.1f}ms)")
            
        except Exception as e:
            component_status.update({
                "status": "unhealthy",
                "errors": [str(e)]
            })
            print(f"  ❌ API check failed: {str(e)}")
        
        self.status_data["components"]["api"] = component_status
    
    async def _check_background_tasks(self):
        """Check Celery background task system"""
        print("⚙️  Checking Background Tasks...")
        
        component_status = {
            "name": "Celery Task Queue",
            "status": "unknown",
            "details": {},
            "metrics": {},
            "errors": []
        }
        
        try:
            # Try to connect to Celery broker (Redis)
            redis_client = redis.from_url(self.settings.CELERY_BROKER_URL)
            broker_info = redis_client.info()
            
            component_status.update({
                "status": "healthy",
                "details": {
                    "broker": "Redis",
                    "broker_version": broker_info.get("redis_version", "unknown"),
                    "result_backend": "Redis"
                },
                "metrics": {
                    "broker_memory": broker_info.get("used_memory_human", "unknown")
                }
            })
            
            print(f"  ✅ Task queue is healthy")
            
        except Exception as e:
            component_status.update({
                "status": "unhealthy",
                "errors": [str(e)]
            })
            print(f"  ❌ Task queue check failed: {str(e)}")
        
        self.status_data["components"]["background_tasks"] = component_status
    
    async def _check_file_system(self):
        """Check file system and required directories"""
        print("📁 Checking File System...")
        
        import os
        import shutil
        
        component_status = {
            "name": "File System",
            "status": "unknown",
            "details": {},
            "metrics": {},
            "errors": []
        }
        
        try:
            # Check disk space
            disk_usage = shutil.disk_usage(".")
            free_space_gb = disk_usage.free / (1024**3)
            total_space_gb = disk_usage.total / (1024**3)
            
            # Check required directories
            required_dirs = ["logs", "backups", "tests", "core", "agents"]
            missing_dirs = [d for d in required_dirs if not os.path.exists(d)]
            
            component_status.update({
                "status": "healthy" if not missing_dirs and free_space_gb > 1 else "warning",
                "details": {
                    "free_space_gb": round(free_space_gb, 2),
                    "total_space_gb": round(total_space_gb, 2),
                    "missing_directories": missing_dirs
                },
                "metrics": {
                    "disk_usage_percent": round((1 - disk_usage.free / disk_usage.total) * 100, 1)
                }
            })
            
            if missing_dirs:
                component_status["errors"].append(f"Missing directories: {', '.join(missing_dirs)}")
            
            print(f"  ✅ File system is healthy ({free_space_gb:.1f}GB free)")
            
        except Exception as e:
            component_status.update({
                "status": "unhealthy",
                "errors": [str(e)]
            })
            print(f"  ❌ File system check failed: {str(e)}")
        
        self.status_data["components"]["file_system"] = component_status
    
    async def _gather_performance_metrics(self):
        """Gather overall performance metrics"""
        print("📈 Gathering Performance Metrics...")
        
        try:
            import psutil
            
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            self.status_data["performance_metrics"] = {
                "cpu_usage_percent": cpu_percent,
                "memory_usage_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            print(f"  📊 CPU: {cpu_percent}%, Memory: {memory.percent}%")
            
        except ImportError:
            print("  ⚠️  psutil not available - skipping system metrics")
        except Exception as e:
            print(f"  ❌ Performance metrics failed: {str(e)}")
    
    def _calculate_overall_health(self):
        """Calculate overall system health based on component statuses"""
        component_statuses = [
            comp["status"] for comp in self.status_data["components"].values()
        ]
        
        if all(status == "healthy" for status in component_statuses):
            self.status_data["overall_health"] = "healthy"
        elif any(status == "unhealthy" for status in component_statuses):
            self.status_data["overall_health"] = "unhealthy"
        else:
            self.status_data["overall_health"] = "degraded"
    
    def _generate_summary(self):
        """Generate a summary of the health check"""
        components = self.status_data["components"]
        
        healthy_count = sum(1 for comp in components.values() if comp["status"] == "healthy")
        total_count = len(components)
        
        self.status_data["summary"] = {
            "healthy_components": healthy_count,
            "total_components": total_count,
            "health_percentage": round((healthy_count / total_count) * 100, 1) if total_count > 0 else 0,
            "status_emoji": "✅" if self.status_data["overall_health"] == "healthy" else 
                           "⚠️" if self.status_data["overall_health"] == "degraded" else "❌"
        }
    
    def print_summary(self):
        """Print a formatted summary of the health check"""
        summary = self.status_data["summary"]
        overall_health = self.status_data["overall_health"]
        
        print("\n" + "=" * 50)
        print(f"🏥 Enterprise Health Summary {summary['status_emoji']}")
        print("=" * 50)
        print(f"Overall Status: {overall_health.upper()}")
        print(f"Components: {summary['healthy_components']}/{summary['total_components']} healthy ({summary['health_percentage']}%)")
        
        # Component details
        for name, component in self.status_data["components"].items():
            status_emoji = "✅" if component["status"] == "healthy" else "⚠️" if component["status"] == "warning" else "❌"
            print(f"  {status_emoji} {component['name']}: {component['status']}")
        
        # Performance metrics
        if self.status_data["performance_metrics"]:
            metrics = self.status_data["performance_metrics"]
            print(f"\n📊 Performance:")
            print(f"  CPU Usage: {metrics.get('cpu_usage_percent', 'N/A')}%")
            print(f"  Memory Usage: {metrics.get('memory_usage_percent', 'N/A')}%")
        
        print(f"\n🕒 Check completed at: {self.status_data['timestamp']}")
        print("=" * 50)


async def main():
    """Main function to run the enterprise status check"""
    checker = EnterpriseStatusChecker()
    
    try:
        status_data = await checker.check_all_components()
        checker.print_summary()
        
        # Optionally save to file
        with open(f"health_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "w") as f:
            json.dump(status_data, f, indent=2)
        
        return status_data
        
    except Exception as e:
        print(f"\n❌ Health check failed: {str(e)}")
        return {"overall_health": "unhealthy", "error": str(e)}


if __name__ == "__main__":
    # Run the status check
    asyncio.run(main())
