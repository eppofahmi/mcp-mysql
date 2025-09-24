#!/usr/bin/env python3
"""
Debug Server Startup Issues
Check if healthcare integration is loading during server startup
"""

import requests
import time

def test_server_modes():
    """Test different query types to understand server mode"""
    print("🔍 Testing Server Healthcare Integration Status")
    print("=" * 50)

    # Test 1: Simple query (should always work)
    print("\n1. Testing simple query...")
    try:
        response = requests.post("http://localhost:8001/database/question",
                               json={"question": "Show me 3 doctors"},
                               timeout=10)
        result = response.json()
        if result.get("success"):
            print("   ✅ Simple queries work")
        else:
            print(f"   ❌ Simple query failed: {result.get('error')}")
    except Exception as e:
        print(f"   ❌ Simple query error: {e}")

    # Test 2: Check guidance/table discovery method
    print("\n2. Testing table discovery method...")
    try:
        response = requests.post("http://localhost:8001/database/question",
                               json={"question": "Show me tables with relationships"},
                               timeout=5)
        result = response.json()

        guidance = result.get("guidance", {})
        available_tables = guidance.get("available_tables", [])
        table_count = len(available_tables)

        print(f"   📊 Available tables count: {table_count}")

        if table_count > 500:
            print("   ❌ Using BASIC schema discovery (healthcare integration NOT loaded)")
            print("   🔧 Healthcare knowledge service failed to initialize")
        elif table_count < 50:
            print("   ✅ Using FOCUSED schema (healthcare integration loaded!)")
            print("   🏥 Healthcare knowledge service is active")
        else:
            print(f"   ⚠️  Unclear - {table_count} tables (investigation needed)")

        # Show first few tables to understand what's being used
        if available_tables:
            sample_tables = available_tables[:10]
            print(f"   📋 Sample tables: {', '.join(sample_tables[:5])}...")

            # Check for healthcare tables
            healthcare_tables = [t for t in sample_tables if t in ['pasien', 'dokter', 'reg_periksa']]
            if healthcare_tables:
                print(f"   🏥 Healthcare tables found: {healthcare_tables}")
            else:
                print("   ⚠️  No core healthcare tables in sample")

    except Exception as e:
        print(f"   ❌ Table discovery test failed: {e}")

    # Test 3: Check server logs or error patterns
    print("\n3. Testing error patterns...")
    try:
        response = requests.post("http://localhost:8001/database/question",
                               json={"question": "Join pasien with dokter"},
                               timeout=8)
        result = response.json()

        if result.get("success"):
            print("   ✅ JOIN query works!")
            print(f"   📝 SQL: {result['sql_query']}")
        else:
            error = result.get("error", "")
            error_type = result.get("error_type", "")
            print(f"   ❌ JOIN failed: {error}")
            print(f"   📝 Error type: {error_type}")

            # Analyze error patterns
            if "Unknown table" in error and "field list" in error:
                print("   🔍 DIAGNOSIS: SQL alias problem - table aliases not defined properly")
            elif "Ollama" in error:
                print("   🔍 DIAGNOSIS: Ollama communication problem")
            elif "timeout" in error.lower():
                print("   🔍 DIAGNOSIS: Query generation timeout")
            else:
                print("   🔍 DIAGNOSIS: Unknown error pattern")

    except Exception as e:
        print(f"   ❌ JOIN test error: {e}")
        if "timeout" in str(e).lower():
            print("   🔍 DIAGNOSIS: Server/Ollama timeout issue")

def check_healthcare_integration_files():
    """Verify healthcare files are accessible"""
    print("\n4. Checking file accessibility...")

    import os
    from pathlib import Path

    # Check if files exist and are readable
    files_to_check = [
        "database_knowledge/schema/enhanced_database_schema.json",
        "src/mysql_mcp_server/schema_knowledge.py"
    ]

    for file_path in files_to_check:
        if Path(file_path).exists():
            try:
                if file_path.endswith('.json'):
                    import json
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    table_count = len(data.get('schema', {}))
                    print(f"   ✅ {file_path} - {table_count} tables")
                else:
                    print(f"   ✅ {file_path} - exists")
            except Exception as e:
                print(f"   ❌ {file_path} - readable but error: {e}")
        else:
            print(f"   ❌ {file_path} - MISSING")

def main():
    """Run startup diagnostics"""
    print("🔧 MCP Server Healthcare Integration Startup Diagnostics")
    print("Checking why healthcare integration isn't loading...\n")

    # Check server responsiveness first
    try:
        response = requests.get("http://localhost:8001/health", timeout=3)
        if response.status_code == 200:
            print("✅ Server is responsive")
        else:
            print(f"❌ Server health check failed: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return

    # Run diagnostic tests
    test_server_modes()
    check_healthcare_integration_files()

    print("\n" + "=" * 60)
    print("🎯 TROUBLESHOOTING RECOMMENDATIONS:")
    print("-" * 30)
    print("If healthcare integration is NOT loaded:")
    print("1. Check server startup logs for errors")
    print("2. Verify .env file location and content")
    print("3. Ensure database_knowledge/ is in working directory")
    print("4. Try starting server with: python3 -c 'from src.mysql_mcp_server.query_intelligence import QueryIntelligenceService; print(QueryIntelligenceService())'")
    print("5. Check Ollama connectivity: curl http://192.168.1.127:11434/api/tags")

if __name__ == "__main__":
    main()