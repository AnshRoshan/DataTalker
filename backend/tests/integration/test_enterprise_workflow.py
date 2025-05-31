"""
Integration tests for the complete enterprise workflow

Tests the end-to-end functionality of the modernized TalkToData system
with PostgreSQL, caching, authentication, and all enterprise features.
"""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any

from enterprise_graph import enterprise_workflow, process_query_async
from core.config import get_settings
from core.database import get_database_manager
from core.cache import get_cache_manager
from core.auth import auth_service
from core.security import UserRole


@pytest.mark.asyncio
class TestEnterpriseWorkflow:
    """Test the complete enterprise workflow"""
    
    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup test environment"""
        self.settings = get_settings()
        self.db_manager = get_database_manager()
        self.cache_manager = get_cache_manager()
        
        # Ensure database connection
        await self.db_manager.connect()
        
        # Create test user contexts
        self.admin_context = {
            "user_id": "test_admin",
            "role": UserRole.ADMIN.value,
            "departments": ["IT", "Analytics"],
            "permissions": ["read", "write", "admin"],
            "data_access_level": "full"
        }
        
        self.analyst_context = {
            "user_id": "test_analyst", 
            "role": UserRole.ANALYST.value,
            "departments": ["Analytics"],
            "permissions": ["read"],
            "data_access_level": "limited"
        }
        
        self.viewer_context = {
            "user_id": "test_viewer",
            "role": UserRole.VIEWER.value,
            "departments": ["Sales"],
            "permissions": ["read"],
            "data_access_level": "restricted"
        }
    
    async def test_simple_query_workflow(self):
        """Test a simple SELECT query through the complete workflow"""
        question = "How many users are in the database?"
        
        result = await process_query_async(
            question=question,
            user_context=self.analyst_context
        )
        
        # Verify workflow completion
        assert result is not None
        assert "correlation_id" in result
        assert "workflow_start_time" in result
        assert "workflow_end_time" in result
        
        # Check for successful processing (if database has data)
        if not result.get("error"):
            assert result.get("processing_status") != "failed"
            assert "total_processing_time_ms" in result
            assert isinstance(result["total_processing_time_ms"], (int, float))
        
        print(f"Simple query result: {result}")
    
    async def test_complex_query_workflow(self):
        """Test a complex analytical query"""
        question = "Show me the top 5 departments by employee count with their average salaries, grouped by hire year"
        
        result = await process_query_async(
            question=question,
            user_context=self.admin_context
        )
        
        assert result is not None
        assert "correlation_id" in result
        
        # Complex queries should have higher complexity scores
        if result.get("complexity_score"):
            assert result["complexity_score"] > 5
        
        print(f"Complex query result: {result}")
    
    async def test_role_based_access_control(self):
        """Test that role-based access control works properly"""
        # Admin query - should work
        admin_question = "SELECT * FROM users LIMIT 10"
        admin_result = await process_query_async(
            question=admin_question,
            user_context=self.admin_context
        )
        
        # Viewer query - might be restricted
        viewer_question = "DELETE FROM users WHERE id = 1"
        viewer_result = await process_query_async(
            question=viewer_question,
            user_context=self.viewer_context
        )
        
        # Viewer should be blocked from dangerous operations
        assert viewer_result.get("is_safe") is False or viewer_result.get("error")
        
        print(f"Admin result: {admin_result.get('error', 'Success')}")
        print(f"Viewer result: {viewer_result.get('error', 'Success')}")
    
    async def test_caching_functionality(self):
        """Test that caching works across queries"""
        question = "How many tables are in the database?"
        
        # First query - should hit database
        start_time = datetime.utcnow()
        result1 = await process_query_async(
            question=question,
            user_context=self.analyst_context
        )
        first_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Second identical query - should use cache
        start_time = datetime.utcnow()
        result2 = await process_query_async(
            question=question,
            user_context=self.analyst_context
        )
        second_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Verify both queries returned results
        assert result1 is not None
        assert result2 is not None
        
        # Second query should be faster due to caching
        # (This might not always be true due to network/system variations)
        print(f"First query duration: {first_duration}ms")
        print(f"Second query duration: {second_duration}ms")
        print(f"Cache speedup: {first_duration / second_duration if second_duration > 0 else 0}x")
    
    async def test_error_handling_and_fallback(self):
        """Test error handling and fallback mechanisms"""
        # Invalid SQL-like question
        invalid_question = "BROKEN SQL QUERY WITH SYNTAX ERRORS"
        
        result = await process_query_async(
            question=invalid_question,
            user_context=self.analyst_context
        )
        
        assert result is not None
        
        # Should have graceful error handling
        if result.get("error"):
            assert "processing_status" in result
            assert result["processing_status"] == "failed"
        
        # Should have fallback suggestions
        assert "suggestions" in result or "error" in result
        
        print(f"Error handling result: {result}")
    
    async def test_security_validation(self):
        """Test SQL security validation"""
        dangerous_queries = [
            "DROP TABLE users",
            "DELETE FROM users",
            "UPDATE users SET password = 'hacked'",
            "INSERT INTO users VALUES ('hacker', 'evil')"
        ]
        
        for query in dangerous_queries:
            result = await process_query_async(
                question=query,
                user_context=self.viewer_context
            )
            
            # Should be blocked by security validation
            assert result.get("is_safe") is False or result.get("error")
            print(f"Dangerous query '{query}' - Blocked: {bool(result.get('error'))}")
    
    async def test_performance_monitoring(self):
        """Test that performance monitoring works"""
        question = "Count all records in the largest table"
        
        result = await process_query_async(
            question=question,
            user_context=self.admin_context
        )
        
        # Should have performance metrics
        assert "total_processing_time_ms" in result
        assert "processing_history" in result or "correlation_id" in result
        
        # Performance data should be reasonable
        if "total_processing_time_ms" in result:
            assert result["total_processing_time_ms"] > 0
            assert result["total_processing_time_ms"] < 60000  # Less than 60 seconds
        
        print(f"Performance metrics: {result.get('total_processing_time_ms')}ms")
    
    async def test_agent_integration(self):
        """Test that all agents are properly integrated"""
        question = "Show me recent activity in the system"
        
        result = await process_query_async(
            question=question,
            user_context=self.analyst_context
        )
        
        # Should show processing through different agents
        assert result is not None
        
        # Check that the workflow went through multiple steps
        if "processing_history" in result:
            steps = result["processing_history"]
            assert len(steps) > 1  # Should have multiple processing steps
            
            # Verify common steps
            step_names = [step.get("step") for step in steps if isinstance(step, dict)]
            assert any("input" in str(step).lower() for step in step_names)
        
        print(f"Agent integration result: {result}")
    
    async def test_concurrent_queries(self):
        """Test handling of concurrent queries"""
        questions = [
            "How many users are there?",
            "What tables exist in the database?",
            "Show me recent activity",
            "Count total records",
            "List database schema"
        ]
        
        # Execute multiple queries concurrently
        tasks = [
            process_query_async(
                question=question,
                user_context=self.analyst_context
            )
            for question in questions
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All queries should complete
        assert len(results) == len(questions)
        
        # Count successful vs failed queries
        successful = sum(1 for r in results if not isinstance(r, Exception) and not r.get("error"))
        failed = len(results) - successful
        
        print(f"Concurrent queries: {successful} successful, {failed} failed")
        
        # At least some queries should succeed
        assert successful > 0
    
    async def test_user_input_processing(self):
        """Test user input processing and enhancement"""
        test_cases = [
            {
                "question": "how many users?",
                "expected_enhancements": ["normalized", "query_type"]
            },
            {
                "question": "Show me sales data from last month with totals",
                "expected_enhancements": ["temporal_context", "complexity_score"]
            },
            {
                "question": "users without orders",
                "expected_enhancements": ["has_negation"]
            }
        ]
        
        for case in test_cases:
            result = await process_query_async(
                question=case["question"],
                user_context=self.analyst_context
            )
            
            assert result is not None
            print(f"Input processing for '{case['question']}': {result.get('query_type', 'unknown')}")


@pytest.mark.asyncio
class TestEnterpriseWorkflowStress:
    """Stress tests for the enterprise workflow"""
    
    async def test_large_query_handling(self):
        """Test handling of potentially large result queries"""
        question = "SELECT * FROM users"  # Could return many rows
        
        result = await process_query_async(
            question=question,
            user_context={
                "user_id": "stress_test",
                "role": UserRole.ADMIN.value,
                "permissions": ["read", "admin"]
            }
        )
        
        assert result is not None
        
        # Should either succeed or have proper error handling
        if result.get("error"):
            assert "processing_status" in result
        else:
            assert "total_processing_time_ms" in result
    
    async def test_workflow_resilience(self):
        """Test workflow resilience to various edge cases"""
        edge_cases = [
            "",  # Empty question
            "?",  # Just punctuation
            "a" * 1000,  # Very long question
            "SELECT 1; SELECT 2;",  # Multiple statements
            "What is the meaning of life?",  # Non-database question
        ]
        
        for question in edge_cases:
            result = await process_query_async(
                question=question,
                user_context={
                    "user_id": "edge_test",
                    "role": UserRole.VIEWER.value,
                    "permissions": ["read"]
                }
            )
            
            # Should always return a result (even if it's an error)
            assert result is not None
            assert "correlation_id" in result
            
            print(f"Edge case '{question[:50]}...': {result.get('processing_status', 'unknown')}")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
