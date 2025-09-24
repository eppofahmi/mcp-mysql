#!/usr/bin/env python3
"""
Fix and Restart Healthcare Integration
Provides instructions for restarting the MCP server with healthcare integration
"""

import subprocess
import sys
import time
import requests
from pathlib import Path

def check_server_running():
    """Check if MCP server is currently running"""
    try:
        response = requests.get("http://localhost:8001/health", timeout=2)
        return response.status_code == 200
    except:
        return False

def wait_for_server(max_wait=30):
    """Wait for server to become available"""
    print("⏳ Waiting for server to start...")
    for i in range(max_wait):
        if check_server_running():
            print(f"✅ Server is running after {i} seconds")
            return True
        time.sleep(1)
        if i % 5 == 0:
            print(f"   Still waiting... ({i}/{max_wait}s)")

    print(f"❌ Server not responding after {max_wait} seconds")
    return False

def test_healthcare_integration():
    """Test if healthcare integration is working"""
    try:
        # Test complex query
        complex_query = {
            "question": "Show me doctors with their specialties"
        }
        response = requests.post("http://localhost:8001/database/question",
                                json=complex_query, timeout=30)
        result = response.json()

        if result.get("success"):
            print("✅ Healthcare integration is working!")
            print(f"   Generated SQL: {result['sql_query']}")
            return True
        else:
            print("❌ Healthcare integration not working")
            print(f"   Error: {result.get('error', 'Unknown')}")

            # Check if it's using basic schema discovery
            guidance = result.get('guidance', {})
            available_tables = guidance.get('available_tables', [])
            if len(available_tables) > 100:
                print("   ⚠️  Still using basic schema discovery")
                return False
            else:
                print(f"   Using {len(available_tables)} tables - this is good!")
                return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    """Main fix and restart procedure"""
    print("🔧 Healthcare Integration Fix & Restart Procedure")
    print("=" * 60)

    # Check if server is running
    if check_server_running():
        print("📍 MCP Server is currently running on port 8001")
        print("\n🚨 IMPORTANT:")
        print("   Your server needs to be restarted to load the new healthcare integration.")
        print("   Please stop your current server (Ctrl+C) and restart it.")

        print("\n🔄 Restart Instructions:")
        print("   1. Stop the current server (Ctrl+C in the terminal where it's running)")
        print("   2. Navigate to your MCP server directory")
        print("   3. Run one of these commands:")
        print("\n   Option A - Standalone Server:")
        print("   python3 standalone_server.py")

        print("\n   Option B - HTTP Server:")
        print("   python3 src/mysql_mcp_server/http_server.py")

        print("\n   Option C - Main Module:")
        print("   python3 -m mysql_mcp_server")

        print("\n🔍 After restarting, run this script again to verify the integration works.")

    else:
        print("📍 No MCP Server detected on port 8001")
        print("   Please start your MCP server with healthcare integration enabled.")

        # Check if we're in the right directory
        standalone_server = Path("standalone_server.py")
        if standalone_server.exists():
            print(f"\n🚀 Found standalone_server.py - you can start with:")
            print("   python3 standalone_server.py")
        else:
            print(f"\n🚀 Start your MCP server from the correct directory")

        print("\n   Make sure your .env file has these settings:")
        print("   USE_HEALTHCARE_CONTEXT=true")
        print("   SCHEMA_KNOWLEDGE_PATH=database_knowledge/")

    print("\n" + "=" * 60)
    print("🎯 Expected Results After Restart:")
    print("   • Complex queries should generate proper JOINs")
    print("   • Healthcare table relationships should be used")
    print("   • Only ~21 core healthcare tables in context (not 1000+)")
    print("   • Better SQL quality with domain knowledge")

if __name__ == "__main__":
    main()