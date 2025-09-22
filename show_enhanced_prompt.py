#!/usr/bin/env python3
"""
Show the actual enhanced prompt that would be sent to Ollama
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mysql_mcp_server.query_intelligence import QueryIntelligenceService

async def show_enhanced_prompt():
    """Show the actual prompt that would be sent to LLM"""
    print("🎯 ENHANCED PROMPT FOR: 'Show me highest sales by a user'")
    print("=" * 70)

    service = QueryIntelligenceService()

    # Simulate realistic schema
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
  3-TABLE: SELECT * FROM users JOIN orders ON users.id = orders.user_id JOIN order_items ON orders.id = order_items.order_id"""

    question = "Show me highest sales by a user"

    # Get query plan
    query_plan = service._analyze_query_requirements(question, schema_context)

    # Get enhanced context
    enhanced_context = service._enhance_context_for_multitable(schema_context, query_plan)

    # Build the actual prompt that would be sent to Ollama
    sql_prompt_template = """You are a MySQL/TiDB SQL expert specializing in complex multi-table queries. Convert natural language to accurate SQL.

DATABASE SCHEMA:
{schema_context}

CRITICAL RULES:
- Only SELECT, SHOW, DESCRIBE queries (READ-ONLY)
- Never INSERT, UPDATE, DELETE, DROP, ALTER
- Use exact table and column names from schema above
- Include LIMIT clause (max 100 rows unless specifically requested)
- Always use proper JOIN syntax for multi-table queries

MULTI-TABLE QUERY STRATEGY:
1. Identify ALL tables mentioned or implied in the question
2. Use the "MULTI-TABLE JOIN PATTERNS" section above to find correct join paths
3. For 3+ table queries, use the provided join examples as templates
4. Always specify the full table.column format for ambiguous columns
5. Use appropriate JOIN types (INNER JOIN is default)

MULTI-TABLE EXAMPLES:
- "Sales by user and product" → Use user-sales-product join path from patterns above
- "Orders with customer details" → JOIN orders with customers table
- "Product sales with category info" → JOIN products, sales, categories using proper foreign keys
- "User activity across projects" → Use junction tables if available

SINGLE TABLE EXAMPLES:
- "How many users?" → "SELECT COUNT(*) FROM users"
- "Recent sales" → "SELECT * FROM sales ORDER BY date DESC LIMIT 20"
- "Top products" → "SELECT product, COUNT(*) as sales_count FROM sales GROUP BY product ORDER BY sales_count DESC LIMIT 10"

AGGREGATION WITH JOINS:
- Always use proper GROUP BY when joining tables with aggregation
- Use table aliases for complex queries: SELECT u.name, COUNT(s.id) FROM users u JOIN sales s ON u.id = s.user_id GROUP BY u.id
- Include meaningful column names in SELECT

USER QUESTION: {question}

Analyze the question for multi-table requirements, then generate ONLY the SQL query:"""

    actual_prompt = sql_prompt_template.format(
        schema_context=enhanced_context,
        question=question
    )

    print(actual_prompt)
    print("\n" + "=" * 70)
    print("📊 ANALYSIS:")
    print(f"✅ Multi-table detected: {query_plan['requires_multiple_tables']}")
    print(f"✅ Complexity: {query_plan['complexity']}")
    print(f"✅ Suggested tables: {', '.join(query_plan['suggested_tables'])}")
    print(f"✅ Enhanced context length: {len(enhanced_context)} characters")
    print("\n💡 Expected SQL output:")
    print("SELECT u.name, SUM(s.sale_amount) as total_sales")
    print("FROM users u")
    print("JOIN sales s ON u.id = s.user_id")
    print("GROUP BY u.id, u.name")
    print("ORDER BY total_sales DESC")
    print("LIMIT 1")

if __name__ == "__main__":
    asyncio.run(show_enhanced_prompt())
    print("\n🎉 This is the enhanced prompt your LLM will receive!")