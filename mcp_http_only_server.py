#!/usr/bin/env python3
"""
Pure MCP HTTP Streamable Server - No stdio, only HTTP with JSON-RPC 2.0
This replaces stdio completely with network-accessible JSON-RPC API
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette import EventSourceResponse
import uvicorn

from mcp.server import Server
from mcp.types import (
    Tool,
    Resource,
    TextContent,
    JSONRPCMessage,
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    ErrorData
)

# Import your MySQL handlers
from mysql_mcp_server.server import get_db_config
from mysql_mcp_server.query_intelligence import QueryIntelligenceService
from mysql.connector import connect, Error
from pydantic import AnyUrl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_http_only")

# Global MCP server and query intelligence
mcp_server = Server("mysql-mcp-http")
query_intelligence = None

# Session management
sessions = {}

class MCPHTTPServer:
    """Pure HTTP MCP Server with JSON-RPC 2.0 compliance"""

    def __init__(self):
        self.app = FastAPI(
            title="MySQL MCP HTTP-Only Server",
            description="JSON-RPC 2.0 compliant MCP server over HTTP",
            version="1.0.0"
        )
        self.setup_cors()
        self.setup_routes()
        self.setup_mcp_handlers()

    def setup_cors(self):
        """Configure CORS for browser access"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def setup_mcp_handlers(self):
        """Register MCP handlers"""

        @mcp_server.list_tools()
        async def handle_list_tools():
            """List available tools"""
            return [
                Tool(
                    name="execute_sql",
                    description="Execute SQL query on MySQL database",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "SQL query to execute"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="answer_database_question",
                    description="Answer natural language database question",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "Natural language question"
                            },
                            "user_context": {
                                "type": "object",
                                "description": "Optional context"
                            }
                        },
                        "required": ["question"]
                    }
                )
            ]

        @mcp_server.list_resources()
        async def handle_list_resources():
            """List all database tables"""
            config = get_db_config()
            try:
                with connect(**config) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SHOW TABLES")
                        tables = cursor.fetchall()
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
                return []

        @mcp_server.read_resource()
        async def handle_read_resource(uri: AnyUrl):
            """Read table contents"""
            config = get_db_config()
            uri_str = str(uri)

            if not uri_str.startswith("mysql://"):
                raise ValueError(f"Invalid URI scheme: {uri_str}")

            parts = uri_str[8:].split('/')
            table = parts[0]

            try:
                with connect(**config) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(f"SELECT * FROM {table} LIMIT 100")
                        columns = [desc[0] for desc in cursor.description]
                        rows = cursor.fetchall()
                        result = [",".join(map(str, row)) for row in rows]
                        return [TextContent(
                            type="text",
                            text="\n".join([",".join(columns)] + result)
                        )]
            except Error as e:
                logger.error(f"Database error: {str(e)}")
                raise RuntimeError(f"Database error: {str(e)}")

        @mcp_server.call_tool()
        async def handle_call_tool(name: str, arguments: dict):
            """Execute tools"""
            if name == "execute_sql":
                query = arguments.get("query")
                if not query:
                    raise ValueError("Query is required")

                config = get_db_config()
                try:
                    with connect(**config) as conn:
                        with conn.cursor() as cursor:
                            cursor.execute(query)

                            if cursor.description is not None:
                                columns = [desc[0] for desc in cursor.description]
                                rows = cursor.fetchall()
                                result = [",".join(map(str, row)) for row in rows]
                                return [TextContent(
                                    type="text",
                                    text="\n".join([",".join(columns)] + result)
                                )]
                            else:
                                conn.commit()
                                return [TextContent(
                                    type="text",
                                    text=f"Query executed. Rows affected: {cursor.rowcount}"
                                )]
                except Error as e:
                    logger.error(f"Error executing SQL: {e}")
                    return [TextContent(type="text", text=f"Error: {str(e)}")]

            elif name == "answer_database_question":
                question = arguments.get("question")
                user_context = arguments.get("user_context", {})

                if not question:
                    raise ValueError("Question is required")

                try:
                    result = await query_intelligence.answer_database_question(question, user_context)
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                except Exception as e:
                    logger.error(f"Error answering question: {e}")
                    error_result = {
                        "success": False,
                        "question": question,
                        "error": str(e)
                    }
                    return [TextContent(type="text", text=json.dumps(error_result, indent=2))]

            else:
                raise ValueError(f"Unknown tool: {name}")

    def setup_routes(self):
        """Setup HTTP routes"""

        @self.app.on_event("startup")
        async def startup():
            """Initialize services on startup"""
            global query_intelligence
            query_intelligence = QueryIntelligenceService()

            # Test database connection
            config = get_db_config()
            logger.info(f"✅ Connected to MySQL: {config['host']}/{config['database']}")
            logger.info(f"🚀 MCP HTTP-Only Server ready at http://0.0.0.0:8002")
            logger.info(f"📡 JSON-RPC endpoint: POST http://0.0.0.0:8002/")
            logger.info(f"⚡ SSE streaming: POST http://0.0.0.0:8002/sse")
            logger.info(f"❌ stdio mode: DISABLED - HTTP only")

        @self.app.get("/")
        async def root():
            """Server information"""
            return {
                "server": "MySQL MCP HTTP-Only",
                "protocol": "JSON-RPC 2.0",
                "endpoints": {
                    "jsonrpc": "POST /",
                    "streaming": "POST /sse",
                    "health": "GET /health"
                },
                "stdio": False,
                "http": True
            }

        @self.app.get("/health")
        async def health():
            """Health check"""
            try:
                config = get_db_config()
                from mysql.connector import connect
                with connect(**config) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.fetchone()

                return {
                    "status": "healthy",
                    "database": "connected",
                    "protocol": "JSON-RPC 2.0"
                }
            except Exception as e:
                return JSONResponse(
                    status_code=503,
                    content={"status": "unhealthy", "error": str(e)}
                )

        @self.app.post("/")
        async def jsonrpc_endpoint(request: Request):
            """
            Main JSON-RPC 2.0 endpoint
            Handles all MCP methods via JSON-RPC protocol
            """
            try:
                body = await request.json()

                # Validate JSON-RPC request
                if "jsonrpc" not in body or body["jsonrpc"] != "2.0":
                    return self.error_response(
                        -32600, "Invalid Request",
                        body.get("id"),
                        "Missing or invalid jsonrpc version"
                    )

                method = body.get("method")
                params = body.get("params", {})
                request_id = body.get("id")

                # Route to appropriate handler
                result = await self.handle_jsonrpc_method(method, params)

                # Return JSON-RPC response
                return {
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id
                }

            except json.JSONDecodeError:
                return self.error_response(-32700, "Parse error", None)
            except Exception as e:
                logger.error(f"Error handling request: {e}")
                return self.error_response(
                    -32603, "Internal error",
                    body.get("id") if "body" in locals() else None,
                    str(e)
                )

        @self.app.post("/sse")
        async def sse_endpoint(request: Request):
            """
            Server-Sent Events endpoint for streaming responses
            Useful for long-running queries or real-time updates
            """
            body = await request.json()

            async def event_generator():
                try:
                    # Send connection established
                    yield {
                        "event": "connected",
                        "data": json.dumps({
                            "jsonrpc": "2.0",
                            "method": "connection.established",
                            "params": {"protocol": "SSE"}
                        })
                    }

                    method = body.get("method")
                    params = body.get("params", {})

                    # For streaming operations
                    if method == "tools/call" and params.get("name") == "answer_database_question":
                        # Stream query processing stages
                        yield {
                            "event": "processing",
                            "data": json.dumps({"stage": "analyzing_question"})
                        }

                        result = await self.handle_jsonrpc_method(method, params)

                        yield {
                            "event": "result",
                            "data": json.dumps({
                                "jsonrpc": "2.0",
                                "result": result,
                                "id": body.get("id")
                            })
                        }
                    else:
                        # Regular processing
                        result = await self.handle_jsonrpc_method(method, params)
                        yield {
                            "event": "result",
                            "data": json.dumps({
                                "jsonrpc": "2.0",
                                "result": result,
                                "id": body.get("id")
                            })
                        }

                    yield {
                        "event": "complete",
                        "data": json.dumps({"status": "success"})
                    }

                except Exception as e:
                    yield {
                        "event": "error",
                        "data": json.dumps(self.error_response(
                            -32603, "Internal error",
                            body.get("id"), str(e)
                        ))
                    }

            return EventSourceResponse(event_generator())

    async def handle_jsonrpc_method(self, method: str, params: Dict[str, Any]) -> Any:
        """
        Route JSON-RPC methods to appropriate handlers

        Supported methods:
        - initialize: Initialize session
        - tools/list: List available tools
        - tools/call: Execute a tool
        - resources/list: List database resources
        - resources/read: Read resource data
        """

        logger.info(f"Handling method: {method}")

        # Initialize session
        if method == "initialize":
            session_id = params.get("sessionId", "default")
            sessions[session_id] = {
                "protocolVersion": params.get("protocolVersion", "1.0.0"),
                "capabilities": params.get("capabilities", {})
            }
            return {
                "protocolVersion": "1.0.0",
                "serverInfo": {
                    "name": "mysql-mcp-http",
                    "version": "1.0.0"
                },
                "capabilities": {
                    "tools": True,
                    "resources": True,
                    "streaming": True
                }
            }

        # List available tools
        elif method == "tools/list":
            tools = await mcp_server._list_tools_handler()
            return {
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema
                    }
                    for tool in tools
                ]
            }

        # Call a tool
        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})

            if not name:
                raise ValueError("Tool name is required")

            # Call the tool directly based on name
            if name == "execute_sql":
                query = arguments.get("query")
                if not query:
                    raise ValueError("Query is required")

                config = get_db_config()
                try:
                    with connect(**config) as conn:
                        with conn.cursor() as cursor:
                            cursor.execute(query)

                            if cursor.description is not None:
                                columns = [desc[0] for desc in cursor.description]
                                rows = cursor.fetchall()
                                data = [dict(zip(columns, row)) for row in rows]
                                return {"columns": columns, "data": data, "rowCount": len(rows)}
                            else:
                                conn.commit()
                                return {"message": f"Query executed. Rows affected: {cursor.rowcount}"}
                except Error as e:
                    logger.error(f"Error executing SQL: {e}")
                    raise ValueError(f"Database error: {str(e)}")

            elif name == "answer_database_question":
                question = arguments.get("question")
                user_context = arguments.get("user_context", {})

                if not question:
                    raise ValueError("Question is required")

                try:
                    result = await query_intelligence.answer_database_question(question, user_context)
                    return result
                except Exception as e:
                    logger.error(f"Error answering question: {e}")
                    raise ValueError(f"Query error: {str(e)}")

            else:
                raise ValueError(f"Unknown tool: {name}")

            # Convert TextContent to dict
            if isinstance(result, list):
                return [{"type": "text", "text": r.text} for r in result]
            return result

        # List resources
        elif method == "resources/list":
            # Use the registered list_resources handler
            handler = mcp_server._list_resources_handler
            if handler:
                resources = await handler()
                return {"resources": [r.__dict__ for r in resources]}
            return {"resources": []}

        # Read resource
        elif method == "resources/read":
            uri = params.get("uri")
            if not uri:
                raise ValueError("Resource URI is required")

            # Use the registered read_resource handler
            handler = mcp_server._read_resource_handler
            if handler:
                result = await handler(uri)
                if isinstance(result, list):
                    return [{"type": "text", "text": r.text} for r in result]
                return result
            raise ValueError("Resource reading not available")

        else:
            raise ValueError(f"Unknown method: {method}")

    def error_response(self, code: int, message: str, id: Any, data: str = None) -> Dict:
        """Create JSON-RPC error response"""
        error = {
            "code": code,
            "message": message
        }
        if data:
            error["data"] = data

        return {
            "jsonrpc": "2.0",
            "error": error,
            "id": id
        }

    def run(self, host: str = "0.0.0.0", port: int = 8002):
        """Run the HTTP server"""
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info"
        )


def main():
    """Main entry point - HTTP only, no stdio"""
    server = MCPHTTPServer()

    # Print startup message
    print("\n" + "="*60)
    print("🚀 MySQL MCP HTTP-Only Server")
    print("="*60)
    print("📡 Protocol: JSON-RPC 2.0 over HTTP")
    print("❌ stdio: DISABLED")
    print("✅ HTTP: ENABLED")
    print("="*60)
    print("\nStarting server...")

    # Run HTTP server only - no stdio
    server.run(host="0.0.0.0", port=8002)


if __name__ == "__main__":
    main()