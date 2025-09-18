# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is a MySQL Model Context Protocol (MCP) server that enables secure interaction with MySQL databases through a controlled interface. The server is designed for integration with AI applications like Claude Desktop and VS Code, not as a standalone application.

## Architecture
- **Core Module**: `src/mysql_mcp_server/server.py` - Main MCP server implementation
- **Entry Point**: `src/mysql_mcp_server/__init__.py` - Package initialization and main() function
- **Configuration**: Environment variables for database connection (MYSQL_HOST, MYSQL_USER, etc.)
- **Dependencies**: Built on `mcp>=1.0.0` and `mysql-connector-python>=9.1.0`

## Development Commands

### Environment Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install in editable mode
pip install -e .
```

### Testing
```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run tests with coverage
pytest --cov
```

### Code Quality
```bash
# Format code
black .

# Sort imports
isort .

# Type checking
mypy src/
```

### Required Environment Variables for Testing
```bash
MYSQL_HOST=127.0.0.1
MYSQL_USER=root
MYSQL_PASSWORD=testpassword
MYSQL_DATABASE=test_db
```

## Key Implementation Details
- Uses async/await pattern throughout
- MCP server exposes MySQL tables as resources and provides SQL query execution tools
- Database configuration loaded from environment variables in `get_db_config()`
- Comprehensive error handling for database connections and SQL operations
- Security-focused design requiring minimal database permissions

## Testing Infrastructure
- Uses pytest with asyncio support
- GitHub Actions CI with MySQL 8.0 service container
- Tests run against Python 3.11 and 3.12
- Integration tests require live MySQL database connection