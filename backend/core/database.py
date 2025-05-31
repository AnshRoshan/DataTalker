"""
Enterprise Database Layer with PostgreSQL Support
Async connection pooling, query optimization, and monitoring
"""

import asyncio
import asyncpg
import logging
from typing import Dict, List, Any, Optional, Tuple
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json

from core.config import settings
from core.monitoring import get_logger, track_performance
from core.cache import CacheManager


logger = get_logger(__name__)


@dataclass
class QueryResult:
    """Structured query result with metadata"""
    data: List[Dict[str, Any]]
    columns: List[str]
    row_count: int
    execution_time: float
    cached: bool = False
    query_hash: str = ""


@dataclass
class SchemaInfo:
    """Enhanced schema information"""
    tables: Dict[str, Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    indexes: Dict[str, List[str]]
    statistics: Dict[str, Any]
    last_updated: datetime


class DatabaseConnectionPool:
    """Async PostgreSQL connection pool manager"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.cache_manager = CacheManager()
        
    async def initialize(self) -> None:
        """Initialize connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                host=settings.database.DB_HOST,
                port=settings.database.DB_PORT,
                user=settings.database.DB_USER,
                password=settings.database.DB_PASSWORD,
                database=settings.database.DB_NAME,
                min_size=settings.database.DB_POOL_SIZE // 2,
                max_size=settings.database.DB_POOL_SIZE,
                max_queries=50000,
                max_inactive_connection_lifetime=300,
                command_timeout=settings.database.MAX_QUERY_TIMEOUT
            )
            logger.info("Database connection pool initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
    
    async def close(self) -> None:
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as connection:
            try:
                yield connection
            except Exception as e:
                logger.error(f"Database connection error: {e}")
                raise
    
    async def health_check(self) -> bool:
        """Check database health"""
        try:
            async with self.get_connection() as conn:
                await conn.fetchval("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


class QueryOptimizer:
    """Query optimization and analysis"""
    
    @staticmethod
    def analyze_query(query: str) -> Dict[str, Any]:
        """Analyze query for optimization opportunities"""
        query_lower = query.lower().strip()
        
        analysis = {
            "type": "unknown",
            "tables": [],
            "has_joins": False,
            "has_aggregation": False,
            "has_subquery": False,
            "estimated_complexity": "low",
            "optimization_suggestions": []
        }
        
        # Detect query type
        if query_lower.startswith("select"):
            analysis["type"] = "select"
        elif query_lower.startswith("insert"):
            analysis["type"] = "insert"
        elif query_lower.startswith("update"):
            analysis["type"] = "update"
        elif query_lower.startswith("delete"):
            analysis["type"] = "delete"
        
        # Analyze complexity indicators
        if "join" in query_lower:
            analysis["has_joins"] = True
            analysis["estimated_complexity"] = "medium"
        
        if any(agg in query_lower for agg in ["count(", "sum(", "avg(", "max(", "min(", "group by"]):
            analysis["has_aggregation"] = True
            analysis["estimated_complexity"] = "medium"
        
        if "select" in query_lower and query_lower.count("select") > 1:
            analysis["has_subquery"] = True
            analysis["estimated_complexity"] = "high"
        
        # Add optimization suggestions
        if "select *" in query_lower:
            analysis["optimization_suggestions"].append(
                "Consider selecting specific columns instead of SELECT *"
            )
        
        if "limit" not in query_lower and analysis["type"] == "select":
            analysis["optimization_suggestions"].append(
                "Consider adding LIMIT clause for large result sets"
            )
        
        return analysis
    
    @staticmethod
    def generate_query_hash(query: str, params: Optional[Tuple] = None) -> str:
        """Generate hash for query caching"""
        query_normalized = " ".join(query.split())  # Normalize whitespace
        content = f"{query_normalized}:{params}" if params else query_normalized
        return hashlib.md5(content.encode()).hexdigest()


class DatabaseManager:
    """Enterprise database manager with caching and optimization"""
    
    def __init__(self):
        self.pool = DatabaseConnectionPool()
        self.cache_manager = CacheManager()
        self.optimizer = QueryOptimizer()
        
    async def initialize(self) -> None:
        """Initialize database manager"""
        await self.pool.initialize()
        logger.info("Database manager initialized")
    
    async def close(self) -> None:
        """Close database manager"""
        await self.pool.close()
        logger.info("Database manager closed")
    
    @track_performance("database_query")
    async def execute_query(
        self,
        query: str,
        params: Optional[Tuple] = None,
        use_cache: bool = True
    ) -> QueryResult:
        """Execute optimized database query with caching"""
        
        start_time = asyncio.get_event_loop().time()
        query_hash = self.optimizer.generate_query_hash(query, params)
        
        # Try cache first
        if use_cache and settings.app.ENABLE_CACHING:
            cached_result = await self.cache_manager.get_query_result(query_hash)
            if cached_result:
                logger.info(f"Query cache hit: {query_hash[:8]}")
                return QueryResult(
                    data=cached_result["data"],
                    columns=cached_result["columns"],
                    row_count=cached_result["row_count"],
                    execution_time=cached_result["execution_time"],
                    cached=True,
                    query_hash=query_hash
                )
        
        # Analyze query
        analysis = self.optimizer.analyze_query(query)
        logger.info(f"Executing {analysis['type']} query with {analysis['estimated_complexity']} complexity")
        
        # Execute query
        try:
            async with self.pool.get_connection() as conn:
                if params:
                    rows = await conn.fetch(query, *params)
                else:
                    rows = await conn.fetch(query)
                
                # Convert to dict format
                data = [dict(row) for row in rows]
                columns = list(rows[0].keys()) if rows else []
                row_count = len(data)
                
                execution_time = asyncio.get_event_loop().time() - start_time
                
                result = QueryResult(
                    data=data,
                    columns=columns,
                    row_count=row_count,
                    execution_time=execution_time,
                    cached=False,
                    query_hash=query_hash
                )
                
                # Cache result if appropriate
                if use_cache and settings.app.ENABLE_CACHING and analysis["type"] == "select":
                    await self.cache_manager.set_query_result(
                        query_hash,
                        {
                            "data": data,
                            "columns": columns,
                            "row_count": row_count,
                            "execution_time": execution_time
                        }
                    )
                
                logger.info(f"Query executed successfully: {row_count} rows in {execution_time:.3f}s")
                return result
                
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise
    
    @track_performance("schema_extraction")
    async def get_schema_info(self, use_cache: bool = True) -> SchemaInfo:
        """Extract comprehensive schema information with caching"""
        
        cache_key = "database_schema"
        
        # Try cache first
        if use_cache and settings.app.ENABLE_CACHING:
            cached_schema = await self.cache_manager.get_schema(cache_key)
            if cached_schema:
                logger.info("Schema cache hit")
                return SchemaInfo(**cached_schema)
        
        logger.info("Extracting database schema")
        
        async with self.pool.get_connection() as conn:
            # Get tables and columns
            tables_query = """
                SELECT 
                    t.table_name,
                    t.table_type,
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.column_default,
                    tc.constraint_type,
                    pg_stat.n_tup_ins + pg_stat.n_tup_upd + pg_stat.n_tup_del as total_operations,
                    pg_stat.n_live_tup as estimated_rows
                FROM information_schema.tables t
                LEFT JOIN information_schema.columns c ON t.table_name = c.table_name
                LEFT JOIN information_schema.table_constraints tc ON t.table_name = tc.table_name 
                    AND c.column_name = ANY(
                        SELECT kcu.column_name 
                        FROM information_schema.key_column_usage kcu 
                        WHERE kcu.table_name = tc.table_name 
                        AND kcu.constraint_name = tc.constraint_name
                    )
                LEFT JOIN pg_stat_user_tables pg_stat ON t.table_name = pg_stat.relname
                WHERE t.table_schema = 'public'
                ORDER BY t.table_name, c.ordinal_position;
            """
            
            table_rows = await conn.fetch(tables_query)
            
            # Get foreign key relationships
            fk_query = """
                SELECT
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name,
                    tc.constraint_name
                FROM information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = 'public';
            """
            
            fk_rows = await conn.fetch(fk_query)
            
            # Get indexes
            index_query = """
                SELECT 
                    t.relname as table_name,
                    i.relname as index_name,
                    array_agg(a.attname ORDER BY c.ordinality) as columns
                FROM pg_index x
                JOIN pg_class i ON i.oid = x.indexrelid
                JOIN pg_class t ON t.oid = x.indrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace,
                     unnest(x.indkey) WITH ORDINALITY AS c(colnum, ordinality)
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = c.colnum
                WHERE n.nspname = 'public'
                GROUP BY t.relname, i.relname;
            """
            
            index_rows = await conn.fetch(index_query)
        
        # Process schema information
        tables = {}
        for row in table_rows:
            table_name = row['table_name']
            if table_name not in tables:
                tables[table_name] = {
                    'table_type': row['table_type'],
                    'columns': {},
                    'estimated_rows': row['estimated_rows'] or 0,
                    'total_operations': row['total_operations'] or 0
                }
            
            if row['column_name']:
                tables[table_name]['columns'][row['column_name']] = {
                    'data_type': row['data_type'],
                    'is_nullable': row['is_nullable'] == 'YES',
                    'column_default': row['column_default'],
                    'constraint_type': row['constraint_type']
                }
        
        # Process relationships
        relationships = []
        for row in fk_rows:
            relationships.append({
                'table': row['table_name'],
                'column': row['column_name'],
                'foreign_table': row['foreign_table_name'],
                'foreign_column': row['foreign_column_name'],
                'constraint_name': row['constraint_name']
            })
        
        # Process indexes
        indexes = {}
        for row in index_rows:
            table_name = row['table_name']
            if table_name not in indexes:
                indexes[table_name] = []
            indexes[table_name].append({
                'name': row['index_name'],
                'columns': row['columns']
            })
        
        # Calculate statistics
        statistics = {
            'total_tables': len(tables),
            'total_relationships': len(relationships),
            'total_indexes': sum(len(idx_list) for idx_list in indexes.values()),
            'estimated_total_rows': sum(table['estimated_rows'] for table in tables.values())
        }
        
        schema_info = SchemaInfo(
            tables=tables,
            relationships=relationships,
            indexes=indexes,
            statistics=statistics,
            last_updated=datetime.utcnow()
        )
        
        # Cache schema information
        if use_cache and settings.app.ENABLE_CACHING:
            await self.cache_manager.set_schema(cache_key, {
                'tables': tables,
                'relationships': relationships,
                'indexes': indexes,
                'statistics': statistics,
                'last_updated': schema_info.last_updated.isoformat()
            })
        
        logger.info(f"Schema extracted: {statistics['total_tables']} tables, {statistics['total_relationships']} relationships")
        return schema_info
    
    async def get_query_plan(self, query: str, params: Optional[Tuple] = None) -> Dict[str, Any]:
        """Get query execution plan for optimization"""
        explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
        
        try:
            async with self.pool.get_connection() as conn:
                if params:
                    result = await conn.fetchval(explain_query, *params)
                else:
                    result = await conn.fetchval(explain_query)
                
                return result[0] if result else {}
                
        except Exception as e:
            logger.error(f"Failed to get query plan: {e}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive database health check"""
        health_info = {
            "status": "healthy",
            "connection_pool": {},
            "performance": {},
            "errors": []
        }
        
        try:
            # Check connection pool
            pool_info = {
                "size": self.pool.pool.get_size() if self.pool.pool else 0,
                "max_size": settings.database.DB_POOL_SIZE,
                "idle_connections": self.pool.pool.get_idle_size() if self.pool.pool else 0
            }
            health_info["connection_pool"] = pool_info
            
            # Test query performance
            start_time = asyncio.get_event_loop().time()
            await self.pool.health_check()
            query_time = asyncio.get_event_loop().time() - start_time
            
            health_info["performance"] = {
                "simple_query_time": query_time,
                "status": "good" if query_time < 1.0 else "slow"
            }
            
        except Exception as e:
            health_info["status"] = "unhealthy"
            health_info["errors"].append(str(e))
            logger.error(f"Database health check failed: {e}")
        
        return health_info


# Global database manager instance
db_manager = DatabaseManager()
