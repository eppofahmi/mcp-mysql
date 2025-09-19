import httpx
import asyncio
import json
import os
from typing import Dict, Any, Optional
from .server import get_db_config
from mysql.connector import connect, Error
import logging

logger = logging.getLogger(__name__)

class QueryIntelligenceService:
    def __init__(self):
        # Use environment configuration for Ollama
        self.ollama_url = os.environ.get('OLLAMA_BASE_URL', "http://192.168.1.127:11434")
        self.ollama_model = os.environ.get('OLLAMA_MODEL', "qwen3")

    async def answer_database_question(self, question: str, user_context: dict = None) -> Dict[str, Any]:
        """
        Complete database question answering service
        Input: Natural language question
        Output: Structured response with data and metadata
        """
        try:
            logger.info(f"Processing database question: {question}")

            # 1. Get complete database context
            schema_context = await self._get_complete_schema_context()

            # 2. Generate SQL using remote Ollama
            sql_query = await self._generate_sql_with_ollama(question, schema_context)
            logger.info(f"Generated SQL: {sql_query}")

            # 3. Validate query safety
            self._validate_query_safety(sql_query)

            # 4. Execute query
            query_result = await self._execute_sql_safely(sql_query)

            # 5. Format response
            return {
                "success": True,
                "question": question,
                "sql_query": sql_query,
                "data": query_result,
                "formatted_response": self._format_for_llm_consumption(query_result),
                "metadata": {
                    "rows_returned": self._count_rows(query_result),
                    "tables_accessed": self._extract_tables_from_sql(sql_query),
                    "query_type": self._classify_query_type(sql_query)
                }
            }

        except Exception as e:
            logger.error(f"Error processing database question: {str(e)}")
            return {
                "success": False,
                "question": question,
                "error": str(e),
                "error_type": type(e).__name__
            }

    async def _get_complete_schema_context(self) -> str:
        """Get comprehensive database schema information"""
        config = get_db_config()

        with connect(**config) as conn:
            with conn.cursor() as cursor:
                # Get all tables
                cursor.execute("SHOW TABLES")
                tables = [table[0] for table in cursor.fetchall()]

                schema_parts = [
                    f"Database: {config['database']}",
                    f"Available tables: {', '.join(tables)}",
                    ""
                ]

                # Get schema for each table
                for table in tables:
                    cursor.execute(f"DESCRIBE {table}")
                    columns = cursor.fetchall()

                    schema_parts.append(f"Table: {table}")
                    for col in columns:
                        field, type_, null, key, default, extra = col
                        key_info = f"({key})" if key else ""
                        schema_parts.append(f"  - {field}: {type_} {key_info}")

                    # Get sample data
                    try:
                        cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                        sample_rows = cursor.fetchall()
                        if sample_rows:
                            schema_parts.append(f"  Sample data: {sample_rows[0]}")
                    except Exception as e:
                        schema_parts.append(f"  Sample data: Could not retrieve ({str(e)})")

                    schema_parts.append("")

                return "\n".join(schema_parts)

    async def _generate_sql_with_ollama(self, question: str, schema_context: str) -> str:
        """Generate SQL using remote Ollama service"""

        # Get system prompt from environment variable
        sql_prompt_template = os.environ.get('OLLAMA_SQL_SYSTEM_PROMPT',
            """You are a SQL expert for MySQL/TiDB. Convert the natural language question to a safe, accurate SQL query.

DATABASE SCHEMA:
{schema_context}

RULES:
- Only SELECT, SHOW, DESCRIBE queries (READ-ONLY)
- Never INSERT, UPDATE, DELETE, DROP, ALTER
- Use proper table and column names from schema above
- Include LIMIT clause (max 100 rows unless specifically requested)
- Use proper MySQL syntax
- If question is unclear, make reasonable assumptions based on available data

EXAMPLES:
- "How many users?" → "SELECT COUNT(*) FROM users"
- "Recent sales" → "SELECT * FROM sales ORDER BY date DESC LIMIT 20"
- "Top products" → "SELECT product, COUNT(*) as sales_count FROM sales GROUP BY product ORDER BY sales_count DESC LIMIT 10"

USER QUESTION: {question}

Generate only the SQL query, no explanation:""")

        sql_prompt = sql_prompt_template.format(
            schema_context=schema_context,
            question=question
        )

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.post(f"{self.ollama_url}/api/generate", json={
                    "model": self.ollama_model,
                    "prompt": sql_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for consistent SQL generation
                        "top_p": 0.9
                    }
                })

                if response.status_code != 200:
                    raise Exception(f"Ollama request failed with status {response.status_code}")

                result = response.json()
                sql_query = result.get("response", "").strip()

                # Clean up the response
                sql_query = self._clean_sql_response(sql_query)

                if not sql_query:
                    raise Exception("Empty SQL query generated by Ollama")

                return sql_query

            except Exception as e:
                logger.error(f"Failed to generate SQL with Ollama: {str(e)}")
                raise Exception(f"Failed to generate SQL with Ollama: {str(e)}")

    def _clean_sql_response(self, sql_response: str) -> str:
        """Clean up SQL response from Ollama"""
        # Handle qwen3 thinking pattern - remove <think>...</think> blocks
        if "<think>" in sql_response and "</think>" in sql_response:
            # Extract content after </think>
            sql_response = sql_response.split("</think>")[1].strip()

        # Remove markdown code blocks
        if "```sql" in sql_response:
            sql_response = sql_response.split("```sql")[1].split("```")[0]
        elif "```" in sql_response:
            parts = sql_response.split("```")
            if len(parts) >= 2:
                sql_response = parts[1]

        # Remove common prefixes
        prefixes_to_remove = ["Query:", "SQL:", "Answer:", "Result:", "SELECT:", "SHOW:", "DESCRIBE:"]
        for prefix in prefixes_to_remove:
            if sql_response.startswith(prefix):
                sql_response = sql_response[len(prefix):].strip()

        # Split by lines and find the first valid SQL statement
        lines = sql_response.split('\n')
        valid_sql_line = None

        for line in lines:
            line = line.strip()
            if line and any(line.upper().startswith(cmd) for cmd in ['SELECT', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN']):
                valid_sql_line = line
                break

        if valid_sql_line:
            sql_response = valid_sql_line
        else:
            # If no valid SQL found, take the first non-empty line
            for line in lines:
                line = line.strip()
                if line:
                    sql_response = line
                    break

        # Remove trailing semicolon if present (we'll add it back when executing)
        sql_response = sql_response.rstrip(';').strip()

        return sql_response

    def _validate_query_safety(self, sql_query: str):
        """Validate that the query is safe to execute"""
        sql_upper = sql_query.upper().strip()

        # Check for allowed operations
        allowed_starts = ['SELECT', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN']
        if not any(sql_upper.startswith(start) for start in allowed_starts):
            raise ValueError(f"Only {', '.join(allowed_starts)} queries are allowed. Got: {sql_query[:50]}")

        # Check for forbidden operations
        forbidden_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 'TRUNCATE', 'GRANT', 'REVOKE']
        for keyword in forbidden_keywords:
            if keyword in sql_upper:
                raise ValueError(f"Forbidden keyword '{keyword}' found in query")

        # Basic SQL injection protection
        if ';' in sql_query and not sql_query.rstrip().endswith(';'):
            raise ValueError("Multiple statements not allowed")

    async def _execute_sql_safely(self, sql_query: str) -> str:
        """Execute SQL query safely and return formatted results"""
        config = get_db_config()

        with connect(**config) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql_query)

                if cursor.description is not None:
                    # Query returns results
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()

                    # Format as CSV
                    if rows:
                        result_lines = [",".join(columns)]
                        result_lines.extend([",".join(str(item) if item is not None else "" for item in row) for row in rows])
                        return "\n".join(result_lines)
                    else:
                        return f"{','.join(columns)}\nNo data found"
                else:
                    # Non-SELECT query (SHOW, DESCRIBE, etc.)
                    return f"Query executed successfully. Rows affected: {cursor.rowcount}"

    def _format_for_llm_consumption(self, query_result: str) -> str:
        """Format database results for LLM consumption"""
        lines = query_result.strip().split('\n')

        if len(lines) <= 1:
            return query_result

        # Parse CSV format
        headers = lines[0].split(',')
        data_rows = lines[1:]

        if not data_rows or (len(data_rows) == 1 and "No data found" in data_rows[0]):
            return "No data found matching the query criteria."

        # Create human-readable format
        formatted_parts = [
            f"Found {len(data_rows)} record(s):",
            ""
        ]

        # Add formatted rows (limit to first 10 for readability)
        display_rows = data_rows[:10]
        for i, row in enumerate(display_rows, 1):
            values = row.split(',')
            row_parts = []
            for header, value in zip(headers, values):
                row_parts.append(f"{header}: {value}")
            formatted_parts.append(f"Record {i}: {' | '.join(row_parts)}")

        if len(data_rows) > 10:
            formatted_parts.append(f"... and {len(data_rows) - 10} more records")

        return "\n".join(formatted_parts)

    def _count_rows(self, query_result: str) -> int:
        """Count number of data rows in result"""
        lines = query_result.strip().split('\n')
        return max(0, len(lines) - 1)  # Subtract header row

    def _extract_tables_from_sql(self, sql_query: str) -> list:
        """Extract table names from SQL query (basic implementation)"""
        import re
        # Simple regex to find table names after FROM and JOIN
        pattern = r'(?:FROM|JOIN)\s+(\w+)'
        matches = re.findall(pattern, sql_query, re.IGNORECASE)
        return list(set(matches))

    def _classify_query_type(self, sql_query: str) -> str:
        """Classify the type of query"""
        sql_upper = sql_query.upper().strip()
        if sql_upper.startswith('SELECT'):
            if 'COUNT(' in sql_upper:
                return "count"
            elif 'GROUP BY' in sql_upper:
                return "aggregation"
            elif 'ORDER BY' in sql_upper:
                return "sorted_data"
            else:
                return "data_retrieval"
        elif sql_upper.startswith('SHOW'):
            return "schema_info"
        elif sql_upper.startswith(('DESCRIBE', 'DESC')):
            return "table_schema"
        else:
            return "other"

# Global instance
query_intelligence = QueryIntelligenceService()