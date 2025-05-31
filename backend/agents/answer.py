"""
Enterprise Answer Formatter Agent - Modernized with enhanced formatting capabilities
"""
import asyncio
from typing import Dict, Any, List, Optional, Union
import json
from datetime import datetime
import pandas as pd

from core.cache import get_cache_manager
from core.monitoring import get_logger, track_performance

# Import the existing LLM functionality
from llm.gemini import format_answer

logger = get_logger(__name__)

class AnswerFormatterAgent:
    """
    Enterprise Answer Formatter Agent with enhanced response capabilities.
    
    Features:
    - Rich response formatting with multiple output formats
    - Intelligent data visualization suggestions
    - Caching of formatted responses
    - Enhanced error handling and user guidance
    - Support for large result sets with pagination
    - Multi-language response formatting
    """
    
    def __init__(self):
        self.cache_manager = get_cache_manager()
    
    def _analyze_result_structure(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze the structure of query results to optimize formatting
        
        Args:
            results: Query results to analyze
            
        Returns:
            Analysis metadata for formatting optimization
        """
        if not results:
            return {
                'result_type': 'empty',
                'row_count': 0,
                'column_count': 0,
                'data_types': {},
                'formatting_hints': []
            }
        
        row_count = len(results)
        sample_row = results[0] if results else {}
        column_count = len(sample_row.keys())
        
        # Analyze data types
        data_types = {}
        numeric_columns = []
        date_columns = []
        text_columns = []
        
        for column, value in sample_row.items():
            if value is None:
                data_types[column] = 'null'
            elif isinstance(value, (int, float)):
                data_types[column] = 'numeric'
                numeric_columns.append(column)
            elif isinstance(value, str):
                # Check if it looks like a date
                if any(date_indicator in column.lower() for date_indicator in ['date', 'time', 'created', 'updated']):
                    data_types[column] = 'date'
                    date_columns.append(column)
                else:
                    data_types[column] = 'text'
                    text_columns.append(column)
            else:
                data_types[column] = 'other'
        
        # Generate formatting hints
        formatting_hints = []
        
        if row_count > 100:
            formatting_hints.append('large_dataset')
        if len(numeric_columns) > 0:
            formatting_hints.append('has_numeric_data')
        if len(date_columns) > 0:
            formatting_hints.append('has_temporal_data')
        if column_count > 10:
            formatting_hints.append('wide_table')
        
        # Determine result type
        result_type = 'table'
        if row_count == 1 and column_count == 1:
            result_type = 'single_value'
        elif column_count <= 2 and row_count <= 20:
            result_type = 'simple_list'
        elif any(agg in str(sample_row).lower() for agg in ['count', 'sum', 'avg', 'max', 'min']):
            result_type = 'aggregation'
        
        return {
            'result_type': result_type,
            'row_count': row_count,
            'column_count': column_count,
            'data_types': data_types,
            'numeric_columns': numeric_columns,
            'date_columns': date_columns,
            'text_columns': text_columns,
            'formatting_hints': formatting_hints
        }
    
    def _format_large_results(self, results: List[Dict[str, Any]], limit: int = 50) -> Dict[str, Any]:
        """
        Format large result sets with intelligent truncation and summary
        
        Args:
            results: Query results
            limit: Maximum number of rows to display
            
        Returns:
            Formatted response with pagination info
        """
        total_rows = len(results)
        displayed_results = results[:limit]
        
        summary = {
            'total_rows': total_rows,
            'displayed_rows': len(displayed_results),
            'truncated': total_rows > limit,
            'pagination_info': f"Showing {len(displayed_results)} of {total_rows} rows"
        }
        
        if total_rows > limit:
            summary['recommendation'] = (
                f"This query returned {total_rows} rows. Consider adding filters "
                "or using LIMIT clause for better performance."
            )
        
        return {
            'results': displayed_results,
            'summary': summary,
            'original_count': total_rows
        }
    
    def _generate_insights(self, results: List[Dict[str, Any]], analysis: Dict[str, Any]) -> List[str]:
        """
        Generate intelligent insights about the query results
        
        Args:
            results: Query results
            analysis: Result structure analysis
            
        Returns:
            List of insights about the data
        """
        insights = []
        
        if not results:
            insights.append("No data found matching your criteria.")
            return insights
        
        row_count = analysis['row_count']
        
        # Row count insights
        if row_count == 1:
            insights.append("Found exactly one matching record.")
        elif row_count < 10:
            insights.append(f"Found {row_count} matching records.")
        elif row_count < 100:
            insights.append(f"Found {row_count} records - a moderate dataset.")
        else:
            insights.append(f"Found {row_count} records - a large dataset.")
        
        # Data type insights
        numeric_cols = analysis['numeric_columns']
        if numeric_cols:
            # Calculate basic statistics for numeric columns
            for col in numeric_cols[:2]:  # Limit to first 2 numeric columns
                values = [row.get(col) for row in results if row.get(col) is not None]
                if values:
                    avg_val = sum(values) / len(values)
                    max_val = max(values)
                    min_val = min(values)
                    insights.append(
                        f"Column '{col}': Average = {avg_val:.2f}, Range = {min_val} to {max_val}"
                    )
        
        # Date insights
        date_cols = analysis['date_columns']
        if date_cols:
            insights.append(f"Dataset includes temporal data in {len(date_cols)} column(s).")
        
        # Data quality insights
        null_counts = {}
        for row in results[:100]:  # Sample first 100 rows
            for col, value in row.items():
                if value is None or value == '':
                    null_counts[col] = null_counts.get(col, 0) + 1
        
        if null_counts:
            high_null_cols = [col for col, count in null_counts.items() if count > len(results) * 0.1]
            if high_null_cols:
                insights.append(f"Note: Some columns have missing data: {', '.join(high_null_cols[:3])}")
        
        return insights
    
    def _generate_follow_up_questions(self, 
                                    question: str, 
                                    results: List[Dict[str, Any]], 
                                    analysis: Dict[str, Any]) -> List[str]:
        """
        Generate intelligent follow-up questions based on the results
        
        Args:
            question: Original user question
            results: Query results
            analysis: Result structure analysis
            
        Returns:
            List of suggested follow-up questions
        """
        follow_ups = []
        
        if not results:
            follow_ups.extend([
                "Could you check the spelling of table or column names?",
                "Would you like to see what tables are available in the database?",
                "Could you try a broader search criteria?"
            ])
            return follow_ups
        
        # Based on result type
        result_type = analysis['result_type']
        
        if result_type == 'aggregation':
            follow_ups.extend([
                "Would you like to see the breakdown by category?",
                "How does this compare to previous periods?",
                "What are the top 10 items in this analysis?"
            ])
        elif result_type == 'table':
            follow_ups.extend([
                "Would you like to filter these results further?",
                "How would you like to sort this data?",
                "Would you like to export this data?"
            ])
        
        # Based on data characteristics
        if analysis['numeric_columns']:
            follow_ups.append("Would you like to see statistics or trends for the numeric data?")
        
        if analysis['date_columns']:
            follow_ups.append("Would you like to analyze trends over time?")
        
        if analysis['row_count'] > 100:
            follow_ups.append("Would you like to add filters to narrow down the results?")
        
        return follow_ups[:5]  # Limit to 5 suggestions
    
    async def _get_cached_response(self, question: str, results_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached formatted response"""
        cache_key = f"formatted_response:{hash(question + results_hash)}"
        return await self.cache_manager.get(cache_key)
    
    async def _cache_response(self, question: str, results_hash: str, response: Dict[str, Any], ttl: int = 1800):
        """Cache formatted response"""
        cache_key = f"formatted_response:{hash(question + results_hash)}"
        await self.cache_manager.set(cache_key, response, ttl)
    
    async def __call__(self, state: dict) -> dict:
        """
        Main entry point for the Answer Formatter Agent
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with formatted answer and insights
        """
        with track_performance("agent.answer_formatter.execution"):
            logger.info(
                "AnswerFormatterAgent processing request",
                extra={
                    "user_id": state.get("user_id"),
                    "correlation_id": state.get("correlation_id")
                }
            )
            
            question = state.get("question", "")
            results = state.get("results", [])
            sql_executed = state.get("sql_executed", False)
            execution_time = state.get("execution_time", 0)
            error = state.get("error")
            
            try:
                # Handle error cases
                if error or not results:
                    error_message = error or "No results found or an error occurred."
                    
                    logger.info(
                        "Formatting error response",
                        extra={
                            "user_id": state.get("user_id"),
                            "error": error_message
                        }
                    )
                    
                    return {
                        **state,
                        "answer": error_message,
                        "follow_up_questions": [
                            "Could you rephrase your question?",
                            "Would you like to see available tables?",
                            "Can you provide more specific criteria?"
                        ],
                        "from_sql": sql_executed,
                        "formatting_metadata": {
                            "agent": "AnswerFormatterAgent",
                            "version": "2.0",
                            "formatted_at": datetime.utcnow().isoformat(),
                            "result_type": "error"
                        }
                    }
                
                # Analyze result structure
                with track_performance("agent.answer_formatter.analysis"):
                    analysis = self._analyze_result_structure(results)
                
                # Check for cached response
                results_hash = str(hash(str(results)))
                cached_response = await self._get_cached_response(question, results_hash)
                
                if cached_response:
                    logger.info("Using cached formatted response")
                    return {
                        **state,
                        **cached_response,
                        "cache_hit": True
                    }
                
                # Format large results if needed
                if analysis['row_count'] > 50:
                    with track_performance("agent.answer_formatter.large_results"):
                        formatted_data = self._format_large_results(results)
                        display_results = formatted_data['results']
                        result_summary = formatted_data['summary']
                else:
                    display_results = results
                    result_summary = {
                        'total_rows': len(results),
                        'displayed_rows': len(results),
                        'truncated': False
                    }
                
                # Generate insights
                with track_performance("agent.answer_formatter.insights"):
                    insights = self._generate_insights(results, analysis)
                
                # Generate follow-up questions
                with track_performance("agent.answer_formatter.follow_ups"):
                    follow_up_questions = self._generate_follow_up_questions(question, results, analysis)
                
                # Use existing LLM formatting with enhanced context
                try:
                    logger.info("Calling LLM for answer formatting")
                    
                    # Prepare context for LLM
                    llm_context = {
                        'results': display_results,
                        'analysis': analysis,
                        'insights': insights,
                        'result_summary': result_summary
                    }
                    
                    with track_performance("agent.answer_formatter.llm_formatting"):
                        formatted_response = format_answer(question, llm_context)
                    
                    if isinstance(formatted_response, dict):
                        answer = formatted_response.get("answer", "No answer provided.")
                        llm_follow_ups = formatted_response.get("follow_up_questions", [])
                        
                        # Combine LLM follow-ups with generated ones
                        all_follow_ups = list(set(llm_follow_ups + follow_up_questions))[:5]
                    else:
                        answer = str(formatted_response)
                        all_follow_ups = follow_up_questions
                        
                except Exception as e:
                    logger.warning(f"LLM formatting failed, using fallback: {e}")
                    
                    # Fallback formatting
                    if analysis['result_type'] == 'single_value':
                        answer = f"The result is: {list(results[0].values())[0]}"
                    elif analysis['result_type'] == 'simple_list':
                        answer = f"Found {len(results)} results:\n" + \
                                "\n".join([str(list(row.values())[0]) for row in results[:10]])
                    else:
                        answer = f"Query completed successfully. Found {len(results)} records."
                        if result_summary.get('truncated'):
                            answer += f" Showing first {result_summary['displayed_rows']} rows."
                    
                    all_follow_ups = follow_up_questions
                
                # Create comprehensive response
                response_data = {
                    "answer": answer,
                    "follow_up_questions": all_follow_ups,
                    "from_sql": sql_executed,
                    "insights": insights,
                    "result_summary": result_summary,
                    "analysis": analysis,
                    "cache_hit": False,
                    "formatting_metadata": {
                        "agent": "AnswerFormatterAgent",
                        "version": "2.0",
                        "formatted_at": datetime.utcnow().isoformat(),
                        "result_type": analysis['result_type'],
                        "execution_time": execution_time
                    }
                }
                
                # Cache the response for future use
                await self._cache_response(question, results_hash, response_data)
                
                logger.info(
                    "Answer formatting completed successfully",
                    extra={
                        "user_id": state.get("user_id"),
                        "result_type": analysis['result_type'],
                        "row_count": analysis['row_count'],
                        "insights_count": len(insights)
                    }
                )
                
                return {**state, **response_data}
                
            except Exception as e:
                error_msg = f"Answer formatting failed: {str(e)}"
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
                    "answer": "I encountered an error while formatting the response. The query may have completed, but I couldn't present the results properly.",
                    "follow_up_questions": [
                        "Could you try asking the question differently?",
                        "Would you like to see the raw query results?"
                    ],
                    "from_sql": sql_executed,
                    "error": error_msg
                }

# Legacy synchronous interface for backward compatibility
def __call__(state: dict) -> dict:
    """Synchronous wrapper for the async answer formatter agent"""
    agent = AnswerFormatterAgent()
    return asyncio.run(agent(state))