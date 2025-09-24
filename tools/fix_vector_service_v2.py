#!/usr/bin/env python3
"""
Fix for vector knowledge service to handle actual schema structure
"""

import sys
from pathlib import Path

# Read the current file
file_path = Path("src/mysql_mcp_server/vector_knowledge_service.py")
content = file_path.read_text()

# The current wrong handling
old_column_handling = """                # Create column details chunk
                columns = table_info.get('columns', [])
                if columns:
                    columns_detail = f"Table {table_name} - Column Details:\\n"
                    if isinstance(columns, list):
                        # Handle columns as list
                        for col_name in columns:
                            columns_detail += f"  - {col_name}\\n"
                    else:
                        # Handle columns as dictionary
                        for col_name, col_info in columns.items():
                            if isinstance(col_info, dict):
                                columns_detail += f"  - {col_name}: {col_info.get('type', 'unknown')}\\n"
                            else:
                                columns_detail += f"  - {col_name}: {col_info}\\n\""""

# The correct handling
new_column_handling = """                # Create column details chunk
                columns = table_info.get('columns', [])
                if columns:
                    columns_detail = f"Table {table_name} - Column Details:\\n"
                    if isinstance(columns, list):
                        # Handle columns as list of dicts
                        for col in columns:
                            if isinstance(col, dict):
                                col_name = col.get('name', 'unknown')
                                col_type = col.get('type', 'unknown')
                                columns_detail += f"  - {col_name}: {col_type}\\n"
                            else:
                                columns_detail += f"  - {col}\\n"
                    else:
                        # Handle columns as dictionary
                        for col_name, col_info in columns.items():
                            if isinstance(col_info, dict):
                                columns_detail += f"  - {col_name}: {col_info.get('type', 'unknown')}\\n"
                            else:
                                columns_detail += f"  - {col_name}: {col_info}\\n\""""

# Also fix foreign keys handling
old_fk_handling = """                if table_info.get('foreign_keys'):
                    table_overview += "Relationships:\\n"
                    for fk in table_info['foreign_keys']:
                        table_overview += f"  - {fk['column']} → {fk['referenced_table']}.{fk['referenced_column']}\\n\""""

new_fk_handling = """                if table_info.get('foreign_keys'):
                    table_overview += "Relationships:\\n"
                    for fk in table_info['foreign_keys']:
                        if isinstance(fk, dict):
                            table_overview += f"  - {fk['column']} → {fk['referenced_table']}.{fk['referenced_column']}\\n"
                        else:
                            # Handle foreign_keys as list of column names
                            table_overview += f"  - {fk} (foreign key)\\n\""""

# Apply fixes
content = content.replace(old_column_handling, new_column_handling)
content = content.replace(old_fk_handling, new_fk_handling)

# Write back
file_path.write_text(content)

print("✅ Fixed vector_knowledge_service.py to handle actual schema structure")
print("   - Columns are list of dicts with 'name' and 'type' properties")
print("   - Foreign keys can be strings or dicts")
print("\nYou can now run: python3 initialize_vector_database.py")