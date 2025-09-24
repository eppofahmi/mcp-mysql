"""
AWS-Inspired Query Validation Pipeline for Healthcare MCP Server

This module implements multi-stage query validation and self-correction
based on AWS's robust text-to-SQL solution patterns.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import sqlparse
from sqlparse import sql, tokens as T

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Validation severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """Result of a validation check"""
    level: ValidationLevel
    message: str
    suggestion: Optional[str] = None
    auto_correctable: bool = False
    corrected_sql: Optional[str] = None


@dataclass
class QueryComplexity:
    """Query complexity analysis"""
    table_count: int
    join_count: int
    subquery_count: int
    aggregate_functions: List[str]
    estimated_rows: Optional[int] = None
    complexity_score: float = 0.0


class HealthcareQueryValidator:
    """
    Healthcare-specific query validation following AWS patterns
    """

    def __init__(self):
        self.healthcare_tables = {
            'pasien', 'dokter', 'reg_periksa', 'pemeriksaan_ralan',
            'pemeriksaan_ranap', 'diagnosa_pasien', 'resep_dokter',
            'rawat_inap_dr', 'rawat_jl_dr', 'kamar_inap', 'operasi',
            'periksa_lab', 'periksa_radiologi'
        }

        self.sensitive_columns = {
            'no_ktp', 'no_rkm_medis', 'alamat', 'no_tlp', 'email',
            'tgl_lahir', 'nama_keluarga', 'diagnosa'
        }

        self.required_joins = {
            ('pasien', 'dokter'): 'reg_periksa',
            ('dokter', 'pemeriksaan'): 'reg_periksa',
            ('pasien', 'diagnosa'): 'reg_periksa'
        }

    def validate_query(self, sql: str, question: str = "") -> List[ValidationResult]:
        """
        Multi-stage validation pipeline inspired by AWS approach
        """
        results = []

        # Stage 1: Syntax validation
        results.extend(self._validate_syntax(sql))

        # Stage 2: Healthcare schema validation
        results.extend(self._validate_healthcare_schema(sql))

        # Stage 3: Business logic validation
        results.extend(self._validate_business_logic(sql, question))

        # Stage 4: Performance validation
        results.extend(self._validate_performance(sql))

        # Stage 5: Security validation
        results.extend(self._validate_security(sql))

        return results

    def _validate_syntax(self, sql: str) -> List[ValidationResult]:
        """Validate SQL syntax"""
        results = []

        try:
            parsed = sqlparse.parse(sql)[0]

            # Check for basic SQL structure
            sql_upper = sql.upper().strip()
            if not sql_upper.startswith('SELECT'):
                results.append(ValidationResult(
                    level=ValidationLevel.ERROR,
                    message="Query must start with SELECT statement",
                    suggestion="Use SELECT to query data from tables"
                ))

            # Check for incomplete queries (aliases without FROM clause)
            if self._has_table_aliases_without_from(sql):
                results.append(ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    message="Table aliases used without proper FROM clause",
                    suggestion="Define table aliases in FROM clause with JOIN statements",
                    auto_correctable=True,
                    corrected_sql=self._fix_missing_from_clause(sql)
                ))

        except Exception as e:
            results.append(ValidationResult(
                level=ValidationLevel.ERROR,
                message=f"SQL syntax error: {str(e)}",
                suggestion="Check SQL syntax and fix parsing errors"
            ))

        return results

    def _validate_healthcare_schema(self, sql: str) -> List[ValidationResult]:
        """Validate healthcare schema usage"""
        results = []

        # Extract table names from query
        tables = self._extract_table_names(sql)

        # Check if healthcare tables are used correctly
        for table in tables:
            if table not in self.healthcare_tables and not table.startswith('temp_'):
                results.append(ValidationResult(
                    level=ValidationLevel.WARNING,
                    message=f"Table '{table}' is not a recognized healthcare table",
                    suggestion=f"Verify table name or use core healthcare tables: {', '.join(list(self.healthcare_tables)[:5])}..."
                ))

        # Validate required joins for healthcare workflows
        results.extend(self._validate_healthcare_joins(tables))

        return results

    def _validate_business_logic(self, sql: str, question: str) -> List[ValidationResult]:
        """Validate healthcare business logic"""
        results = []

        # Check for patient-doctor relationships
        if 'pasien' in sql and 'dokter' in sql:
            if 'reg_periksa' not in sql:
                results.append(ValidationResult(
                    level=ValidationLevel.WARNING,
                    message="Patient-doctor queries should include registration (reg_periksa) table",
                    suggestion="JOIN through reg_periksa to establish patient-doctor relationships"
                ))

        # Check for proper date filtering in healthcare contexts
        if any(word in question.lower() for word in ['recent', 'latest', 'today', 'yesterday']):
            if 'ORDER BY' not in sql.upper() or 'tgl_' not in sql:
                results.append(ValidationResult(
                    level=ValidationLevel.INFO,
                    message="Time-based queries should include date ordering",
                    suggestion="Add ORDER BY tgl_registrasi DESC or similar date column"
                ))

        return results

    def _validate_performance(self, sql: str) -> List[ValidationResult]:
        """Validate query performance"""
        results = []

        complexity = self._analyze_complexity(sql)

        # Check for LIMIT clause
        if 'LIMIT' not in sql.upper():
            results.append(ValidationResult(
                level=ValidationLevel.WARNING,
                message="Query without LIMIT clause may return too many rows",
                suggestion="Add LIMIT clause to control result set size",
                auto_correctable=True,
                corrected_sql=f"{sql.rstrip(';')} LIMIT 100"
            ))

        # Check for complex joins without proper indexing hints
        if complexity.join_count > 3:
            results.append(ValidationResult(
                level=ValidationLevel.INFO,
                message=f"Complex query with {complexity.join_count} JOINs may be slow",
                suggestion="Consider query optimization or adding appropriate indexes"
            ))

        return results

    def _validate_security(self, sql: str) -> List[ValidationResult]:
        """Validate security aspects"""
        results = []

        # Check for sensitive column access
        for column in self.sensitive_columns:
            if column in sql.lower():
                results.append(ValidationResult(
                    level=ValidationLevel.WARNING,
                    message=f"Query accesses sensitive column: {column}",
                    suggestion="Ensure proper authorization for accessing sensitive healthcare data"
                ))

        # Check for potential SQL injection patterns
        suspicious_patterns = [
            r"'\s*OR\s*'1'\s*=\s*'1'",
            r";\s*DROP\s+TABLE",
            r"UNION\s+SELECT",
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                results.append(ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    message="Potential SQL injection pattern detected",
                    suggestion="Review query for malicious content"
                ))

        return results

    def _has_table_aliases_without_from(self, sql: str) -> bool:
        """Check if query uses table.column syntax but no FROM clause"""
        # Look for patterns like "SELECT tablename.column" without FROM clause
        table_dot_column = r'SELECT\s+[a-zA-Z_]\w*\.[a-zA-Z_]\w*'
        from_pattern = r'FROM\s+\w+'

        has_table_columns = bool(re.search(table_dot_column, sql, re.IGNORECASE))
        has_from = bool(re.search(from_pattern, sql, re.IGNORECASE))

        return has_table_columns and not has_from

    def _fix_missing_from_clause(self, sql: str) -> str:
        """Simple fix for missing FROM clause - add basic FROM if missing"""
        # Since we now require full table names, just return as-is
        # The AI should generate complete SQL with proper FROM clauses
        return sql

    def _extract_table_names(self, sql: str) -> List[str]:
        """Extract table names from SQL query"""
        tables = set()

        try:
            parsed = sqlparse.parse(sql)[0]
            from_seen = False

            for token in parsed.flatten():
                if from_seen and token.ttype is None and not token.is_keyword:
                    # Clean table name (remove aliases)
                    table_name = token.value.strip().split()[0]
                    if table_name and not table_name.upper() in ['ON', 'WHERE', 'ORDER', 'GROUP', 'HAVING']:
                        tables.add(table_name.lower())

                if token.ttype is T.Keyword and token.value.upper() in ['FROM', 'JOIN']:
                    from_seen = True
                elif token.ttype is T.Keyword and token.value.upper() in ['WHERE', 'ORDER', 'GROUP', 'HAVING']:
                    from_seen = False

        except Exception as e:
            logger.warning(f"Error extracting table names: {e}")

        return list(tables)

    def _validate_healthcare_joins(self, tables: List[str]) -> List[ValidationResult]:
        """Validate healthcare-specific join requirements"""
        results = []

        for (table1, table2), bridge_table in self.required_joins.items():
            if table1 in tables and table2 in tables and bridge_table not in tables:
                results.append(ValidationResult(
                    level=ValidationLevel.WARNING,
                    message=f"Query joining {table1} and {table2} should include {bridge_table}",
                    suggestion=f"Add JOIN with {bridge_table} to establish proper healthcare relationships"
                ))

        return results

    def _analyze_complexity(self, sql: str) -> QueryComplexity:
        """Analyze query complexity"""
        sql_upper = sql.upper()

        table_count = len(re.findall(r'\bFROM\b|\bJOIN\b', sql_upper))
        join_count = len(re.findall(r'\bJOIN\b', sql_upper))
        subquery_count = sql.count('(') - sql.count(')')  # Rough estimate

        # Find aggregate functions
        agg_functions = []
        agg_patterns = [r'\bCOUNT\(', r'\bSUM\(', r'\bAVG\(', r'\bMAX\(', r'\bMIN\(']
        for pattern in agg_patterns:
            matches = re.findall(pattern, sql_upper)
            agg_functions.extend([match.replace('(', '') for match in matches])

        # Calculate complexity score
        complexity_score = (
            table_count * 1.0 +
            join_count * 2.0 +
            subquery_count * 3.0 +
            len(agg_functions) * 1.5
        )

        return QueryComplexity(
            table_count=table_count,
            join_count=join_count,
            subquery_count=max(0, subquery_count),
            aggregate_functions=agg_functions,
            complexity_score=complexity_score
        )


class QuerySelfCorrection:
    """
    Self-correction mechanism inspired by AWS approach
    """

    def __init__(self, validator: HealthcareQueryValidator):
        self.validator = validator
        self.correction_history = {}

    def auto_correct_query(self, sql: str, question: str = "") -> Tuple[str, List[ValidationResult]]:
        """
        Automatically correct common query issues
        """
        validation_results = self.validator.validate_query(sql, question)
        corrected_sql = sql
        corrections_applied = []

        # Apply corrections in priority order (critical first)
        critical_corrections = [r for r in validation_results if r.auto_correctable and r.level == ValidationLevel.CRITICAL]
        other_corrections = [r for r in validation_results if r.auto_correctable and r.level != ValidationLevel.CRITICAL]

        for result in critical_corrections + other_corrections:
            if result.corrected_sql:
                corrected_sql = result.corrected_sql
                corrections_applied.append(result)
                logger.info(f"Auto-corrected: {result.message}")
                break  # Apply only the first applicable correction

        # If no critical corrections, apply LIMIT if needed
        if not corrections_applied:
            for result in validation_results:
                if result.auto_correctable and result.corrected_sql and 'LIMIT' in result.corrected_sql:
                    corrected_sql = result.corrected_sql
                    corrections_applied.append(result)
                    logger.info(f"Auto-corrected: {result.message}")
                    break

        # Re-validate corrected query
        if corrections_applied:
            final_validation = self.validator.validate_query(corrected_sql, question)
            return corrected_sql, final_validation

        return corrected_sql, validation_results

    def suggest_improvements(self, sql: str, question: str = "") -> List[str]:
        """Generate improvement suggestions"""
        validation_results = self.validator.validate_query(sql, question)
        suggestions = []

        for result in validation_results:
            if result.suggestion:
                suggestions.append(f"{result.level.value.upper()}: {result.suggestion}")

        return suggestions