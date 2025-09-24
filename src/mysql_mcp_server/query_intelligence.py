import httpx
import asyncio
import json
import os
import hashlib
import time
from typing import Dict, Any, Optional, List, Tuple
from .server import get_db_config
from mysql.connector import connect, Error
import logging

# Import AWS-inspired validation components
try:
    from .query_validation import HealthcareQueryValidator, QuerySelfCorrection, ValidationLevel
except ImportError:
    # Fallback if validation module isn't available
    HealthcareQueryValidator = None
    QuerySelfCorrection = None
    ValidationLevel = None

# Initialize logger first
logger = logging.getLogger(__name__)

# Import our healthcare schema knowledge service
try:
    from .schema_knowledge import SchemaKnowledgeService
except ImportError:
    logger.warning("SchemaKnowledgeService not available, falling back to basic schema discovery")
    SchemaKnowledgeService = None

# Import vector knowledge service for healthcare context
try:
    from .vector_knowledge_service import VectorKnowledgeService
except ImportError:
    logger.warning("VectorKnowledgeService not available")
    VectorKnowledgeService = None

class QueryIntelligenceService:
    def __init__(self):
        # Use environment configuration for Ollama
        self.ollama_url = os.environ.get('OLLAMA_BASE_URL', "http://192.168.1.127:11434")
        self.ollama_model = os.environ.get('OLLAMA_MODEL', "qwen3")

        # Healthcare schema knowledge integration
        self.use_healthcare_context = os.environ.get('USE_HEALTHCARE_CONTEXT', 'true').lower() == 'true'
        self.schema_knowledge_path = os.environ.get('SCHEMA_KNOWLEDGE_PATH', 'database_knowledge/')
        self.enable_vector_search = os.environ.get('ENABLE_VECTOR_SEARCH', 'true').lower() == 'true'

        # Initialize vector knowledge service if available (new approach)
        self.vector_knowledge = None
        if VectorKnowledgeService and self.enable_vector_search and self.use_healthcare_context:
            try:
                self.vector_knowledge = VectorKnowledgeService()
                logger.info("Healthcare vector knowledge service initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize vector knowledge service: {e}")
                self.vector_knowledge = None

        # Initialize schema knowledge service if available (fallback)
        self.schema_knowledge = None
        if SchemaKnowledgeService and self.use_healthcare_context and not self.vector_knowledge:
            try:
                self.schema_knowledge = SchemaKnowledgeService(self.schema_knowledge_path)
                logger.info("Healthcare schema knowledge service initialized successfully (fallback mode)")
            except Exception as e:
                logger.warning(f"Failed to initialize schema knowledge service: {e}")
                self.schema_knowledge = None

        # Relationship caching system (fallback for basic mode)
        self.enable_cache = os.environ.get('ENABLE_RELATIONSHIP_CACHE', 'true').lower() == 'true'
        self.cache_ttl_minutes = int(os.environ.get('CACHE_TTL_MINUTES', '30'))
        self.max_cached_relationships = int(os.environ.get('MAX_CACHED_RELATIONSHIPS', '100'))

        # In-memory caches
        self._schema_cache = {}
        self._relationship_cache = {}
        self._schema_hash_cache = None
        self._last_schema_check = 0

        # Initialize AWS-inspired validation system (local-only)
        self.enable_validation = os.environ.get('ENABLE_QUERY_VALIDATION', 'true').lower() == 'true'
        self.query_validator = None
        self.query_self_correction = None

        if HealthcareQueryValidator and self.enable_validation:
            try:
                self.query_validator = HealthcareQueryValidator()
                self.query_self_correction = QuerySelfCorrection(self.query_validator)
                logger.info("AWS-inspired healthcare query validation system initialized (local)")
            except Exception as e:
                logger.warning(f"Failed to initialize query validation: {e}")
                self.query_validator = None
                self.query_self_correction = None

        # Determine mode based on available services
        validation_status = " + validation" if self.query_validator else ""
        if self.vector_knowledge:
            mode = f"healthcare-aware (vector search){validation_status}"
        elif self.schema_knowledge:
            mode = f"healthcare-aware (full context){validation_status}"
        else:
            mode = f"basic{validation_status}"

        logger.info(f"QueryIntelligenceService initialized in {mode} mode with caching {'enabled' if self.enable_cache else 'disabled'}")

    async def answer_database_question(self, question: str, user_context: dict = None) -> Dict[str, Any]:
        """
        Complete database question answering service with caching and query planning
        """
        try:
            logger.info(f"Processing database question: {question}")

            # 1. Get healthcare-aware database context
            schema_context = await self._get_schema_context(question=question)

            # 2. Analyze question for multi-table requirements (enhanced with healthcare knowledge)
            query_plan = self._analyze_query_requirements(question, schema_context)
            logger.info(f"Query plan: {query_plan}")

            # 3. Generate enhanced schema context for multi-table queries
            if query_plan['requires_multiple_tables']:
                enhanced_context = self._enhance_context_for_multitable(schema_context, query_plan)
            else:
                enhanced_context = schema_context

            # 4. Generate SQL using remote Ollama with enhanced context
            sql_query = await self._generate_sql_with_ollama(question, enhanced_context)
            logger.info(f"Generated SQL: {sql_query}")

            # 4.5. AWS-Inspired Multi-Stage Validation & Self-Correction (Local)
            validation_results = []
            if self.query_validator and self.query_self_correction:
                try:
                    # Apply AWS-inspired self-correction
                    corrected_sql, validation_results = self.query_self_correction.auto_correct_query(sql_query, question)

                    if corrected_sql != sql_query:
                        logger.info(f"Query auto-corrected. Original length: {len(sql_query)}, Corrected length: {len(corrected_sql)}")
                        sql_query = corrected_sql

                    # Log validation insights
                    critical_issues = [r for r in validation_results if r.level.value == 'critical']
                    if critical_issues:
                        logger.warning(f"Critical validation issues detected: {len(critical_issues)}")

                except Exception as e:
                    logger.warning(f"Validation/correction failed: {e}")

            # 5. Validate query safety
            self._validate_query_safety(sql_query)

            # 6. Execute query
            query_result = await self._execute_sql_safely(sql_query)

            # 7. Format response
            # Healthcare-aware query validation and enhancement
            tables_accessed = self._extract_tables_from_sql(sql_query)
            validation_result = None
            suggestions = []

            # Use vector knowledge for enhanced validation if available
            if self.vector_knowledge and question:
                try:
                    related_tables = await self.vector_knowledge.get_related_tables(question)
                    if related_tables:
                        suggestions = [f"Consider querying related tables: {', '.join(related_tables[:3])}"]
                except Exception as e:
                    logger.warning(f"Failed to get vector-based suggestions: {e}")

            # Fallback to schema knowledge validation
            elif self.schema_knowledge:
                validation_result = self.schema_knowledge.validate_healthcare_query(sql_query, tables_accessed)
                if tables_accessed:
                    suggestions = self.schema_knowledge.suggest_related_queries(tables_accessed[0])

            return {
                "success": True,
                "question": question,
                "sql_query": sql_query,
                "data": query_result,
                "formatted_response": self._format_for_llm_consumption(query_result),
                "query_plan": query_plan,
                "metadata": {
                    "rows_returned": self._count_rows(query_result),
                    "tables_accessed": tables_accessed,
                    "query_type": self._classify_query_type(sql_query),
                    "cache_used": self.enable_cache,
                    "complexity": query_plan['complexity'],
                    "healthcare_validation": validation_result,
                    "related_suggestions": suggestions[:3] if suggestions else []  # Limit to 3 suggestions
                }
            }

        except Exception as e:
            logger.error(f"Error processing database question: {str(e)}")

            # Enhanced error handling with user guidance
            error_message = str(e)
            guidance = await self._provide_query_guidance(question, error_message, schema_context)

            return {
                "success": False,
                "question": question,
                "error": error_message,
                "error_type": type(e).__name__,
                "guidance": guidance,
                "formatted_response": self._format_guidance_response(question, guidance, error_message)
            }

    async def _get_schema_context(self, tables: List[str] = None, question: str = None) -> str:
        """Get schema context - vector search if available, otherwise healthcare-aware or basic"""
        if self.vector_knowledge:
            return await self._get_vector_schema_context(question)
        elif self.schema_knowledge:
            return await self._get_healthcare_schema_context(tables, question)
        else:
            return await self._get_complete_schema_context_cached()

    async def _get_vector_schema_context(self, question: str) -> str:
        """Get healthcare context using vector search (optimal approach)"""
        try:
            if not self.vector_knowledge.initialized:
                await self.vector_knowledge.initialize()
                # Load healthcare knowledge on first use
                await self.vector_knowledge.load_healthcare_knowledge(self.schema_knowledge_path)

            # Get focused context based on question
            context = await self.vector_knowledge.build_context_from_search(question, max_context_length=1500)
            logger.info("Built vector-based healthcare context")
            logger.debug(f"Vector context: {context[:800]}...")
            return context

        except Exception as e:
            logger.warning(f"Failed to build vector context: {e}, falling back to basic context")
            return await self._get_complete_schema_context_cached()

    async def _get_healthcare_schema_context(self, tables: List[str] = None, question: str = None) -> str:
        """Get healthcare-aware schema context using our knowledge service"""
        try:
            # If no specific tables provided, analyze question to determine relevant tables
            if not tables and question:
                tables = await self._identify_relevant_tables(question)

            # Build comprehensive healthcare context
            context = await self.schema_knowledge.build_healthcare_context(tables, question)
            logger.info(f"Built healthcare context for tables: {tables}")
            return context
        except Exception as e:
            logger.warning(f"Failed to build healthcare context: {e}, falling back to basic context")
            return await self._get_complete_schema_context_cached()

    async def _identify_relevant_tables(self, question: str) -> List[str]:
        """Identify relevant tables from the question using healthcare knowledge"""
        # Use vector knowledge for table identification if available
        if self.vector_knowledge:
            try:
                if not self.vector_knowledge.initialized:
                    await self.vector_knowledge.initialize()
                return await self.vector_knowledge.get_related_tables(question)
            except Exception as e:
                logger.warning(f"Failed to use vector knowledge for table identification: {e}")

        # Fallback to schema knowledge or basic approach
        if not self.schema_knowledge:
            return []

        question_lower = question.lower()
        relevant_tables = set()

        # Check for explicit table mentions or healthcare domain terms
        healthcare_terms = {
            'patient': ['pasien'],
            'doctor': ['dokter'],
            'visit': ['reg_periksa'],
            'diagnosis': ['diagnosa_pasien', 'penyakit'],
            'treatment': ['rawat_jl_dr', 'rawat_inap_dr'],
            'lab': ['periksa_lab'],
            'radiology': ['periksa_radiologi'],
            'surgery': ['operasi'],
            'medication': ['resep_dokter', 'obat_racikan'],
            'billing': ['nota_jalan', 'nota_inap'],
            'insurance': ['bridging_sep', 'penjab'],
            'room': ['kamar_inap', 'kamar', 'bangsal']
        }

        # Find relevant tables based on question content
        for domain, tables in healthcare_terms.items():
            if domain in question_lower or any(table in question_lower for table in tables):
                relevant_tables.update(tables)

        # If specific table names are mentioned, add them
        for table_name in self.schema_knowledge.table_info.keys():
            if table_name in question_lower:
                relevant_tables.add(table_name)

        # If no specific tables identified, provide core healthcare tables
        if not relevant_tables:
            relevant_tables = {'pasien', 'reg_periksa', 'dokter', 'diagnosa_pasien'}

        return list(relevant_tables)

    async def _get_complete_schema_context_cached(self) -> str:
        """Get comprehensive database schema information with caching (fallback method)"""
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

        # Enhanced relationship discovery with join paths for multi-table queries
        if enable_relationships and len(tables) > 1:
            relationships = self._get_relationships_cached(cursor, tables)
            join_paths = self._generate_join_paths(cursor, tables)

            if relationships:
                schema_parts.append("Table relationships:")
                schema_parts.extend([f"  {rel}" for rel in relationships])
                schema_parts.append("")

            if join_paths:
                schema_parts.append("MULTI-TABLE JOIN PATTERNS:")
                for path in join_paths:
                    schema_parts.append(f"  {path}")
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
        env_prompt = os.environ.get('OLLAMA_SQL_SYSTEM_PROMPT')
        logger.debug(f"Environment prompt loaded: {env_prompt is not None}")
        logger.debug(f"Environment prompt length: {len(env_prompt) if env_prompt else 0}")

        sql_prompt_template = env_prompt or """You are an expert MySQL query generator. Convert the question to a valid SQL query using ONLY the database schema provided below.

DATABASE SCHEMA:
{schema_context}

CRITICAL RULES:
1. ONLY generate SELECT, SHOW, or DESCRIBE queries (READ-ONLY)
2. NEVER use INSERT, UPDATE, DELETE, DROP, ALTER or any write operations
3. Use EXACTLY the table names and column names from the schema above
4. Use EXACTLY the column names shown in the schema - do not guess or invent column names
5. NEVER use table aliases (like d, p, r) - always use full table names
6. Always include LIMIT clause (default 100)
7. Only reference tables and columns that exist in the provided schema

STRICT SCHEMA ADHERENCE:
- Look at the "Available tables" list in the schema
- Look at the column names under each table description
- Use the exact spelling and case of table names and column names
- If a table or column doesn't exist in the schema, do not use it

EXAMPLES USING ACTUAL SCHEMA:
If schema shows "Table: dokter" with columns "kd_dokter, nm_dokter":
✅ CORRECT: SELECT dokter.nm_dokter FROM dokter LIMIT 10
❌ WRONG: SELECT d.nm_dokter FROM dokter d LIMIT 10
❌ WRONG: SELECT dokter.nama_dokter FROM dokter LIMIT 10 (column doesn't exist)

If schema shows "Table: pasien" and "Table: reg_periksa":
✅ CORRECT: SELECT pasien.nm_pasien FROM pasien JOIN reg_periksa ON pasien.no_rkm_medis = reg_periksa.no_rkm_medis LIMIT 10
❌ WRONG: SELECT p.nm_pasien FROM pasien p JOIN reg_periksa r ON p.no_rkm_medis = r.no_rkm_medis LIMIT 10

QUESTION: {question}

Generate ONLY the SQL query using exact table names and column names from the schema above:"""

        sql_prompt = sql_prompt_template.format(
            schema_context=schema_context,
            question=question
        )

        # Calculate timeout based on context size
        context_length = len(sql_prompt)
        if context_length > 3000:
            timeout = 60  # Large context needs more time
        elif context_length > 1500:
            timeout = 45  # Medium context
        else:
            timeout = 30  # Small context

        logger.info(f"Ollama request: context length={context_length}, timeout={timeout}s")
        logger.debug(f"SQL prompt sent to Ollama: {sql_prompt[:500]}...")  # First 500 chars for debugging

        async with httpx.AsyncClient(timeout=timeout) as client:
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
                raw_response = result.get("response", "").strip()
                logger.debug(f"Raw Ollama response: {raw_response}")
                sql_query = self._clean_sql_response(raw_response)

                if not sql_query:
                    raise Exception("Empty SQL query generated by Ollama")

                return sql_query

            except httpx.TimeoutException:
                logger.error(f"Ollama timeout after {timeout}s, context length: {context_length}")
                raise Exception(f"Ollama timeout after {timeout}s - try a simpler query")
            except httpx.HTTPStatusError as e:
                logger.error(f"Ollama HTTP error {e.response.status_code}: {e.response.text}")
                raise Exception(f"Ollama HTTP error {e.response.status_code}")
            except Exception as e:
                logger.error(f"Failed to generate SQL with Ollama: {str(e)} (type: {type(e).__name__})")
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

    async def _provide_query_guidance(self, question: str, error_message: str, schema_context: str) -> dict:
        """Analyze error and provide helpful guidance for better queries"""
        guidance = {
            "suggestions": [],
            "available_tables": [],
            "column_hints": {},
            "example_queries": []
        }

        try:
            # Parse schema to extract available information
            config = get_db_config()
            with connect(**config) as conn:
                with conn.cursor() as cursor:
                    # Get available tables
                    cursor.execute("SHOW TABLES")
                    tables = [table[0] for table in cursor.fetchall()]
                    guidance["available_tables"] = tables

                    # Get column information for each table
                    for table in tables:
                        cursor.execute(f"DESCRIBE {table}")
                        columns = cursor.fetchall()
                        guidance["column_hints"][table] = [col[0] for col in columns]

                    # Analyze the error and provide specific suggestions
                    guidance["suggestions"] = self._analyze_query_error(question, error_message, tables, guidance["column_hints"])

                    # Generate example queries
                    guidance["example_queries"] = self._generate_example_queries(tables, guidance["column_hints"])

        except Exception as e:
            logger.warning(f"Could not generate guidance: {str(e)}")
            guidance["suggestions"] = ["Could not analyze the database schema. Please try a simpler query."]

        return guidance

    def _analyze_query_error(self, question: str, error_message: str, tables: list, column_hints: dict) -> list:
        """Analyze specific errors and provide targeted suggestions"""
        suggestions = []
        question_lower = question.lower()

        # Handle unknown column errors
        if "unknown column" in error_message.lower() or "42s22" in error_message:
            # Extract problematic column name from error
            import re
            column_match = re.search(r"Unknown column '([^']+)'", error_message)
            if column_match:
                bad_column = column_match.group(1)

                # Find similar columns across tables
                similar_columns = []
                for table, columns in column_hints.items():
                    for col in columns:
                        if (bad_column.lower() in col.lower() or
                            col.lower() in bad_column.lower() or
                            any(word in col.lower() for word in bad_column.lower().split('_'))):
                            similar_columns.append(f"{table}.{col}")

                if similar_columns:
                    suggestions.append(f"Column '{bad_column}' not found. Did you mean one of these: {', '.join(similar_columns[:5])}?")
                else:
                    suggestions.append(f"Column '{bad_column}' doesn't exist. Available columns:")
                    for table, cols in column_hints.items():
                        suggestions.append(f"  • {table}: {', '.join(cols)}")

        # Handle revenue/sales related queries
        if any(word in question_lower for word in ['revenue', 'sales', 'money', 'amount', 'total']):
            revenue_columns = []
            for table, columns in column_hints.items():
                for col in columns:
                    if any(keyword in col.lower() for keyword in ['amount', 'revenue', 'price', 'total', 'cost', 'sales']):
                        revenue_columns.append(f"{table}.{col}")

            if revenue_columns:
                suggestions.append(f"For financial data, try these columns: {', '.join(revenue_columns[:5])}")

        # Handle product-related queries
        if any(word in question_lower for word in ['product', 'item', 'goods']):
            product_info = []
            for table, columns in column_hints.items():
                if 'product' in table.lower():
                    product_info.append(f"Table '{table}' has: {', '.join(columns)}")

            if product_info:
                suggestions.append("Product information available in:")
                suggestions.extend([f"  • {info}" for info in product_info[:3]])

        # Handle multi-table relationship queries dynamically
        multi_table_words = []
        for table in tables:
            if table.lower() in question_lower:
                multi_table_words.append(table)

        if len(multi_table_words) >= 2 or any(phrase in question_lower for phrase in ['by', 'with', 'join', 'connect']):
            # Detect potential table relationships dynamically
            potential_joins = self._detect_potential_joins(tables, column_hints)
            if potential_joins:
                suggestions.append("Detected possible table relationships:")
                for join_info in potential_joins[:3]:
                    suggestions.append(f"  • {join_info}")
            else:
                suggestions.append("No obvious relationships detected between tables.")
                suggestions.append("Consider using foreign key columns ending with '_id' or intermediary tables.")

        # Handle count queries
        if any(word in question_lower for word in ['how many', 'count', 'number of']):
            suggestions.append(f"For counting, try: 'How many records in [table]?' Available tables: {', '.join(tables)}")

        # Generic suggestions if no specific matches
        if not suggestions:
            suggestions.append("Try being more specific about which table and columns you want to query.")
            suggestions.append(f"Available tables: {', '.join(tables)}")

        return suggestions

    def _detect_potential_joins(self, tables: list, column_hints: dict) -> list:
        """Dynamically detect potential JOIN relationships between tables"""
        potential_joins = []

        # 1. Direct foreign key relationships (table1.foreign_key_id = table2.id)
        for table1 in tables:
            cols1 = column_hints.get(table1, [])
            for col in cols1:
                if col.endswith('_id') and col != 'id':
                    # Extract the referenced table name (e.g., user_id -> user)
                    referenced_table_base = col.replace('_id', '')

                    # Find matching table (handle both singular and plural forms)
                    for table2 in tables:
                        if (table2.lower() == referenced_table_base.lower() or
                            table2.lower() == referenced_table_base.lower() + 's' or
                            table2.lower() + 's' == referenced_table_base.lower()):
                            cols2 = column_hints.get(table2, [])
                            if 'id' in cols2:
                                potential_joins.append(f"JOIN {table2} ON {table1}.{col} = {table2}.id")

        # 2. Indirect relationships through common foreign keys
        # Group tables by their foreign key columns
        foreign_key_groups = {}
        for table, columns in column_hints.items():
            for col in columns:
                if col.endswith('_id') and col != 'id':
                    base_name = col.replace('_id', '')
                    if base_name not in foreign_key_groups:
                        foreign_key_groups[base_name] = []
                    foreign_key_groups[base_name].append((table, col))

        # Find indirect connections where multiple tables reference the same entity
        for base_name, table_refs in foreign_key_groups.items():
            if len(table_refs) >= 2:
                for i, (table1, col1) in enumerate(table_refs):
                    for table2, col2 in table_refs[i+1:]:
                        # Create indirect JOIN suggestion
                        potential_joins.append(f"JOIN {table2} ON {table1}.{col1} = {table2}.{col2} (both reference {base_name})")

        # 4. Enhanced indirect detection for common patterns like user_id/owner_id
        # Find all _id columns and group by potential target table
        id_pattern_groups = {}
        for table, columns in column_hints.items():
            for col in columns:
                if col.endswith('_id') and col != 'id':
                    # Check if this could reference users (owner_id, user_id, etc.)
                    if 'user' in col.lower() or 'owner' in col.lower():
                        if 'user' not in id_pattern_groups:
                            id_pattern_groups['user'] = []
                        id_pattern_groups['user'].append((table, col))

        # Create indirect connections for user-related fields
        for entity, refs in id_pattern_groups.items():
            if len(refs) >= 2:
                for i, (table1, col1) in enumerate(refs):
                    for table2, col2 in refs[i+1:]:
                        potential_joins.append(f"JOIN {table2} ON {table1}.{col1} = {table2}.{col2} (both are {entity} references)")

        # 3. Many-to-many through junction tables
        # Look for tables that might be junction tables (have multiple foreign keys)
        for table, columns in column_hints.items():
            foreign_keys = [col for col in columns if col.endswith('_id') and col != 'id']
            if len(foreign_keys) >= 2:
                # This might be a junction table
                potential_joins.append(f"Table '{table}' appears to link {', '.join([fk.replace('_id', '') for fk in foreign_keys])}")

        # Remove duplicates and limit results
        unique_joins = list(dict.fromkeys(potential_joins))  # Preserve order while removing duplicates
        return unique_joins[:5]  # Limit to most relevant relationships

    def _generate_example_queries(self, tables: list, column_hints: dict) -> list:
        """Generate example queries based on available schema"""
        examples = []

        for table in tables[:3]:  # Show examples for first 3 tables
            columns = column_hints.get(table, [])
            if columns:
                examples.append(f"'How many records in {table} table?'")

                # Find likely name/description columns
                name_cols = [col for col in columns if any(word in col.lower() for word in ['name', 'title', 'description'])]
                if name_cols:
                    examples.append(f"'Show me all {name_cols[0]} from {table}'")

                # Find likely numeric columns
                numeric_cols = [col for col in columns if any(word in col.lower() for word in ['amount', 'count', 'total', 'price', 'id'])]
                if numeric_cols and len(numeric_cols) > 1:
                    examples.append(f"'What is the total {numeric_cols[1]} in {table}?'")

        return examples[:5]

    def _format_guidance_response(self, question: str, guidance: dict, error_message: str) -> str:
        """Format guidance into a user-friendly response"""
        response_parts = [
            "I had trouble understanding your database question. Let me help you find what you're looking for:",
            ""
        ]

        # Add specific suggestions
        if guidance.get("suggestions"):
            response_parts.append("💡 **Suggestions:**")
            for suggestion in guidance["suggestions"][:4]:
                response_parts.append(f"   {suggestion}")
            response_parts.append("")

        # Add available tables
        if guidance.get("available_tables"):
            tables = guidance["available_tables"]
            response_parts.append(f"📋 **Available tables:** {', '.join(tables)}")
            response_parts.append("")

        # Add example queries
        if guidance.get("example_queries"):
            response_parts.append("✨ **Try asking:**")
            for example in guidance["example_queries"][:3]:
                response_parts.append(f"   {example}")
            response_parts.append("")

        response_parts.append("Feel free to ask about specific tables or columns, and I'll help you build the right query!")

        return "\n".join(response_parts)

    def _discover_relationships(self, cursor, tables: list) -> list:
        """Discover relationships between tables including indirect connections"""
        relationships = []

        try:
            table_columns = {}
            for table in tables:
                cursor.execute(f"DESCRIBE {table}")
                columns = cursor.fetchall()
                table_columns[table] = [col[0] for col in columns]

            # 1. Direct foreign key detection
            for table1 in tables:
                cols1 = table_columns[table1]
                for col in cols1:
                    if col.endswith('_id') and col != 'id':
                        referenced_table = col.replace('_id', '')
                        for table2 in tables:
                            if (table2.lower() == referenced_table.lower() and 'id' in table_columns[table2]):
                                relationships.append(f"DIRECT: {table1}.{col} = {table2}.id")

            # 2. Indirect relationships through common foreign keys
            # Example: projects.owner_id and sales.user_id both reference users
            id_columns = {}  # Track which tables have which _id columns
            for table, columns in table_columns.items():
                for col in columns:
                    if col.endswith('_id') and col != 'id':
                        base_name = col.replace('_id', '')
                        if base_name not in id_columns:
                            id_columns[base_name] = []
                        id_columns[base_name].append((table, col))

            # Find indirect connections
            for base_name, references in id_columns.items():
                if len(references) >= 2:  # Multiple tables reference the same entity
                    for i, (table1, col1) in enumerate(references):
                        for table2, col2 in references[i+1:]:
                            # Special cases for common patterns
                            if base_name == 'user' and 'owner_id' in [col1, col2]:
                                relationships.append(f"INDIRECT: {table1}.{col1} = {table2}.{col2} (both reference users)")
                            else:
                                relationships.append(f"INDIRECT: {table1}.{col1} = {table2}.{col2} (via {base_name})")

            # 3. Enhanced JOIN examples for complex queries - use generic relationship detection
            # Find any indirect relationships that could be used for complex queries
            for base_name, references in id_columns.items():
                if len(references) >= 2:
                    for (table1, col1), (table2, col2) in zip(references, references[1:]):
                        relationships.append(f"COMPLEX: JOIN {table2} ON {table2}.{col2} = {table1}.{col1} ({table1} {col1.replace('_id', '')} linked to {table2})")

        except Exception as e:
            logger.warning(f"Error discovering relationships: {e}")

        return relationships[:8]  # Increased limit for more comprehensive relationships

    def _generate_join_paths(self, cursor, tables: list) -> list:
        """Generate comprehensive join paths for multi-table queries"""
        try:
            # Get all table columns with their types
            table_columns = {}
            foreign_keys = {}
            primary_keys = {}

            for table in tables:
                cursor.execute(f"DESCRIBE {table}")
                columns = cursor.fetchall()
                table_columns[table] = {}

                for col in columns:
                    field, type_, null, key, default, extra = col
                    table_columns[table][field] = {
                        'type': type_,
                        'key': key,
                        'nullable': null == 'YES'
                    }

                    if key == 'PRI':
                        primary_keys[table] = field
                    elif field.endswith('_id') and field != 'id':
                        if table not in foreign_keys:
                            foreign_keys[table] = []
                        foreign_keys[table].append(field)

            join_paths = []

            # 1. Direct 2-table joins
            for table1 in tables:
                if table1 in foreign_keys:
                    for fk in foreign_keys[table1]:
                        referenced_table = fk.replace('_id', '')
                        for table2 in tables:
                            if (table2.lower() == referenced_table.lower() or
                                table2.lower() == referenced_table.lower() + 's' or
                                table2.lower() + 's' == referenced_table.lower()):
                                if table2 in primary_keys:
                                    join_paths.append(f"2-TABLE: SELECT * FROM {table1} JOIN {table2} ON {table1}.{fk} = {table2}.{primary_keys[table2]}")

            # 2. Three-table join paths through intermediary tables
            for table1 in tables:
                if table1 in foreign_keys and len(foreign_keys[table1]) >= 2:
                    # This could be a junction/bridge table
                    fks = foreign_keys[table1]
                    if len(fks) >= 2:
                        for i, fk1 in enumerate(fks):
                            for fk2 in fks[i+1:]:
                                ref1 = fk1.replace('_id', '')
                                ref2 = fk2.replace('_id', '')

                                table2 = self._find_table_by_name(tables, ref1)
                                table3 = self._find_table_by_name(tables, ref2)

                                if table2 and table3 and table2 != table3:
                                    join_paths.append(
                                        f"3-TABLE: SELECT * FROM {table2} "
                                        f"JOIN {table1} ON {table2}.{primary_keys.get(table2, 'id')} = {table1}.{fk1} "
                                        f"JOIN {table3} ON {table1}.{fk2} = {table3}.{primary_keys.get(table3, 'id')}"
                                    )

            # 3. Chain joins (A->B->C through foreign keys)
            for start_table in tables:
                if start_table in foreign_keys:
                    for fk in foreign_keys[start_table]:
                        middle_table = self._find_table_by_name(tables, fk.replace('_id', ''))
                        if middle_table and middle_table in foreign_keys:
                            for middle_fk in foreign_keys[middle_table]:
                                end_table = self._find_table_by_name(tables, middle_fk.replace('_id', ''))
                                if end_table and end_table != start_table:
                                    join_paths.append(
                                        f"CHAIN: SELECT * FROM {start_table} "
                                        f"JOIN {middle_table} ON {start_table}.{fk} = {middle_table}.{primary_keys.get(middle_table, 'id')} "
                                        f"JOIN {end_table} ON {middle_table}.{middle_fk} = {end_table}.{primary_keys.get(end_table, 'id')}"
                                    )

            # 4. Complex multi-table scenarios (4+ tables)
            if len(tables) >= 4:
                central_tables = []
                for table, fks in foreign_keys.items():
                    if len(fks) >= 2:  # Tables with multiple foreign keys could be central
                        central_tables.append(table)

                for central in central_tables:
                    connected_tables = []
                    for fk in foreign_keys[central]:
                        target = self._find_table_by_name(tables, fk.replace('_id', ''))
                        if target:
                            connected_tables.append((target, fk))

                    if len(connected_tables) >= 3:
                        # Generate a 4-table join example
                        table_joins = [f"FROM {central}"]
                        for target, fk in connected_tables[:3]:
                            table_joins.append(f"JOIN {target} ON {central}.{fk} = {target}.{primary_keys.get(target, 'id')}")

                        join_paths.append(f"4-TABLE: SELECT * {' '.join(table_joins)}")

            # Remove duplicates and return limited results
            unique_paths = list(dict.fromkeys(join_paths))
            return unique_paths[:10]  # Limit to most important patterns

        except Exception as e:
            logger.warning(f"Error generating join paths: {e}")
            return []

    def _find_table_by_name(self, tables: list, name: str) -> str:
        """Find table by name with fuzzy matching"""
        name_lower = name.lower()
        for table in tables:
            table_lower = table.lower()
            if (table_lower == name_lower or
                table_lower == name_lower + 's' or
                table_lower + 's' == name_lower or
                name_lower in table_lower or
                table_lower in name_lower):
                return table
        return None

    def _analyze_query_requirements(self, question: str, schema_context: str) -> dict:
        """Analyze question to determine query complexity and requirements"""
        question_lower = question.lower()

        # Extract table names mentioned in schema
        tables = []
        lines = schema_context.split('\n')
        for line in lines:
            if line.startswith('Table: '):
                tables.append(line.replace('Table: ', '').strip())

        # Detect multi-table indicators
        multi_table_keywords = [
            'join', 'with', 'and', 'by', 'across', 'between', 'relating', 'connected',
            'along with', 'together with', 'including', 'combined with'
        ]

        # Count tables mentioned or implied
        mentioned_tables = []
        for table in tables:
            if table.lower() in question_lower:
                mentioned_tables.append(table)

        # Detect entity relationships in question (enhanced with healthcare)
        relationship_indicators = []

        # Healthcare-specific relationships
        if any(keyword in question_lower for keyword in ['patient', 'pasien']):
            relationship_indicators.append('patient_related')
        if any(keyword in question_lower for keyword in ['doctor', 'dokter', 'physician']):
            relationship_indicators.append('doctor_related')
        if any(keyword in question_lower for keyword in ['visit', 'periksa', 'appointment', 'registration']):
            relationship_indicators.append('visit_related')
        if any(keyword in question_lower for keyword in ['diagnosis', 'diagnosa', 'disease']):
            relationship_indicators.append('diagnosis_related')
        if any(keyword in question_lower for keyword in ['prescription', 'medication', 'obat', 'resep']):
            relationship_indicators.append('medication_related')

        # Original generic relationships
        if any(keyword in question_lower for keyword in ['user', 'customer', 'owner']):
            relationship_indicators.append('user_related')
        if any(keyword in question_lower for keyword in ['product', 'item', 'goods']):
            relationship_indicators.append('product_related')
        if any(keyword in question_lower for keyword in ['order', 'sale', 'purchase', 'transaction']):
            relationship_indicators.append('transaction_related')
        if any(keyword in question_lower for keyword in ['project', 'task', 'activity']):
            relationship_indicators.append('project_related')

        # Determine complexity
        complexity = 'simple'
        requires_multiple_tables = False

        if len(mentioned_tables) >= 2:
            requires_multiple_tables = True
            complexity = 'complex'
        elif len(relationship_indicators) >= 2:
            # Healthcare relationships that clearly need multiple tables
            requires_multiple_tables = True
            complexity = 'complex'
        elif any(keyword in question_lower for keyword in multi_table_keywords):
            requires_multiple_tables = True
            complexity = 'moderate'
        # Special healthcare cases that always need JOINs
        elif ('doctor' in question_lower or 'dokter' in question_lower) and \
             ('patient' in question_lower or 'visit' in question_lower or 'pasien' in question_lower):
            requires_multiple_tables = True
            complexity = 'complex'
        elif ('patient' in question_lower or 'pasien' in question_lower) and \
             ('diagnosis' in question_lower or 'diagnosa' in question_lower):
            requires_multiple_tables = True
            complexity = 'complex'
        elif any(phrase in question_lower for phrase in ['total', 'sum', 'count', 'average', 'max', 'min']) and \
             any(phrase in question_lower for phrase in ['by', 'per', 'for each', 'group']):
            # Aggregation queries might need joins
            complexity = 'moderate'
            requires_multiple_tables = len(tables) > 1  # Only if multiple tables exist

        return {
            'requires_multiple_tables': requires_multiple_tables,
            'complexity': complexity,
            'mentioned_tables': mentioned_tables,
            'relationship_indicators': relationship_indicators,
            'suggested_tables': self._suggest_relevant_tables(question_lower, tables, relationship_indicators)
        }

    def _suggest_relevant_tables(self, question_lower: str, tables: list, relationship_indicators: list) -> list:
        """Suggest which tables are likely relevant to the question"""
        relevant_tables = []

        # Direct table name matches
        for table in tables:
            if table.lower() in question_lower:
                relevant_tables.append(table)

        # Semantic matching based on relationship indicators
        for indicator in relationship_indicators:
            if indicator == 'user_related':
                for table in tables:
                    if any(word in table.lower() for word in ['user', 'customer', 'person', 'account', 'profile']):
                        if table not in relevant_tables:
                            relevant_tables.append(table)

            elif indicator == 'product_related':
                for table in tables:
                    if any(word in table.lower() for word in ['product', 'item', 'goods', 'catalog', 'inventory']):
                        if table not in relevant_tables:
                            relevant_tables.append(table)

            elif indicator == 'transaction_related':
                for table in tables:
                    if any(word in table.lower() for word in ['order', 'sale', 'purchase', 'transaction', 'payment', 'invoice']):
                        if table not in relevant_tables:
                            relevant_tables.append(table)

            elif indicator == 'project_related':
                for table in tables:
                    if any(word in table.lower() for word in ['project', 'task', 'activity', 'work', 'assignment']):
                        if table not in relevant_tables:
                            relevant_tables.append(table)

        return relevant_tables

    def _enhance_context_for_multitable(self, schema_context: str, query_plan: dict) -> str:
        """Enhance schema context specifically for multi-table queries"""
        enhanced_parts = [schema_context]

        if query_plan['requires_multiple_tables']:
            enhanced_parts.append("\n=== MULTI-TABLE QUERY GUIDANCE ===")

            if query_plan['suggested_tables']:
                enhanced_parts.append(f"FOCUS ON THESE TABLES: {', '.join(query_plan['suggested_tables'])}")

            enhanced_parts.append("\nCOMMON MULTI-TABLE PATTERNS:")
            enhanced_parts.append("- User activities: JOIN users table with activity/transaction tables")
            enhanced_parts.append("- Product sales: JOIN products with sales/orders tables")
            enhanced_parts.append("- Order details: JOIN orders with customers and products")
            enhanced_parts.append("- Project assignments: JOIN projects with users through assignment tables")

            enhanced_parts.append("\nJOIN STRATEGY:")
            enhanced_parts.append("1. Start with the main entity table (users, products, orders)")
            enhanced_parts.append("2. Join related tables using foreign key relationships")
            enhanced_parts.append("3. Use table aliases for clarity: u.name, p.title, o.date")
            enhanced_parts.append("4. Include proper GROUP BY for aggregations")

            if query_plan['complexity'] == 'complex':
                enhanced_parts.append("\nCOMPLEX QUERY TIPS:")
                enhanced_parts.append("- Use subqueries if direct joins are complex")
                enhanced_parts.append("- Consider intermediate result sets")
                enhanced_parts.append("- Use EXISTS for existence checks")
                enhanced_parts.append("- Apply LIMIT after all joins and filters")

        return "\n".join(enhanced_parts)

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