# SQL Query Retry Functionality

This document describes the intelligent retry mechanism that automatically attempts to improve SQL queries when they return no results.

## Overview

The system now includes an automatic retry mechanism that activates when SQL queries execute successfully but return no results. This helps handle cases where:

- Queries use non-existent values (e.g., department names that don't exist)
- Filters are too restrictive
- Exact string matches fail due to case sensitivity or typos
- JOIN conditions are overly complex

## How It Works

### 1. Automatic Detection
The system automatically detects when a query needs retry by checking:
- SQL executed successfully (`sql_executed = True`)
- Results are empty (`results = []` or all statements return 0 rows)
- Retry count is below the maximum limit (2 attempts)

### 2. Intelligent Analysis
When a retry is triggered, the system:
- Analyzes the failed SQL query
- Identifies common failure patterns
- Provides specific guidance for improvement
- Suggests alternative approaches

### 3. Enhanced Context
The retry agent provides the LLM with:
- Details about why the previous query failed
- Specific suggestions for improvement
- Alternative query patterns
- Context-aware recommendations

## Retry Flow

```
Initial Query → Execute → No Results? → Retry Agent → Enhanced Query → Execute → Still No Results? → Final Retry → Execute → Format Results
```

### Graph Flow
1. **SQL Writer** generates initial query
2. **Validator** checks safety
3. **Executor** runs query
4. **Router** detects empty results → routes to **Retry Agent**
5. **Retry Agent** analyzes failure and generates improved query
6. Process repeats up to 2 times
7. **Formatter** presents final results

## Retry Strategies

### 1. String Matching Improvements
- **From**: `WHERE name = 'Emergency Department'`
- **To**: `WHERE name LIKE '%Emergency%'`

### 2. Condition Relaxation
- **From**: Complex JOINs with restrictive WHERE clauses
- **To**: Simpler queries or removed restrictions

### 3. Multiple Query Approach
- **From**: Single complex query
- **To**: Multiple simpler queries to explore available data

### 4. Exploratory Queries
- **From**: Specific entity queries
- **To**: General queries to show what data exists

## Example Scenarios

### Scenario 1: Non-existent Department
**Original Query**: 
```sql
SELECT * FROM appointments a 
JOIN doctors d ON a.doctor_id = d.doctor_id 
JOIN departments dp ON d.department_id = dp.department_id 
WHERE dp.name = 'Emergency Department'
```

**Retry 1**: 
```sql
SELECT * FROM appointments a 
JOIN doctors d ON a.doctor_id = d.doctor_id 
JOIN departments dp ON d.department_id = dp.department_id 
WHERE dp.name LIKE '%Emergency%'
```

**Retry 2**: 
```sql
SELECT name FROM departments; 
SELECT * FROM appointments LIMIT 10;
```

### Scenario 2: Non-existent Patient Name
**Original Query**: 
```sql
SELECT * FROM patients WHERE name = 'Dr. John Smith'
```

**Retry 1**: 
```sql
SELECT * FROM patients WHERE name LIKE '%John%'
```

**Retry 2**: 
```sql
SELECT name FROM patients; 
SELECT * FROM patients;
```

## Configuration

### Retry Limits
- **Maximum Retries**: 2 attempts
- **Total Attempts**: 3 (initial + 2 retries)

### Retry Conditions
- Query executed successfully
- Results are empty (0 rows)
- Retry count below maximum
- No critical errors occurred

## Benefits

### 1. Improved User Experience
- Users get meaningful results even when initial queries fail
- Reduces frustration from "no results found" responses
- Provides alternative data when specific requests can't be fulfilled

### 2. Intelligent Problem Solving
- Automatically identifies and fixes common query issues
- Learns from failure patterns
- Suggests better approaches

### 3. Robust Query Handling
- Handles typos and case sensitivity issues
- Manages non-existent entity references
- Adapts to database content dynamically

### 4. Educational Value
- Shows users what data is actually available
- Demonstrates alternative query approaches
- Provides context about database structure

## Implementation Details

### New Components

1. **SQLRetryAgent** (`agents/sql_retry.py`)
   - Analyzes failed queries
   - Generates improvement suggestions
   - Provides enhanced context to LLM

2. **Enhanced Query Graph** (`graphs/query_graph.py`)
   - Added retry routing logic
   - Integrated retry node into workflow
   - Handles multiple query result formats

3. **State Management**
   - `retry_count`: Tracks number of retry attempts
   - `previous_sql_attempts`: Stores failed queries for learning

### Routing Logic
```python
def route_after_executor(state):
    if sql_executed and no_meaningful_results and retry_count < 2:
        return "retry_node"
    else:
        return "formatter_node"
```

## Monitoring and Debugging

### Log Messages
- `[SQLRetryAgent] Retry attempt X/2 for {dialect}...`
- `[SQLRetryAgent] Previous SQL failed: {sql}`
- `[QueryGraph] Execution successful but no meaningful results, routing to retry.`

### State Tracking
- Previous SQL attempts are stored in state
- Retry count is tracked and incremented
- Failure analysis is logged for debugging

## Future Enhancements

Potential improvements could include:
- Machine learning from successful retry patterns
- Database-specific retry strategies
- User feedback integration for retry effectiveness
- Advanced query optimization techniques
- Contextual learning from user interactions

## Compatibility

- ✅ **Backward Compatible**: Single queries work exactly as before
- ✅ **Multiple Queries**: Supports both single and multiple query formats
- ✅ **Security**: All retry queries go through the same validation process
- ✅ **Performance**: Minimal overhead for successful queries