# Database Knowledge Repository

Organized collection of allammedica database schema, analysis, and tools for graph-based query generation.

## 📁 Folder Structure

```
database_knowledge/
├── schema/                     # Database schema files
├── analysis/                   # Analysis results and reports
├── tools/                      # Analysis and generation tools
├── docs/                       # Documentation and summaries
└── README.md                   # This file
```

## 📊 Schema Files (`schema/`)

### `database_schema.json`
- **Core healthcare tables schema** (21 tables)
- **Complete column definitions** with data types
- **Primary/foreign key relationships**
- **Sample data** for understanding structure
- **Ready for graph database import**

### `enhanced_database_schema.json`
- **Complete analysis** including views and relationships
- **Graph structure** with nodes and edges
- **Complex relationship mapping**
- **Metadata and statistics**
- **Junction table analysis**

## 🔧 Tools (`tools/`)

### `generate_healthcare_schema.py`
- **Extracts core healthcare tables** from allammedica database
- **Generates structured schema** with relationships
- **Creates sample data** for testing
- **Focuses on 21 essential healthcare entities**

### `analyze_views_and_relationships.py`
- **Analyzes database views** and complex relationships
- **Creates graph structure** (nodes/edges)
- **Identifies relationship patterns**
- **Generates enhanced schema**

## 📖 Documentation (`docs/`)

### `SCHEMA_ANALYSIS_SUMMARY.md`
- **Comprehensive overview** of database structure
- **Healthcare workflow mapping**
- **Graph database recommendations**
- **Query pattern suggestions**

## 🏥 Database Overview

**Healthcare Database**: allammedica
**Total Tables**: 1,007+
**Core Tables Analyzed**: 21
**Views**: 2
**Relationships**: 71 foreign keys

### Key Healthcare Entities
- **Patients**: `pasien` (master records)
- **Registrations**: `reg_periksa` (visits/encounters)
- **Clinical**: `diagnosa_pasien`, `rawat_*`, `periksa_*`
- **Staff**: `dokter`, linked to specializations
- **Infrastructure**: `kamar_inap`, `bangsal`, `poliklinik`
- **Billing**: `nota_*`, `bridging_sep` (BPJS)

### Relationship Patterns
```
pasien → reg_periksa → diagnosa_pasien
       → rawat_jl_dr/rawat_inap_dr
       → periksa_lab/periksa_radiologi
       → operasi → nota_*
```

## 🎯 Usage for Graph Database

### 1. **Import Schema**
```python
import json
with open('schema/enhanced_database_schema.json') as f:
    schema = json.load(f)

nodes = schema['graph_structure']['nodes']
edges = schema['graph_structure']['edges']
```

### 2. **Query Generation Context**
- Use relationship mappings for JOIN detection
- Follow patient/registration workflows for semantic understanding
- Apply healthcare domain knowledge for query optimization

### 3. **Natural Language Processing**
- Map healthcare terms to table/column names
- Use relationship context for query path finding
- Apply domain-specific validation rules

## 📈 Statistics

- **318 total columns** across core tables
- **71 foreign key relationships**
- **15.1 average columns** per table
- **Most complex**: `operasi` table (57 columns, 25 FKs)
- **Central hubs**: `pasien` and `reg_periksa`

## 🔄 Maintenance

### Updating Schema
```bash
cd database_knowledge/tools
python3 generate_healthcare_schema.py
python3 analyze_views_and_relationships.py
```

### Adding New Analysis
1. Create new analysis script in `tools/`
2. Save results in `analysis/`
3. Update documentation in `docs/`
4. Update this README

## 🚀 Next Steps

1. **Graph Database Setup**: Import nodes/edges into Neo4j/ArangoDB
2. **Query Generation**: Build semantic query parser using schema knowledge
3. **Relationship Intelligence**: Implement path-finding for complex queries
4. **Healthcare Validation**: Add domain-specific query validation rules

---
*Generated for allammedica healthcare database - January 2025*