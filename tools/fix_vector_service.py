#!/usr/bin/env python3
"""
Quick fix for vector knowledge service to handle list-type columns
"""

import sys
from pathlib import Path

# Read the current file
file_path = Path("src/mysql_mcp_server/vector_knowledge_service.py")
content = file_path.read_text()

# Fix 1: Handle columns as list instead of dict
old_line1 = "                table_overview += f\"Columns: {len(table_info.get('columns', {}))}\\n\""
new_line1 = """                columns = table_info.get('columns', [])
                table_overview += f\"Columns: {len(columns)}\\n\""""

# Fix 2: Handle column details for list
old_block = """                # Create column details chunk
                if table_info.get('columns'):
                    columns_detail = f\"Table {table_name} - Column Details:\\n\"
                    for col_name, col_info in table_info['columns'].items():
                        columns_detail += f\"  - {col_name}: {col_info.get('type', 'unknown')} - {col_info.get('description', 'No description')}\\n\""""

new_block = """                # Create column details chunk
                columns = table_info.get('columns', [])
                if columns:
                    columns_detail = f\"Table {table_name} - Column Details:\\n\"
                    if isinstance(columns, list):
                        # Handle columns as list
                        for col_name in columns:
                            columns_detail += f\"  - {col_name}\\n\"
                    else:
                        # Handle columns as dictionary
                        for col_name, col_info in columns.items():
                            if isinstance(col_info, dict):
                                columns_detail += f\"  - {col_name}: {col_info.get('type', 'unknown')}\\n\"
                            else:
                                columns_detail += f\"  - {col_name}: {col_info}\\n\""""

# Apply fixes
content = content.replace(old_line1, new_line1)
content = content.replace(old_block, new_block)

# Write back
file_path.write_text(content)

print("✅ Fixed vector_knowledge_service.py to handle list-type columns")
print("   - Updated column count handling")
print("   - Updated column details iteration")
print("\nYou can now run: python3 initialize_vector_database.py")