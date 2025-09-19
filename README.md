# Loom4 MySQL MCP Server

A Model Context Protocol (MCP) implementation that enables secure interaction with MySQL databases for the Loom4 platform. This server component facilitates communication between AI applications and MySQL databases, making database exploration and analysis safer and more structured through a controlled interface.

## 🚀 Quick Start

### Local Development Setup
```bash
# Navigate to project directory
cd mcp-mysql

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Start HTTP wrapper server (for Loom4 backend integration)
uvicorn http_wrapper:app --reload --port 8001

# Or start native MCP server (for direct MCP protocol communication)
python -m mysql_mcp_server
```

### Environment Configuration
Create a `.env` file in the project root:
```bash
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=your_username
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=your_database
```

## ✨ Features

### Core Functionality
- 🗄️ **Database Resources** - List and explore MySQL tables as MCP resources
- 📊 **Table Content Reading** - Read and analyze table data
- 🔍 **SQL Query Execution** - Execute SQL queries with proper error handling
- 🛡️ **Secure Access** - Environment-based database configuration
- 📝 **Comprehensive Logging** - Detailed operation logging for debugging

### Loom4 Integration Features
- 🌐 **HTTP Wrapper** - FastAPI-based REST endpoints for backend integration
- 🧠 **Intelligent Querying** - AI-powered query generation and optimization
- 🔄 **Real-time Processing** - Async operation support
- 📈 **Performance Monitoring** - Built-in query performance tracking

## 🛠️ Installation & Setup

### For Loom4 Development
```bash
# Clone from Loom4 project
git clone <repository-url>
cd mcp-mysql

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install in editable mode for development
pip install -e .
```

### Standalone Installation
```bash
pip install mysql-mcp-server
```

## 🔧 Usage

### For Loom4 Backend Integration

**HTTP Wrapper Mode** (Recommended for backend integration):

```bash
# Start HTTP wrapper server
uvicorn http_wrapper:app --reload --port 8001
```

This provides REST API endpoints at `http://127.0.0.1:8001`:

- `POST /mcp/tools/call` - Execute SQL queries and MCP tools
- `GET /mcp/resources` - List database resources
- `POST /query/intelligent` - AI-powered intelligent querying
- `GET /health` - Health check endpoint

**Example API usage:**

```python
import requests

# Execute SQL query
response = requests.post("http://127.0.0.1:8001/mcp/tools/call", json={
    "name": "execute_sql",
    "arguments": {"query": "SELECT * FROM users LIMIT 10"}
})

# Intelligent query
response = requests.post("http://127.0.0.1:8001/query/intelligent", json={
    "question": "How many users registered this month?",
    "user_context": {"department": "analytics"}
})
```

### Native MCP Server Mode

For direct MCP protocol communication:

```bash
python -m mysql_mcp_server
```

### With Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mysql": {
      "command": "python",
      "args": ["-m", "mysql_mcp_server"],
      "env": {
        "MYSQL_HOST": "localhost",
        "MYSQL_PORT": "3306",
        "MYSQL_USER": "your_username",
        "MYSQL_PASSWORD": "your_password",
        "MYSQL_DATABASE": "your_database"
      }
    }
  }
}
```

## 🧪 Development & Testing

### Development Setup

```bash
# Clone the Loom4 repository
git clone <repository-url>
cd loom4/mcp-mysql

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install in editable mode
pip install -e .
```

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
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

## 🔒 Security Considerations

### Database Security

- ✅ **Never commit credentials** - Use environment variables only
- ✅ **Create dedicated MySQL user** with minimal required permissions
- ✅ **Never use root credentials** or administrative accounts
- ✅ **Restrict database access** to only necessary operations
- ✅ **Enable comprehensive logging** for audit purposes
- ✅ **Regular security reviews** of database access patterns

### Best Practices

1. **Principle of Least Privilege** - Grant only necessary database permissions
2. **Query Whitelisting** - Consider implementing query validation for production
3. **Connection Monitoring** - Monitor and log all database operations
4. **Environment Isolation** - Separate development, staging, and production databases
5. **Regular Audits** - Periodically review database access logs

### Example MySQL User Setup

```sql
-- Create dedicated user for MCP server
CREATE USER 'mcp_user'@'localhost' IDENTIFIED BY 'secure_password';

-- Grant minimal required permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON your_database.* TO 'mcp_user'@'localhost';

-- Flush privileges
FLUSH PRIVILEGES;
```

## 📄 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

For Loom4-specific issues and integration support, please refer to the main Loom4 documentation or contact the development team.
