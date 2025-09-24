"""
Schema Knowledge Service for Healthcare Database
Provides comprehensive database knowledge integration for intelligent query generation
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class TableInfo:
    """Enhanced table information with healthcare context"""
    name: str
    columns: List[Dict[str, Any]]
    primary_keys: List[str]
    foreign_keys: List[str]
    relationships: List[str]
    healthcare_role: str
    category: str
    sample_data: List[Dict[str, Any]]

    def get_column_names(self) -> List[str]:
        return [col['name'] for col in self.columns]

    def get_key_columns(self) -> List[str]:
        """Get important columns (primary keys, foreign keys, indexed)"""
        key_cols = set(self.primary_keys + self.foreign_keys)
        indexed_cols = [col['name'] for col in self.columns if col.get('key') in ['MUL', 'UNI']]
        key_cols.update(indexed_cols)
        return list(key_cols)

@dataclass
class RelationshipEdge:
    """Represents a relationship between two tables"""
    source_table: str
    target_table: str
    source_column: str
    target_column: str
    relationship_type: str = "foreign_key"

    def __str__(self):
        return f"{self.source_table}.{self.source_column} → {self.target_table}.{self.target_column}"

class RelationshipGraph:
    """Graph representation of table relationships for optimal query planning"""

    def __init__(self):
        self.nodes: Dict[str, TableInfo] = {}
        self.edges: List[RelationshipEdge] = []
        self.adjacency: Dict[str, List[str]] = defaultdict(list)

    def add_table(self, table_info: TableInfo):
        """Add a table to the graph"""
        self.nodes[table_info.name] = table_info

    def add_relationship(self, edge: RelationshipEdge):
        """Add a relationship edge"""
        self.edges.append(edge)
        self.adjacency[edge.source_table].append(edge.target_table)
        # Add reverse relationship for bi-directional traversal
        self.adjacency[edge.target_table].append(edge.source_table)

    def find_shortest_path(self, start_table: str, end_table: str) -> List[str]:
        """Find shortest path between two tables using BFS"""
        if start_table == end_table:
            return [start_table]

        visited = set()
        queue = [(start_table, [start_table])]

        while queue:
            current, path = queue.pop(0)
            if current in visited:
                continue

            visited.add(current)

            for neighbor in self.adjacency[current]:
                if neighbor == end_table:
                    return path + [neighbor]

                if neighbor not in visited:
                    queue.append((neighbor, path + [neighbor]))

        return []  # No path found

    def find_join_path(self, tables: List[str]) -> List[RelationshipEdge]:
        """Find optimal JOIN path for multiple tables"""
        if len(tables) <= 1:
            return []

        # Start with most connected table (usually 'pasien' or 'reg_periksa')
        hub_tables = ['pasien', 'reg_periksa']
        start_table = None

        for hub in hub_tables:
            if hub in tables:
                start_table = hub
                break

        if not start_table:
            start_table = tables[0]

        join_edges = []
        connected_tables = {start_table}
        remaining_tables = set(tables) - connected_tables

        while remaining_tables:
            best_edge = None
            best_distance = float('inf')

            # Find closest unconnected table to any connected table
            for connected_table in connected_tables:
                for remaining_table in remaining_tables:
                    path = self.find_shortest_path(connected_table, remaining_table)
                    if path and len(path) < best_distance:
                        best_distance = len(path)
                        # Find the edge for this path
                        for edge in self.edges:
                            if ((edge.source_table == connected_table and edge.target_table == remaining_table) or
                                (edge.source_table == remaining_table and edge.target_table == connected_table)):
                                best_edge = edge
                                break

            if best_edge:
                join_edges.append(best_edge)
                if best_edge.source_table in remaining_tables:
                    connected_tables.add(best_edge.source_table)
                    remaining_tables.discard(best_edge.source_table)
                elif best_edge.target_table in remaining_tables:
                    connected_tables.add(best_edge.target_table)
                    remaining_tables.discard(best_edge.target_table)
            else:
                # No path found, add remaining tables individually
                break

        return join_edges

    def get_related_tables(self, table: str, max_distance: int = 2) -> List[str]:
        """Get tables related to given table within max_distance"""
        if table not in self.nodes:
            return []

        visited = set()
        queue = [(table, 0)]
        related = []

        while queue:
            current, distance = queue.pop(0)
            if current in visited or distance > max_distance:
                continue

            visited.add(current)
            if current != table:
                related.append(current)

            if distance < max_distance:
                for neighbor in self.adjacency[current]:
                    if neighbor not in visited:
                        queue.append((neighbor, distance + 1))

        return related

class SchemaKnowledgeService:
    """Comprehensive schema knowledge service for healthcare database"""

    def __init__(self, knowledge_path: str = "database_knowledge/"):
        self.knowledge_path = Path(knowledge_path)
        self.schema_data: Dict[str, Any] = {}
        self.relationship_data: Dict[str, Any] = {}
        self.table_info: Dict[str, TableInfo] = {}
        self.relationship_graph = RelationshipGraph()

        # Healthcare-specific configurations
        self.healthcare_categories = {
            "patient": {"description": "Patient master data and demographics", "icon": "👥"},
            "clinical": {"description": "Clinical data, diagnoses, and procedures", "icon": "🏥"},
            "administrative": {"description": "Registration, scheduling, and administration", "icon": "📋"},
            "staff": {"description": "Medical staff and personnel", "icon": "👩‍⚕️"},
            "infrastructure": {"description": "Facilities, rooms, and equipment", "icon": "🏢"},
            "pharmacy": {"description": "Medications and pharmacy management", "icon": "💊"},
            "billing": {"description": "Financial and billing information", "icon": "💰"},
            "external": {"description": "External system integrations", "icon": "🔗"}
        }

        self.healthcare_workflows = {
            "patient_registration": {
                "description": "Patient registration and visit setup",
                "tables": ["pasien", "reg_periksa", "dokter", "poliklinik"],
                "flow": "pasien → reg_periksa → dokter → poliklinik"
            },
            "clinical_diagnosis": {
                "description": "Clinical diagnosis and treatment planning",
                "tables": ["reg_periksa", "diagnosa_pasien", "penyakit", "rawat_jl_dr"],
                "flow": "reg_periksa → diagnosa_pasien → penyakit"
            },
            "diagnostic_procedures": {
                "description": "Laboratory and radiology examinations",
                "tables": ["reg_periksa", "periksa_lab", "periksa_radiologi"],
                "flow": "reg_periksa → periksa_lab/periksa_radiologi"
            },
            "surgical_procedures": {
                "description": "Surgical operations and procedures",
                "tables": ["reg_periksa", "operasi", "dokter"],
                "flow": "reg_periksa → operasi (multiple doctor roles)"
            },
            "medication_management": {
                "description": "Prescription and medication dispensing",
                "tables": ["reg_periksa", "resep_dokter", "obat_racikan"],
                "flow": "reg_periksa → resep_dokter → obat_racikan"
            },
            "billing_process": {
                "description": "Patient billing and insurance processing",
                "tables": ["reg_periksa", "nota_jalan", "nota_inap", "bridging_sep"],
                "flow": "reg_periksa → nota_jalan/nota_inap → bridging_sep"
            }
        }

        try:
            self._load_schema_knowledge()
            self._build_relationship_graph()
            logger.info(f"Successfully loaded healthcare schema knowledge: {len(self.table_info)} tables")
        except Exception as e:
            logger.error(f"Failed to load schema knowledge: {e}")
            raise

    def _load_schema_knowledge(self):
        """Load comprehensive schema knowledge from files"""

        # Load enhanced schema
        enhanced_schema_path = self.knowledge_path / "schema" / "enhanced_database_schema.json"
        if enhanced_schema_path.exists():
            with open(enhanced_schema_path, 'r', encoding='utf-8') as f:
                self.schema_data = json.load(f)
            logger.info("Loaded enhanced database schema")
        else:
            # Fallback to basic schema
            basic_schema_path = self.knowledge_path / "schema" / "database_schema.json"
            if basic_schema_path.exists():
                with open(basic_schema_path, 'r', encoding='utf-8') as f:
                    self.schema_data = json.load(f)
                logger.info("Loaded basic database schema")
            else:
                raise FileNotFoundError("No schema files found in knowledge base")

        # Load relationship analysis
        relationship_path = self.knowledge_path / "analysis" / "relationship_summary.json"
        if relationship_path.exists():
            with open(relationship_path, 'r', encoding='utf-8') as f:
                self.relationship_data = json.load(f)
            logger.info("Loaded relationship analysis")

        # Build TableInfo objects
        for table_name, table_schema in self.schema_data.get("schema", {}).items():
            healthcare_role = self._get_healthcare_role(table_name)
            category = self._categorize_table(table_name)

            self.table_info[table_name] = TableInfo(
                name=table_name,
                columns=table_schema.get("columns", []),
                primary_keys=table_schema.get("primary_keys", []),
                foreign_keys=table_schema.get("foreign_keys", []),
                relationships=table_schema.get("relationships", []),
                healthcare_role=healthcare_role,
                category=category,
                sample_data=table_schema.get("sample_data", [])
            )

    def _build_relationship_graph(self):
        """Build relationship graph from schema data"""
        # Add all tables as nodes
        for table_name, table_info in self.table_info.items():
            self.relationship_graph.add_table(table_info)

        # Add relationship edges
        for table_name, table_info in self.table_info.items():
            for relationship in table_info.relationships:
                # Parse relationship: "table.column → ref_table.ref_column"
                if " → " in relationship:
                    source_part, target_part = relationship.split(" → ")
                    source_table, source_column = source_part.split(".")
                    target_table, target_column = target_part.split(".")

                    edge = RelationshipEdge(
                        source_table=source_table,
                        target_table=target_table,
                        source_column=source_column,
                        target_column=target_column
                    )
                    self.relationship_graph.add_relationship(edge)

        logger.info(f"Built relationship graph: {len(self.relationship_graph.nodes)} nodes, {len(self.relationship_graph.edges)} edges")

    def _categorize_table(self, table_name: str) -> str:
        """Categorize table by healthcare domain"""
        table_lower = table_name.lower()

        if any(keyword in table_lower for keyword in ["pasien"]):
            return "patient"
        elif any(keyword in table_lower for keyword in ["diagnosa", "penyakit", "operasi", "periksa"]):
            return "clinical"
        elif any(keyword in table_lower for keyword in ["reg_", "nota", "bridging"]):
            return "administrative"
        elif any(keyword in table_lower for keyword in ["dokter", "pegawai", "petugas"]):
            return "staff"
        elif any(keyword in table_lower for keyword in ["kamar", "bangsal", "poli"]):
            return "infrastructure"
        elif any(keyword in table_lower for keyword in ["obat", "resep", "racikan"]):
            return "pharmacy"
        elif any(keyword in table_lower for keyword in ["bayar", "piutang", "tarif", "biaya", "nota"]):
            return "billing"
        elif any(keyword in table_lower for keyword in ["bridging", "rujuk"]):
            return "external"
        else:
            return "other"

    def _get_healthcare_role(self, table_name: str) -> str:
        """Get healthcare-specific role description for table"""
        healthcare_roles = {
            "pasien": "Central patient master record with demographics and contact information",
            "dokter": "Medical staff information with specializations and credentials",
            "reg_periksa": "Patient visit registration and encounter management",
            "diagnosa_pasien": "Clinical diagnoses assigned to patients during visits",
            "penyakit": "Disease classification and ICD code reference",
            "rawat_jl_dr": "Outpatient treatment records by doctors",
            "rawat_inap_dr": "Inpatient treatment records by doctors",
            "periksa_lab": "Laboratory examination requests and results",
            "periksa_radiologi": "Radiology examination requests and results",
            "operasi": "Surgical procedure records with multiple staff roles",
            "resep_dokter": "Medication prescriptions written by doctors",
            "obat_racikan": "Pharmaceutical compounds and medication details",
            "kamar_inap": "Inpatient room assignments and bed management",
            "poliklinik": "Outpatient clinic departments and specialties",
            "nota_jalan": "Outpatient billing and invoice generation",
            "nota_inap": "Inpatient billing and invoice generation",
            "bridging_sep": "BPJS insurance integration and claim processing",
            "rujuk": "Patient referrals to other facilities or specialists",
            "bangsal": "Hospital ward and department organization",
            "kamar": "Physical room and facility management",
            "penjab": "Payment methods and insurance types"
        }

        return healthcare_roles.get(table_name, f"Healthcare database table: {table_name}")

    def get_table_info(self, table_name: str) -> Optional[TableInfo]:
        """Get comprehensive table information"""
        return self.table_info.get(table_name)

    def get_related_tables(self, table_name: str, max_distance: int = 2) -> List[str]:
        """Get tables related to given table"""
        return self.relationship_graph.get_related_tables(table_name, max_distance)

    def find_optimal_join_path(self, tables: List[str]) -> List[RelationshipEdge]:
        """Find optimal JOIN path between tables"""
        return self.relationship_graph.find_join_path(tables)

    def get_workflow_tables(self, workflow_name: str) -> List[str]:
        """Get tables involved in a specific healthcare workflow"""
        workflow = self.healthcare_workflows.get(workflow_name, {})
        return workflow.get("tables", [])

    def suggest_related_queries(self, table_name: str) -> List[Dict[str, str]]:
        """Suggest related queries based on healthcare workflows"""
        suggestions = []

        # Find workflows involving this table
        for workflow_name, workflow in self.healthcare_workflows.items():
            if table_name in workflow["tables"]:
                suggestions.append({
                    "workflow": workflow_name,
                    "description": workflow["description"],
                    "suggested_query": f"Analyze {workflow['description'].lower()} involving {table_name}",
                    "related_tables": ", ".join(workflow["tables"])
                })

        return suggestions

    async def build_healthcare_context(self, tables: List[str] = None, question: str = None) -> str:
        """Build comprehensive healthcare context for query generation"""
        context_parts = []

        # Header
        context_parts.append("# 🏥 ALLAMMEDICA HEALTHCARE DATABASE CONTEXT")
        context_parts.append("")

        # Database overview
        context_parts.append("## 📊 Database Overview")
        context_parts.append(f"Healthcare Database: {self.schema_data.get('database', 'allammedica')}")
        context_parts.append(f"Total Tables: {len(self.table_info)}")
        context_parts.append("")

        # Table information
        if tables:
            context_parts.append("## 📋 Relevant Tables")
            for table_name in tables:
                table_info = self.get_table_info(table_name)
                if table_info:
                    category_info = self.healthcare_categories.get(table_info.category, {})
                    icon = category_info.get("icon", "📄")

                    context_parts.append(f"### {icon} {table_name}")
                    context_parts.append(f"**Healthcare Role**: {table_info.healthcare_role}")
                    context_parts.append(f"**Category**: {table_info.category}")
                    context_parts.append(f"**Key Columns**: {', '.join(table_info.get_key_columns())}")

                    if table_info.relationships:
                        context_parts.append("**Relationships**:")
                        for rel in table_info.relationships[:3]:  # Limit to first 3
                            context_parts.append(f"  - {rel}")
                    context_parts.append("")

            # Add optimal JOIN path if multiple tables
            if len(tables) > 1:
                join_edges = self.find_optimal_join_path(tables)
                if join_edges:
                    context_parts.append("## 🔗 Optimal JOIN Path")
                    for edge in join_edges:
                        context_parts.append(f"- {edge}")
                    context_parts.append("")

        # Healthcare workflows
        relevant_workflows = []
        if tables:
            for workflow_name, workflow in self.healthcare_workflows.items():
                if any(table in workflow["tables"] for table in tables):
                    relevant_workflows.append((workflow_name, workflow))

        if relevant_workflows:
            context_parts.append("## 🔄 Relevant Healthcare Workflows")
            for workflow_name, workflow in relevant_workflows:
                context_parts.append(f"### {workflow_name.replace('_', ' ').title()}")
                context_parts.append(f"**Description**: {workflow['description']}")
                context_parts.append(f"**Flow**: {workflow['flow']}")
                context_parts.append(f"**Tables**: {', '.join(workflow['tables'])}")
                context_parts.append("")

        # Domain-specific guidelines
        context_parts.append("## ⚕️ Healthcare Domain Guidelines")
        context_parts.append("- **Patient Privacy**: Always consider patient data privacy requirements")
        context_parts.append("- **Primary Keys**: Use no_rkm_medis for patients, no_rawat for visits")
        context_parts.append("- **Date Filtering**: Consider using registration dates (tgl_registrasi) for time-based queries")
        context_parts.append("- **BPJS Integration**: Include bridging_sep for insurance-related queries")
        context_parts.append("- **Clinical Flow**: Follow patient → registration → clinical activities sequence")
        context_parts.append("")

        return "\n".join(context_parts)

    def get_table_categories(self) -> Dict[str, List[str]]:
        """Get tables organized by healthcare categories"""
        categories = defaultdict(list)
        for table_name, table_info in self.table_info.items():
            categories[table_info.category].append(table_name)
        return dict(categories)

    def validate_healthcare_query(self, sql: str, tables: List[str]) -> Dict[str, Any]:
        """Validate query against healthcare domain rules"""
        validation_result = {
            "valid": True,
            "warnings": [],
            "suggestions": []
        }

        sql_lower = sql.lower()

        # Check for patient privacy considerations
        if "pasien" in tables and "nm_pasien" in sql_lower:
            validation_result["warnings"].append(
                "Query includes patient names - ensure compliance with privacy policies"
            )

        # Check for proper date filtering
        if any(table in ["reg_periksa", "rawat_jl_dr", "rawat_inap_dr"] for table in tables):
            if "tgl_registrasi" not in sql_lower and "limit" not in sql_lower:
                validation_result["suggestions"].append(
                    "Consider adding date filtering (tgl_registrasi) or LIMIT clause for performance"
                )

        # Check for BPJS integration
        if "penjab" in tables and "bridging_sep" not in tables:
            validation_result["suggestions"].append(
                "Consider including bridging_sep table for complete insurance information"
            )

        return validation_result