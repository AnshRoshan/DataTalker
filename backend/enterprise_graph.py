"""
Enterprise LangGraph Workflow for TalkToData

Orchestrates the complete natural language to database query pipeline
with enterprise-grade async operations, monitoring, and error handling.
"""

import asyncio
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from langgraph.graph import StateGraph
import structlog

from core.config import settings
from core.monitoring import performance_tracker
from core.security import get_current_user_context

# Import all modernized agents
from agents.user_input import UserInputAgent
from agents.schema import SchemaAgent
from agents.sql_writer import SQLWriterAgent
from agents.validator import ValidatorAgent
from agents.db_executor import DBExecutorAgent
from agents.answer import AnswerFormatterAgent
from agents.fallback import FallbackAgent

logger = structlog.get_logger(__name__)


class EnterpriseState:
    """
    Enhanced state management for the enterprise workflow
    """
    
    def __init__(self, initial_state: Dict[str, Any]):
        self.state = {
            "correlation_id": str(uuid.uuid4()),
            "workflow_start_time": datetime.utcnow().isoformat(),
            "current_step": "initialization",
            "errors": [],
            "warnings": [],
            "processing_history": [],
            **initial_state
        }
    
    def update(self, updates: Dict[str, Any]) -> None:
        """Update state with new values"""
        self.state.update(updates)
        
        # Track processing history
        if "current_step" in updates:
            self.state["processing_history"].append({
                "step": updates["current_step"],
                "timestamp": datetime.utcnow().isoformat(),
                "duration_ms": self._calculate_step_duration()
            })
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from state"""
        return self.state.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.state.copy()
    
    def _calculate_step_duration(self) -> Optional[float]:
        """Calculate duration of current step"""
        if len(self.state["processing_history"]) > 0:
            last_step = self.state["processing_history"][-1]
            last_time = datetime.fromisoformat(last_step["timestamp"])
            current_time = datetime.utcnow()
            return (current_time - last_time).total_seconds() * 1000
        return None


class EnterpriseWorkflow:
    """
    Enterprise workflow orchestrator with async support and comprehensive monitoring
    """
    
    def __init__(self):
        self.user_input_agent = UserInputAgent()
        self.schema_agent = SchemaAgent()
        self.sql_writer_agent = SQLWriterAgent()
        self.validator_agent = ValidatorAgent()
        self.db_executor_agent = DBExecutorAgent()
        self.answer_formatter_agent = AnswerFormatterAgent()
        self.fallback_agent = FallbackAgent()
        
        # Initialize the workflow graph
        self.graph = self._build_workflow_graph()
        self.app = self.graph.compile()
    
    def _build_workflow_graph(self) -> StateGraph:
        """Build the enterprise workflow graph"""
        graph = StateGraph(state_schema=dict)
        
        # Add all agent nodes
        graph.add_node("user_input", self._wrap_async_agent(self.user_input_agent, "user_input"))
        graph.add_node("schema_extraction", self._wrap_async_agent(self.schema_agent, "schema_extraction"))
        graph.add_node("sql_generation", self._wrap_async_agent(self.sql_writer_agent, "sql_generation"))
        graph.add_node("sql_validation", self._wrap_async_agent(self.validator_agent, "sql_validation"))
        graph.add_node("query_execution", self._wrap_async_agent(self.db_executor_agent, "query_execution"))
        graph.add_node("answer_formatting", self._wrap_async_agent(self.answer_formatter_agent, "answer_formatting"))
        graph.add_node("fallback_handling", self._wrap_async_agent(self.fallback_agent, "fallback_handling"))
        
        # Define workflow edges
        graph.set_entry_point("user_input")
        graph.add_edge("user_input", "schema_extraction")
        
        # Conditional routing after schema extraction
        graph.add_conditional_edges(
            "schema_extraction",
            self._route_after_schema,
            {
                "continue": "sql_generation",
                "error": "fallback_handling"
            }
        )
        
        # Conditional routing after SQL generation
        graph.add_conditional_edges(
            "sql_generation",
            self._route_after_sql_generation,
            {
                "validate": "sql_validation",
                "error": "fallback_handling"
            }
        )
        
        # Conditional routing after validation
        graph.add_conditional_edges(
            "sql_validation",
            self._route_after_validation,
            {
                "execute": "query_execution",
                "reject": "fallback_handling"
            }
        )
        
        # Continue to formatting after successful execution
        graph.add_edge("query_execution", "answer_formatting")
        graph.add_edge("fallback_handling", "answer_formatting")
        
        # Set final endpoint
        graph.set_finish_point("answer_formatting")
        
        return graph
    
    def _wrap_async_agent(self, agent, step_name: str):
        """Wrap agent with async support and monitoring"""
        async def wrapped_agent(state: Dict[str, Any]) -> Dict[str, Any]:
            correlation_id = state.get("correlation_id", "unknown")
            
            logger.info(
                f"Starting {step_name}",
                correlation_id=correlation_id,
                step=step_name
            )
            
            try:
                with performance_tracker.track_operation(step_name, correlation_id):
                    # Update current step
                    state["current_step"] = step_name
                    
                    # Check if agent has async method
                    if hasattr(agent, 'process_input'):
                        result = await agent.process_input(state)
                    elif hasattr(agent, 'extract_schema'):
                        result = await agent.extract_schema(state)
                    elif hasattr(agent, 'generate_sql'):
                        result = await agent.generate_sql(state)
                    elif hasattr(agent, 'validate_sql'):
                        result = await agent.validate_sql(state)
                    elif hasattr(agent, 'execute_query'):
                        result = await agent.execute_query(state)
                    elif hasattr(agent, 'format_answer'):
                        result = await agent.format_answer(state)
                    elif hasattr(agent, 'handle_error'):
                        result = await agent.handle_error(state)
                    else:
                        # Fallback to synchronous call
                        result = agent(state)
                    
                    logger.info(
                        f"Completed {step_name}",
                        correlation_id=correlation_id,
                        step=step_name,
                        success=True
                    )
                    
                    return result
                    
            except Exception as e:
                logger.error(
                    f"Error in {step_name}",
                    correlation_id=correlation_id,
                    step=step_name,
                    error=str(e),
                    exc_info=True
                )
                
                return {
                    **state,
                    "error": f"Error in {step_name}: {str(e)}",
                    "step_failed": step_name,
                    "processing_status": "failed"
                }
        
        return wrapped_agent
    
    def _route_after_schema(self, state: Dict[str, Any]) -> str:
        """Routing logic after schema extraction"""
        if state.get("error") or state.get("step_failed"):
            return "error"
        if not state.get("schema_info"):
            return "error"
        return "continue"
    
    def _route_after_sql_generation(self, state: Dict[str, Any]) -> str:
        """Routing logic after SQL generation"""
        if state.get("error") or state.get("step_failed"):
            return "error"
        if not state.get("sql"):
            return "error"
        return "validate"
    
    def _route_after_validation(self, state: Dict[str, Any]) -> str:
        """Routing logic after SQL validation"""
        if state.get("error") or state.get("step_failed"):
            return "reject"
        if not state.get("is_safe", False):
            return "reject"
        return "execute"
    
    async def process_query(
        self,
        question: str,
        user_context: Optional[Dict[str, Any]] = None,
        db_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a natural language query through the complete enterprise pipeline
        """
        correlation_id = str(uuid.uuid4())
        
        try:
            # Initialize state
            initial_state = {
                "question": question,
                "user_context": user_context or {},
                "db_config": db_config or {},
                "correlation_id": correlation_id,
                "workflow_start_time": datetime.utcnow().isoformat()
            }
            
            logger.info(
                "Starting enterprise query processing",
                correlation_id=correlation_id,
                question_length=len(question),
                user_id=user_context.get("user_id") if user_context else None
            )
            
            # Execute the workflow
            with performance_tracker.track_operation("complete_workflow", correlation_id):
                result = await self._execute_workflow(initial_state)
            
            # Calculate total processing time
            start_time = datetime.fromisoformat(initial_state["workflow_start_time"])
            end_time = datetime.utcnow()
            total_duration = (end_time - start_time).total_seconds() * 1000
            
            result["total_processing_time_ms"] = total_duration
            result["workflow_end_time"] = end_time.isoformat()
            
            logger.info(
                "Completed enterprise query processing",
                correlation_id=correlation_id,
                success=not bool(result.get("error")),
                duration_ms=total_duration,
                steps_completed=len(result.get("processing_history", []))
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Fatal error in enterprise workflow",
                correlation_id=correlation_id,
                error=str(e),
                exc_info=True
            )
            
            return {
                "correlation_id": correlation_id,
                "error": f"Workflow failed: {str(e)}",
                "processing_status": "failed",
                "workflow_end_time": datetime.utcnow().isoformat()
            }
    
    async def _execute_workflow(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the workflow with proper async handling"""
        try:
            # Convert to async generator if needed
            async for state in self.app.astream(initial_state):
                # LangGraph returns the final state
                if isinstance(state, dict):
                    return state
            
            # If we get here, something went wrong
            return {
                **initial_state,
                "error": "Workflow completed without returning final state",
                "processing_status": "failed"
            }
            
        except Exception as e:
            logger.error(
                "Error executing workflow",
                correlation_id=initial_state.get("correlation_id"),
                error=str(e),
                exc_info=True
            )
            
            return {
                **initial_state,
                "error": f"Workflow execution failed: {str(e)}",
                "processing_status": "failed"
            }
    
    def process_query_sync(
        self,
        question: str,
        user_context: Optional[Dict[str, Any]] = None,
        db_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for backward compatibility
        """
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
                    future = executor.submit(
                        asyncio.run,
                        self.process_query(question, user_context, db_config)
                    )
                    return future.result()
            else:
                # Run in the current loop
                return loop.run_until_complete(
                    self.process_query(question, user_context, db_config)
                )
                
        except Exception as e:
            logger.error(f"Error in synchronous workflow wrapper: {str(e)}", exc_info=True)
            return {
                "error": f"Workflow processing failed: {str(e)}",
                "processing_status": "failed"
            }


# Global workflow instance
enterprise_workflow = EnterpriseWorkflow()

# Backward compatibility - maintain the same interface as original main_graph.py
app = enterprise_workflow.app

# For direct invocation
async def process_query_async(
    question: str,
    user_context: Optional[Dict[str, Any]] = None,
    db_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Direct async query processing function"""
    return await enterprise_workflow.process_query(question, user_context, db_config)

def process_query(
    question: str,
    user_context: Optional[Dict[str, Any]] = None,
    db_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Direct synchronous query processing function"""
    return enterprise_workflow.process_query_sync(question, user_context, db_config)
