"""
Enterprise Fallback Agent - Intelligent error handling and recovery
"""
import asyncio
from typing import Dict, Any, List, Optional
import re
from datetime import datetime

from core.cache import get_cache_manager
from core.monitoring import get_logger, track_performance

logger = get_logger(__name__)

class FallbackAgent:
    """
    Enterprise Fallback Agent with intelligent error handling and recovery.
    
    Features:
    - Context-aware error analysis and classification
    - Intelligent suggestion generation based on error type
    - Learning from failed queries to improve responses
    - User-friendly error messages with actionable guidance
    - Escalation paths for complex issues
    """
    
    def __init__(self):
        self.cache_manager = get_cache_manager()
    
    def _classify_error(self, error_msg: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify the type of error to provide targeted assistance
        
        Args:
            error_msg: Error message to analyze
            state: Current workflow state
            
        Returns:
            Error classification with guidance
        """
        error_msg_lower = error_msg.lower()
        
        # Define error patterns and their classifications
        error_patterns = {
            'sql_syntax': {
                'keywords': ['syntax error', 'invalid syntax', 'parse error', 'malformed'],
                'category': 'SQL Syntax Error',
                'severity': 'medium',
                'user_friendly': 'There was an issue with the SQL query structure'
            },
            'permission_denied': {
                'keywords': ['permission denied', 'access denied', 'not allowed', 'unauthorized'],
                'category': 'Access Control',
                'severity': 'high',
                'user_friendly': 'You don\'t have permission to perform this operation'
            },
            'table_not_found': {
                'keywords': ['table does not exist', 'relation does not exist', 'table not found'],
                'category': 'Schema Error',
                'severity': 'medium',
                'user_friendly': 'The requested table or column doesn\'t exist'
            },
            'connection_error': {
                'keywords': ['connection', 'timeout', 'network', 'cannot connect'],
                'category': 'Database Connection',
                'severity': 'high',
                'user_friendly': 'There was a problem connecting to the database'
            },
            'validation_error': {
                'keywords': ['validation', 'blocked', 'unsafe', 'security'],
                'category': 'Security Validation',
                'severity': 'medium',
                'user_friendly': 'The query was blocked for security reasons'
            },
            'data_type_error': {
                'keywords': ['type mismatch', 'cannot convert', 'invalid data type'],
                'category': 'Data Type',
                'severity': 'low',
                'user_friendly': 'There was a data type compatibility issue'
            }
        }
        
        # Classify the error
        classification = {
            'error_type': 'unknown',
            'category': 'General Error',
            'severity': 'medium',
            'user_friendly': 'An unexpected error occurred'
        }
        
        for error_type, pattern_info in error_patterns.items():
            if any(keyword in error_msg_lower for keyword in pattern_info['keywords']):
                classification.update({
                    'error_type': error_type,
                    'category': pattern_info['category'],
                    'severity': pattern_info['severity'],
                    'user_friendly': pattern_info['user_friendly']
                })
                break
        
        # Add context-specific information
        if state.get('sql'):
            classification['has_sql'] = True
            classification['sql_complexity'] = 'complex' if len(state['sql']) > 200 else 'simple'
        
        if state.get('user_role'):
            classification['user_role'] = state['user_role']
        
        return classification
    
    def _generate_suggestions(self, 
                            error_classification: Dict[str, Any], 
                            state: Dict[str, Any]) -> List[str]:
        """
        Generate intelligent suggestions based on error classification
        
        Args:
            error_classification: Error analysis results
            state: Current workflow state
            
        Returns:
            List of actionable suggestions
        """
        suggestions = []
        error_type = error_classification['error_type']
        user_question = state.get('question', '')
        
        # Type-specific suggestions
        if error_type == 'sql_syntax':
            suggestions.extend([
                "Try rephrasing your question in simpler terms",
                "Break down complex requests into smaller parts",
                "Check if all table and column names are spelled correctly"
            ])
        
        elif error_type == 'permission_denied':
            user_role = state.get('user_role', 'VIEWER')
            if user_role == 'VIEWER':
                suggestions.extend([
                    "As a Viewer, you can only read data, not modify it",
                    "Contact your administrator for additional permissions",
                    "Try querying data instead of modifying it"
                ])
            elif user_role == 'ANALYST':
                suggestions.extend([
                    "Some operations require Admin privileges",
                    "Try reading data or creating reports instead",
                    "Contact your administrator for schema modifications"
                ])
        
        elif error_type == 'table_not_found':
            suggestions.extend([
                "Would you like to see a list of available tables?",
                "Check the spelling of table and column names",
                "Try using partial matches or searching for similar names"
            ])
        
        elif error_type == 'connection_error':
            suggestions.extend([
                "Please try again in a moment",
                "The database may be temporarily unavailable",
                "Contact support if the problem persists"
            ])
        
        elif error_type == 'validation_error':
            suggestions.extend([
                "Try using only SELECT statements for data retrieval",
                "Avoid complex SQL constructs that might be flagged",
                "Rephrase your question to focus on data analysis"
            ])
        
        elif error_type == 'data_type_error':
            suggestions.extend([
                "Check that you're comparing compatible data types",
                "Use appropriate date/time formats in your queries",
                "Verify numeric values are in the correct format"
            ])
        
        # General suggestions based on question content
        question_lower = user_question.lower()
        
        if any(word in question_lower for word in ['show', 'list', 'what', 'which']):
            suggestions.append("Try asking for specific information rather than general listings")
        
        if any(word in question_lower for word in ['all', 'everything', 'total']):
            suggestions.append("Consider adding filters to narrow down your search")
        
        # Add context-aware suggestions
        if state.get('schema'):
            suggestions.append("You can ask about available tables and their structure")
        
        return suggestions[:5]  # Limit to 5 most relevant suggestions
    
    def _generate_alternative_queries(self, 
                                    user_question: str, 
                                    error_classification: Dict[str, Any]) -> List[str]:
        """
        Generate alternative query suggestions based on the original question
        
        Args:
            user_question: Original user question
            error_classification: Error analysis results
            
        Returns:
            List of alternative query suggestions
        """
        alternatives = []
        question_lower = user_question.lower()
        
        # Extract key terms from the question
        key_terms = re.findall(r'\b\w+\b', question_lower)
        potential_tables = [term for term in key_terms if len(term) > 3 and term not in ['show', 'give', 'find', 'what', 'where', 'when', 'data']]
        
        # Generate alternatives based on error type
        error_type = error_classification['error_type']
        
        if error_type == 'table_not_found':
            if potential_tables:
                for table in potential_tables[:2]:
                    alternatives.append(f"What tables are similar to '{table}'?")
            alternatives.append("What tables are available in this database?")
            alternatives.append("Show me the database schema")
        
        elif error_type == 'permission_denied':
            if 'update' in question_lower or 'delete' in question_lower or 'insert' in question_lower:
                # Convert modification to read operation
                if potential_tables:
                    alternatives.append(f"Show me data from {potential_tables[0]}")
                alternatives.append("What data can I view in this database?")
            
        elif error_type == 'sql_syntax':
            # Simplify the question
            if 'and' in question_lower:
                parts = user_question.split(' and ')
                if len(parts) > 1:
                    alternatives.append(f"First, let me find: {parts[0].strip()}")
            
            if potential_tables:
                alternatives.append(f"Show me some sample data from {potential_tables[0]}")
        
        # General alternatives
        alternatives.extend([
            "What kind of data is available in this database?",
            "Can you show me some example queries I can try?",
            "Help me understand the database structure"
        ])
        
        return alternatives[:4]  # Limit to 4 alternatives
    
    def _create_recovery_plan(self, 
                            error_classification: Dict[str, Any], 
                            state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a recovery plan with escalation options
        
        Args:
            error_classification: Error analysis results
            state: Current workflow state
            
        Returns:
            Recovery plan with next steps
        """
        severity = error_classification['severity']
        error_type = error_classification['error_type']
        
        recovery_plan = {
            'immediate_actions': [],
            'next_steps': [],
            'escalation_needed': False,
            'escalation_reason': None
        }
        
        if severity == 'high':
            recovery_plan['escalation_needed'] = True
            recovery_plan['escalation_reason'] = f"High severity {error_classification['category']} error"
            recovery_plan['immediate_actions'].append("Please contact support for assistance")
        
        if error_type == 'connection_error':
            recovery_plan['immediate_actions'].extend([
                "Wait a moment and try again",
                "Check if other database operations are working"
            ])
            recovery_plan['next_steps'].append("If problem persists, contact system administrator")
        
        elif error_type == 'permission_denied':
            recovery_plan['immediate_actions'].append("Review your access permissions")
            recovery_plan['next_steps'].extend([
                "Contact your administrator for additional permissions",
                "Try queries that only read data"
            ])
        
        elif error_type in ['table_not_found', 'sql_syntax']:
            recovery_plan['immediate_actions'].append("Review the database schema")
            recovery_plan['next_steps'].extend([
                "Try simpler queries first",
                "Use the schema information to guide your questions"
            ])
        
        return recovery_plan
    
    async def __call__(self, state: dict) -> dict:
        """
        Main entry point for the Fallback Agent
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with intelligent error handling
        """
        with track_performance("agent.fallback.execution"):
            logger.info(
                "FallbackAgent processing error",
                extra={
                    "user_id": state.get("user_id"),
                    "correlation_id": state.get("correlation_id"),
                    "error": state.get("error", "Unknown error")
                }
            )
            
            user_question = state.get("question", "")
            error_msg = state.get("error") or state.get("validation_error", "Unknown error occurred")
            
            try:
                # Classify the error
                with track_performance("agent.fallback.error_classification"):
                    error_classification = self._classify_error(error_msg, state)
                
                # Generate suggestions
                with track_performance("agent.fallback.suggestion_generation"):
                    suggestions = self._generate_suggestions(error_classification, state)
                
                # Generate alternative queries
                with track_performance("agent.fallback.alternative_generation"):
                    alternatives = self._generate_alternative_queries(user_question, error_classification)
                
                # Create recovery plan
                with track_performance("agent.fallback.recovery_planning"):
                    recovery_plan = self._create_recovery_plan(error_classification, state)
                
                # Build user-friendly response
                severity_emoji = {
                    'low': '⚠️',
                    'medium': '🔶',
                    'high': '🚨'
                }
                
                emoji = severity_emoji.get(error_classification['severity'], '⚠️')
                
                response = f"""{emoji} **{error_classification['category']}**

{error_classification['user_friendly']}.

**💡 What you can try:**
{chr(10).join([f"• {suggestion}" for suggestion in suggestions])}

**🔄 Alternative questions:**
{chr(10).join([f"• {alt}" for alt in alternatives])}
"""
                
                if recovery_plan['escalation_needed']:
                    response += f"\n\n🆘 **Support needed:** {recovery_plan['escalation_reason']}"
                
                logger.info(
                    "Fallback response generated",
                    extra={
                        "user_id": state.get("user_id"),
                        "error_type": error_classification['error_type'],
                        "severity": error_classification['severity'],
                        "suggestions_count": len(suggestions),
                        "escalation_needed": recovery_plan['escalation_needed']
                    }
                )
                
                return {
                    **state,
                    "results": response,
                    "sql_executed": False,
                    "error_classification": error_classification,
                    "suggestions": suggestions,
                    "alternatives": alternatives,
                    "recovery_plan": recovery_plan,
                    "follow_up_questions": alternatives,
                    "fallback_metadata": {
                        "agent": "FallbackAgent",
                        "version": "2.0",
                        "processed_at": datetime.utcnow().isoformat(),
                        "error_type": error_classification['error_type']
                    }
                }
                
            except Exception as e:
                logger.error(
                    f"Fallback agent error: {e}",
                    extra={
                        "user_id": state.get("user_id"),
                        "correlation_id": state.get("correlation_id")
                    },
                    exc_info=True
                )
                
                # Ultra-simple fallback
                return {
                    **state,
                    "results": "❌ I encountered an error while processing your request. Please try rephrasing your question or contact support for assistance.",
                    "sql_executed": False,
                    "follow_up_questions": [
                        "Could you try asking your question differently?",
                        "Would you like to see what data is available?",
                        "Should I contact support for help?"
                    ]
                }

# Legacy synchronous interface for backward compatibility
def __call__(state: dict) -> dict:
    """Synchronous wrapper for the async fallback agent"""
    agent = FallbackAgent()
    return asyncio.run(agent(state))
