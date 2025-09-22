#!/usr/bin/env python3
"""
MySQL MCP Standalone Server
Combines HTTP REST API, Server-Sent Events streaming, and WebSocket real-time communication
Replaces stdio interface with full HTTP/WebSocket standalone application
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Import MCP components
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mysql_mcp_server.http_server import MySQLMCPHTTPServer
from mysql_mcp_server.websocket_server import connection_manager, websocket_handler
from mysql_mcp_server.server import get_db_config

# Custom JSON encoder for database types
class DatabaseJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)

def json_dumps(obj):
    """Custom JSON dumps with database type handling"""
    return json.dumps(obj, cls=DatabaseJSONEncoder)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mysql_mcp_standalone")

class StandaloneMySQLMCPServer:
    """Unified standalone server with HTTP REST, SSE streaming, and WebSocket support"""

    def __init__(self):
        self.app = FastAPI(
            title="MySQL MCP Standalone Server",
            description="Complete MySQL database interface with REST API, streaming, and real-time WebSocket communication",
            version="2.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )

        # Configure CORS for web applications
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Initialize HTTP server
        self.http_server = MySQLMCPHTTPServer()

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup all routes for the standalone server"""

        # ============= BASIC INFO ENDPOINTS =============
        @self.app.get("/", response_class=HTMLResponse)
        async def root():
            """Server information and documentation"""
            return f"""
            <html>
                <head>
                    <title>MySQL MCP Standalone Server</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 40px; }}
                        .endpoint {{ background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 5px; }}
                        .method {{ font-weight: bold; color: #007acc; }}
                        .ws {{ color: #ff6b35; }}
                    </style>
                </head>
                <body>
                    <h1>MySQL MCP Standalone Server</h1>
                    <p>Version 2.0.0 - HTTP REST API, Server-Sent Events, and WebSocket interface</p>

                    <h2>Available Endpoints</h2>

                    <div class="endpoint">
                        <span class="method">GET</span> <code>/health</code> - Health check
                    </div>

                    <div class="endpoint">
                        <span class="method">GET</span> <code>/resources</code> - List database resources
                    </div>

                    <div class="endpoint">
                        <span class="method">POST</span> <code>/database/question</code> - Natural language database queries
                    </div>

                    <div class="endpoint">
                        <span class="method">POST</span> <code>/database/question/stream</code> - Streaming database queries (SSE)
                    </div>

                    <div class="endpoint">
                        <span class="method">POST</span> <code>/tools/call</code> - Execute MCP tools
                    </div>

                    <div class="endpoint">
                        <span class="method">POST</span> <code>/sql/execute</code> - Execute SQL queries
                    </div>

                    <div class="endpoint">
                        <span class="method">POST</span> <code>/sql/stream</code> - Stream SQL execution (SSE)
                    </div>

                    <div class="endpoint">
                        <span class="method ws">WebSocket</span> <code>/ws</code> - Real-time WebSocket interface
                    </div>

                    <h2>Documentation</h2>
                    <p><a href="/docs">OpenAPI Documentation (Swagger UI)</a></p>
                    <p><a href="/redoc">ReDoc Documentation</a></p>

                    <h2>WebSocket Usage</h2>
                    <p>Connect to <code>ws://{{host}}:{{port}}/ws?client_id={{uuid}}&user_id={{optional}}</code></p>

                    <h3>WebSocket Message Types</h3>
                    <ul>
                        <li><code>database_question</code> - Ask natural language questions</li>
                        <li><code>execute_sql</code> - Execute SQL queries</li>
                        <li><code>list_resources</code> - Get database resources</li>
                        <li><code>health_check</code> - Check server health</li>
                        <li><code>ping</code> - Ping/pong for connection testing</li>
                    </ul>
                </body>
            </html>
            """

        @self.app.get("/info")
        async def server_info():
            """Get server information and configuration"""
            try:
                config = get_db_config()
                return {
                    "server": "MySQL MCP Standalone Server",
                    "version": "2.0.0",
                    "interfaces": ["HTTP REST", "Server-Sent Events", "WebSocket"],
                    "capabilities": [
                        "natural_language_queries",
                        "sql_execution",
                        "real_time_streaming",
                        "database_schema_analysis",
                        "query_intelligence"
                    ],
                    "database": {
                        "host": config["host"],
                        "port": config["port"],
                        "database": config["database"],
                        "user": config["user"]
                    },
                    "connections": {
                        "websocket_active": len(connection_manager.active_connections),
                        "users_online": len(connection_manager.user_sessions)
                    },
                    "timestamp": time.time()
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        # ============= INHERIT HTTP SERVER ROUTES =============
        # Health check
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            try:
                config = get_db_config()
                from mysql.connector import connect

                # Test database connection
                with connect(**config) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT 1 as test")
                        result = cursor.fetchone()

                return {
                    "status": "healthy",
                    "service": "mysql-mcp-standalone-server",
                    "timestamp": time.time(),
                    "database": "connected",
                    "test_query": "passed"
                }
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return {
                    "status": "unhealthy",
                    "service": "mysql-mcp-standalone-server",
                    "timestamp": time.time(),
                    "database": "disconnected",
                    "error": str(e)
                }

        # Resources
        @self.app.get("/resources")
        async def get_resources(limit: Optional[int] = None, offset: int = 0):
            # Call the HTTP server's resources endpoint
            from mysql_mcp_server.server import list_resources
            try:
                resources = await list_resources()
                if limit is not None:
                    resources = resources[offset:offset + limit]
                return {
                    "success": True,
                    "resources": resources,
                    "total": len(resources),
                    "offset": offset,
                    "limit": limit
                }
            except Exception as e:
                logger.error(f"Failed to list resources: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        # ============= ENHANCED STREAMING ENDPOINTS =============
        @self.app.post("/database/question")
        async def database_question(request: Dict[str, Any]):
            """Non-streaming database questions"""
            from mysql_mcp_server.query_intelligence import query_intelligence
            try:
                result = await query_intelligence.answer_database_question(
                    request.get("question", ""),
                    request.get("user_context", {})
                )

                # Parse the CSV data to return as structured JSON
                if result.get("success") and result.get("data"):
                    raw_data = result["data"]

                    # Handle different data formats
                    if isinstance(raw_data, str):
                        lines = raw_data.strip().split('\n')
                        if lines and len(lines) > 1:
                            headers = lines[0].split(',')
                            data_rows = []

                            for line in lines[1:]:
                                if line.strip() and line != "No data found":
                                    # Handle comma-separated values, being careful with commas in data
                                    values = line.split(',')
                                    if len(values) >= len(headers):
                                        row_dict = dict(zip(headers, values[:len(headers)]))
                                        data_rows.append(row_dict)

                            return {
                                "success": True,
                                "sql_query": result.get("sql_query"),
                                "rows_returned": len(data_rows),
                                "columns": headers,
                                "data": data_rows
                            }

                # If parsing fails or data is in different format, try direct approach
                if result.get("success"):
                    # Execute the SQL directly to get clean results
                    sql_query = result.get("sql_query")
                    if sql_query:
                        config = get_db_config()
                        from mysql.connector import connect

                        with connect(**config) as conn:
                            with conn.cursor() as cursor:
                                cursor.execute(sql_query)

                                if cursor.description is not None:
                                    columns = [desc[0] for desc in cursor.description]
                                    rows = cursor.fetchall()
                                    data_rows = [dict(zip(columns, row)) for row in rows]

                                    return {
                                        "success": True,
                                        "sql_query": sql_query,
                                        "rows_returned": len(data_rows),
                                        "columns": columns,
                                        "data": data_rows
                                    }

                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/database/question/stream")
        async def stream_database_question(request: Dict[str, Any]):
            """Server-Sent Events streaming for database questions"""
            return StreamingResponse(
                self._stream_database_question(
                    request.get("question", ""),
                    request.get("user_context", {})
                ),
                media_type="text/plain"
            )

        @self.app.post("/sql/execute")
        async def execute_sql(request: Dict[str, Any]):
            """Execute SQL query (non-streaming)"""
            try:
                query = request.get("query")
                if not query:
                    raise HTTPException(status_code=400, detail="SQL query is required")

                config = get_db_config()
                from mysql.connector import connect

                with connect(**config) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(query)

                        if cursor.description is not None:
                            columns = [desc[0] for desc in cursor.description]
                            rows = cursor.fetchall()
                            return {
                                "success": True,
                                "sql_query": query,
                                "columns": columns,
                                "rows_returned": len(rows),
                                "data": [dict(zip(columns, row)) for row in rows]
                            }
                        else:
                            return {
                                "success": True,
                                "sql_query": query,
                                "rows_affected": cursor.rowcount,
                                "query_type": "modification"
                            }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/sql/stream")
        async def stream_sql_execution(request: Dict[str, Any]):
            """Server-Sent Events streaming for SQL execution"""
            query = request.get("query")
            if not query:
                raise HTTPException(status_code=400, detail="SQL query is required")

            return StreamingResponse(
                self._stream_sql_execution(query),
                media_type="text/plain"
            )

        # ============= WEBSOCKET ENDPOINT =============
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time communication"""
            client_id = websocket.query_params.get("client_id", str(uuid.uuid4()))
            await websocket_handler.handle_connection(websocket, client_id)

        # ============= LEGACY COMPATIBILITY =============
        @self.app.post("/mcp/database/question")
        async def legacy_database_question(request: Dict[str, Any]):
            """Legacy endpoint for backward compatibility"""
            return await database_question(request)

        @self.app.post("/tools/call")
        async def call_tool(request: Dict[str, Any]):
            """Tool calling endpoint"""
            try:
                tool_name = request.get("name")
                arguments = request.get("arguments", {})

                if tool_name == "execute_sql":
                    query = arguments.get("query")
                    return await execute_sql({"query": query})
                else:
                    raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")

            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

    async def _stream_database_question(self, question: str, user_context: Dict[str, Any]):
        """Stream database question processing using Server-Sent Events"""
        from mysql_mcp_server.query_intelligence import query_intelligence

        try:
            yield self._format_sse_event("start", {
                "question": question,
                "timestamp": time.time()
            })

            # Analyze query
            yield self._format_sse_event("analysis", {"status": "analyzing"})

            schema_context = await query_intelligence._get_complete_schema_context_cached()
            query_plan = query_intelligence._analyze_query_requirements(question, schema_context)
            yield self._format_sse_event("plan", {"query_plan": query_plan})

            # Generate SQL
            yield self._format_sse_event("sql_generation", {"status": "generating"})

            sql_query = await query_intelligence._generate_sql_with_ollama(question, schema_context)
            yield self._format_sse_event("sql_generated", {"sql_query": sql_query})

            # Execute with streaming
            yield self._format_sse_event("execution", {"status": "executing"})

            async for chunk in self._stream_sql_execution(sql_query):
                yield chunk

            yield self._format_sse_event("complete", {
                "question": question,
                "timestamp": time.time()
            })

        except Exception as e:
            yield self._format_sse_event("error", {"error": str(e)})

    async def _stream_sql_execution(self, query: str):
        """Stream SQL execution results"""
        from mysql.connector import connect

        try:
            yield self._format_sse_event("sql_start", {"query": query})

            config = get_db_config()
            with connect(**config) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)

                    if cursor.description is not None:
                        columns = [desc[0] for desc in cursor.description]
                        yield self._format_sse_event("columns", {"columns": columns})

                        row_count = 0
                        batch_size = 10
                        batch = []

                        for row in cursor:
                            row_dict = dict(zip(columns, row))
                            batch.append(row_dict)
                            row_count += 1

                            if len(batch) >= batch_size:
                                yield self._format_sse_event("data_batch", {
                                    "rows": batch,
                                    "batch_size": len(batch),
                                    "total_rows_so_far": row_count
                                })
                                batch = []

                        if batch:
                            yield self._format_sse_event("data_batch", {
                                "rows": batch,
                                "batch_size": len(batch),
                                "total_rows_so_far": row_count
                            })

                        yield self._format_sse_event("sql_complete", {
                            "total_rows": row_count,
                            "columns": columns
                        })
                    else:
                        yield self._format_sse_event("sql_complete", {
                            "rows_affected": cursor.rowcount,
                            "query_type": "modification"
                        })

        except Exception as e:
            yield self._format_sse_event("error", {"error": str(e), "query": query})

    def _format_sse_event(self, event: str, data: Dict[str, Any]) -> str:
        """Format Server-Sent Events"""
        return f"event: {event}\\ndata: {json_dumps(data)}\\n\\n"

    def run(self, host: str = "0.0.0.0", port: int = 8001, **kwargs):
        """Run the standalone server"""
        logger.info("="*60)
        logger.info("🚀 MySQL MCP Standalone Server Starting")
        logger.info("="*60)
        logger.info(f"📍 Host: {host}")
        logger.info(f"🔌 Port: {port}")
        logger.info(f"📊 HTTP REST API: http://{host}:{port}")
        logger.info(f"⚡ WebSocket: ws://{host}:{port}/ws")
        logger.info(f"📖 Documentation: http://{host}:{port}/docs")
        logger.info("="*60)

        # Validate database connection
        try:
            config = get_db_config()
            logger.info(f"🗄️  Database: {config['host']}/{config['database']} as {config['user']}")
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return

        # Remove reload if passed to avoid the warning
        if 'reload' in kwargs:
            logger.warning("⚠️  Reload mode not supported in direct execution. Use: uvicorn app:app --reload")
            kwargs.pop('reload')

        uvicorn.run(self.app, host=host, port=port, **kwargs)

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="MySQL MCP Standalone Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")

    args = parser.parse_args()

    server = StandaloneMySQLMCPServer()
    server.run(
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1
    )

if __name__ == "__main__":
    main()