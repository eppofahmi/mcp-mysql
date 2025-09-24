# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is a MySQL Model Context Protocol (MCP) server that enables secure interaction with MySQL databases through multiple interfaces. The server supports traditional MCP protocol, HTTP REST API, real-time streaming via Server-Sent Events (SSE), and WebSocket communication. It includes advanced AI-powered query intelligence for healthcare-aware database interactions.

## Architecture

### Core Components
- **MCP Server**: `src/mysql_mcp_server/server.py` - Native MCP protocol implementation
- **HTTP Server**: `src/mysql_mcp_server/http_server.py` - HTTP REST API with streaming support
- **WebSocket Server**: `src/mysql_mcp_server/websocket_server.py` - Real-time bi-directional communication
- **Query Intelligence**: `src/mysql_mcp_server/query_intelligence.py` - AI-powered natural language to SQL conversion
- **Schema Knowledge**: `src/mysql_mcp_server/schema_knowledge.py` - Database schema understanding and vectorization
- **Query Validation**: `src/mysql_mcp_server/query_validation.py` - Healthcare-aware query validation and security

### Server Modes
1. **Standalone Server**: `tools/standalone_server.py` - Full-featured HTTP/WebSocket server (recommended)
2. **HTTP Wrapper**: `tools/http_wrapper.py` - Legacy compatibility for Loom4 backend integration
3. **Native MCP**: Direct MCP protocol for Claude Desktop integration

### Key Features
- Multi-interface support (MCP, HTTP, SSE, WebSocket)
- AI-powered query intelligence with healthcare context awareness
- Vector-based schema knowledge for semantic query understanding
- Real-time streaming for long-running queries
- Comprehensive query validation and security features

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

### Running the Server
```bash
# Recommended: Standalone server with all features
python tools/standalone_server.py --host 0.0.0.0 --port 8001 --reload

# Alternative: HTTP wrapper for legacy compatibility
uvicorn tools.http_wrapper:app --reload --port 8001

# Native MCP server (for Claude Desktop)
python -m mysql_mcp_server
```

### Testing
```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run tests with coverage
pytest --cov

# Run specific test file
pytest tests/test_server.py
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

### Required Environment Variables
```bash
# Database connection (required)
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=your_username
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=your_database

# Optional configuration
MYSQL_CHARSET=utf8mb4
MYSQL_COLLATION=utf8mb4_unicode_ci
MYSQL_SQL_MODE=TRADITIONAL
```

## Key Implementation Details

### Multi-Interface Architecture
- **Native MCP Protocol**: Direct integration with Claude Desktop via stdio
- **HTTP REST API**: Traditional request/response endpoints for simple operations
- **Server-Sent Events (SSE)**: Real-time streaming for long-running database queries
- **WebSocket**: Bi-directional real-time communication with connection management
- **Async/Await Pattern**: Used throughout for optimal performance

### AI-Powered Query Intelligence
- **Natural Language Processing**: Converts human questions to optimized SQL queries
- **Healthcare Context Awareness**: Special handling for medical/healthcare database queries
- **Schema Vectorization**: Uses sentence transformers to understand database schema semantically
- **Multi-Table Analysis**: Automatic relationship detection and join path generation
- **Query Validation**: Healthcare-specific query validation and security checks

### Database Integration
- Configuration loaded from environment variables via `get_db_config()`
- Comprehensive error handling for connections and SQL operations
- Support for MySQL, TiDB Cloud, and other MySQL-compatible databases
- Security-focused design requiring minimal database permissions

## Testing Infrastructure
- **pytest** with asyncio support for comprehensive testing
- **GitHub Actions CI** with MySQL 8.0 service container
- **Multi-Python Support**: Tests run against Python 3.11 and 3.12
- **Integration Tests**: Require live MySQL database connection
- **Test Database Setup**: Automated via `tests/conftest.py` fixtures