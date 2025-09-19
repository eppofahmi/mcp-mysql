import asyncio
import logging
import os
import sys
import json
from pathlib import Path
from mysql.connector import connect, Error
from mcp.server import Server
from mcp.types import Resource, Tool, TextContent
from pydantic import AnyUrl

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load .env file from the current directory
    env_path = Path('.') / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment from: {env_path.absolute()}")
    else:
        print(f"No .env file found at: {env_path.absolute()}")
except ImportError:
    print("python-dotenv not installed, using system environment variables only")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mysql_mcp_server")

def get_db_config():
    """Get database configuration from environment variables."""
    config = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "database": os.getenv("MYSQL_DATABASE"),
        # Add charset and collation to avoid utf8mb4_0900_ai_ci issues with older MySQL versions
        # These can be overridden via environment variables for specific MySQL versions
        "charset": os.getenv("MYSQL_CHARSET", "utf8mb4"),
        "collation": os.getenv("MYSQL_COLLATION", "utf8mb4_unicode_ci"),
        # Disable autocommit for better transaction control
        "autocommit": True,
        # Set SQL mode for better compatibility - can be overridden
        "sql_mode": os.getenv("MYSQL_SQL_MODE", "TRADITIONAL")
    }

    # TiDB Cloud / SSL Configuration
    use_ssl = os.getenv("USE_SSL", "false").lower() == "true"
    if use_ssl:
        ssl_config = {}

        # SSL CA certificate path
        ssl_ca = os.getenv("SSL_CA")
        if ssl_ca and os.path.exists(ssl_ca):
            ssl_config["ssl_ca"] = ssl_ca

        # SSL verification settings
        ssl_verify_cert = os.getenv("SSL_VERIFY_CERT", "false").lower() == "true"
        ssl_verify_identity = os.getenv("SSL_VERIFY_IDENTITY", "false").lower() == "true"

        if ssl_verify_cert:
            ssl_config["ssl_verify_cert"] = True
        if ssl_verify_identity:
            ssl_config["ssl_verify_identity"] = True

        # Add SSL config if any SSL settings are present
        if ssl_config:
            config.update(ssl_config)
            logger.info("SSL configuration enabled for TiDB Cloud connection")

    # Remove None values to let MySQL connector use defaults if not specified
    config = {k: v for k, v in config.items() if v is not None}

    if not all([config.get("user"), config.get("password"), config.get("database")]):
        logger.error("Missing required database configuration. Please check environment variables:")
        logger.error("MYSQL_USER, MYSQL_PASSWORD, and MYSQL_DATABASE are required")
        raise ValueError("Missing required database configuration")

    return config

# Initialize server
app = Server("mysql_mcp_server")

# Import query intelligence service
from .query_intelligence import query_intelligence

@app.list_resources()
async def list_resources() -> list[Resource]:
    """List MySQL tables as resources."""
    config = get_db_config()
    try:
        logger.info(f"Connecting to MySQL with charset: {config.get('charset')}, collation: {config.get('collation')}")
        with connect(**config) as conn:
            logger.info(f"Successfully connected to MySQL server version: {conn.get_server_info()}")
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                logger.info(f"Found tables: {tables}")

                resources = []
                for table in tables:
                    resources.append(
                        Resource(
                            uri=f"mysql://{table[0]}/data",
                            name=f"Table: {table[0]}",
                            mimeType="text/plain",
                            description=f"Data in table: {table[0]}"
                        )
                    )
                return resources
    except Error as e:
        logger.error(f"Failed to list resources: {str(e)}")
        logger.error(f"Error code: {e.errno}, SQL state: {e.sqlstate}")
        return []

@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    """Read table contents."""
    config = get_db_config()
    uri_str = str(uri)
    logger.info(f"Reading resource: {uri_str}")

    if not uri_str.startswith("mysql://"):
        raise ValueError(f"Invalid URI scheme: {uri_str}")

    parts = uri_str[8:].split('/')
    table = parts[0]

    try:
        logger.info(f"Connecting to MySQL with charset: {config.get('charset')}, collation: {config.get('collation')}")
        with connect(**config) as conn:
            logger.info(f"Successfully connected to MySQL server version: {conn.get_server_info()}")
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT * FROM {table} LIMIT 100")
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                result = [",".join(map(str, row)) for row in rows]
                return "\n".join([",".join(columns)] + result)

    except Error as e:
        logger.error(f"Database error reading resource {uri}: {str(e)}")
        logger.error(f"Error code: {e.errno}, SQL state: {e.sqlstate}")
        raise RuntimeError(f"Database error: {str(e)}")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MySQL tools."""
    logger.info("Listing tools...")
    return [
        Tool(
            name="execute_sql",
            description="Execute an SQL query on the MySQL server",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL query to execute"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="answer_database_question",
            description="Answer natural language questions about the database using AI",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Natural language question about the database"
                    },
                    "user_context": {
                        "type": "object",
                        "description": "Optional user context for the query"
                    }
                },
                "required": ["question"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute SQL commands or answer database questions."""
    logger.info(f"Calling tool: {name} with arguments: {arguments}")

    if name == "execute_sql":
        config = get_db_config()
        query = arguments.get("query")
        if not query:
            raise ValueError("Query is required")

        try:
            logger.info(f"Connecting to MySQL with charset: {config.get('charset')}, collation: {config.get('collation')}")
            with connect(**config) as conn:
                logger.info(f"Successfully connected to MySQL server version: {conn.get_server_info()}")
                with conn.cursor() as cursor:
                    cursor.execute(query)

                    # Special handling for SHOW TABLES
                    if query.strip().upper().startswith("SHOW TABLES"):
                        tables = cursor.fetchall()
                        result = ["Tables_in_" + config["database"]]  # Header
                        result.extend([table[0] for table in tables])
                        return [TextContent(type="text", text="\n".join(result))]

                    # Handle all other queries that return result sets (SELECT, SHOW, DESCRIBE etc.)
                    elif cursor.description is not None:
                        columns = [desc[0] for desc in cursor.description]
                        try:
                            rows = cursor.fetchall()
                            result = [",".join(map(str, row)) for row in rows]
                            return [TextContent(type="text", text="\n".join([",".join(columns)] + result))]
                        except Error as e:
                            logger.warning(f"Error fetching results: {str(e)}")
                            return [TextContent(type="text", text=f"Query executed but error fetching results: {str(e)}")]

                    # Non-SELECT queries
                    else:
                        conn.commit()
                        return [TextContent(type="text", text=f"Query executed successfully. Rows affected: {cursor.rowcount}")]

        except Error as e:
            logger.error(f"Error executing SQL '{query}': {e}")
            logger.error(f"Error code: {e.errno}, SQL state: {e.sqlstate}")
            return [TextContent(type="text", text=f"Error executing query: {str(e)}")]

    elif name == "answer_database_question":
        question = arguments.get("question")
        user_context = arguments.get("user_context", {})

        if not question:
            raise ValueError("Question is required")

        try:
            result = await query_intelligence.answer_database_question(question, user_context)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            logger.error(f"Error answering database question '{question}': {e}")
            error_result = {
                "success": False,
                "question": question,
                "error": str(e),
                "error_type": type(e).__name__
            }
            return [TextContent(type="text", text=json.dumps(error_result, indent=2))]

    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    """Main entry point to run the MCP server."""
    from mcp.server.stdio import stdio_server

    # Add additional debug output
    print("Starting MySQL MCP server with config:", file=sys.stderr)
    config = get_db_config()
    print(f"Host: {config['host']}", file=sys.stderr)
    print(f"Port: {config['port']}", file=sys.stderr)
    print(f"User: {config['user']}", file=sys.stderr)
    print(f"Database: {config['database']}", file=sys.stderr)

    logger.info("Starting MySQL MCP server...")
    logger.info(f"Database config: {config['host']}/{config['database']} as {config['user']}")

    async with stdio_server() as (read_stream, write_stream):
        try:
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
        except Exception as e:
            logger.error(f"Server error: {str(e)}", exc_info=True)
            raise

if __name__ == "__main__":
    asyncio.run(main())