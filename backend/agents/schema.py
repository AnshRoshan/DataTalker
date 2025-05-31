# agents/schema.py
"""
Enterprise Schema Agent - Modernized for PostgreSQL with async operations and caching
"""
import asyncio
from typing import Dict, List, Any, Optional
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.database import get_database_manager
from core.cache import get_cache_manager
from core.monitoring import get_logger, track_performance

logger = get_logger(__name__)

class SchemaAgent:
    """
    Enterprise Schema Agent for PostgreSQL databases with intelligent caching.
    
    Features:
    - Async PostgreSQL schema extraction
    - Redis-based schema caching with TTL
    - Enhanced schema formatting for LLM consumption
    - Performance monitoring and error handling
    - Support for large databases (100+ tables)
    """
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.cache_manager = get_cache_manager()
    
    def _format_schema_for_llm(self, detailed_schema: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Format schema information in a clear, structured way for the LLM
        
        Args:
            detailed_schema: Complete schema information with tables, columns, relationships
            
        Returns:
            Formatted schema string optimized for LLM understanding
        """
        formatted = "🏢 ENTERPRISE DATABASE SCHEMA INFORMATION:\n\n"
        
        # Sort tables by row count (most important first)
        all_tables = []
        for table_name, table_list in detailed_schema.items():
            for table_info in table_list:
                all_tables.append((table_name, table_info))
        
        # Sort by row count descending, then by name
        all_tables.sort(key=lambda x: (-x[1].get('statistics', {}).get('row_count', 0), x[0]))
        
        for table_name, table_info in all_tables:
            columns = table_info.get('columns', [])
            foreign_keys = table_info.get('foreign_keys', [])
            stats = table_info.get('statistics', {})
            row_count = stats.get('row_count', 'Unknown')
            table_size = stats.get('size_mb', 0)
            
            # Table header with statistics
            size_info = f" - {table_size:.1f}MB" if table_size > 0 else ""
            formatted += f"📊 TABLE: {table_name} ({row_count:,} rows{size_info})\n"
            
            # Primary and foreign keys summary
            primary_keys = [col['column_name'] for col in columns if col.get('is_primary_key')]
            if primary_keys:
                formatted += f"🔑 PRIMARY KEY: {', '.join(primary_keys)}\n"
            
            # Columns with enhanced type information
            formatted += "📋 COLUMNS:\n"
            for col in columns:
                col_name = col['column_name']
                col_type = col['data_type']
                
                # Enhanced column attributes
                attributes = []
                if col.get('is_primary_key'):
                    attributes.append("PK")
                if col.get('is_nullable') == 'NO':
                    attributes.append("NOT NULL")
                if col.get('column_default'):
                    attributes.append(f"DEFAULT: {col['column_default']}")
                if col.get('character_maximum_length'):
                    attributes.append(f"MAX_LEN: {col['character_maximum_length']}")
                
                attr_str = f" [{', '.join(attributes)}]" if attributes else ""
                formatted += f"  • {col_name}: {col_type}{attr_str}\n"
            
            # Foreign key relationships
            if foreign_keys:
                formatted += "🔗 RELATIONSHIPS:\n"
                for fk in foreign_keys:
                    formatted += f"  • {fk['column_name']} → {fk['foreign_table_name']}.{fk['foreign_column_name']}\n"
            
            # Indexes information
            indexes = table_info.get('indexes', [])
            if indexes:
                formatted += "📇 INDEXES:\n"
                for idx in indexes:
                    idx_cols = ', '.join(idx.get('columns', []))
                    unique_str = " [UNIQUE]" if idx.get('is_unique') else ""
                    formatted += f"  • {idx['index_name']}: ({idx_cols}){unique_str}\n"
            
            formatted += "\n"
        
        # Add relationship summary
        total_relationships = sum(len(table.get('foreign_keys', [])) for table_list in detailed_schema.values() for table in table_list)
        total_tables = len(detailed_schema)
        
        formatted += f"📈 SCHEMA SUMMARY:\n"
        formatted += f"  • Total Tables: {total_tables}\n"
        formatted += f"  • Total Relationships: {total_relationships}\n"
        formatted += f"  • Cache Status: ✅ Cached for optimal performance\n\n"
        
        return formatted
    
    async def _extract_postgresql_schema(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract comprehensive schema from PostgreSQL database
        
        Returns:
            Complete schema information including tables, columns, relationships, and statistics
        """
        schema_data = {}
        
        try:
            async with self.db_manager.get_session() as session:
                # Get all tables with enhanced information
                tables_query = text("""
                    SELECT 
                        t.table_name,
                        t.table_type,
                        obj_description(c.oid) as table_comment
                    FROM information_schema.tables t
                    LEFT JOIN pg_class c ON c.relname = t.table_name
                    WHERE t.table_schema = 'public' 
                    AND t.table_type = 'BASE TABLE'
                    ORDER BY t.table_name
                """)
                
                tables_result = await session.execute(tables_query)
                tables = tables_result.fetchall()
                
                for table in tables:
                    table_name = table[0]
                    
                    # Get column information
                    columns_query = text("""
                        SELECT 
                            column_name,
                            data_type,
                            is_nullable,
                            column_default,
                            character_maximum_length,
                            numeric_precision,
                            numeric_scale,
                            CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_primary_key
                        FROM information_schema.columns c
                        LEFT JOIN (
                            SELECT kcu.column_name
                            FROM information_schema.table_constraints tc
                            JOIN information_schema.key_column_usage kcu 
                                ON tc.constraint_name = kcu.constraint_name
                            WHERE tc.table_name = :table_name 
                            AND tc.constraint_type = 'PRIMARY KEY'
                        ) pk ON c.column_name = pk.column_name
                        WHERE c.table_name = :table_name
                        ORDER BY c.ordinal_position
                    """)
                    
                    columns_result = await session.execute(columns_query, {"table_name": table_name})
                    columns = [dict(row._mapping) for row in columns_result.fetchall()]
                    
                    # Get foreign key relationships
                    fk_query = text("""
                        SELECT
                            kcu.column_name,
                            ccu.table_name AS foreign_table_name,
                            ccu.column_name AS foreign_column_name,
                            tc.constraint_name
                        FROM information_schema.table_constraints AS tc
                        JOIN information_schema.key_column_usage AS kcu
                            ON tc.constraint_name = kcu.constraint_name
                        JOIN information_schema.constraint_column_usage AS ccu
                            ON ccu.constraint_name = tc.constraint_name
                        WHERE tc.constraint_type = 'FOREIGN KEY'
                        AND tc.table_name = :table_name
                    """)
                    
                    fk_result = await session.execute(fk_query, {"table_name": table_name})
                    foreign_keys = [dict(row._mapping) for row in fk_result.fetchall()]
                    
                    # Get table statistics
                    stats_query = text("""
                        SELECT 
                            schemaname,
                            tablename,
                            attname,
                            n_distinct,
                            correlation
                        FROM pg_stats 
                        WHERE tablename = :table_name
                        LIMIT 5
                    """)
                    
                    try:
                        # Get row count
                        count_query = text(f"SELECT COUNT(*) FROM {table_name}")
                        count_result = await session.execute(count_query)
                        row_count = count_result.scalar()
                        
                        # Get table size
                        size_query = text("SELECT pg_total_relation_size(:table_name)")
                        size_result = await session.execute(size_query, {"table_name": table_name})
                        table_size_bytes = size_result.scalar() or 0
                        table_size_mb = table_size_bytes / (1024 * 1024)
                    except Exception:
                        row_count = 0
                        table_size_mb = 0
                    
                    # Get indexes
                    indexes_query = text("""
                        SELECT
                            i.relname as index_name,
                            a.attname as column_name,
                            ix.indisunique as is_unique,
                            ix.indisprimary as is_primary
                        FROM pg_class t
                        JOIN pg_index ix ON t.oid = ix.indrelid
                        JOIN pg_class i ON i.oid = ix.indexrelid
                        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                        WHERE t.relname = :table_name
                        AND t.relkind = 'r'
                        ORDER BY i.relname, a.attnum
                    """)
                    
                    indexes_result = await session.execute(indexes_query, {"table_name": table_name})
                    indexes_raw = indexes_result.fetchall()
                    
                    # Group indexes by name
                    indexes_dict = {}
                    for idx in indexes_raw:
                        idx_name = idx[0]
                        if idx_name not in indexes_dict:
                            indexes_dict[idx_name] = {
                                'index_name': idx_name,
                                'columns': [],
                                'is_unique': idx[2],
                                'is_primary': idx[3]
                            }
                        indexes_dict[idx_name]['columns'].append(idx[1])
                    
                    indexes = list(indexes_dict.values())
                    
                    # Compile table information
                    table_info = {
                        'table_name': table_name,
                        'table_type': table[1],
                        'table_comment': table[2],
                        'columns': columns,
                        'foreign_keys': foreign_keys,
                        'indexes': indexes,
                        'statistics': {
                            'row_count': row_count,
                            'size_bytes': table_size_bytes,
                            'size_mb': round(table_size_mb, 2)
                        }
                    }
                    
                    schema_data[table_name] = [table_info]
                    
                    logger.debug(
                        f"Extracted schema for table {table_name}",
                        extra={
                            "table_name": table_name,
                            "column_count": len(columns),
                            "fk_count": len(foreign_keys),
                            "row_count": row_count
                        }
                    )
        
        except SQLAlchemyError as e:
            logger.error(f"Database error during schema extraction: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during schema extraction: {e}")
            raise
        
        return schema_data
    
    async def __call__(self, state: dict) -> dict:
        """
        Main entry point for the Schema Agent
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with schema information
        """
        with track_performance("agent.schema.execution"):
            logger.info(
                "SchemaAgent processing request",
                extra={
                    "user_id": state.get("user_id"),
                    "correlation_id": state.get("correlation_id")
                }
            )
            
            try:
                # Try to get cached schema first
                cached_schema = await self.cache_manager.get_schema()
                
                if cached_schema:
                    logger.info("Using cached schema data")
                    schema_description = self._format_schema_for_llm(cached_schema)
                    
                    return {
                        **state,
                        "schema": cached_schema,
                        "detailed_schema": cached_schema,
                        "schema_description": schema_description,
                        "cache_hit": True,
                        "error": None
                    }
                
                # Extract fresh schema from database
                logger.info("Extracting fresh schema from database")
                
                with track_performance("agent.schema.extraction"):
                    detailed_schema = await self._extract_postgresql_schema()
                
                # Cache the schema for future use
                await self.cache_manager.set_schema(detailed_schema)
                
                # Format for LLM consumption
                schema_description = self._format_schema_for_llm(detailed_schema)
                
                # Create legacy format for backward compatibility
                legacy_schema = {}
                for table_name, table_list in detailed_schema.items():
                    for table_info in table_list:
                        columns = table_info.get('columns', [])
                        legacy_schema[table_name] = [
                            f"{col['column_name']} ({col['data_type']})" 
                            for col in columns
                        ]
                
                logger.info(
                    "Schema extraction completed successfully",
                    extra={
                        "table_count": len(detailed_schema),
                        "total_columns": sum(len(table[0].get('columns', [])) for table in detailed_schema.values()),
                        "cache_hit": False
                    }
                )
                
                return {
                    **state,
                    "schema": legacy_schema,  # For backward compatibility
                    "detailed_schema": detailed_schema,  # Enhanced schema
                    "schema_description": schema_description,  # LLM-formatted
                    "cache_hit": False,
                    "error": None
                }
                
            except Exception as e:
                error_msg = f"Schema extraction failed: {str(e)}"
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
                    "schema": {},
                    "detailed_schema": {},
                    "schema_description": "",
                    "error": error_msg
                }

# Legacy synchronous interface for backward compatibility
def __call__(state: dict) -> dict:
    """Synchronous wrapper for the async schema agent"""
    agent = SchemaAgent()
    return asyncio.run(agent(state))