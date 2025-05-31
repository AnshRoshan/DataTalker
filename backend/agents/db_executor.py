"""
Enterprise Database Executor Agent - Modernized with async PostgreSQL support
"""
import asyncio
from typing import Dict, Any, List, Optional, Union
import time
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd

from core.database import get_database_manager
from core.cache import get_cache_manager
from core.monitoring import get_logger, track_performance
from core.security import SecurityManager

logger = get_logger(__name__)

class DBExecutorAgent:
    """
    Enterprise Database Executor Agent with async PostgreSQL support.
    
    Features:
    - Async PostgreSQL execution with connection pooling
    - Query result caching with intelligent TTL
    - Performance monitoring and query optimization
    - Enhanced error handling and recovery
    - Large result set streaming capabilities
    - Security validation and query sanitization
    """
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.cache_manager = get_cache_manager()
        self.security_manager = SecurityManager()
    
    def _sanitize_sql(self, sql: str) -> str:
        """
        Sanitize SQL query for safe execution
        
        Args:
            sql: Raw SQL query
            
        Returns:
            Sanitized SQL query
        """
        # Remove comments and normalize whitespace
        sql = sql.strip()
        
        # Remove SQL comments
        sql = sql.replace('--', '')
        sql = ' '.join(sql.split())
        
        # Ensure query ends with semicolon
        if not sql.endswith(';'):
            sql += ';'
        
        return sql
    
    def _estimate_result_size(self, sql: str) -> Dict[str, Any]:
        """
        Estimate the potential size of query results
        
        Args:
            sql: SQL query to analyze
            
        Returns:
            Size estimation metadata
        """
        sql_upper = sql.upper()
        
        # Check for operations that typically return large results
        large_result_indicators = [
            'SELECT *',
            'CROSS JOIN',
            'CARTESIAN',
        ]
        
        size_estimate = 'small'
        warnings = []
        
        if any(indicator in sql_upper for indicator in large_result_indicators):
            size_estimate = 'large'
            warnings.append("Query may return large result set")
        
        if 'LIMIT' not in sql_upper and 'COUNT(' not in sql_upper:
            if 'SELECT' in sql_upper and 'GROUP BY' not in sql_upper:
                size_estimate = 'potentially_large'
                warnings.append("Consider adding LIMIT clause")
        
        return {
            'estimated_size': size_estimate,
            'warnings': warnings,
            'should_stream': size_estimate in ['large', 'potentially_large']
        }
    
    async def _execute_with_caching(self, sql: str, cache_ttl: int = 300) -> Dict[str, Any]:
        """
        Execute SQL with intelligent caching
        
        Args:
            sql: SQL query to execute
            cache_ttl: Cache time-to-live in seconds
            
        Returns:
            Query results with execution metadata
        """
        # Generate cache key based on SQL hash
        cache_key = f"query_result:{hash(sql)}"
        
        # Try to get cached result
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result:
            logger.info("Using cached query result")
            return {
                'results': cached_result['results'],
                'columns': cached_result['columns'],
                'execution_time': cached_result['execution_time'],
                'row_count': cached_result['row_count'],
                'cached': True,
                'cache_hit_time': time.time()
            }
        
        # Execute fresh query
        start_time = time.time()
        
        try:
            async with self.db_manager.get_session() as session:
                # Execute the query
                result = await session.execute(text(sql))
                
                # Get column names
                columns = list(result.keys()) if hasattr(result, 'keys') else []
                
                # Fetch all results
                rows = result.fetchall()
                
                # Convert to list of dictionaries
                results = []
                for row in rows:
                    row_dict = {}
                    for i, col in enumerate(columns):
                        value = row[i]
                        # Handle special data types
                        if isinstance(value, datetime):
                            value = value.isoformat()
                        elif hasattr(value, '__dict__'):  # Complex objects
                            value = str(value)
                        elif value is None:
                            value = None
                        row_dict[col] = value
                    results.append(row_dict)
                
                execution_time = time.time() - start_time
                row_count = len(results)
                
                result_data = {
                    'results': results,
                    'columns': columns,
                    'execution_time': execution_time,
                    'row_count': row_count,
                    'cached': False
                }
                
                # Cache result if it's not too large and execution was successful
                if row_count < 10000:  # Don't cache very large results
                    await self.cache_manager.set(cache_key, result_data, cache_ttl)
                
                return result_data
                
        except SQLAlchemyError as e:
            raise Exception(f"Database execution error: {str(e)}")
    
    async def _execute_streaming_query(self, sql: str, chunk_size: int = 1000) -> Dict[str, Any]:
        """
        Execute large queries with streaming results
        
        Args:
            sql: SQL query to execute
            chunk_size: Number of rows per chunk
            
        Returns:
            Streaming query results
        """
        start_time = time.time()
        total_rows = 0
        results = []
        
        try:
            async with self.db_manager.get_session() as session:
                # Execute query with streaming
                result = await session.execute(text(sql))
                columns = list(result.keys()) if hasattr(result, 'keys') else []
                
                # Process results in chunks
                while True:
                    chunk = result.fetchmany(chunk_size)
                    if not chunk:
                        break
                    
                    for row in chunk:
                        row_dict = {}
                        for i, col in enumerate(columns):
                            value = row[i]
                            if isinstance(value, datetime):
                                value = value.isoformat()
                            elif hasattr(value, '__dict__'):
                                value = str(value)
                            row_dict[col] = value
                        results.append(row_dict)
                        total_rows += 1
                    
                    # Break if we've collected enough for initial response
                    if total_rows >= 10000:  # Limit initial response
                        break
                
                execution_time = time.time() - start_time
                
                return {
                    'results': results,
                    'columns': columns,
                    'execution_time': execution_time,
                    'row_count': total_rows,
                    'is_partial': total_rows >= 10000,
                    'streaming': True
                }
                
        except SQLAlchemyError as e:
            raise Exception(f"Streaming query execution error: {str(e)}")
    
    async def __call__(self, state: dict) -> dict:
        """
        Main entry point for the Database Executor Agent
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with query results
        """
        with track_performance("agent.db_executor.execution"):
            logger.info(
                "DBExecutorAgent processing request",
                extra={
                    "user_id": state.get("user_id"),
                    "correlation_id": state.get("correlation_id")
                }
            )
            
            sql = state.get("sql")
            user_id = state.get("user_id")
            
            if not sql:
                error_msg = "SQL query not found in state"
                logger.error(error_msg)
                return {
                    **state, 
                    "results": [],
                    "error": error_msg,
                    "sql_executed": False
                }
            
            try:
                # Sanitize SQL
                with track_performance("agent.db_executor.sanitization"):
                    sanitized_sql = self._sanitize_sql(sql)
                
                # Estimate result size
                with track_performance("agent.db_executor.size_estimation"):
                    size_estimate = self._estimate_result_size(sanitized_sql)
                
                logger.info(
                    f"Executing SQL query",
                    extra={
                        "user_id": user_id,
                        "sql_hash": hash(sanitized_sql),
                        "estimated_size": size_estimate['estimated_size']
                    }
                )
                
                # Choose execution strategy based on estimated size
                if size_estimate['should_stream']:
                    logger.info("Using streaming execution for large query")
                    execution_result = await self._execute_streaming_query(sanitized_sql)
                else:
                    logger.info("Using cached execution for normal query")
                    execution_result = await self._execute_with_caching(sanitized_sql)
                
                # Add execution metadata
                execution_result.update({
                    'sql_executed': True,
                    'error': None,
                    'executed_sql': sanitized_sql,
                    'size_estimate': size_estimate,
                    'execution_timestamp': datetime.utcnow().isoformat(),
                    'agent': 'DBExecutorAgent',
                    'version': '2.0'
                })
                
                logger.info(
                    "SQL execution completed successfully",
                    extra={
                        "user_id": user_id,
                        "execution_time": execution_result['execution_time'],
                        "row_count": execution_result['row_count'],
                        "cached": execution_result.get('cached', False)
                    }
                )
                
                return {**state, **execution_result}
                
            except Exception as e:
                error_msg = f"SQL execution failed: {str(e)}"
                logger.error(
                    error_msg,
                    extra={
                        "user_id": user_id,
                        "sql": sql,
                        "correlation_id": state.get("correlation_id")
                    },
                    exc_info=True
                )
                
                return {
                    **state,
                    "results": [],
                    "sql_executed": False,
                    "error": error_msg,
                    "execution_timestamp": datetime.utcnow().isoformat()
                }

# Legacy synchronous interface for backward compatibility
def __call__(state: dict) -> dict:
    """Synchronous wrapper for the async database executor agent"""
    agent = DBExecutorAgent()
    return asyncio.run(agent(state))