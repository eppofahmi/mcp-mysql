#!/usr/bin/env python3
"""
Test Healthcare Schema Knowledge Integration
Verify that the MCP server can load and use our healthcare database knowledge
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_schema_knowledge_service():
    """Test SchemaKnowledgeService initialization and basic functionality"""
    print("🧪 Testing SchemaKnowledgeService...")

    try:
        from mysql_mcp_server.schema_knowledge import SchemaKnowledgeService

        # Initialize with our knowledge path
        knowledge_path = "database_knowledge/"
        service = SchemaKnowledgeService(knowledge_path)

        print(f"✅ SchemaKnowledgeService initialized successfully")
        print(f"   • Loaded {len(service.table_info)} tables")
        print(f"   • Built relationship graph with {len(service.relationship_graph.nodes)} nodes and {len(service.relationship_graph.edges)} edges")

        # Test table information retrieval
        print("\n📋 Testing table information retrieval...")
        pasien_info = service.get_table_info("pasien")
        if pasien_info:
            print(f"✅ Retrieved pasien table info: {pasien_info.healthcare_role}")
            print(f"   • Category: {pasien_info.category}")
            print(f"   • Columns: {len(pasien_info.columns)}")
            print(f"   • Key columns: {', '.join(pasien_info.get_key_columns())}")
        else:
            print("❌ Failed to retrieve pasien table info")

        # Test relationship graph
        print("\n🔗 Testing relationship graph...")
        related_tables = service.get_related_tables("pasien", max_distance=2)
        print(f"✅ Found {len(related_tables)} tables related to 'pasien': {', '.join(related_tables[:5])}...")

        # Test JOIN path finding
        test_tables = ["pasien", "reg_periksa", "dokter"]
        join_path = service.find_optimal_join_path(test_tables)
        print(f"✅ Optimal JOIN path for {test_tables}:")
        for edge in join_path:
            print(f"   • {edge}")

        # Test healthcare context building
        print("\n🏥 Testing healthcare context building...")
        context = await service.build_healthcare_context(["pasien", "reg_periksa"], "Show me patient visits")
        print(f"✅ Built healthcare context ({len(context)} characters)")
        print(f"   Preview: {context[:200]}...")

        return True

    except Exception as e:
        print(f"❌ SchemaKnowledgeService test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_query_intelligence_integration():
    """Test QueryIntelligenceService with healthcare knowledge integration"""
    print("\n🤖 Testing QueryIntelligenceService integration...")

    try:
        from mysql_mcp_server.query_intelligence import QueryIntelligenceService

        # Initialize service (should automatically load healthcare knowledge)
        service = QueryIntelligenceService()

        if service.schema_knowledge:
            print(f"✅ QueryIntelligenceService initialized with healthcare knowledge")

            # Test table identification from question
            test_question = "Show me patient treatments by doctors"
            relevant_tables = await service._identify_relevant_tables(test_question)
            print(f"✅ Identified relevant tables for '{test_question}': {relevant_tables}")

            # Test healthcare context generation
            context = await service._get_healthcare_schema_context(relevant_tables, test_question)
            print(f"✅ Generated healthcare context ({len(context)} characters)")

            return True
        else:
            print("⚠️  QueryIntelligenceService initialized without healthcare knowledge")
            return False

    except Exception as e:
        print(f"❌ QueryIntelligenceService test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_file_structure():
    """Test that all required files exist"""
    print("📁 Testing file structure...")

    required_files = [
        "database_knowledge/schema/enhanced_database_schema.json",
        "database_knowledge/analysis/relationship_summary.json",
        "database_knowledge/README.md",
        "src/mysql_mcp_server/schema_knowledge.py"
    ]

    all_exist = True
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - Missing!")
            all_exist = False

    return all_exist

async def main():
    """Run all tests"""
    print("🚀 Healthcare Schema Knowledge Integration Tests")
    print("=" * 60)

    # Test file structure
    files_ok = await test_file_structure()

    if not files_ok:
        print("\n❌ Required files missing. Please ensure database_knowledge/ folder is properly set up.")
        return

    # Test schema knowledge service
    schema_ok = await test_schema_knowledge_service()

    # Test query intelligence integration
    query_ok = await test_query_intelligence_integration()

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"   File Structure: {'✅ PASS' if files_ok else '❌ FAIL'}")
    print(f"   Schema Knowledge: {'✅ PASS' if schema_ok else '❌ FAIL'}")
    print(f"   Query Intelligence: {'✅ PASS' if query_ok else '❌ FAIL'}")

    if all([files_ok, schema_ok, query_ok]):
        print("\n🎉 All tests passed! Healthcare knowledge integration is ready.")
        print("\n🔧 To use the enhanced MCP server:")
        print("   1. Ensure database_knowledge/ folder is in the same directory as your MCP server")
        print("   2. Set USE_HEALTHCARE_CONTEXT=true in your .env file")
        print("   3. Start the MCP server normally - it will automatically use healthcare knowledge")
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")

if __name__ == "__main__":
    asyncio.run(main())