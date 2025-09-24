#!/usr/bin/env python3
"""
Healthcare Database Schema Generator for Allammedica
Focuses on core healthcare entities: patients, doctors, registrations, etc.
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

def get_core_healthcare_tables():
    """Define core healthcare tables to focus on"""
    return [
        'pasien',           # Patients
        'dokter',           # Doctors
        'reg_periksa',      # Registration/Visits
        'poliklinik',       # Polyclinics/Departments
        'penjab',           # Payment methods/Insurance
        'kamar_inap',       # Inpatient rooms
        'bangsal',          # Wards
        'kamar',            # Rooms
        'penyakit',         # Diseases
        'diagnosa_pasien',  # Patient diagnoses
        'rawat_jl_dr',      # Outpatient doctor treatments
        'rawat_inap_dr',    # Inpatient doctor treatments
        'periksa_lab',      # Lab examinations
        'periksa_radiologi',# Radiology examinations
        'obat_racikan',     # Medications
        'resep_dokter',     # Doctor prescriptions
        'operasi',          # Surgeries
        'rujuk',            # Referrals
        'bridging_sep',     # BPJS SEP
        'nota_jalan',       # Outpatient billing
        'nota_inap',        # Inpatient billing
    ]

def analyze_table_structure(cursor, table_name):
    """Get detailed table structure including foreign keys"""
    # Get column information
    cursor.execute(f"DESCRIBE {table_name}")
    columns = []
    primary_keys = []

    for row in cursor.fetchall():
        field, type_info, null, key, default, extra = row
        columns.append({
            "name": field,
            "type": type_info,
            "nullable": null == "YES",
            "key": key,
            "default": default,
            "extra": extra or ""
        })

        if key == "PRI":
            primary_keys.append(field)

    # Get foreign key information
    cursor.execute(f"""
        SELECT
            COLUMN_NAME,
            REFERENCED_TABLE_NAME,
            REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = %s
        AND TABLE_NAME = %s
        AND REFERENCED_TABLE_NAME IS NOT NULL
    """, (os.getenv('MYSQL_DATABASE'), table_name))

    foreign_keys = []
    relationships = []
    for row in cursor.fetchall():
        column_name, ref_table, ref_column = row
        foreign_keys.append(column_name)
        relationships.append(f"{table_name}.{column_name} → {ref_table}.{ref_column}")

    # Get sample data (limit 3 rows)
    try:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
        rows = cursor.fetchall()
        column_names = [col[0] for col in cursor.description]

        sample_data = []
        for row in rows:
            row_dict = {}
            for i, value in enumerate(row):
                # Convert various objects to string for JSON serialization
                if hasattr(value, 'strftime'):  # datetime, date objects
                    row_dict[column_names[i]] = str(value)
                elif hasattr(value, 'total_seconds'):  # timedelta objects
                    row_dict[column_names[i]] = str(value)
                elif isinstance(value, (bytes, bytearray)):  # binary data
                    row_dict[column_names[i]] = "<<BINARY_DATA>>"
                else:
                    row_dict[column_names[i]] = value
            sample_data.append(row_dict)
    except Exception as e:
        print(f"⚠️  Could not get sample data for {table_name}: {e}")
        sample_data = []

    return {
        "columns": columns,
        "primary_keys": primary_keys,
        "foreign_keys": foreign_keys,
        "relationships": relationships,
        "sample_data": sample_data
    }

def generate_test_queries(tables):
    """Generate sample test queries for the healthcare database"""
    return [
        "How many patients are registered?",
        "Show me all doctors",
        "What are the available polyclinics?",
        "Show recent patient registrations",
        "Which patients have been diagnosed recently?",
        "Show lab examination results",
        "What are the most common diseases?",
        "Show inpatient room occupancy",
        "List all prescriptions by doctors",
        "Show BPJS patient registrations",
        "What surgeries were performed this month?",
        "Show radiology examination results",
        "Which patients have been referred?",
        "Show billing information for outpatients",
        "List all medication prescriptions"
    ]

def main():
    """Main function to generate healthcare schema"""
    config = get_db_config()
    core_tables = get_core_healthcare_tables()

    print(f"🏥 Generating healthcare schema for: {config['database']}")
    print(f"📋 Focusing on {len(core_tables)} core healthcare tables")

    try:
        with mysql.connector.connect(**config) as conn:
            with conn.cursor() as cursor:
                # Check which core tables actually exist
                cursor.execute("SHOW TABLES")
                existing_tables = [table[0] for table in cursor.fetchall()]

                available_core_tables = [t for t in core_tables if t in existing_tables]
                missing_tables = [t for t in core_tables if t not in existing_tables]

                print(f"✅ Found {len(available_core_tables)} core tables")
                if missing_tables:
                    print(f"❌ Missing tables: {', '.join(missing_tables)}")

                schema_data = {
                    "database": config['database'],
                    "tables": available_core_tables,
                    "schema": {},
                    "relationships": {
                        "direct": [],
                        "summary": "Healthcare database relationships"
                    },
                    "test_cases": generate_test_queries(available_core_tables)
                }

                # Analyze each available core table
                for table in available_core_tables:
                    print(f"\n🔍 Analyzing table: {table}")
                    try:
                        table_info = analyze_table_structure(cursor, table)
                        schema_data["schema"][table] = table_info

                        # Add relationships to the global list
                        schema_data["relationships"]["direct"].extend(table_info["relationships"])

                        print(f"  ✅ {len(table_info['columns'])} columns, {len(table_info['foreign_keys'])} FKs")

                    except Exception as e:
                        print(f"  ❌ Error analyzing {table}: {e}")
                        continue

                # Write the schema file
                output_file = "database_schema.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(schema_data, f, indent=2, ensure_ascii=False)

                print(f"\n✅ Healthcare schema generated: {output_file}")
                print(f"📊 Total tables analyzed: {len(schema_data['schema'])}")
                print(f"🔗 Total relationships found: {len(schema_data['relationships']['direct'])}")

                # Show some basic stats
                total_columns = sum(len(table['columns']) for table in schema_data['schema'].values())
                total_fks = sum(len(table['foreign_keys']) for table in schema_data['schema'].values())

                print(f"📈 Database statistics:")
                print(f"  • Total columns: {total_columns}")
                print(f"  • Total foreign keys: {total_fks}")
                print(f"  • Average columns per table: {total_columns/len(schema_data['schema']):.1f}")

    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())