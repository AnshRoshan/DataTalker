"""
Enterprise SQL Writer Agent - Modernized with enhanced capabilities
"""
import asyncio
from typing import Dict, Any, Optional, List
import re
from datetime import datetime

from core.cache import get_cache_manager
from core.monitoring import get_logger, track_performance
from core.security import SecurityManager

# Import the existing LLM functionality
from llm.gemini import generate_sql_or_response_with_gemini

logger = get_logger(__name__)

class SQLWriterAgent:
    """
    Enterprise SQL Writer Agent with enhanced security and optimization features.
    
    Features:
    - Advanced SQL generation with security validation
    - Query optimization hints and suggestions
    - Caching of generated SQL patterns
    - Role-based query restrictions
    - Performance monitoring and logging
    """
    
    def __init__(self):
        self.cache_manager = get_cache_manager()
        self.security_manager = SecurityManager()
    
    def _analyze_query_complexity(self, question: str) -> Dict[str, Any]:
        """
        Analyze the complexity of the user's question to optimize SQL generation
        
        Args:
            question: Natural language question
            
        Returns:
            Analysis results including complexity level and required features
        """
        complexity_indicators = {
            'joins': ['join', 'combine', 'merge', 'relate', 'link'],
            'aggregations': ['sum', 'count', 'average', 'avg', 'total', 'maximum', 'minimum', 'max', 'min'],
            'time_series': ['trend', 'over time', 'monthly', 'daily', 'yearly', 'period', 'date'],
            'grouping': ['group by', 'grouped', 'category', 'type', 'each'],
            'filtering': ['where', 'filter', 'only', 'exclude', 'greater than', 'less than', 'between'],
            'sorting': ['order', 'sort', 'highest', 'lowest', 'top', 'bottom', 'rank'],
            'advanced': ['window', 'cte', 'recursive', 'pivot', 'unpivot', 'lateral']
        }
        
        question_lower = question.lower()
        detected_features = {}
        complexity_score = 0
        
        for feature, keywords in complexity_indicators.items():
            feature_count = sum(1 for keyword in keywords if keyword in question_lower)
            if feature_count > 0:
                detected_features[feature] = feature_count
                complexity_score += feature_count * (2 if feature == 'advanced' else 1)
        
        complexity_level = 'simple'
        if complexity_score > 5:
            complexity_level = 'complex'
        elif complexity_score > 2:
            complexity_level = 'moderate'
        
        return {
            'complexity_level': complexity_level,
            'complexity_score': complexity_score,
            'detected_features': detected_features,
            'requires_optimization': complexity_score > 3
        }
    
    def _validate_sql_security(self, sql: str, user_role: str = 'VIEWER') -> Dict[str, Any]:
        """
        Validate SQL for security issues and role-based restrictions
        
        Args:
            sql: Generated SQL query
            user_role: User's role (ADMIN, ANALYST, VIEWER)
            
        Returns:
            Validation results with security assessment
        """
        validation_result = {
            'is_valid': True,
            'warnings': [],
            'errors': [],
            'blocked_operations': []
        }
        
        sql_upper = sql.upper()
        
        # Check for dangerous operations
        dangerous_operations = {
            'DROP': 'Table/database deletion',
            'DELETE': 'Data deletion',
            'UPDATE': 'Data modification',
            'INSERT': 'Data insertion',
            'CREATE': 'Table/object creation',
            'ALTER': 'Schema modification',
            'TRUNCATE': 'Table truncation',
            'GRANT': 'Permission modification',
            'REVOKE': 'Permission modification'
        }
        
        for operation, description in dangerous_operations.items():
            if operation in sql_upper:
                if user_role == 'VIEWER':
                    validation_result['errors'].append(
                        f"Operation '{operation}' not allowed for VIEWER role: {description}"
                    )
                    validation_result['blocked_operations'].append(operation)
                    validation_result['is_valid'] = False
                elif user_role == 'ANALYST' and operation in ['DROP', 'CREATE', 'ALTER', 'GRANT', 'REVOKE']:
                    validation_result['errors'].append(
                        f"Operation '{operation}' requires ADMIN role: {description}"
                    )
                    validation_result['blocked_operations'].append(operation)
                    validation_result['is_valid'] = False
                else:
                    validation_result['warnings'].append(
                        f"Potentially dangerous operation detected: {operation} - {description}"
                    )
        
        # Check for potential injection patterns
        injection_patterns = [
            r"(\bOR\b.*=.*|\bAND\b.*=.*)\s*--",  # Comment injection
            r"UNION\s+SELECT",  # Union injection
            r";\s*(DROP|DELETE|UPDATE)",  # Statement chaining
            r"EXEC\s*\(",  # Stored procedure execution
            r"sp_\w+",  # System stored procedures
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, sql_upper):
                validation_result['warnings'].append(
                    f"Potential SQL injection pattern detected: {pattern}"
                )
        
        # Performance warnings
        if 'SELECT *' in sql_upper:
            validation_result['warnings'].append(
                "Consider selecting specific columns instead of using SELECT *"
            )
        
        if not re.search(r'\bLIMIT\b|\bTOP\b', sql_upper) and 'COUNT' not in sql_upper:
            validation_result['warnings'].append(
                "Consider adding LIMIT clause for large result sets"
            )
        
        return validation_result
    
    def _optimize_sql_query(self, sql: str, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Provide optimization suggestions for the generated SQL
        
        Args:
            sql: Generated SQL query
            schema_info: Database schema information
            
        Returns:
            Optimization suggestions and improved query
        """
        suggestions = []
        optimized_sql = sql
        
        # Check for missing indexes
        table_pattern = r'FROM\s+(\w+)|JOIN\s+(\w+)'
        tables = re.findall(table_pattern, sql, re.IGNORECASE)
        tables = [table[0] or table[1] for table in tables]
        
        for table in tables:
            if table in schema_info:
                table_info = schema_info[table]
                if isinstance(table_info, list) and len(table_info) > 0:
                    # Check if WHERE clause uses non-indexed columns
                    where_pattern = r'WHERE\s+.*?(\w+)\s*[=<>]'
                    where_columns = re.findall(where_pattern, sql, re.IGNORECASE)
                    
                    for col in where_columns:
                        suggestions.append(
                            f"Consider adding an index on {table}.{col} for better performance"
                        )
        
        # Suggest query optimizations
        if 'ORDER BY' in sql.upper() and 'LIMIT' not in sql.upper():
            suggestions.append("Consider adding LIMIT clause when using ORDER BY")
        
        if sql.upper().count('JOIN') > 3:
            suggestions.append("Complex joins detected - consider breaking into smaller queries")
        
        # Check for N+1 query patterns
        if 'SELECT' in sql.upper() and 'IN (' in sql.upper():
            suggestions.append("Consider using JOIN instead of IN clause for better performance")
        
        return {
            'original_sql': sql,
            'optimized_sql': optimized_sql,
            'suggestions': suggestions,
            'estimated_performance': 'good' if len(suggestions) < 2 else 'needs_optimization'
        }
    
    async def _get_cached_sql(self, question: str, schema_hash: str) -> Optional[str]:
        """Get cached SQL for similar questions"""
        cache_key = f"sql_generation:{hash(question + schema_hash)}"
        return await self.cache_manager.get(cache_key)
    
    async def _cache_sql(self, question: str, schema_hash: str, sql: str, ttl: int = 3600):
        """Cache generated SQL for reuse"""
        cache_key = f"sql_generation:{hash(question + schema_hash)}"
        await self.cache_manager.set(cache_key, sql, ttl)
    
    async def __call__(self, state: dict) -> dict:
        """
        Main entry point for the SQL Writer Agent
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with SQL query or direct response
        """
        with track_performance("agent.sql_writer.execution"):
            logger.info(
                "SQLWriterAgent processing request",
                extra={
                    "user_id": state.get("user_id"),
                    "correlation_id": state.get("correlation_id")
                }
            )
            
            question = state.get("question", "")
            schema_info = state.get("schema_description") or state.get("schema", "")
            user_role = state.get("user_role", "VIEWER")
            
            if not question:
                return {
                    **state, 
                    "results": "No question provided for SQL generation.", 
                    "sql_needed": False,
                    "error": "Missing question"
                }
            
            if not schema_info:
                return {
                    **state, 
                    "results": "No database schema information available.", 
                    "sql_needed": False,
                    "error": "Missing schema"
                }
            
            try:
                # Analyze query complexity
                with track_performance("agent.sql_writer.complexity_analysis"):
                    complexity_analysis = self._analyze_query_complexity(question)
                
                # Check for cached SQL
                schema_hash = str(hash(str(schema_info)))
                cached_sql = await self._get_cached_sql(question, schema_hash)
                
                if cached_sql:
                    logger.info("Using cached SQL generation")
                    
                    return {
                        **state,
                        "sql": cached_sql,
                        "sql_needed": True,
                        "cache_hit": True,
                        "complexity_analysis": complexity_analysis
                    }
                
                # Generate SQL using existing LLM functionality
                with track_performance("agent.sql_writer.llm_generation"):
                    result = generate_sql_or_response_with_gemini(schema_info, question)
                
                if "sql" in result:
                    sql = result["sql"]
                    
                    # Validate SQL security
                    with track_performance("agent.sql_writer.security_validation"):
                        security_validation = self._validate_sql_security(sql, user_role)
                    
                    if not security_validation['is_valid']:
                        error_msg = "SQL query blocked by security validation: " + "; ".join(security_validation['errors'])
                        logger.warning(
                            error_msg,
                            extra={
                                "user_id": state.get("user_id"),
                                "user_role": user_role,
                                "blocked_operations": security_validation['blocked_operations']
                            }
                        )
                        
                        return {
                            **state,
                            "results": error_msg,
                            "sql_needed": False,
                            "error": "Security validation failed",
                            "security_validation": security_validation
                        }
                    
                    # Optimize SQL query
                    with track_performance("agent.sql_writer.optimization"):
                        optimization_result = self._optimize_sql_query(sql, state.get("schema", {}))
                    
                    # Cache the SQL for future use
                    await self._cache_sql(question, schema_hash, sql)
                    
                    logger.info(
                        "SQL generation completed successfully",
                        extra={
                            "user_id": state.get("user_id"),
                            "complexity_level": complexity_analysis['complexity_level'],
                            "optimization_suggestions": len(optimization_result['suggestions']),
                            "security_warnings": len(security_validation['warnings'])
                        }
                    )
                    
                    return {
                        **state,
                        "sql": sql,
                        "sql_needed": True,
                        "cache_hit": False,
                        "complexity_analysis": complexity_analysis,
                        "security_validation": security_validation,
                        "optimization_result": optimization_result,
                        "metadata": {
                            "generated_at": datetime.utcnow().isoformat(),
                            "agent": "SQLWriterAgent",
                            "version": "2.0"
                        }
                    }
                else:
                    # Direct response without SQL
                    response = result.get("response", "Unable to generate appropriate response.")
                    
                    logger.info(
                        "Generated direct response without SQL",
                        extra={
                            "user_id": state.get("user_id"),
                            "complexity_level": complexity_analysis['complexity_level']
                        }
                    )
                    
                    return {
                        **state,
                        "results": response,
                        "sql_needed": False,
                        "complexity_analysis": complexity_analysis,
                        "metadata": {
                            "generated_at": datetime.utcnow().isoformat(),
                            "agent": "SQLWriterAgent",
                            "version": "2.0"
                        }
                    }
                    
            except Exception as e:
                error_msg = f"SQL generation failed: {str(e)}"
                logger.error(
                    error_msg,
                    extra={
                        "user_id": state.get("user_id"),
                        "correlation_id": state.get("correlation_id")
                    },
                    exc_info=True
                )
                
                return {
                    **state,
                    "results": "I encountered an error while generating the SQL query. Please try rephrasing your question.",
                    "sql_needed": False,
                    "error": error_msg
                }

# Legacy synchronous interface for backward compatibility
def __call__(state: dict) -> dict:
    """Synchronous wrapper for the async SQL writer agent"""
    agent = SQLWriterAgent()
    return asyncio.run(agent(state))
