#!/usr/bin/env python3
"""
Test the specific query: "Show me highest sales by a user"
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mysql_mcp_server.query_intelligence import QueryIntelligenceService

async def test_highest_sales_query():
    """Test the specific query about highest sales by user"""
    print("🧪 Testing Query: 'Show me highest sales by a user'")
    print("=" * 50)

    service = QueryIntelligenceService()

    # Simulate a typical e-commerce schema
    schema_context = """Database: ecommerce_db
Available tables: users, orders, products, order_items, sales

Table: users
  - id: int(11) (PRI) (required)
  - name: varchar(255) (required)
  - email: varchar(255) (required)
  Total rows: 1000

Table: orders
  - id: int(11) (PRI) (required)
  - user_id: int(11) (required)
  - order_date: datetime (required)
  - total_amount: decimal(10,2) (required)
  Total rows: 5000

Table: products
  - id: int(11) (PRI) (required)
  - name: varchar(255) (required)
  - price: decimal(10,2) (required)
  Total rows: 200

Table: order_items
  - id: int(11) (PRI) (required)
  - order_id: int(11) (required)
  - product_id: int(11) (required)
  - quantity: int(11) (required)
  - unit_price: decimal(10,2) (required)
  Total rows: 15000

Table: sales
  - id: int(11) (PRI) (required)
  - user_id: int(11) (required)
  - product_id: int(11) (required)
  - sale_amount: decimal(10,2) (required)
  - sale_date: datetime (required)
  Total rows: 8000

MULTI-TABLE JOIN PATTERNS:
  2-TABLE: SELECT * FROM orders JOIN users ON orders.user_id = users.id
  2-TABLE: SELECT * FROM sales JOIN users ON sales.user_id = users.id
  3-TABLE: SELECT * FROM users JOIN orders ON users.id = orders.user_id JOIN order_items ON orders.id = order_items.order_id
  CHAIN: SELECT * FROM users JOIN sales ON users.id = sales.user_id JOIN products ON sales.product_id = products.id
"""

    question = "Show me highest sales by a user"

    # Test query planning
    print("1️⃣ Query Analysis:")
    query_plan = service._analyze_query_requirements(question, schema_context)
    for key, value in query_plan.items():
        print(f"   {key}: {value}")

    print(f"\n2️⃣ Multi-table Detection: {'✅ YES' if query_plan['requires_multiple_tables'] else '❌ NO'}")
    print(f"   Complexity: {query_plan['complexity']}")

    # Test context enhancement
    if query_plan['requires_multiple_tables']:
        print("\n3️⃣ Enhanced Context Generation:")
        enhanced_context = service._enhance_context_for_multitable(schema_context, query_plan)

        # Show the enhancement part
        enhancement_start = enhanced_context.find("=== MULTI-TABLE QUERY GUIDANCE ===")
        if enhancement_start != -1:
            enhancement = enhanced_context[enhancement_start:]
            print("   Enhancement added:")
            for line in enhancement.split('\n')[:10]:  # Show first 10 lines
                if line.strip():
                    print(f"   {line}")
            print("   ...")

    # Show what the enhanced prompt would look like
    print(f"\n4️⃣ Expected SQL Query Types for this question:")
    print("   Option 1: SELECT u.name, SUM(s.sale_amount) as total_sales FROM users u JOIN sales s ON u.id = s.user_id GROUP BY u.id ORDER BY total_sales DESC LIMIT 1")
    print("   Option 2: SELECT u.name, SUM(o.total_amount) as total_sales FROM users u JOIN orders o ON u.id = o.user_id GROUP BY u.id ORDER BY total_sales DESC LIMIT 1")
    print("   Option 3: SELECT u.name, SUM(oi.quantity * oi.unit_price) as total_sales FROM users u JOIN orders o ON u.id = o.user_id JOIN order_items oi ON o.id = oi.order_id GROUP BY u.id ORDER BY total_sales DESC LIMIT 1")

    print(f"\n5️⃣ Prompt Enhancement Preview:")
    print("   The LLM will now receive:")
    print("   ✅ Clear table relationships")
    print("   ✅ Specific join patterns")
    print("   ✅ Multi-table strategy guidance")
    print("   ✅ Aggregation with GROUP BY guidance")
    print("   ✅ Focus on relevant tables: users + sales/orders")

if __name__ == "__main__":
    asyncio.run(test_highest_sales_query())
    print("\n🎉 Query analysis complete!")