"""
Background Task Implementations

Contains the actual Celery task implementations for heavy operations
like large queries, schema analysis, data exports, and LLM operations.
"""

import asyncio
import json
import time
import csv
import io
import zipfile
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import traceback

from celery import current_task
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from .tasks import celery_app, AsyncTask
from .database import DatabaseManager
from .cache import get_cache_manager
from .config import get_settings
from .monitoring import get_logger, track_performance

logger = get_logger(__name__)
settings = get_settings()

class ProgressTracker:
    """Utility for tracking task progress"""
    
    def __init__(self, total_steps: int):
        self.total_steps = total_steps
        self.current_step = 0
    
    def update(self, step: int = None, message: str = ""):
        """Update progress"""
        if step is not None:
            self.current_step = step
        else:
            self.current_step += 1
        
        progress = min(100, int((self.current_step / self.total_steps) * 100))
        
        current_task.update_state(
            state="PROGRESS",
            meta={
                "progress": progress,
                "current_step": self.current_step,
                "total_steps": self.total_steps,
                "message": message
            }
        )

@celery_app.task(base=AsyncTask, bind=True)
async def execute_large_query(
    self,
    query: str,
    user_id: int,
    limit: Optional[int] = None,
    timeout: int = 300
) -> Dict[str, Any]:
    """
    Execute a large database query asynchronously
    
    Args:
        query: SQL query to execute
        user_id: ID of the user requesting the query
        limit: Optional limit for results
        timeout: Query timeout in seconds
    
    Returns:
        Query results with metadata
    """
    progress = ProgressTracker(5)
    start_time = time.time()
    
    try:
        progress.update(message="Initializing database connection")
        
        # Initialize database manager
        db_manager = DatabaseManager()
        await db_manager.init()
        
        progress.update(message="Validating query")
        
        # Basic query validation
        query_lower = query.lower().strip()
        if not query_lower.startswith(('select', 'with')):
            raise ValueError("Only SELECT and WITH queries are allowed")
        
        # Dangerous keywords check
        dangerous_keywords = ['drop', 'delete', 'update', 'insert', 'alter', 'create', 'truncate']
        if any(keyword in query_lower for keyword in dangerous_keywords):
            raise ValueError("Query contains forbidden operations")
        
        progress.update(message="Executing query")
        
        # Add limit if specified
        if limit:
            if 'limit' not in query_lower:
                query += f" LIMIT {limit}"
        
        # Execute query with timeout
        async with db_manager.get_session() as session:
            result = await asyncio.wait_for(
                session.execute(text(query)),
                timeout=timeout
            )
            
            progress.update(message="Processing results")
            
            # Fetch all results
            rows = result.fetchall()
            columns = list(result.keys()) if rows else []
            
            # Convert to list of dictionaries
            data = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    # Handle special types
                    if isinstance(value, datetime):
                        value = value.isoformat()
                    elif hasattr(value, '__dict__'):  # Complex objects
                        value = str(value)
                    row_dict[col] = value
                data.append(row_dict)
            
            progress.update(message="Finalizing results")
            
            execution_time = time.time() - start_time
            
            result_data = {
                "success": True,
                "data": data,
                "columns": columns,
                "row_count": len(data),
                "execution_time": execution_time,
                "query": query,
                "user_id": user_id,
                "executed_at": datetime.utcnow().isoformat(),
                "limited": bool(limit and len(data) == limit)
            }
            
            # Cache results for future reference
            cache_manager = get_cache_manager()
            await cache_manager.set_query_result(
                query=query,
                result=result_data,
                user_id=user_id
            )
            
            logger.info(
                "Large query executed successfully",
                extra={
                    "user_id": user_id,
                    "row_count": len(data),
                    "execution_time": execution_time,
                    "task_id": self.request.id
                }
            )
            
            return result_data
            
    except asyncio.TimeoutError:
        error_msg = f"Query execution timed out after {timeout} seconds"
        logger.error(error_msg, extra={"user_id": user_id, "task_id": self.request.id})
        return {
            "success": False,
            "error": error_msg,
            "error_type": "timeout",
            "execution_time": time.time() - start_time
        }
    except Exception as e:
        error_msg = str(e)
        logger.error(
            f"Large query execution failed: {error_msg}",
            extra={"user_id": user_id, "task_id": self.request.id},
            exc_info=True
        )
        return {
            "success": False,
            "error": error_msg,
            "error_type": type(e).__name__,
            "execution_time": time.time() - start_time,
            "traceback": traceback.format_exc()
        }

@celery_app.task(base=AsyncTask, bind=True)
async def analyze_schema(
    self,
    user_id: int,
    include_statistics: bool = True,
    include_relationships: bool = True
) -> Dict[str, Any]:
    """
    Perform comprehensive schema analysis
    
    Args:
        user_id: ID of the user requesting the analysis
        include_statistics: Whether to include table statistics
        include_relationships: Whether to analyze relationships
    
    Returns:
        Complete schema analysis results
    """
    progress = ProgressTracker(6)
    start_time = time.time()
    
    try:
        progress.update(message="Connecting to database")
        
        # Initialize database manager
        db_manager = DatabaseManager()
        await db_manager.init()
        
        progress.update(message="Extracting basic schema")
        
        # Get basic schema
        schema = await db_manager.get_schema()
        
        progress.update(message="Analyzing table statistics")
        
        # Add detailed statistics if requested
        if include_statistics:
            for table_name in schema["tables"]:
                try:
                    async with db_manager.get_session() as session:
                        # Get row count
                        count_result = await session.execute(
                            text(f"SELECT COUNT(*) FROM {table_name}")
                        )
                        row_count = count_result.scalar()
                        
                        # Get table size (PostgreSQL specific)
                        size_result = await session.execute(
                            text(f"SELECT pg_total_relation_size('{table_name}')")
                        )
                        table_size = size_result.scalar()
                        
                        # Update schema with statistics
                        for table in schema["tables"][table_name]:
                            if table["table_name"] == table_name:
                                table["statistics"] = {
                                    "row_count": row_count,
                                    "size_bytes": table_size,
                                    "size_mb": round(table_size / 1024 / 1024, 2)
                                }
                                break
                                
                except Exception as e:
                    logger.warning(f"Failed to get statistics for table {table_name}: {e}")
        
        progress.update(message="Analyzing relationships")
        
        # Analyze relationships if requested
        relationships = []
        if include_relationships:
            try:
                async with db_manager.get_session() as session:
                    # Get foreign key relationships (PostgreSQL specific)
                    fk_query = text("""
                        SELECT
                            tc.table_name,
                            kcu.column_name,
                            ccu.table_name AS foreign_table_name,
                            ccu.column_name AS foreign_column_name
                        FROM information_schema.table_constraints AS tc
                        JOIN information_schema.key_column_usage AS kcu
                            ON tc.constraint_name = kcu.constraint_name
                        JOIN information_schema.constraint_column_usage AS ccu
                            ON ccu.constraint_name = tc.constraint_name
                        WHERE tc.constraint_type = 'FOREIGN KEY'
                    """)
                    
                    result = await session.execute(fk_query)
                    for row in result:
                        relationships.append({
                            "from_table": row[0],
                            "from_column": row[1],
                            "to_table": row[2],
                            "to_column": row[3]
                        })
                        
            except Exception as e:
                logger.warning(f"Failed to analyze relationships: {e}")
        
        progress.update(message="Generating insights")
        
        # Generate insights
        insights = []
        
        # Table size insights
        if include_statistics:
            large_tables = []
            for table_name, table_info in schema["tables"].items():
                for table in table_info:
                    stats = table.get("statistics", {})
                    if stats.get("row_count", 0) > 1000000:  # 1M rows
                        large_tables.append({
                            "table": table_name,
                            "rows": stats["row_count"]
                        })
            
            if large_tables:
                insights.append({
                    "type": "large_tables",
                    "description": "Tables with over 1 million rows",
                    "data": large_tables
                })
        
        # Relationship insights
        if relationships:
            insights.append({
                "type": "relationships",
                "description": f"Found {len(relationships)} foreign key relationships",
                "data": relationships
            })
        
        progress.update(message="Finalizing analysis")
        
        analysis_result = {
            "success": True,
            "schema": schema,
            "relationships": relationships,
            "insights": insights,
            "metadata": {
                "analyzed_at": datetime.utcnow().isoformat(),
                "analysis_time": time.time() - start_time,
                "user_id": user_id,
                "include_statistics": include_statistics,
                "include_relationships": include_relationships
            }
        }
        
        # Cache the analysis
        cache_manager = get_cache_manager()
        await cache_manager.set_schema(schema)
        
        logger.info(
            "Schema analysis completed",
            extra={
                "user_id": user_id,
                "table_count": len(schema["tables"]),
                "relationship_count": len(relationships),
                "analysis_time": time.time() - start_time,
                "task_id": self.request.id
            }
        )
        
        return analysis_result
        
    except Exception as e:
        error_msg = str(e)
        logger.error(
            f"Schema analysis failed: {error_msg}",
            extra={"user_id": user_id, "task_id": self.request.id},
            exc_info=True
        )
        return {
            "success": False,
            "error": error_msg,
            "error_type": type(e).__name__,
            "analysis_time": time.time() - start_time,
            "traceback": traceback.format_exc()
        }

@celery_app.task(base=AsyncTask, bind=True)
async def export_data(
    self,
    query: str,
    user_id: int,
    format: str = "csv",
    filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    Export query results to various formats
    
    Args:
        query: SQL query to execute
        user_id: ID of the user requesting the export
        format: Export format (csv, json, excel, parquet)
        filename: Optional custom filename
    
    Returns:
        Export result with download information
    """
    progress = ProgressTracker(5)
    start_time = time.time()
    
    try:
        progress.update(message="Executing query for export")
        
        # Execute the query first
        query_result = await execute_large_query.apply_async(
            args=[query, user_id],
            kwargs={"limit": None}  # No limit for exports
        ).get()
        
        if not query_result.get("success"):
            return query_result
        
        data = query_result["data"]
        columns = query_result["columns"]
        
        progress.update(message="Converting to DataFrame")
        
        # Convert to pandas DataFrame
        df = pd.DataFrame(data)
        
        progress.update(message=f"Exporting to {format}")
        
        # Generate filename
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"export_{timestamp}"
        
        # Export based on format
        export_result = None
        
        if format.lower() == "csv":
            output = io.StringIO()
            df.to_csv(output, index=False)
            export_result = {
                "content": output.getvalue(),
                "mime_type": "text/csv",
                "filename": f"{filename}.csv"
            }
            
        elif format.lower() == "json":
            export_result = {
                "content": df.to_json(orient="records", indent=2),
                "mime_type": "application/json",
                "filename": f"{filename}.json"
            }
            
        elif format.lower() == "excel":
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Data')
            export_result = {
                "content": output.getvalue(),
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "filename": f"{filename}.xlsx",
                "is_binary": True
            }
            
        elif format.lower() == "parquet":
            output = io.BytesIO()
            df.to_parquet(output, index=False)
            export_result = {
                "content": output.getvalue(),
                "mime_type": "application/octet-stream",
                "filename": f"{filename}.parquet",
                "is_binary": True
            }
            
        else:
            raise ValueError(f"Unsupported export format: {format}")
        
        progress.update(message="Saving export file")
        
        # Store the file content (in a real system, this would go to cloud storage)
        file_id = f"export_{user_id}_{self.request.id}"
        
        # For now, we'll just return the content info
        # In production, you'd save to S3/GCS and return a download URL
        
        progress.update(message="Export completed")
        
        result = {
            "success": True,
            "file_id": file_id,
            "filename": export_result["filename"],
            "mime_type": export_result["mime_type"],
            "row_count": len(data),
            "file_size": len(export_result["content"]) if isinstance(export_result["content"], str) else len(export_result["content"]),
            "format": format,
            "export_time": time.time() - start_time,
            "user_id": user_id,
            "exported_at": datetime.utcnow().isoformat(),
            # In production, this would be a secure download URL
            "download_url": f"/api/exports/{file_id}/download"
        }
        
        logger.info(
            "Data export completed",
            extra={
                "user_id": user_id,
                "format": format,
                "row_count": len(data),
                "file_size": result["file_size"],
                "export_time": time.time() - start_time,
                "task_id": self.request.id
            }
        )
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        logger.error(
            f"Data export failed: {error_msg}",
            extra={"user_id": user_id, "format": format, "task_id": self.request.id},
            exc_info=True
        )
        return {
            "success": False,
            "error": error_msg,
            "error_type": type(e).__name__,
            "export_time": time.time() - start_time,
            "traceback": traceback.format_exc()
        }

@celery_app.task(base=AsyncTask, bind=True)
async def generate_llm_response(
    self,
    prompt: str,
    user_id: int,
    model: str = "gemini-1.5-flash",
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate LLM response asynchronously
    
    Args:
        prompt: User prompt/question
        user_id: ID of the user requesting the response
        model: LLM model to use
        context: Additional context (schema, previous queries, etc.)
    
    Returns:
        LLM response with metadata
    """
    progress = ProgressTracker(4)
    start_time = time.time()
    
    try:
        progress.update(message="Preparing LLM request")
        
        # Import LLM manager (assuming it exists)
        from ..llm.gemini import GeminiManager
        
        llm_manager = GeminiManager()
        
        progress.update(message="Adding context")
        
        # Prepare full prompt with context
        full_prompt = prompt
        if context:
            if context.get("schema"):
                full_prompt = f"Schema: {json.dumps(context['schema'], indent=2)}\n\nUser Question: {prompt}"
            if context.get("previous_queries"):
                full_prompt += f"\n\nPrevious Queries: {context['previous_queries']}"
        
        progress.update(message="Generating response")
        
        # Generate response
        response = await llm_manager.generate_response(
            prompt=full_prompt,
            model=model
        )
        
        progress.update(message="Processing response")
        
        result = {
            "success": True,
            "response": response,
            "prompt": prompt,
            "model": model,
            "context_included": bool(context),
            "generation_time": time.time() - start_time,
            "user_id": user_id,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        logger.info(
            "LLM response generated",
            extra={
                "user_id": user_id,
                "model": model,
                "generation_time": time.time() - start_time,
                "task_id": self.request.id
            }
        )
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        logger.error(
            f"LLM response generation failed: {error_msg}",
            extra={"user_id": user_id, "model": model, "task_id": self.request.id},
            exc_info=True
        )
        return {
            "success": False,
            "error": error_msg,
            "error_type": type(e).__name__,
            "generation_time": time.time() - start_time,
            "traceback": traceback.format_exc()
        }
