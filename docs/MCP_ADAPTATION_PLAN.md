# MCP Server Adaptation Plan for Enhanced Database Knowledge

## Current State Analysis

The current MCP server has basic schema discovery but lacks the comprehensive healthcare domain knowledge we've extracted. Here's what needs to be updated:

## 🔧 Required Adaptations

### 1. **Schema Knowledge Integration**
**Current**: Dynamic schema discovery via SQL queries
**Needed**: Load our comprehensive schema from `database_knowledge/`

**Files to Update**:
- `src/mysql_mcp_server/query_intelligence.py`
- `src/mysql_mcp_server/server.py`

### 2. **Healthcare Domain Intelligence**
**Current**: Basic table and column discovery
**Needed**: Healthcare workflow understanding, relationship patterns

### 3. **Graph-Based Query Planning**
**Current**: Simple multi-table detection
**Needed**: Use relationship graph for optimal JOIN path finding

### 4. **Enhanced Context Generation**
**Current**: Basic schema context for Ollama
**Needed**: Rich healthcare context with workflows and patterns

## 📋 Implementation Tasks

### Phase 1: Schema Knowledge Integration

#### A. Create Schema Loader Service
```python
# New file: src/mysql_mcp_server/schema_knowledge.py
class SchemaKnowledgeService:
    def __init__(self, knowledge_path="database_knowledge/"):
        self.load_schema_knowledge()
        self.load_relationship_patterns()
        self.build_relationship_graph()
```

#### B. Update Query Intelligence Service
**File**: `src/mysql_mcp_server/query_intelligence.py`

**Changes Needed**:
1. Replace `_get_complete_schema_context_cached()` with knowledge-based context
2. Add `_get_healthcare_context()` method
3. Enhance `_analyze_query_requirements()` with domain knowledge
4. Add `_find_optimal_join_path()` using relationship graph

#### C. Enhance System Prompt
**Current prompt location**: `.env` file `OLLAMA_SQL_SYSTEM_PROMPT`

**Enhancements**:
- Add healthcare-specific table descriptions
- Include common workflow patterns
- Add domain-specific validation rules

### Phase 2: Graph-Based Query Planning

#### A. Relationship Graph Builder
```python
class RelationshipGraph:
    def __init__(self, schema_data):
        self.nodes = {}  # table_name -> TableNode
        self.edges = []  # relationships

    def find_join_path(self, tables):
        """Find optimal JOIN path between tables"""

    def get_related_tables(self, table):
        """Get tables related to given table"""
```

#### B. Query Path Optimizer
- Implement shortest path algorithm for JOINs
- Add healthcare workflow-aware routing
- Consider relationship strength and data volume

### Phase 3: Enhanced Context Generation

#### A. Healthcare Context Builder
```python
async def _build_healthcare_context(self, question: str, tables: list) -> str:
    """Build rich healthcare context with domain knowledge"""
    context = []

    # Add table descriptions with healthcare context
    for table in tables:
        table_info = self.schema_knowledge.get_table_info(table)
        context.append(f"## {table} - {table_info['description']}")
        context.append(f"Healthcare Role: {table_info['healthcare_role']}")
        context.append(f"Common Workflows: {table_info['workflows']}")

    # Add relationship context
    relationships = self.schema_knowledge.get_relationships(tables)
    context.append(f"## Table Relationships:")
    for rel in relationships:
        context.append(f"- {rel['description']}")

    return "\n".join(context)
```

#### B. Query Guidance Enhancement
- Add healthcare-specific query suggestions
- Include common reporting patterns
- Suggest related analyses

## 🛠️ Specific Code Updates

### 1. Update `query_intelligence.py`

**Add at top**:
```python
from .schema_knowledge import SchemaKnowledgeService
```

**Modify `__init__`**:
```python
def __init__(self):
    # Existing code...
    self.schema_knowledge = SchemaKnowledgeService()
    logger.info("Loaded healthcare schema knowledge")
```

**Replace `_get_complete_schema_context_cached`**:
```python
async def _get_healthcare_schema_context(self, tables: list = None) -> str:
    """Get healthcare-aware schema context"""
    return await self.schema_knowledge.build_context_for_tables(tables)
```

### 2. Create New Schema Knowledge Service

**New file**: `src/mysql_mcp_server/schema_knowledge.py`

**Key methods**:
- `load_enhanced_schema()` - Load from `enhanced_database_schema.json`
- `get_table_healthcare_role()` - Get healthcare domain context
- `find_relationship_path()` - Graph-based JOIN planning
- `get_workflow_suggestions()` - Suggest related queries

### 3. Update Environment Variables

**Add to `.env`**:
```env
# Schema Knowledge Configuration
SCHEMA_KNOWLEDGE_PATH=database_knowledge/
USE_HEALTHCARE_CONTEXT=true
ENABLE_RELATIONSHIP_GRAPH=true
```

### 4. Enhanced System Prompt

**Update `OLLAMA_SQL_SYSTEM_PROMPT` in `.env`**:
```
You are a healthcare database expert for the allammedica hospital system.

## Healthcare Database Context:
{healthcare_context}

## Relationship Workflows:
{workflow_patterns}

## Domain-Specific Rules:
- Patient data: Use 'pasien' table (no_rkm_medis primary key)
- Visits/encounters: Use 'reg_periksa' table (no_rawat primary key)
- Clinical data flows: pasien → reg_periksa → clinical tables
- Always consider BPJS integration via 'bridging_sep'
- Follow healthcare privacy guidelines

## Optimization Guidelines:
- Use relationship graph for optimal JOINs
- Consider data volume in path selection
- Prioritize indexed columns for filtering
```

## 📊 Implementation Priority

### Phase 1 (Critical) - Schema Integration
1. ✅ Create `SchemaKnowledgeService`
2. ✅ Update `QueryIntelligenceService` initialization
3. ✅ Replace basic schema discovery with knowledge-based approach

### Phase 2 (High) - Relationship Graph
1. ✅ Implement relationship graph builder
2. ✅ Add JOIN path optimization
3. ✅ Update query planning logic

### Phase 3 (Medium) - Enhanced Context
1. ✅ Add healthcare domain descriptions
2. ✅ Include workflow patterns in context
3. ✅ Update system prompt with domain knowledge

## 🎯 Expected Improvements

**Before**: Basic SQL generation with limited context
**After**: Healthcare-aware intelligent query generation

### Query Quality Improvements:
- **Better JOINs**: Optimal paths using relationship graph
- **Domain Awareness**: Healthcare-specific query patterns
- **Validation**: Healthcare workflow compliance
- **Suggestions**: Related analyses and follow-up queries

### Example Query Improvement:

**Before** (Question: "Show me patient treatments"):
```sql
SELECT * FROM pasien LIMIT 100;
```

**After** (With healthcare knowledge):
```sql
SELECT
    p.nm_pasien,
    r.tgl_registrasi,
    d.nm_dokter,
    pol.nm_poli,
    rj.diagnosa_awal,
    dp.status
FROM pasien p
JOIN reg_periksa r ON p.no_rkm_medis = r.no_rkm_medis
JOIN dokter d ON r.kd_dokter = d.kd_dokter
JOIN poliklinik pol ON r.kd_poli = pol.kd_poli
LEFT JOIN rawat_jl_dr rj ON r.no_rawat = rj.no_rawat
LEFT JOIN diagnosa_pasien dp ON r.no_rawat = dp.no_rawat
ORDER BY r.tgl_registrasi DESC
LIMIT 50;
```

## 🚀 Next Steps

1. **Implement Phase 1** - Basic schema knowledge integration
2. **Test with existing queries** - Ensure compatibility
3. **Add Phase 2** - Relationship graph optimization
4. **Enhance prompts** - Include healthcare domain knowledge
5. **Performance testing** - Measure query improvement

---

The adaptation will transform the MCP server from basic SQL generation to intelligent healthcare-aware query system using our comprehensive database knowledge.