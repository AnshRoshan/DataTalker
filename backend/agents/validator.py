"""
Enterprise SQL Validator Agent for TalkToData

Provides comprehensive SQL validation, security analysis, and query optimization
recommendations for enterprise database environments.
"""

import re
import asyncio
import hashlib
from typing import Dict, Any, List, Tuple, Optional, Set
from datetime import datetime
from enum import Enum
import structlog

from core.config import settings
from core.cache import cache_manager
from core.monitoring import performance_tracker
from core.security import get_current_user_context

logger = structlog.get_logger(__name__)

class SecurityLevel(Enum):
    """Security levels for SQL validation"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class QueryType(Enum):
    """Types of SQL queries"""
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    DDL = "ddl"
    ADMIN = "admin"
    UNKNOWN = "unknown"

class ValidatorAgent:
    """
    Enterprise SQL validator that provides comprehensive security analysis,
    performance optimization suggestions, and role-based access control.
    """
    
    def __init__(self):
        self.forbidden_patterns = self._load_forbidden_patterns()
        self.dangerous_functions = self._load_dangerous_functions()
        self.performance_patterns = self._load_performance_patterns()
        self.role_permissions = self._load_role_permissions()
    
    def _load_forbidden_patterns(self) -> Dict[SecurityLevel, List[str]]:
        """Load forbidden SQL patterns by security level"""
        return {
            SecurityLevel.CRITICAL: [
                r'\bdrop\s+table\b',
                r'\bdrop\s+database\b',
                r'\btruncate\b',
                r'\bdelete\s+from\s+\w+\s*(?:;|$)',  # DELETE without WHERE
                r'\bupdate\s+\w+\s+set\s+.*(?:;|$)(?!.*where)',  # UPDATE without WHERE
                r'\bexec\b',
                r'\bexecute\b',
                r'\bsp_\w+\b',  # Stored procedures
                r'\bxp_\w+\b',  # Extended procedures
                r'--.*\r?\n',   # SQL comments (potential injection)
                r'/\*.*?\*/',   # Block comments
                r'\bunion\s+select\b',  # UNION-based injection
                r'\bor\s+1\s*=\s*1\b',  # Common injection pattern
                r'\band\s+1\s*=\s*1\b',  # Common injection pattern
            ],
            SecurityLevel.HIGH: [
                r'\bdelete\b',
                r'\bupdate\b',
                r'\binsert\b',
                r'\balter\b',
                r'\bcreate\b',
                r'\bgrant\b',
                r'\brevoke\b',
                r'\bload_file\b',
                r'\binto\s+outfile\b',
                r'\binto\s+dumpfile\b',
            ],
            SecurityLevel.MEDIUM: [
                r'\binformation_schema\b',
                r'\bpg_catalog\b',
                r'\bsys\.\w+\b',
                r'\bmaster\.\w+\b',
                r'\bshow\s+tables\b',
                r'\bshow\s+databases\b',
                r'\bdesc\b',
                r'\bdescribe\b',
            ],
            SecurityLevel.LOW: [
                r'\bselect\s+\*\s+from\s+\w+\s*(?:;|$)(?!.*limit)',  # SELECT * without LIMIT
                r'\bselect\s+.*\s+from\s+\w+\s*(?:;|$)(?!.*limit)(?=.*count\s*\(\s*\*\s*\))',  # Large counts
            ]
        }
    
    def _load_dangerous_functions(self) -> Set[str]:
        """Load list of potentially dangerous SQL functions"""
        return {
            'load_file', 'into_outfile', 'into_dumpfile',
            'system', 'shell', 'exec', 'execute',
            'sp_executesql', 'sp_sqlexec', 'xp_cmdshell',
            'openrowset', 'opendatasource', 'openquery',
            'bulk', 'sqlcmd', 'osql', 'bcp'
        }
    
    def _load_performance_patterns(self) -> Dict[str, str]:
        """Load patterns that may indicate performance issues"""
        return {
            r'\bselect\s+\*\b': "Avoid SELECT * - specify only needed columns",
            r'\bselect\s+.*\s+from\s+\w+\s*(?:;|$)(?!.*limit)': "Consider adding LIMIT for large result sets",
            r'\blike\s+[\'"][%].*[%][\'"]': "Leading wildcard in LIKE may prevent index usage",
            r'\bor\b': "OR conditions may prevent index usage - consider UNION",
            r'\bnot\s+in\b': "NOT IN with NULL values can cause unexpected results",
            r'\bselect\s+.*\s+from\s+\w+\s+where\s+\w+\s*\(\s*\w+\s*\)': "Functions in WHERE clause prevent index usage",
            r'\bgroup\s+by\s+.*\s+having\s+count\s*\(\s*\*\s*\)\s*>\s*\d{3,}': "Large GROUP BY operations may be slow",
        }
    
    def _load_role_permissions(self) -> Dict[str, Dict[str, bool]]:
        """Load role-based permissions"""
        return {
            "admin": {
                "select": True,
                "insert": True,
                "update": True,
                "delete": True,
                "ddl": True,
                "system_tables": True,
                "large_queries": True
            },
            "analyst": {
                "select": True,
                "insert": False,
                "update": False,
                "delete": False,
                "ddl": False,
                "system_tables": True,
                "large_queries": True
            },
            "viewer": {
                "select": True,
                "insert": False,
                "update": False,
                "delete": False,
                "ddl": False,
                "system_tables": False,
                "large_queries": False
            }
        }
    
    async def validate_sql(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for SQL validation
        """
        try:
            correlation_id = state.get("correlation_id", "unknown")
            user_context = state.get("user_context", {})
            
            with performance_tracker.track_operation("sql_validation", correlation_id):
                sql = state.get("sql", "").strip()
                
                if not sql:
                    logger.warning("Empty SQL received for validation", correlation_id=correlation_id)
                    return {
                        **state,
                        "is_safe": False,
                        "validation_status": "failed",
                        "reason": "Empty SQL query",
                        "security_level": SecurityLevel.CRITICAL.value,
                        "errors": ["SQL query cannot be empty"]
                    }
                
                # Check cache first
                cache_key = f"sql_validation:{hashlib.md5(sql.encode()).hexdigest()}:{user_context.get('role', 'viewer')}"
                cached_result = await cache_manager.get_cached_data(cache_key, "sql_validation")
                
                if cached_result:
                    logger.debug("Using cached validation result", correlation_id=correlation_id)
                    return {**state, **cached_result}
                
                # Perform comprehensive validation
                validation_result = await self._comprehensive_validation(sql, user_context, correlation_id)
                
                # Update state with validation results
                updated_state = {
                    **state,
                    **validation_result,
                    "validation_timestamp": datetime.utcnow().isoformat(),
                    "validation_status": "completed"
                }
                
                # Cache the result
                await cache_manager.cache_data(
                    cache_key,
                    validation_result,
                    "sql_validation",
                    ttl=settings.CACHE_SQL_VALIDATION_TTL
                )
                
                logger.info(
                    "SQL validation completed",
                    correlation_id=correlation_id,
                    is_safe=validation_result["is_safe"],
                    security_level=validation_result["security_level"],
                    query_type=validation_result["query_type"],
                    warnings_count=len(validation_result.get("warnings", []))
                )
                
                return updated_state
                
        except Exception as e:
            logger.error(
                "Error during SQL validation",
                correlation_id=correlation_id,
                error=str(e),
                exc_info=True
            )
            return {
                **state,
                "is_safe": False,
                "validation_status": "failed",
                "reason": f"Validation error: {str(e)}",
                "security_level": SecurityLevel.CRITICAL.value,
                "errors": [f"Validation failed: {str(e)}"]
            }
    
    async def _comprehensive_validation(self, sql: str, user_context: Dict, correlation_id: str) -> Dict[str, Any]:
        """Perform comprehensive SQL validation"""
        
        # Initialize validation result
        result = {
            "is_safe": True,
            "reason": "SQL is valid and safe",
            "security_level": SecurityLevel.LOW.value,
            "query_type": QueryType.UNKNOWN.value,
            "errors": [],
            "warnings": [],
            "suggestions": [],
            "performance_hints": [],
            "role_violations": []
        }
        
        # Step 1: Basic security validation
        security_validation = self._validate_security(sql)
        result.update(security_validation)
        
        # Step 2: Query type classification
        query_type = self._classify_query_type(sql)
        result["query_type"] = query_type.value
        
        # Step 3: Role-based validation
        role_validation = self._validate_role_permissions(sql, query_type, user_context)
        if role_validation["violations"]:
            result["is_safe"] = False
            result["role_violations"] = role_validation["violations"]
            result["reason"] = "Role permission violations detected"
        
        # Step 4: Performance analysis
        performance_analysis = self._analyze_performance(sql)
        result["performance_hints"] = performance_analysis["hints"]
        result["warnings"].extend(performance_analysis["warnings"])
        
        # Step 5: Injection detection
        injection_analysis = self._detect_injection_patterns(sql)
        if injection_analysis["suspicious"]:
            result["is_safe"] = False
            result["security_level"] = SecurityLevel.CRITICAL.value
            result["errors"].extend(injection_analysis["patterns"])
            result["reason"] = "Potential SQL injection detected"
        
        # Step 6: Query complexity analysis
        complexity_analysis = self._analyze_complexity(sql)
        result["complexity_score"] = complexity_analysis["score"]
        if complexity_analysis["warnings"]:
            result["warnings"].extend(complexity_analysis["warnings"])
        
        # Step 7: Generate suggestions
        suggestions = self._generate_suggestions(sql, result)
        result["suggestions"] = suggestions
        
        # Final safety determination
        if result["errors"]:
            result["is_safe"] = False
            result["security_level"] = SecurityLevel.CRITICAL.value
        elif result["role_violations"]:
            result["is_safe"] = False
            result["security_level"] = SecurityLevel.HIGH.value
        
        return result
    
    def _validate_security(self, sql: str) -> Dict[str, Any]:
        """Validate SQL against security patterns"""
        sql_lower = sql.lower()
        errors = []
        security_level = SecurityLevel.LOW
        
        # Check against forbidden patterns by security level
        for level, patterns in self.forbidden_patterns.items():
            for pattern in patterns:
                if re.search(pattern, sql_lower, re.IGNORECASE | re.MULTILINE):
                    errors.append(f"Forbidden pattern detected: {pattern}")
                    if level.value in [SecurityLevel.CRITICAL.value, SecurityLevel.HIGH.value]:
                        security_level = level
                    break
        
        # Check dangerous functions
        for func in self.dangerous_functions:
            if func.lower() in sql_lower:
                errors.append(f"Dangerous function detected: {func}")
                security_level = SecurityLevel.CRITICAL
        
        return {
            "security_errors": errors,
            "security_level": security_level.value
        }
    
    def _classify_query_type(self, sql: str) -> QueryType:
        """Classify the type of SQL query"""
        sql_lower = sql.strip().lower()
        
        if sql_lower.startswith('select'):
            return QueryType.SELECT
        elif sql_lower.startswith('insert'):
            return QueryType.INSERT
        elif sql_lower.startswith('update'):
            return QueryType.UPDATE
        elif sql_lower.startswith('delete'):
            return QueryType.DELETE
        elif any(sql_lower.startswith(cmd) for cmd in ['create', 'alter', 'drop', 'truncate']):
            return QueryType.DDL
        elif any(sql_lower.startswith(cmd) for cmd in ['grant', 'revoke', 'show', 'describe', 'explain']):
            return QueryType.ADMIN
        else:
            return QueryType.UNKNOWN
    
    def _validate_role_permissions(self, sql: str, query_type: QueryType, user_context: Dict) -> Dict[str, Any]:
        """Validate query against user role permissions"""
        user_role = user_context.get("role", "viewer")
        permissions = self.role_permissions.get(user_role, self.role_permissions["viewer"])
        violations = []
        
        # Check query type permissions
        if query_type == QueryType.SELECT and not permissions["select"]:
            violations.append("Role does not permit SELECT operations")
        elif query_type == QueryType.INSERT and not permissions["insert"]:
            violations.append("Role does not permit INSERT operations")
        elif query_type == QueryType.UPDATE and not permissions["update"]:
            violations.append("Role does not permit UPDATE operations")
        elif query_type == QueryType.DELETE and not permissions["delete"]:
            violations.append("Role does not permit DELETE operations")
        elif query_type == QueryType.DDL and not permissions["ddl"]:
            violations.append("Role does not permit DDL operations")
        
        # Check system table access
        sql_lower = sql.lower()
        system_tables = ['information_schema', 'pg_catalog', 'sys.', 'master.']
        if not permissions["system_tables"]:
            for table in system_tables:
                if table in sql_lower:
                    violations.append(f"Role does not permit access to system tables: {table}")
        
        # Check large query permissions
        if not permissions["large_queries"]:
            if len(sql) > 1000 or 'select *' in sql_lower:
                violations.append("Role does not permit large or unrestricted queries")
        
        return {"violations": violations}
    
    def _analyze_performance(self, sql: str) -> Dict[str, Any]:
        """Analyze SQL for performance issues"""
        hints = []
        warnings = []
        
        for pattern, hint in self.performance_patterns.items():
            if re.search(pattern, sql, re.IGNORECASE):
                hints.append(hint)
                if "may be slow" in hint.lower() or "prevent index" in hint.lower():
                    warnings.append(f"Performance concern: {hint}")
        
        return {"hints": hints, "warnings": warnings}
    
    def _detect_injection_patterns(self, sql: str) -> Dict[str, Any]:
        """Detect potential SQL injection patterns"""
        suspicious_patterns = [
            r"'\s*or\s*'1'\s*=\s*'1",
            r"'\s*or\s*1\s*=\s*1\s*--",
            r"union\s+select\s+.*\s+from",
            r";\s*drop\s+table",
            r";\s*delete\s+from",
            r"benchmark\s*\(",
            r"sleep\s*\(",
            r"waitfor\s+delay",
            r"pg_sleep\s*\(",
            r"'\s*;\s*exec\s*\(",
            r"'\s*;\s*execute\s*\(",
        ]
        
        detected_patterns = []
        for pattern in suspicious_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                detected_patterns.append(f"Suspicious pattern: {pattern}")
        
        return {
            "suspicious": len(detected_patterns) > 0,
            "patterns": detected_patterns
        }
    
    def _analyze_complexity(self, sql: str) -> Dict[str, Any]:
        """Analyze query complexity"""
        sql_lower = sql.lower()
        score = 0
        warnings = []
        
        # Count joins
        join_count = len(re.findall(r'\bjoin\b', sql_lower))
        score += join_count * 2
        
        # Count subqueries
        subquery_count = sql.count('(') - sql.count(')')
        if subquery_count > 0:
            score += subquery_count * 3
        
        # Count functions
        function_count = len(re.findall(r'\w+\s*\(', sql))
        score += function_count
        
        # Count conditions
        condition_count = len(re.findall(r'\bwhere\b|\band\b|\bor\b', sql_lower))
        score += condition_count
        
        # Generate warnings based on complexity
        if score > 20:
            warnings.append("Very high complexity query - consider optimization")
        elif score > 10:
            warnings.append("High complexity query - may impact performance")
        
        if join_count > 5:
            warnings.append(f"Many joins detected ({join_count}) - consider query redesign")
        
        return {"score": score, "warnings": warnings}
    
    def _generate_suggestions(self, sql: str, validation_result: Dict) -> List[str]:
        """Generate optimization and improvement suggestions"""
        suggestions = []
        
        # Security suggestions
        if validation_result["security_level"] in [SecurityLevel.HIGH.value, SecurityLevel.CRITICAL.value]:
            suggestions.append("Consider using parameterized queries to prevent injection")
        
        # Performance suggestions
        if "SELECT *" in sql.upper():
            suggestions.append("Specify only the columns you need instead of using SELECT *")
        
        if validation_result.get("complexity_score", 0) > 15:
            suggestions.append("Break complex queries into smaller, simpler queries")
        
        # Role-based suggestions
        if validation_result.get("role_violations"):
            suggestions.append("Request elevated permissions or modify query to match your role")
        
        return suggestions
    
    # Synchronous wrapper for backward compatibility
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous wrapper for the async validate_sql method"""
        try:
            # Get or create event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Run the async method
            if loop.is_running():
                # If we're already in an async context, create a task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.validate_sql(state))
                    return future.result()
            else:
                # Run in the current loop
                return loop.run_until_complete(self.validate_sql(state))
                
        except Exception as e:
            logger.error(f"Error in ValidatorAgent: {str(e)}", exc_info=True)
            return {
                **state,
                "is_safe": False,
                "validation_status": "failed",
                "reason": f"Validation failed: {str(e)}",
                "security_level": SecurityLevel.CRITICAL.value,
                "errors": [f"Validation error: {str(e)}"]
            }
