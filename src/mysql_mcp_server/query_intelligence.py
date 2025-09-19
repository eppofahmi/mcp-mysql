import httpx
import asyncio
import json
import os
import hashlib
import time
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

        # Relationship caching system
        self.enable_cache = os.environ.get('ENABLE_RELATIONSHIP_CACHE', 'true').lower() == 'true'
        self.cache_ttl_minutes = int(os.environ.get('CACHE_TTL_MINUTES', '30'))
        self.max_cached_relationships = int(os.environ.get('MAX_CACHED_RELATIONSHIPS', '100'))

        # In-memory caches
        self._schema_cache = {}
        self._relationship_cache = {}
        self._schema_hash_cache = None
        self._last_schema_check = 0

        logger.info(f"QueryIntelligenceService initialized with caching {'enabled' if self.enable_cache else 'disabled'}")

    async def answer_database_question(self, question: str, user_context: dict = None) -> Dict[str, Any]:
        """
        Complete database question answering service with caching
        """
        try:
            logger.info(f"Processing database question: {question}")

            # 1. Get complete database context (with caching)
            schema_context = await self._get_complete_schema_context_cached()

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
                    "query_type": self._classify_query_type(sql_query),
                    "cache_used": self.enable_cache
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

    async def _get_complete_schema_context_cached(self) -> str:
        """Get comprehensive database schema information with caching"""
        config = get_db_config()

        with connect(**config) as conn:
            with conn.cursor() as cursor:
                # Get all tables
                cursor.execute("SHOW TABLES")
                tables = [table[0] for table in cursor.fetchall()]

                # Generate cache key
                cache_key = f"schema_{hashlib.md5(json.dumps(sorted(tables)).encode()).hexdigest()}"

                # Check if we should refresh cache
                if self._should_refresh_cache(cursor):
                    logger.info("Refreshing schema and relationship cache")
                    self._schema_cache.clear()
                    self._relationship_cache.clear()
                    self._last_schema_check = time.time()

                # Check cache first
                if self.enable_cache and cache_key in self._schema_cache:
                    cached_data = self._schema_cache[cache_key]
                    if time.time() - cached_data['timestamp'] < (self.cache_ttl_minutes * 60):
                        logger.info("Using cached schema context")
                        return cached_data['context']

                # Generate fresh schema context
                context = self._build_schema_context(cursor, tables)

                # Cache the result
                if self.enable_cache:
                    self._schema_cache[cache_key] = {
                        'timestamp': time.time(),
                        'context': context
                    }
                    logger.info(f"Cached schema context for {len(tables)} tables")

                return context

    def _build_schema_context(self, cursor, tables: list) -> str:
        """Build comprehensive schema context with relationships"""
        config = get_db_config()

        # Get configuration from environment
        preview_rows = int(os.environ.get('SCHEMA_PREVIEW_ROWS', '5'))
        enable_analysis = os.environ.get('ENABLE_DATA_ANALYSIS', 'true').lower() == 'true'
        enable_relationships = os.environ.get('ENABLE_RELATIONSHIP_DISCOVERY', 'true').lower() == 'true'
        max_columns = int(os.environ.get('MAX_PREVIEW_COLUMNS', '10'))

        schema_parts = [
            f"Database: {config['database']}",
            f"Available tables: {', '.join(tables)}",
            ""
        ]

        # Get enhanced schema for each table
        for table in tables:
            cursor.execute(f"DESCRIBE {table}")
            columns = cursor.fetchall()
            column_names = [col[0] for col in columns]

            schema_parts.append(f"Table: {table}")

            # Enhanced column information
            for col in columns:
                field, type_, null, key, default, extra = col
                key_info = f" ({key})" if key else ""
                null_info = " (nullable)" if null == 'YES' else " (required)"
                default_info = f" default='{default}'" if default else ""
                schema_parts.append(f"  - {field}: {type_}{key_info}{null_info}{default_info}")

            # Get row count
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cursor.fetchone()[0]
                schema_parts.append(f"  Total rows: {row_count}")
            except Exception:
                pass

            # Enhanced sample data
            self._add_sample_data(cursor, table, column_names, schema_parts, preview_rows, max_columns, enable_analysis)
            schema_parts.append("")

        # Relationship discovery with caching
        if enable_relationships and len(tables) > 1:
            relationships = self._get_relationships_cached(cursor, tables)
            if relationships:
                schema_parts.append("Potential table relationships:")
                schema_parts.extend([f"  {rel}" for rel in relationships])
                schema_parts.append("")

        return "\n".join(schema_parts)

    def _add_sample_data(self, cursor, table, column_names, schema_parts, preview_rows, max_columns, enable_analysis):
        """Add sample data to schema parts"""
        try:
            if len(column_names) > max_columns:
                display_columns = column_names[:max_columns]
                cursor.execute(f"SELECT {', '.join(display_columns)} FROM {table} LIMIT {preview_rows}")
                schema_parts.append(f"  Sample data (showing first {max_columns} columns):")
            else:
                cursor.execute(f"SELECT * FROM {table} LIMIT {preview_rows}")
                display_columns = column_names
                schema_parts.append("  Sample data:")

            sample_rows = cursor.fetchall()
            if sample_rows:
                schema_parts.append(f"    Columns: {' | '.join(display_columns)}")
                for i, row in enumerate(sample_rows, 1):
                    formatted_row = ' | '.join(str(val) if val is not None else 'NULL' for val in row)
                    schema_parts.append(f"    Row {i}: {formatted_row}")

                # Data analysis
                if enable_analysis and sample_rows:
                    analysis = self._analyze_sample_data(display_columns, sample_rows)
                    if analysis:
                        schema_parts.append("  Data insights:")
                        schema_parts.extend([f"    {insight}" for insight in analysis])
            else:
                schema_parts.append("    No data found")

        except Exception as e:
            schema_parts.append(f"    Could not retrieve sample data: {str(e)}")

    def _get_relationships_cached(self, cursor, tables: list) -> list:
        """Get relationships with caching"""
        # Try cached relationships first
        cached_relationships = self._get_cached_relationships(tables)
        if cached_relationships is not None:
            return cached_relationships

        # Generate fresh relationships
        relationships = self._discover_relationships(cursor, tables)

        # Cache the results
        self._cache_relationships(tables, relationships)
        return relationships

    def _get_cached_relationships(self, tables: list) -> Optional[list]:
        """Get cached relationships for a set of tables"""
        if not self.enable_cache:
            return None

        cache_key = hashlib.md5(json.dumps(sorted(tables)).encode()).hexdigest()
        cached_data = self._relationship_cache.get(cache_key)

        if cached_data:
            if time.time() - cached_data['timestamp'] < (self.cache_ttl_minutes * 60):
                logger.info(f"Using cached relationships for {len(tables)} tables")
                return cached_data['relationships']

        return None

    def _cache_relationships(self, tables: list, relationships: list):
        """Cache relationships for a set of tables"""
        if not self.enable_cache:
            return

        cache_key = hashlib.md5(json.dumps(sorted(tables)).encode()).hexdigest()

        # Manage cache size
        if len(self._relationship_cache) >= self.max_cached_relationships:
            oldest_key = min(self._relationship_cache.keys(),
                           key=lambda k: self._relationship_cache[k]['timestamp'])
            del self._relationship_cache[oldest_key]
            logger.info("Removed oldest relationship cache entry")

        self._relationship_cache[cache_key] = {
            'timestamp': time.time(),
            'relationships': relationships,
            'tables': tables
        }

        logger.info(f"Cached {len(relationships)} relationships for {len(tables)} tables")

    def _should_refresh_cache(self, cursor) -> bool:
        """Check if cache should be refreshed"""
        if not self.enable_cache:
            return True

        current_time = time.time()

        # Check TTL
        if current_time - self._last_schema_check > (self.cache_ttl_minutes * 60):
            logger.info("Cache TTL expired, refreshing")
            return True

        # Check schema changes
        if os.environ.get('CACHE_REFRESH_ON_SCHEMA_CHANGE', 'true').lower() == 'true':
            current_hash = self._get_schema_hash(cursor)
            if self._schema_hash_cache != current_hash:
                self._schema_hash_cache = current_hash
                logger.info("Schema change detected, refreshing cache")
                return True

        return False

    def _get_schema_hash(self, cursor) -> str:
        """Generate schema hash for cache invalidation"""
        try:
            cursor.execute("SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME, COLUMN_NAME")
            schema_info = cursor.fetchall()
            schema_string = json.dumps(schema_info, sort_keys=True)
            return hashlib.md5(schema_string.encode()).hexdigest()
        except Exception:
            # Fallback
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            fallback_string = f"{tables}_{int(time.time() // 3600)}"
            return hashlib.md5(fallback_string.encode()).hexdigest()

    # Import remaining methods from original file
    async def _generate_sql_with_ollama(self, question: str, schema_context: str) -> str:
        """Generate SQL using remote Ollama service"""
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
                        "temperature": 0.1,
                        "top_p": 0.9
                    }
                })

                if response.status_code != 200:
                    raise Exception(f"Ollama request failed with status {response.status_code}")

                result = response.json()
                sql_query = result.get("response", "").strip()
                sql_query = self._clean_sql_response(sql_query)

                if not sql_query:
                    raise Exception("Empty SQL query generated by Ollama")

                return sql_query

            except Exception as e:
                logger.error(f"Failed to generate SQL with Ollama: {str(e)}")
                raise Exception(f"Failed to generate SQL with Ollama: {str(e)}")

    def _clean_sql_response(self, sql_response: str) -> str:
        """Clean up SQL response from Ollama"""
        # Handle qwen3 thinking pattern
        if "<think>" in sql_response and "</think>" in sql_response:
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

        # Find first valid SQL statement
        lines = sql_response.split('\n')
        for line in lines:
            line = line.strip()
            if line and any(line.upper().startswith(cmd) for cmd in ['SELECT', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN']):
                sql_response = line
                break

        return sql_response.rstrip(';').strip()

    def _validate_query_safety(self, sql_query: str):
        """Validate query safety"""
        sql_upper = sql_query.upper().strip()

        allowed_starts = ['SELECT', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN']
        if not any(sql_upper.startswith(start) for start in allowed_starts):
            raise ValueError(f"Only {', '.join(allowed_starts)} queries are allowed")

        forbidden_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 'TRUNCATE', 'GRANT', 'REVOKE']
        for keyword in forbidden_keywords:
            if keyword in sql_upper:
                raise ValueError(f"Forbidden keyword '{keyword}' found in query")

        if ';' in sql_query and not sql_query.rstrip().endswith(';'):
            raise ValueError("Multiple statements not allowed")

    async def _execute_sql_safely(self, sql_query: str) -> str:
        """Execute SQL query safely"""
        config = get_db_config()

        with connect(**config) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql_query)

                if cursor.description is not None:
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()

                    if rows:
                        result_lines = [",".join(columns)]
                        result_lines.extend([",".join(str(item) if item is not None else "" for item in row) for row in rows])
                        return "\n".join(result_lines)
                    else:
                        return f"{','.join(columns)}\nNo data found"
                else:
                    return f"Query executed successfully. Rows affected: {cursor.rowcount}"

    # Additional helper methods
    def _analyze_sample_data(self, columns: list, rows: list) -> list:
        """Analyze sample data for insights"""
        insights = []
        if not rows:
            return insights

        for col_idx, col_name in enumerate(columns):
            values = [row[col_idx] for row in rows if row[col_idx] is not None]
            if not values:
                continue

            if all(isinstance(v, (int, float)) for v in values):
                min_val, max_val = min(values), max(values)
                insights.append(f"{col_name}: numeric range {min_val}-{max_val}")
            elif all(isinstance(v, str) for v in values):
                unique_count = len(set(values))
                if unique_count < len(values):
                    insights.append(f"{col_name}: {unique_count} unique values in sample")

        return insights[:3]

    def _discover_relationships(self, cursor, tables: list) -> list:
        """Discover relationships between tables"""
        relationships = []

        try:
            table_columns = {}
            for table in tables:
                cursor.execute(f"DESCRIBE {table}")
                columns = cursor.fetchall()
                table_columns[table] = [col[0] for col in columns]

            # Foreign key detection
            for table1 in tables:
                cols1 = table_columns[table1]
                for col in cols1:
                    if col.endswith('_id') and col != 'id':
                        referenced_table = col.replace('_id', '')
                        for table2 in tables:
                            if (table2.lower() == referenced_table.lower() and 'id' in table_columns[table2]):
                                relationships.append(f"JOIN: {table1}.{col} = {table2}.id")

        except Exception:
            pass

        return relationships[:5]

    def _format_for_llm_consumption(self, query_result: str) -> str:
        """Format results for LLM"""
        lines = query_result.strip().split('\n')
        if len(lines) <= 1:
            return query_result

        headers = lines[0].split(',')
        data_rows = lines[1:]

        if not data_rows or (len(data_rows) == 1 and "No data found" in data_rows[0]):
            return "No data found matching the query criteria."

        formatted_parts = [f"Found {len(data_rows)} record(s):", ""]

        display_rows = data_rows[:10]
        for i, row in enumerate(display_rows, 1):
            values = row.split(',')
            row_parts = [f"{header}: {value}" for header, value in zip(headers, values)]
            formatted_parts.append(f"Record {i}: {' | '.join(row_parts)}")

        if len(data_rows) > 10:
            formatted_parts.append(f"... and {len(data_rows) - 10} more records")

        return "\n".join(formatted_parts)

    def _count_rows(self, query_result: str) -> int:
        """Count data rows in result"""
        lines = query_result.strip().split('\n')
        return max(0, len(lines) - 1)

    def _extract_tables_from_sql(self, sql_query: str) -> list:
        """Extract table names from SQL"""
        import re
        pattern = r'(?:FROM|JOIN)\s+(\w+)'
        matches = re.findall(pattern, sql_query, re.IGNORECASE)
        return list(set(matches))

    def _classify_query_type(self, sql_query: str) -> str:
        """Classify query type"""
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