# Multiple Query Support

This document describes the enhanced multiple query functionality that allows executing multiple SQL statements in a single request.

## Overview

The system has been updated to support executing multiple SQL queries simultaneously, while maintaining security and safety measures. This enhancement allows users to request data from multiple tables or perform different operations in a single query request.

## Key Features

### 1. Multiple Statement Execution
- **Semicolon Separation**: Multiple SQL statements can be separated by semicolons
- **Sequential Execution**: Statements are executed in the order they appear
- **Individual Validation**: Each statement is validated separately for security
- **Structured Results**: Results are organized by statement index for clarity

### 2. Enhanced Security
- **Per-Statement Validation**: Each SQL statement is individually checked against forbidden keywords
- **Maintained Safety**: All existing security measures remain in place
- **Graceful Blocking**: Unsafe statements are blocked with clear error messages

### 3. Result Organization
- **Statement Indexing**: Each result set includes the statement index and original SQL
- **Row Count Tracking**: Number of rows returned for each statement
- **Mixed Operations**: Support for both SELECT and non-SELECT operations
- **Backward Compatibility**: Single queries work exactly as before

## Examples

### Basic Multiple Queries
```sql
SELECT * FROM patients LIMIT 5; 
SELECT * FROM doctors LIMIT 5;
```

### Mixed Operations
```sql
SELECT * FROM patients LIMIT 3; 
SELECT COUNT(*) FROM doctors; 
SELECT name FROM departments;
```

### Analytical Queries
```sql
SELECT COUNT(*) FROM patients; 
SELECT COUNT(*) FROM doctors; 
SELECT COUNT(*) FROM appointments;
```

## Result Structure

### Single Query (Backward Compatible)
```json
{
  "results": [
    {"patient_id": 1, "name": "John Doe", ...},
    {"patient_id": 2, "name": "Jane Roe", ...}
  ]
}
```

### Multiple Queries
```json
{
  "results": [
    {
      "statement_index": 1,
      "statement": "SELECT * FROM patients LIMIT 5",
      "results": [
        {"patient_id": 1, "name": "John Doe", ...},
        {"patient_id": 2, "name": "Jane Roe", ...}
      ],
      "row_count": 5
    },
    {
      "statement_index": 2,
      "statement": "SELECT COUNT(*) FROM doctors",
      "results": [{"COUNT(*)": 5}],
      "row_count": 1
    }
  ]
}
```

## Security Considerations

### Maintained Protections
- **Forbidden Keywords**: DROP, DELETE, UPDATE, INSERT, ALTER, etc. are still blocked
- **Individual Validation**: Each statement in a multi-query request is validated separately
- **Safe Execution**: Only SELECT and other read-only operations are allowed by default

### Enhanced Validation
- **Statement-Level Blocking**: If any statement in a multi-query request is unsafe, the entire request is blocked
- **Clear Error Messages**: Users receive specific information about which statement caused the security violation
- **Graceful Degradation**: The system can handle mixed safe/unsafe scenarios appropriately

## Implementation Details

### Modified Components

1. **DB Executor Agent** (`agents/db_executor.py`)
   - Splits SQL by semicolons
   - Executes statements sequentially
   - Organizes results by statement index

2. **Validator Agent** (`agents/validator.py`)
   - Validates each statement individually
   - Provides statement-specific error messages
   - Maintains security for all statements

3. **LLM Instructions** (`llm/gemini.py`)
   - Updated to allow multiple statements
   - Enhanced formatting guidelines for multiple results
   - Added examples for multi-query scenarios

### Backward Compatibility
- Single queries continue to work exactly as before
- Existing API endpoints remain unchanged
- Result format is backward compatible for single queries

## Usage Examples

### Natural Language Requests
Users can now make requests like:
- "Show me the first 5 rows from each table: patients, doctors, and hospitals"
- "Count the total number of records in patients, doctors, and appointments tables"
- "Show me the first 3 patients, count all doctors, and list all department names"

### Generated SQL
The system automatically generates appropriate multi-statement SQL:
```sql
-- For table exploration
SELECT * FROM patients LIMIT 5; 
SELECT * FROM doctors LIMIT 5; 
SELECT * FROM hospitals LIMIT 5;

-- For analytics
SELECT COUNT(*) FROM patients; 
SELECT COUNT(*) FROM doctors; 
SELECT COUNT(*) FROM appointments;

-- For mixed operations
SELECT * FROM patients LIMIT 3; 
SELECT COUNT(*) FROM doctors; 
SELECT name FROM departments;
```

## Testing

The functionality has been thoroughly tested with:
- Multiple SELECT statements
- Mixed query types (SELECT, COUNT, etc.)
- Security validation with dangerous statements
- Backward compatibility verification
- Error handling scenarios

See `test_multiple_queries.py` and `test_advanced_multiple_queries.py` for comprehensive test examples.

## Benefits

1. **Efficiency**: Reduce the number of API calls needed for complex data requests
2. **User Experience**: More natural language queries can be handled in a single request
3. **Performance**: Batch operations reduce connection overhead
4. **Flexibility**: Support for diverse query patterns and use cases
5. **Safety**: Maintained security while expanding functionality

## Limitations

- All statements must be read-only (SELECT operations)
- Forbidden operations (DROP, DELETE, etc.) are still blocked
- Large result sets may impact performance
- Transaction boundaries are not explicitly managed across statements

## Future Enhancements

Potential future improvements could include:
- Transaction support for related operations
- Result set size limits and pagination
- Performance optimization for large multi-query requests
- Enhanced error recovery and partial execution options