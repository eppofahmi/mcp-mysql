#!/usr/bin/env python3
"""
Database Schema Explorer
Connects to your TiDB Cloud MySQL database to understand the actual table structure
"""

import mysql.connector
import os
from dotenv import load_dotenv
import json
from collections import defaultdict

# Load environment variables
load_dotenv()

def get_db_config():
    """Get database configuration from environment variables"""
    return {
        'host': os.getenv('MYSQL_HOST'),
        'port': int(os.getenv('MYSQL_PORT', 4000)),
        'user': os.getenv('MYSQL_USER'),
        'password': os.getenv('MYSQL_PASSWORD'),
        'database': os.getenv('MYSQL_DATABASE'),
        'ssl_disabled': False,  # Enable SSL for TiDB Cloud
        'autocommit': True
    }

def explore_database():
    """Explore the database schema and relationships"""
    config = get_db_config()
    print(f"🔍 Connecting to database: {config['database']} at {config['host']}:{config['port']}")

    try:
        with mysql.connector.connect(**config) as conn:
            with conn.cursor() as cursor:
                print("\n" + "="*60)
                print("DATABASE SCHEMA EXPLORATION")
                print("="*60)

                # Get all tables
                cursor.execute("SHOW TABLES")
                tables = [table[0] for table in cursor.fetchall()]
                print(f"\n📋 Found {len(tables)} tables: {', '.join(tables)}")

                schema_info = {}
                relationships = defaultdict(list)

                # Analyze each table
                for table in tables:
                    print(f"\n🔍 Table: {table}")
                    print("-" * 40)

                    # Get column information
                    cursor.execute(f"DESCRIBE {table}")
                    columns = cursor.fetchall()

                    table_info = {
                        'columns': [],
                        'primary_keys': [],
                        'foreign_keys': [],
                        'sample_data': []
                    }

                    print("📊 Columns:")
                    for col in columns:
                        field, type_, null, key, default, extra = col
                        table_info['columns'].append({
                            'name': field,
                            'type': type_,
                            'nullable': null == 'YES',
                            'key': key,
                            'default': default,
                            'extra': extra
                        })

                        # Track primary and foreign keys
                        if key == 'PRI':
                            table_info['primary_keys'].append(field)

                        # Detect potential foreign keys (ending with _id)
                        if field.endswith('_id') and field != 'id':
                            table_info['foreign_keys'].append(field)
                            base_name = field.replace('_id', '')
                            relationships[base_name].append((table, field))

                        print(f"  • {field:<20} {type_:<20} {'NULL' if null == 'YES' else 'NOT NULL':<10} {key:<5}")

                    # Get sample data (first 3 rows)
                    try:
                        cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                        sample_rows = cursor.fetchall()
                        if sample_rows:
                            print(f"\n📝 Sample data ({len(sample_rows)} rows):")
                            column_names = [col[0] for col in columns]
                            for i, row in enumerate(sample_rows, 1):
                                row_dict = dict(zip(column_names, row))
                                table_info['sample_data'].append(row_dict)
                                print(f"  Row {i}: {dict(list(row_dict.items())[:4])}...")  # Show first 4 columns
                    except Exception as e:
                        print(f"  ⚠️  Could not fetch sample data: {e}")

                    schema_info[table] = table_info

                # Analyze relationships
                print(f"\n🔗 RELATIONSHIP ANALYSIS")
                print("-" * 40)

                # Direct foreign key relationships
                direct_relationships = []
                for table_info in schema_info.values():
                    for fk in table_info['foreign_keys']:
                        referenced_table = fk.replace('_id', '')
                        # Check if referenced table exists (singular or plural)
                        for existing_table in tables:
                            if (existing_table.lower() == referenced_table.lower() or
                                existing_table.lower() == referenced_table.lower() + 's' or
                                existing_table.lower() + 's' == referenced_table.lower()):
                                direct_relationships.append(f"{table}.{fk} → {existing_table}.id")

                print("🎯 Direct Foreign Key Relationships:")
                for rel in direct_relationships:
                    print(f"  • {rel}")

                # Indirect relationships
                print("\n🔄 Indirect Relationships (through common foreign keys):")
                for base_name, refs in relationships.items():
                    if len(refs) >= 2:
                        print(f"  • {base_name} connections:")
                        for i, (table1, col1) in enumerate(refs):
                            for table2, col2 in refs[i+1:]:
                                print(f"    - {table1}.{col1} = {table2}.{col2} (both reference {base_name})")

                # Generate test cases
                print(f"\n🧪 SUGGESTED TEST CASES")
                print("-" * 40)

                test_cases = []

                # Simple queries for each table
                for table in tables:
                    test_cases.extend([
                        f"How many records are in the {table} table?",
                        f"Show me all data from {table}",
                    ])

                # Relationship-based queries
                if 'projects' in tables and 'sales' in tables:
                    test_cases.extend([
                        "Show me projects by sales performance",
                        "What are the top projects by revenue?",
                        "Which projects have the highest sales?",
                    ])

                if 'users' in tables:
                    test_cases.extend([
                        "Show me all users and their projects",
                        "Which user has the most sales?",
                    ])

                # Financial queries if sales data exists
                if any('sales' in table for table in tables):
                    test_cases.extend([
                        "What is the total sales amount?",
                        "Show sales by region",
                        "What are the top selling products?",
                    ])

                for i, test_case in enumerate(test_cases[:10], 1):
                    print(f"  {i:2d}. {test_case}")

                # Save schema to JSON for later use
                with open('/Volumes/repoku/product/loom4/mcp-mysql/database_schema.json', 'w') as f:
                    json.dump({
                        'tables': list(tables),
                        'schema': schema_info,
                        'relationships': {
                            'direct': direct_relationships,
                            'indirect': dict(relationships)
                        },
                        'test_cases': test_cases
                    }, f, indent=2, default=str)

                print(f"\n💾 Schema saved to database_schema.json")
                print(f"\n✅ Database exploration complete!")

    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        print(f"Config used: {config}")

if __name__ == "__main__":
    explore_database()