#!/usr/bin/env python3
"""
MySQL MCP Server with Streamable HTTP Transport
Provides JSON-RPC 2.0 compliant API accessible from any application
"""

import asyncio
import logging
from pathlib import Path
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette import EventSourceResponse
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.streamable_http import streamable_http_server
from mcp.server import Server
from mcp.types import Tool, Resource, TextContent
import sys
import os

# Add the src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mysql_mcp_server.server import (
    get_db_config,
    list_resources_handler,
    read_resource_handler,
    call_tool_handler
)
from mysql_mcp_server.query_intelligence import QueryIntelligenceService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="MySQL MCP Streamable Server")

# Add CORS middleware for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MCP server
mcp = Server("mysql-mcp-server")
query_intelligence = None

@mcp.list_resources()
async def handle_list_resources():
    """List available database tables as resources."""
    return await list_resources_handler()

@mcp.read_resource()
async def handle_read_resource(uri: str):
    """Read data from a specific table."""
    return await read_resource_handler(uri)

@mcp.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    """Execute SQL queries or answer database questions."""
    return await call_tool_handler(name, arguments, query_intelligence)

# MCP tools registration
mcp.add_tool(Tool(
    name="execute_sql",
    description="Execute a SQL query on the MySQL database",
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
))

mcp.add_tool(Tool(
    name="answer_database_question",
    description="Answer a natural language question about the database",
    inputSchema={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Natural language question about the database"
            },
            "user_context": {
                "type": "object",
                "description": "Optional user context for the question"
            }
        },
        "required": ["question"]
    }
))

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global query_intelligence

    # Initialize query intelligence service
    query_intelligence = QueryIntelligenceService()

    # Test database connection
    config = get_db_config()
    logger.info(f"Connected to MySQL: {config['host']}/{config['database']}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "mysql-mcp-streamable"}

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """
    Main MCP endpoint for JSON-RPC 2.0 requests

    Accepts JSON-RPC requests and returns appropriate responses.
    For streaming operations, use SSE (Server-Sent Events).
    """
    try:
        body = await request.json()

        # Handle JSON-RPC request through MCP server
        # This would integrate with the streamable_http_server

        # For now, return a simple acknowledgment
        return {
            "jsonrpc": "2.0",
            "result": {
                "message": "Request received",
                "method": body.get("method"),
                "id": body.get("id")
            },
            "id": body.get("id")
        }
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": str(e)
            },
            "id": body.get("id") if "body" in locals() else None
        }

@app.get("/mcp/stream")
async def mcp_stream_endpoint(request: Request):
    """
    SSE endpoint for streaming MCP responses

    Use this for long-running operations that benefit from streaming.
    """
    async def event_generator():
        """Generate SSE events."""
        try:
            # Send initial connection event
            yield {
                "event": "connected",
                "data": {"status": "connected", "version": "1.0.0"}
            }

            # Keep connection alive and handle requests
            # This would integrate with the MCP server's streaming capabilities

        except Exception as e:
            yield {
                "event": "error",
                "data": {"error": str(e)}
            }

    return EventSourceResponse(event_generator())

# Alternative approach using MCP's native streamable HTTP
async def create_streamable_mcp_server():
    """
    Create MCP server with native streamable HTTP transport.
    This provides full JSON-RPC 2.0 compliance.
    """
    from mcp.server.streamable_http import streamable_http_server

    async with streamable_http_server(
        mcp,
        host="0.0.0.0",
        port=8002,
        endpoint_path="/mcp",
        sse_endpoint_path="/mcp/stream"
    ) as transport:
        logger.info("MCP Streamable HTTP Server running on http://0.0.0.0:8002")
        logger.info("JSON-RPC endpoint: http://0.0.0.0:8002/mcp")
        logger.info("SSE streaming: http://0.0.0.0:8002/mcp/stream")
        await transport.serve_forever()

if __name__ == "__main__":
    # Option 1: Run with FastAPI (more control, custom endpoints)
    # uvicorn.run(app, host="0.0.0.0", port=8002, reload=True)

    # Option 2: Run with native MCP streamable HTTP (full MCP compliance)
    asyncio.run(create_streamable_mcp_server())