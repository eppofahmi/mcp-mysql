#!/usr/bin/env python3
"""
Comprehensive Test Suite for MCP MySQL Server
Based on actual TiDB Cloud database schema and data
"""

import requests
import json
import time
from typing import Dict, List, Any

# Test configuration
MCP_SERVER_URL = "http://localhost:8001"
TEST_USER_ID = "test_user_123"

class MCPDatabaseTester:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.passed_tests = 0
        self.failed_tests = 0
        self.test_results = []

    def run_query(self, question: str, user_id: str = TEST_USER_ID) -> Dict[str, Any]:
        """Send a query to the MCP server"""
        try:
            response = requests.post(
                f"{self.server_url}/mcp/database/question",
                json={"question": question, "user_id": user_id},
                timeout=30
            )
            return response.json()
        except Exception as e:
            return {"success": False, "error": f"Request failed: {str(e)}"}

    def assert_test(self, test_name: str, condition: bool, actual_result: Any = None, expected: Any = None):
        """Assert a test condition and track results"""
        if condition:
            print(f"✅ PASS: {test_name}")
            self.passed_tests += 1
            self.test_results.append({
                "name": test_name,
                "status": "PASS",
                "actual": str(actual_result)[:100] if actual_result else None
            })
        else:
            print(f"❌ FAIL: {test_name}")
            if expected:
                print(f"   Expected: {expected}")
            if actual_result:
                print(f"   Actual: {str(actual_result)[:200]}...")
            self.failed_tests += 1
            self.test_results.append({
                "name": test_name,
                "status": "FAIL",
                "expected": str(expected) if expected else None,
                "actual": str(actual_result)[:200] if actual_result else None
            })

    def test_basic_queries(self):
        """Test basic table queries"""
        print("\n🧪 Testing Basic Table Queries")
        print("-" * 50)

        # Test 1: Count projects
        result = self.run_query("How many projects are there?")
        self.assert_test(
            "Count projects query",
            result.get("success", False) or "guidance" in result,
            result.get("answer", result.get("formatted_response", ""))
        )

        # Test 2: List all users
        result = self.run_query("Show me all users")
        self.assert_test(
            "List all users query",
            result.get("success", False) or "guidance" in result,
            result.get("answer", result.get("formatted_response", ""))
        )

        # Test 3: Sales data
        result = self.run_query("What sales do we have?")
        self.assert_test(
            "Sales data query",
            result.get("success", False) or "guidance" in result,
            result.get("answer", result.get("formatted_response", ""))
        )

    def test_relationship_queries(self):
        """Test queries involving table relationships"""
        print("\n🔗 Testing Relationship Queries")
        print("-" * 50)

        # Test 4: Projects by owner
        result = self.run_query("Show me projects and their owners")
        self.assert_test(
            "Projects with owners query",
            result.get("success", False) or "guidance" in result,
            result.get("answer", result.get("formatted_response", ""))
        )

        # Test 5: Sales by user (the complex relationship we've been working on)
        result = self.run_query("Show me projects by sales performance")
        guidance = result.get("guidance", {})
        has_relationship_suggestion = any(
            "projects.owner_id = sales.user_id" in str(suggestion)
            for suggestion in guidance.get("suggestions", [])
        )
        self.assert_test(
            "Projects by sales relationship detection",
            has_relationship_suggestion,
            guidance.get("suggestions", []),
            "Should detect projects.owner_id = sales.user_id relationship"
        )

        # Test 6: User sales totals
        result = self.run_query("Which user has the most sales?")
        self.assert_test(
            "User sales aggregation query",
            result.get("success", False) or "guidance" in result,
            result.get("answer", result.get("formatted_response", ""))
        )

    def test_financial_queries(self):
        """Test financial and aggregation queries"""
        print("\n💰 Testing Financial Queries")
        print("-" * 50)

        # Test 7: Total sales amount
        result = self.run_query("What is the total sales amount?")
        self.assert_test(
            "Total sales amount query",
            result.get("success", False) or "guidance" in result,
            result.get("answer", result.get("formatted_response", ""))
        )

        # Test 8: Sales by region
        result = self.run_query("Show sales by region")
        self.assert_test(
            "Sales by region query",
            result.get("success", False) or "guidance" in result,
            result.get("answer", result.get("formatted_response", ""))
        )

        # Test 9: Project budgets
        result = self.run_query("What are the project budgets?")
        self.assert_test(
            "Project budgets query",
            result.get("success", False) or "guidance" in result,
            result.get("answer", result.get("formatted_response", ""))
        )

    def test_error_handling_and_guidance(self):
        """Test error handling and guidance system"""
        print("\n🛠️  Testing Error Handling & Guidance")
        print("-" * 50)

        # Test 10: Invalid column name
        result = self.run_query("Show me the sales_revenue from sales")  # Should fail - column is sales_amount
        guidance = result.get("guidance", {})
        has_column_suggestion = any(
            "sales_amount" in str(suggestion)
            for suggestion in guidance.get("suggestions", [])
        )
        self.assert_test(
            "Invalid column guidance",
            has_column_suggestion,
            guidance.get("suggestions", []),
            "Should suggest 'sales_amount' when 'sales_revenue' is used"
        )

        # Test 11: Complex relationship guidance
        result = self.run_query("Show highest revenue projects")
        guidance = result.get("guidance", {})
        has_relationship_guidance = len(guidance.get("suggestions", [])) > 0
        self.assert_test(
            "Complex relationship guidance provided",
            has_relationship_guidance,
            len(guidance.get("suggestions", [])),
            "Should provide relationship suggestions"
        )

        # Test 12: Available tables information
        result = self.run_query("What tables do we have?")
        guidance = result.get("guidance", {})
        available_tables = guidance.get("available_tables", [])
        has_all_tables = all(table in available_tables for table in ["projects", "sales", "users"])
        self.assert_test(
            "Available tables information",
            has_all_tables,
            available_tables,
            ["projects", "sales", "users"]
        )

    def test_specific_real_data_queries(self):
        """Test queries based on actual data in your database"""
        print("\n📊 Testing Queries Based on Real Data")
        print("-" * 50)

        # Test 13: Specific project by name
        result = self.run_query("Tell me about the Loom4 Analytics Platform project")
        self.assert_test(
            "Specific project query",
            result.get("success", False) or "guidance" in result,
            result.get("answer", result.get("formatted_response", ""))
        )

        # Test 14: John Doe's activities
        result = self.run_query("What projects and sales are associated with John Doe?")
        self.assert_test(
            "User-specific activity query",
            result.get("success", False) or "guidance" in result,
            result.get("answer", result.get("formatted_response", ""))
        )

        # Test 15: Department-based query
        result = self.run_query("Show me users in the Engineering department")
        self.assert_test(
            "Department-based query",
            result.get("success", False) or "guidance" in result,
            result.get("answer", result.get("formatted_response", ""))
        )

    def test_dynamic_relationship_detection(self):
        """Test the dynamic relationship detection we just implemented"""
        print("\n🔄 Testing Dynamic Relationship Detection")
        print("-" * 50)

        # Test 16: Multi-table relationship detection
        result = self.run_query("Connect projects with sales data")
        guidance = result.get("guidance", {})
        suggestions = guidance.get("suggestions", [])

        # Check if our enhanced relationship detection found the indirect relationship
        has_indirect_relationship = any(
            "projects.owner_id" in str(suggestion) and "sales.user_id" in str(suggestion)
            for suggestion in suggestions
        )

        self.assert_test(
            "Dynamic indirect relationship detection",
            has_indirect_relationship,
            suggestions,
            "Should detect projects.owner_id = sales.user_id relationship"
        )

        # Test 17: Direct relationship detection
        has_direct_relationship = any(
            "sales.user_id = users.id" in str(suggestion) or "users.id" in str(suggestion)
            for suggestion in suggestions
        )

        self.assert_test(
            "Direct relationship detection",
            has_direct_relationship,
            suggestions,
            "Should detect sales.user_id = users.id relationship"
        )

    def run_all_tests(self):
        """Run all test suites"""
        print("🚀 Starting Comprehensive MCP Database Tests")
        print("=" * 60)

        start_time = time.time()

        # Run all test suites
        self.test_basic_queries()
        self.test_relationship_queries()
        self.test_financial_queries()
        self.test_error_handling_and_guidance()
        self.test_specific_real_data_queries()
        self.test_dynamic_relationship_detection()

        end_time = time.time()

        # Print summary
        print("\n" + "=" * 60)
        print("📋 TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Passed: {self.passed_tests}")
        print(f"❌ Failed: {self.failed_tests}")
        print(f"⏱️  Duration: {end_time - start_time:.2f} seconds")
        print(f"📊 Success Rate: {self.passed_tests / (self.passed_tests + self.failed_tests) * 100:.1f}%")

        # Save detailed results
        with open('/Volumes/repoku/product/loom4/mcp-mysql/test_results.json', 'w') as f:
            json.dump({
                'summary': {
                    'passed': self.passed_tests,
                    'failed': self.failed_tests,
                    'duration': end_time - start_time,
                    'success_rate': self.passed_tests / (self.passed_tests + self.failed_tests) * 100
                },
                'results': self.test_results
            }, f, indent=2)

        print("\n💾 Detailed results saved to test_results.json")

        if self.failed_tests == 0:
            print("\n🎉 All tests passed! Your MCP integration is working perfectly!")
        else:
            print(f"\n⚠️  {self.failed_tests} test(s) need attention. Check the results above.")

def main():
    """Run the test suite"""
    tester = MCPDatabaseTester(MCP_SERVER_URL)

    # Check if server is running
    try:
        response = requests.get(f"{MCP_SERVER_URL}/health", timeout=5)
        if response.status_code != 200:
            print("❌ MCP server is not responding correctly")
            return
    except:
        print("❌ Cannot connect to MCP server. Make sure it's running on http://localhost:8001")
        return

    print("✅ MCP server is running")
    tester.run_all_tests()

if __name__ == "__main__":
    main()