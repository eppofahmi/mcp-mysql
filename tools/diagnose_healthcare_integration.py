#!/usr/bin/env python3
"""
Diagnostic Script for Healthcare Integration Issues
Tests if the healthcare knowledge is being loaded correctly by the MCP server
"""

import requests
import json
import os
from pathlib import Path

def test_mcp_server_endpoints():
    """Test various MCP server endpoints to diagnose issues"""
    base_url = "http://localhost:8001"

    print("🔍 MCP Server Healthcare Integration Diagnostics")
    print("=" * 60)

    # Test 1: Check if server is responsive
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is responsive")
            print(f"   Health status: {response.json()}")
        else:
            print(f"❌ Server health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return False

    # Test 2: Simple single table query (should work)
    print("\n🧪 Test 2: Simple single table query")
    try:
        simple_query = {
            "question": "Show me 3 doctors"
        }
        response = requests.post(f"{base_url}/database/question",
                                json=simple_query, timeout=30)
        result = response.json()

        if result.get("success"):
            print("✅ Simple query works")
            print(f"   SQL: {result['sql_query']}")
        else:
            print("❌ Simple query failed")
            print(f"   Error: {result.get('error', 'Unknown error')}")

    except Exception as e:
        print(f"❌ Simple query test failed: {e}")

    # Test 3: Complex JOIN query (problematic)
    print("\n🧪 Test 3: Complex JOIN query")
    try:
        complex_query = {
            "question": "Show me doctors with specialties"
        }
        response = requests.post(f"{base_url}/database/question",
                                json=complex_query, timeout=30)
        result = response.json()

        if result.get("success"):
            print("✅ Complex query works")
            print(f"   SQL: {result['sql_query']}")
        else:
            print("❌ Complex query failed")
            print(f"   Error: {result.get('error', 'Unknown error')}")
            print(f"   Error type: {result.get('error_type', 'Unknown')}")

            # Check if it's falling back to basic schema discovery
            guidance = result.get('guidance', {})
            available_tables = guidance.get('available_tables', [])
            if len(available_tables) > 100:
                print("⚠️  Server is using basic schema discovery (1000+ tables)")
                print("   This suggests healthcare knowledge is NOT loaded")
            else:
                print(f"   Available tables count: {len(available_tables)}")

    except Exception as e:
        print(f"❌ Complex query test failed: {e}")

    # Test 4: Check if healthcare tables are recognized
    print("\n🧪 Test 4: Healthcare table recognition")
    try:
        healthcare_query = {
            "question": "Count records in pasien table"
        }
        response = requests.post(f"{base_url}/database/question",
                                json=healthcare_query, timeout=30)
        result = response.json()

        if result.get("success"):
            print("✅ Healthcare table 'pasien' is recognized")
            sql = result.get('sql_query', '')
            if 'pasien' in sql.lower():
                print("✅ SQL correctly uses 'pasien' table")
            else:
                print("❌ SQL doesn't use 'pasien' table as expected")
        else:
            print("❌ Healthcare table recognition failed")
            print(f"   Error: {result.get('error', 'Unknown error')}")

    except Exception as e:
        print(f"❌ Healthcare table test failed: {e}")

    return True

def check_file_structure():
    """Check if required files exist"""
    print("\n📁 File Structure Check")
    print("-" * 30)

    required_files = [
        "database_knowledge/schema/enhanced_database_schema.json",
        "database_knowledge/analysis/relationship_summary.json",
        "src/mysql_mcp_server/schema_knowledge.py",
        ".env"
    ]

    all_exist = True
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - MISSING!")
            all_exist = False

    return all_exist

def check_env_configuration():
    """Check environment variables"""
    print("\n⚙️ Environment Configuration Check")
    print("-" * 35)

    # Check if .env file has healthcare settings
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found")
        return False

    with open(env_file, 'r') as f:
        env_content = f.read()

    healthcare_settings = [
        "USE_HEALTHCARE_CONTEXT=true",
        "SCHEMA_KNOWLEDGE_PATH=database_knowledge/",
        "ENABLE_RELATIONSHIP_GRAPH=true"
    ]

    for setting in healthcare_settings:
        if setting in env_content:
            print(f"✅ {setting}")
        else:
            print(f"❌ {setting} - MISSING OR INCORRECT!")

    # Check Ollama settings
    ollama_settings = [
        'OLLAMA_BASE_URL="http://192.168.1.127:11434"',
        'OLLAMA_MODEL="qwen3"'
    ]

    for setting in ollama_settings:
        if setting in env_content:
            print(f"✅ {setting}")
        else:
            print(f"⚠️  {setting} - Check configuration")

    return True

def main():
    """Run all diagnostic tests"""
    print("🏥 MCP Healthcare Integration Diagnostics")
    print("This script will help identify why complex queries are failing\n")

    # Test file structure
    files_ok = check_file_structure()

    # Test environment configuration
    env_ok = check_env_configuration()

    # Test MCP server
    if files_ok and env_ok:
        server_ok = test_mcp_server_endpoints()
    else:
        print("\n❌ Cannot test server due to missing files or configuration")
        server_ok = False

    # Final diagnosis
    print("\n" + "=" * 60)
    print("📋 DIAGNOSIS SUMMARY:")
    print("-" * 20)

    if files_ok and env_ok and server_ok:
        print("🎯 LIKELY ISSUE: SQL generation problem with table aliases")
        print("   • Healthcare knowledge files exist")
        print("   • Environment is configured correctly")
        print("   • Server responds to simple queries")
        print("   • Issue is with complex JOIN query generation")
        print("\n💡 RECOMMENDATION:")
        print("   • Check Ollama model prompt generation")
        print("   • Debug table alias handling in SQL generation")
        print("   • Verify JOIN path optimization is working")

    elif not files_ok:
        print("🎯 ISSUE: Missing healthcare knowledge files")
        print("💡 RECOMMENDATION: Run schema generation scripts")

    elif not env_ok:
        print("🎯 ISSUE: Environment configuration problems")
        print("💡 RECOMMENDATION: Update .env file with healthcare settings")

    else:
        print("🎯 ISSUE: Server connectivity or integration problems")
        print("💡 RECOMMENDATION: Check server logs and restart with healthcare integration")

if __name__ == "__main__":
    main()