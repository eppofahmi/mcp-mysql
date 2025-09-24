#!/usr/bin/env python3
"""
Enhanced Database Analysis: Views, Complex Relationships & Graph Structure
Analyzes views, many-to-many relationships, and creates graph-ready relationship data
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
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'user': os.getenv('MYSQL_USER'),
        'password': os.getenv('MYSQL_PASSWORD'),
        'database': os.getenv('MYSQL_DATABASE'),
        'autocommit': True
    }

def extract_views(cursor, database_name):
    """Extract all views from the database"""
    cursor.execute(f"""
        SELECT
            TABLE_NAME as view_name,
            VIEW_DEFINITION as definition,
            IS_UPDATABLE as updatable
        FROM information_schema.VIEWS
        WHERE TABLE_SCHEMA = %s
        ORDER BY TABLE_NAME
    """, (database_name,))

    views = {}
    for row in cursor.fetchall():
        view_name, definition, updatable = row

        # Try to get view columns
        try:
            cursor.execute(f"DESCRIBE {view_name}")
            columns = []
            for col_row in cursor.fetchall():
                field, type_info, null, key, default, extra = col_row
                columns.append({
                    "name": field,
                    "type": type_info,
                    "nullable": null == "YES",
                    "key": key,
                    "default": default
                })
        except Exception as e:
            print(f"⚠️  Could not describe view {view_name}: {e}")
            columns = []

        views[view_name] = {
            "definition": definition,
            "updatable": updatable == "YES",
            "columns": columns
        }

    return views

def analyze_complex_relationships(cursor, database_name, core_tables):
    """Analyze many-to-many and indirect relationships"""
    relationships = {
        "one_to_many": [],
        "many_to_many": [],
        "indirect_paths": [],
        "junction_tables": []
    }

    # Find junction tables (tables with multiple foreign keys, few other columns)
    for table in core_tables:
        cursor.execute(f"""
            SELECT
                COLUMN_NAME,
                REFERENCED_TABLE_NAME,
                REFERENCED_COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s
            AND TABLE_NAME = %s
            AND REFERENCED_TABLE_NAME IS NOT NULL
        """, (database_name, table))

        foreign_keys = cursor.fetchall()

        if len(foreign_keys) >= 2:
            # Get total column count
            cursor.execute(f"SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s", (database_name, table))
            total_columns = cursor.fetchone()[0]

            # If table has mostly foreign keys, it's likely a junction table
            if len(foreign_keys) / total_columns > 0.5:
                relationships["junction_tables"].append({
                    "table": table,
                    "foreign_keys": [
                        f"{fk[0]} → {fk[1]}.{fk[2]}" for fk in foreign_keys
                    ],
                    "total_columns": total_columns
                })

                # Create many-to-many relationship
                if len(foreign_keys) == 2:
                    fk1, fk2 = foreign_keys[:2]
                    relationships["many_to_many"].append({
                        "table1": fk1[1],
                        "table2": fk2[1],
                        "junction_table": table,
                        "relationship": f"{fk1[1]} ↔ {fk2[1]} (via {table})"
                    })

    # Find common relationship patterns
    common_patterns = find_relationship_patterns(cursor, database_name, core_tables)
    relationships["patterns"] = common_patterns

    return relationships

def find_relationship_patterns(cursor, database_name, tables):
    """Find common relationship patterns in healthcare data"""
    patterns = {}

    # Patient-centric relationships
    patient_related = []
    doctor_related = []
    registration_related = []

    for table in tables:
        cursor.execute(f"""
            SELECT COLUMN_NAME FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            AND COLUMN_NAME IN ('no_rkm_medis', 'kd_dokter', 'no_rawat')
        """, (database_name, table))

        columns = [row[0] for row in cursor.fetchall()]

        if 'no_rkm_medis' in columns:
            patient_related.append(table)
        if 'kd_dokter' in columns:
            doctor_related.append(table)
        if 'no_rawat' in columns:
            registration_related.append(table)

    patterns["patient_centric"] = patient_related
    patterns["doctor_centric"] = doctor_related
    patterns["registration_centric"] = registration_related

    return patterns

def create_graph_nodes_edges(schema_data, relationships):
    """Create graph-ready nodes and edges data"""
    nodes = []
    edges = []

    # Create nodes for each table
    for table_name, table_info in schema_data.get("schema", {}).items():
        node = {
            "id": table_name,
            "label": table_name,
            "type": "table",
            "columns": len(table_info["columns"]),
            "primary_keys": table_info["primary_keys"],
            "category": categorize_table(table_name)
        }
        nodes.append(node)

    # Create edges from foreign key relationships
    edge_id = 0
    for table_name, table_info in schema_data.get("schema", {}).items():
        for relationship in table_info.get("relationships", []):
            # Parse relationship: "table.column → ref_table.ref_column"
            if " → " in relationship:
                source_part, target_part = relationship.split(" → ")
                source_table = source_part.split(".")[0]
                target_table = target_part.split(".")[0]

                edge = {
                    "id": f"edge_{edge_id}",
                    "source": source_table,
                    "target": target_table,
                    "type": "foreign_key",
                    "relationship": relationship
                }
                edges.append(edge)
                edge_id += 1

    return {"nodes": nodes, "edges": edges}

def categorize_table(table_name):
    """Categorize tables by their healthcare domain"""
    categories = {
        "patient": ["pasien", "pasien_"],
        "clinical": ["diagnosa", "penyakit", "operasi", "periksa"],
        "administrative": ["reg_periksa", "nota", "bridging"],
        "staff": ["dokter", "pegawai", "petugas"],
        "infrastructure": ["kamar", "bangsal", "poliklinik"],
        "pharmacy": ["obat", "resep", "racikan"],
        "billing": ["bayar", "piutang", "tarif", "biaya"]
    }

    table_lower = table_name.lower()
    for category, keywords in categories.items():
        if any(keyword in table_lower for keyword in keywords):
            return category

    return "other"

def main():
    """Main function to analyze views and relationships"""
    config = get_db_config()
    database_name = config['database']

    print(f"🔍 Analyzing views and relationships in: {database_name}")

    try:
        with mysql.connector.connect(**config) as conn:
            with conn.cursor() as cursor:
                # Load existing schema
                try:
                    with open("database_schema.json", "r") as f:
                        existing_schema = json.load(f)
                    core_tables = existing_schema.get("tables", [])
                    print(f"📋 Loaded {len(core_tables)} core tables from existing schema")
                except FileNotFoundError:
                    print("❌ database_schema.json not found. Run generate_healthcare_schema.py first.")
                    return 1

                # Extract views
                print("\n🔍 Extracting database views...")
                views = extract_views(cursor, database_name)
                print(f"✅ Found {len(views)} views")

                # Analyze complex relationships
                print("\n🔗 Analyzing complex relationships...")
                complex_relationships = analyze_complex_relationships(cursor, database_name, core_tables)
                print(f"✅ Found {len(complex_relationships['junction_tables'])} junction tables")
                print(f"✅ Found {len(complex_relationships['many_to_many'])} many-to-many relationships")

                # Create graph structure
                print("\n📊 Creating graph nodes and edges...")
                graph_data = create_graph_nodes_edges(existing_schema, complex_relationships)
                print(f"✅ Created {len(graph_data['nodes'])} nodes and {len(graph_data['edges'])} edges")

                # Enhanced schema with views and relationships
                enhanced_schema = existing_schema.copy()
                enhanced_schema["views"] = views
                enhanced_schema["complex_relationships"] = complex_relationships
                enhanced_schema["graph_structure"] = graph_data
                enhanced_schema["metadata"] = {
                    "total_tables": len(core_tables),
                    "total_views": len(views),
                    "total_relationships": len(graph_data['edges']),
                    "junction_tables": len(complex_relationships['junction_tables']),
                    "analysis_timestamp": "2025-01-12"
                }

                # Save enhanced schema
                output_file = "enhanced_database_schema.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(enhanced_schema, f, indent=2, ensure_ascii=False)

                print(f"\n✅ Enhanced schema saved: {output_file}")

                # Print summary
                print(f"\n📈 Analysis Summary:")
                print(f"  • Views: {len(views)}")
                print(f"  • Junction tables: {len(complex_relationships['junction_tables'])}")
                print(f"  • Many-to-many relationships: {len(complex_relationships['many_to_many'])}")
                print(f"  • Graph nodes: {len(graph_data['nodes'])}")
                print(f"  • Graph edges: {len(graph_data['edges'])}")

                if views:
                    print(f"\n📋 Sample views found:")
                    for i, view_name in enumerate(list(views.keys())[:5]):
                        print(f"  • {view_name}")
                        if i >= 4:
                            break

                if complex_relationships['many_to_many']:
                    print(f"\n🔗 Many-to-many relationships:")
                    for rel in complex_relationships['many_to_many'][:3]:
                        print(f"  • {rel['relationship']}")

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())