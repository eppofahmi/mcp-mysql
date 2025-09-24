# Tools Directory

This directory contains development and diagnostic tools for the MySQL MCP server.

## Scripts Overview

### Core Tools
- `initialize_vector_database.py` - Initialize MongoDB vector database with healthcare knowledge
- `standalone_server.py` - Run the MCP server in standalone mode for testing
- `start_standalone.py` - Simple startup script for standalone mode

### Diagnostic Tools
- `debug_server_startup.py` - Debug server startup issues
- `diagnose_healthcare_integration.py` - Diagnose healthcare integration problems
- `verify_healthcare_integration.py` - Verify healthcare knowledge is properly integrated
- `test_healthcare_integration.py` - Test healthcare-specific functionality

### Database Tools
- `explore_database.py` - Explore and analyze database structure
- `test_real_database.py` - Test queries against real database
- `test_specific_query.py` - Test specific query scenarios

### Utility Scripts
- `fix_and_restart.py` - Fix common issues and restart server
- `fix_vector_service.py` - Fix vector service issues
- `fix_vector_service_v2.py` - Updated vector service fixes
- `http_wrapper.py` - HTTP wrapper utilities
- `show_enhanced_prompt.py` - Display enhanced prompts for debugging

## Usage

Run any script from the project root directory:

```bash
python tools/script_name.py
```