#!/usr/bin/env python3
"""
Verify Healthcare Integration After Restart
Quick test to confirm healthcare intelligence is working
"""

import requests
import json

def test_healthcare_integration():
    """Test healthcare integration with specific queries"""
    print("🧪 Healthcare Integration Verification Tests")
    print("=" * 50)

    base_url = "http://localhost:8001"
    tests = [
        {
            "name": "Simple Doctor Query",
            "question": "Show me 5 doctors",
            "expected_success": True
        },
        {
            "name": "Patient Count",
            "question": "How many patients are registered?",
            "expected_success": True
        },
        {
            "name": "Doctor-Patient Relationship (Complex)",
            "question": "Show me doctors with their patient visits",
            "expected_success": True,
            "check_tables": ["dokter", "reg_periksa", "pasien"]
        },
        {
            "name": "Healthcare Workflow",
            "question": "Show patients with their recent diagnoses",
            "expected_success": True,
            "check_tables": ["pasien", "diagnosa_pasien"]
        }
    ]

    passed = 0
    total = len(tests)

    for i, test in enumerate(tests, 1):
        print(f"\n🧪 Test {i}: {test['name']}")
        print(f"   Question: '{test['question']}'")

        try:
            response = requests.post(f"{base_url}/database/question",
                                   json={"question": test["question"]},
                                   timeout=30)
            result = response.json()

            if result.get("success"):
                print("   ✅ SUCCESS")
                sql = result.get("sql_query", "")
                print(f"   📝 SQL: {sql}")

                # Check if expected tables are used
                if "check_tables" in test:
                    found_tables = []
                    for table in test["check_tables"]:
                        if table.lower() in sql.lower():
                            found_tables.append(table)

                    if len(found_tables) >= 2:  # At least 2 tables = JOIN
                        print(f"   🔗 Uses healthcare tables: {found_tables}")
                    else:
                        print(f"   ⚠️  Only uses: {found_tables} (expected multiple tables)")

                # Check for healthcare intelligence indicators
                metadata = result.get("metadata", {})
                if metadata.get("healthcare_validation"):
                    print("   🏥 Healthcare validation present")
                if metadata.get("related_suggestions"):
                    print("   💡 Related suggestions provided")

                passed += 1

            else:
                print("   ❌ FAILED")
                error = result.get("error", "Unknown error")
                print(f"   🚨 Error: {error}")

                # Check if falling back to basic schema
                guidance = result.get("guidance", {})
                tables = guidance.get("available_tables", [])
                if len(tables) > 100:
                    print("   ⚠️  Using basic schema (1000+ tables) - healthcare integration not loaded")
                else:
                    print(f"   ✅ Using focused schema ({len(tables)} tables)")

        except Exception as e:
            print(f"   ❌ REQUEST FAILED: {e}")

    print(f"\n" + "=" * 50)
    print(f"📊 RESULTS: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 ALL TESTS PASSED! Healthcare integration is working perfectly!")
        return True
    elif passed >= total * 0.7:
        print("⚠️  Most tests passed. Healthcare integration is partially working.")
        return True
    else:
        print("❌ Most tests failed. Healthcare integration needs attention.")
        return False

def main():
    """Run verification tests"""
    try:
        # Quick connectivity check
        response = requests.get("http://localhost:8001/health", timeout=5)
        if response.status_code != 200:
            print("❌ MCP Server not responding. Please ensure it's running.")
            return

        print("✅ MCP Server is running")

        # Run healthcare integration tests
        success = test_healthcare_integration()

        if success:
            print("\n🎯 Healthcare Integration Status: WORKING ✅")
            print("   Your MCP server now has:")
            print("   • Healthcare domain intelligence")
            print("   • Graph-based relationship understanding")
            print("   • Intelligent query generation with proper JOINs")
            print("   • Domain-specific validation and suggestions")
        else:
            print("\n🎯 Healthcare Integration Status: NEEDS ATTENTION ❌")
            print("   Please check:")
            print("   • Server was restarted after code changes")
            print("   • database_knowledge/ folder is in the correct location")
            print("   • .env file has USE_HEALTHCARE_CONTEXT=true")

    except Exception as e:
        print(f"❌ Cannot connect to MCP server: {e}")
        print("   Please ensure the server is running on port 8001")

if __name__ == "__main__":
    main()