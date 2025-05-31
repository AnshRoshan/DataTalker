"""
Enterprise User Input Agent for TalkToData

Handles user input processing, validation, and context enrichment
for enterprise-grade natural language database queries.
"""

import re
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import structlog

from core.config import settings
from core.cache import cache_manager
from core.monitoring import performance_tracker
from core.security import get_current_user_context

logger = structlog.get_logger(__name__)

class UserInputAgent:
    """
    Enterprise user input processor that validates, enriches, and normalizes
    user questions for the database query pipeline.
    """
    
    def __init__(self):
        self.query_patterns = self._load_query_patterns()
        self.domain_keywords = self._load_domain_keywords()
    
    def _load_query_patterns(self) -> Dict[str, str]:
        """Load common query patterns for classification"""
        return {
            "count": r"\b(how many|count|number of|total)\b",
            "filter": r"\b(where|with|having|filter|show me|find)\b",
            "aggregate": r"\b(sum|average|avg|min|max|total|count)\b",
            "temporal": r"\b(today|yesterday|this week|last month|between|since|before|after)\b",
            "comparison": r"\b(compare|versus|vs|difference|more than|less than|greater|smaller)\b",
            "ranking": r"\b(top|bottom|highest|lowest|best|worst|rank|order)\b",
            "trend": r"\b(trend|over time|growth|decline|change|pattern)\b"
        }
    
    def _load_domain_keywords(self) -> Dict[str, List[str]]:
        """Load domain-specific keywords for context enhancement"""
        return {
            "business": ["revenue", "profit", "sales", "customer", "order", "product"],
            "finance": ["transaction", "payment", "invoice", "account", "balance", "cost"],
            "hr": ["employee", "department", "salary", "hire", "performance", "team"],
            "analytics": ["metric", "kpi", "dashboard", "report", "analysis", "insight"]
        }
    
    async def process_input(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for processing user input
        """
        try:
            correlation_id = state.get("correlation_id", "unknown")
            user_context = state.get("user_context", {})
            
            with performance_tracker.track_operation("user_input_processing", correlation_id):
                question = state.get("question", "").strip()
                
                if not question:
                    logger.warning("Empty question received", correlation_id=correlation_id)
                    return {
                        **state,
                        "error": "Question cannot be empty",
                        "processing_status": "failed"
                    }
                
                # Process the question
                processed_result = await self._process_question(question, user_context, correlation_id)
                
                # Update state with processed information
                updated_state = {
                    **state,
                    **processed_result,
                    "original_question": question,
                    "processing_timestamp": datetime.utcnow().isoformat(),
                    "processing_status": "completed"
                }
                
                logger.info(
                    "User input processed successfully",
                    correlation_id=correlation_id,
                    question_length=len(question),
                    query_type=processed_result.get("query_type"),
                    complexity_score=processed_result.get("complexity_score")
                )
                
                return updated_state
                
        except Exception as e:
            logger.error(
                "Error processing user input",
                correlation_id=correlation_id,
                error=str(e),
                exc_info=True
            )
            return {
                **state,
                "error": f"Input processing failed: {str(e)}",
                "processing_status": "failed"
            }
    
    async def _process_question(self, question: str, user_context: Dict, correlation_id: str) -> Dict[str, Any]:
        """Process and analyze the user question"""
        
        # Check cache first
        cache_key = f"user_input:{hash(question)}:{user_context.get('user_id', 'anonymous')}"
        cached_result = await cache_manager.get_cached_data(cache_key, "user_input")
        
        if cached_result:
            logger.debug("Using cached input processing result", correlation_id=correlation_id)
            return cached_result
        
        # Normalize and clean the question
        normalized_question = self._normalize_question(question)
        
        # Analyze query characteristics
        analysis = await self._analyze_question(normalized_question, correlation_id)
        
        # Enhance with context
        enhanced_context = self._enhance_context(analysis, user_context)
        
        # Generate suggestions and warnings
        suggestions = self._generate_suggestions(analysis)
        warnings = self._check_for_warnings(analysis, user_context)
        
        result = {
            "question": normalized_question,
            "original_question": question,
            "query_type": analysis["query_type"],
            "complexity_score": analysis["complexity_score"],
            "domain_context": analysis["domain_context"],
            "temporal_context": analysis["temporal_context"],
            "entities_mentioned": analysis["entities"],
            "enhanced_context": enhanced_context,
            "suggestions": suggestions,
            "warnings": warnings,
            "requires_approval": self._requires_approval(analysis, user_context)
        }
        
        # Cache the result
        await cache_manager.cache_data(
            cache_key, 
            result, 
            "user_input", 
            ttl=settings.CACHE_USER_INPUT_TTL
        )
        
        return result
    
    def _normalize_question(self, question: str) -> str:
        """Normalize and clean the user question"""
        # Remove extra whitespace
        question = re.sub(r'\s+', ' ', question.strip())
        
        # Handle common abbreviations
        abbreviations = {
            r'\bw/\b': 'with',
            r'\bw/o\b': 'without',
            r'\betc\b': 'and others',
            r'\bye?a?r?\b': 'year',
            r'\bmon\b': 'month',
            r'\bpct\b': 'percent',
            r'\b%\b': 'percent'
        }
        
        for pattern, replacement in abbreviations.items():
            question = re.sub(pattern, replacement, question, flags=re.IGNORECASE)
        
        return question
    
    async def _analyze_question(self, question: str, correlation_id: str) -> Dict[str, Any]:
        """Analyze question characteristics and extract metadata"""
        
        # Classify query type
        query_type = self._classify_query_type(question)
        
        # Calculate complexity score
        complexity_score = self._calculate_complexity(question)
        
        # Extract entities and context
        entities = self._extract_entities(question)
        domain_context = self._identify_domain_context(question)
        temporal_context = self._extract_temporal_context(question)
        
        return {
            "query_type": query_type,
            "complexity_score": complexity_score,
            "entities": entities,
            "domain_context": domain_context,
            "temporal_context": temporal_context,
            "word_count": len(question.split()),
            "has_negation": self._has_negation(question),
            "has_multiple_conditions": self._has_multiple_conditions(question)
        }
    
    def _classify_query_type(self, question: str) -> str:
        """Classify the type of query based on patterns"""
        question_lower = question.lower()
        
        # Check patterns in order of specificity
        for query_type, pattern in self.query_patterns.items():
            if re.search(pattern, question_lower):
                return query_type
        
        # Default classification based on question words
        if any(q in question_lower for q in ["what", "which", "show"]):
            return "select"
        elif any(q in question_lower for q in ["how many", "count"]):
            return "count"
        else:
            return "general"
    
    def _calculate_complexity(self, question: str) -> float:
        """Calculate complexity score based on various factors"""
        score = 0.0
        question_lower = question.lower()
        
        # Base complexity factors
        word_count = len(question.split())
        score += min(word_count * 0.1, 2.0)  # Max 2 points for length
        
        # Conditional complexity
        conditions = ["where", "and", "or", "if", "when", "but"]
        score += sum(1 for cond in conditions if cond in question_lower) * 0.5
        
        # Aggregation complexity
        aggregations = ["sum", "count", "average", "max", "min", "group by"]
        score += sum(1 for agg in aggregations if agg in question_lower) * 0.8
        
        # Temporal complexity
        temporal_indicators = ["between", "since", "before", "after", "during"]
        score += sum(1 for temp in temporal_indicators if temp in question_lower) * 0.6
        
        # Join complexity (implied)
        join_indicators = ["and", "with", "from", "related", "associated"]
        score += sum(1 for join in join_indicators if join in question_lower) * 0.4
        
        return min(score, 10.0)  # Cap at 10
    
    def _extract_entities(self, question: str) -> List[str]:
        """Extract potential table/column entities from the question"""
        # Simple entity extraction - in production, use NER
        entities = []
        
        # Common database entity patterns
        entity_patterns = [
            r'\b[a-z_]+_id\b',  # ID fields
            r'\b[a-z_]+_date\b',  # Date fields
            r'\b[a-z_]+_name\b',  # Name fields
            r'\b[a-z_]+_code\b',  # Code fields
        ]
        
        for pattern in entity_patterns:
            matches = re.findall(pattern, question.lower())
            entities.extend(matches)
        
        return list(set(entities))
    
    def _identify_domain_context(self, question: str) -> List[str]:
        """Identify domain context based on keywords"""
        question_lower = question.lower()
        identified_domains = []
        
        for domain, keywords in self.domain_keywords.items():
            if any(keyword in question_lower for keyword in keywords):
                identified_domains.append(domain)
        
        return identified_domains
    
    def _extract_temporal_context(self, question: str) -> Dict[str, Any]:
        """Extract temporal context from the question"""
        question_lower = question.lower()
        
        temporal_context = {
            "has_temporal": False,
            "time_range": None,
            "relative_time": None,
            "specific_dates": []
        }
        
        # Check for relative time indicators
        relative_patterns = {
            "today": "current_day",
            "yesterday": "previous_day",
            "this week": "current_week",
            "last week": "previous_week",
            "this month": "current_month",
            "last month": "previous_month",
            "this year": "current_year",
            "last year": "previous_year"
        }
        
        for pattern, time_type in relative_patterns.items():
            if pattern in question_lower:
                temporal_context["has_temporal"] = True
                temporal_context["relative_time"] = time_type
                break
        
        # Check for date ranges
        if any(word in question_lower for word in ["between", "from", "to", "since", "until"]):
            temporal_context["has_temporal"] = True
            temporal_context["time_range"] = "custom_range"
        
        return temporal_context
    
    def _has_negation(self, question: str) -> bool:
        """Check if question contains negation"""
        negation_words = ["not", "no", "never", "without", "except", "exclude"]
        return any(neg in question.lower() for neg in negation_words)
    
    def _has_multiple_conditions(self, question: str) -> bool:
        """Check if question has multiple conditions"""
        condition_words = ["and", "or", "but", "also", "plus", "including"]
        return sum(1 for word in condition_words if word in question.lower()) >= 2
    
    def _enhance_context(self, analysis: Dict, user_context: Dict) -> Dict[str, Any]:
        """Enhance context based on user profile and analysis"""
        enhanced = {
            "user_role": user_context.get("role", "viewer"),
            "user_departments": user_context.get("departments", []),
            "preferred_metrics": user_context.get("preferred_metrics", []),
            "data_access_level": user_context.get("data_access_level", "limited")
        }
        
        # Add role-specific enhancements
        if enhanced["user_role"] == "admin":
            enhanced["can_access_sensitive"] = True
            enhanced["can_modify_data"] = True
        elif enhanced["user_role"] == "analyst":
            enhanced["can_access_sensitive"] = False
            enhanced["can_modify_data"] = False
        else:  # viewer
            enhanced["can_access_sensitive"] = False
            enhanced["can_modify_data"] = False
        
        return enhanced
    
    def _generate_suggestions(self, analysis: Dict) -> List[str]:
        """Generate helpful suggestions based on analysis"""
        suggestions = []
        
        if analysis["complexity_score"] > 7:
            suggestions.append("Consider breaking this into simpler questions for better results")
        
        if analysis["query_type"] == "general":
            suggestions.append("Try being more specific about what data you want to see")
        
        if not analysis["temporal_context"]["has_temporal"] and analysis["query_type"] in ["trend", "comparison"]:
            suggestions.append("Consider specifying a time period for more meaningful results")
        
        if len(analysis["entities"]) == 0:
            suggestions.append("Try mentioning specific tables or fields you're interested in")
        
        return suggestions
    
    def _check_for_warnings(self, analysis: Dict, user_context: Dict) -> List[str]:
        """Check for potential warnings or issues"""
        warnings = []
        
        if analysis["complexity_score"] > 8:
            warnings.append("High complexity query - may take longer to process")
        
        if analysis["has_negation"] and analysis["complexity_score"] > 5:
            warnings.append("Complex negation queries may require manual review")
        
        # Role-based warnings
        user_role = user_context.get("role", "viewer")
        if analysis["query_type"] in ["aggregate", "trend"] and user_role == "viewer":
            warnings.append("Advanced analytics may require analyst privileges")
        
        return warnings
    
    def _requires_approval(self, analysis: Dict, user_context: Dict) -> bool:
        """Determine if query requires approval"""
        user_role = user_context.get("role", "viewer")
        
        # High complexity queries for non-admin users
        if analysis["complexity_score"] > 8 and user_role != "admin":
            return True
        
        # Queries with potential performance impact
        if analysis["query_type"] in ["trend", "comparison"] and user_role == "viewer":
            return True
        
        return False
    
    # Synchronous wrapper for backward compatibility
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous wrapper for the async process_input method"""
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
                    future = executor.submit(asyncio.run, self.process_input(state))
                    return future.result()
            else:
                # Run in the current loop
                return loop.run_until_complete(self.process_input(state))
                
        except Exception as e:
            logger.error(f"Error in UserInputAgent: {str(e)}", exc_info=True)
            return {
                **state,
                "error": f"User input processing failed: {str(e)}",
                "processing_status": "failed"
            }