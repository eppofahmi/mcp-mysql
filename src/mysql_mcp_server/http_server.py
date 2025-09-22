"""
HTTP Streaming Server for MySQL MCP
Standalone HTTP server with streaming capabilities to replace stdio interface
"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Import existing MCP components
from .server import get_db_config, list_resources
from .query_intelligence import QueryIntelligenceService
from mysql.connector import connect, Error

# Configure logging
logger = logging.getLogger("mysql_mcp_http_server")

class DatabaseQueryRequest(BaseModel):
    question: str
    user_context: Dict[str, Any] = {}
    stream: bool = True

class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]
    stream: bool = False

class ResourceListRequest(BaseModel):
    limit: Optional[int] = None
    offset: Optional[int] = 0

class StreamEvent(BaseModel):
    event: str
    data: Dict[str, Any]
    timestamp: float = None

    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = time.time()
        super().__init__(**data)

class MySQLMCPHTTPServer:
    """HTTP Streaming Server for MySQL MCP"""

    def __init__(self):
        self.app = FastAPI(
            title="MySQL MCP HTTP Streaming Server",
            description="Standalone HTTP server with streaming capabilities for MySQL database operations",
            version="1.0.0"
        )

        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Initialize query intelligence service
        self.query_intelligence = QueryIntelligenceService()

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup HTTP routes"""

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            try:
                config = get_db_config()
                with connect(**config) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT 1")
                        cursor.fetchone()

                return {
                    "status": "healthy",
                    "service": "mysql-mcp-http-server",
                    "timestamp": time.time(),
                    "database": "connected"
                }
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                raise HTTPException(status_code=503, detail=f"Database connection failed: {str(e)}")

        @self.app.get("/resources")
        async def get_resources(limit: Optional[int] = None, offset: int = 0):
            """Get available database resources"""
            try:
                resources = await list_resources()

                # Apply pagination if needed
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

        @self.app.post("/tools/call")
        async def call_tool(request: ToolCallRequest):
            """Execute MCP tool calls"""
            try:
                if request.stream:
                    return StreamingResponse(
                        self._stream_tool_execution(request.name, request.arguments),
                        media_type="text/plain"
                    )
                else:
                    result = await self._execute_tool(request.name, request.arguments)
                    return {"success": True, "result": result}

            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/database/question")
        async def answer_database_question(request: DatabaseQueryRequest):
            """Answer natural language database questions with streaming support"""
            try:
                if request.stream:
                    return StreamingResponse(
                        self._stream_database_question(request.question, request.user_context),
                        media_type="text/plain"
                    )
                else:
                    result = await self.query_intelligence.answer_database_question(
                        request.question,
                        request.user_context
                    )
                    return result

            except Exception as e:
                logger.error(f"Database question failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/database/query/stream")
        async def stream_sql_query(request: Dict[str, Any]):
            """Stream SQL query execution results"""
            try:
                return StreamingResponse(
                    self._stream_sql_execution(request.get("query", "")),
                    media_type="text/plain"
                )
            except Exception as e:
                logger.error(f"SQL streaming failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    async def _stream_database_question(self, question: str, user_context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Stream database question processing"""
        try:
            # Emit start event
            yield self._format_stream_event("start", {
                "question": question,
                "status": "processing"
            })

            # Emit query analysis event
            yield self._format_stream_event("analysis", {
                "status": "analyzing_question",
                "question": question
            })

            # Get query plan
            schema_context = await self.query_intelligence._get_complete_schema_context_cached()
            query_plan = self.query_intelligence._analyze_query_requirements(question, schema_context)
            yield self._format_stream_event("plan", {
                "query_plan": query_plan,
                "complexity": query_plan.get("complexity", "unknown")
            })

            # Generate SQL
            yield self._format_stream_event("sql_generation", {
                "status": "generating_sql"
            })

            sql_query = await self.query_intelligence._generate_sql_with_ollama(question, schema_context)
            yield self._format_stream_event("sql_generated", {
                "sql_query": sql_query
            })

            # Execute SQL with streaming
            yield self._format_stream_event("execution", {
                "status": "executing_query"
            })

            # Stream SQL execution results
            async for chunk in self._stream_sql_execution(sql_query):
                yield chunk

            # Emit completion event
            yield self._format_stream_event("complete", {
                "status": "completed",
                "question": question
            })

        except Exception as e:
            logger.error(f"Streaming database question failed: {e}")
            yield self._format_stream_event("error", {
                "error": str(e),
                "question": question
            })

    async def _stream_sql_execution(self, query: str) -> AsyncGenerator[str, None]:
        """Stream SQL query execution with real-time results"""
        try:
            config = get_db_config()

            yield self._format_stream_event("sql_start", {
                "query": query,
                "status": "connecting"
            })

            with connect(**config) as conn:
                with conn.cursor() as cursor:
                    yield self._format_stream_event("sql_executing", {
                        "status": "executing"
                    })

                    cursor.execute(query)

                    if cursor.description is not None:
                        # Get column names
                        columns = [desc[0] for desc in cursor.description]

                        yield self._format_stream_event("columns", {
                            "columns": columns
                        })

                        # Stream rows as they come
                        row_count = 0
                        batch_size = 10  # Stream in batches
                        batch = []

                        for row in cursor:
                            row_dict = dict(zip(columns, row))
                            batch.append(row_dict)
                            row_count += 1

                            # Yield batch when full
                            if len(batch) >= batch_size:
                                yield self._format_stream_event("data_batch", {
                                    "rows": batch,
                                    "batch_size": len(batch),
                                    "total_rows_so_far": row_count
                                })
                                batch = []

                        # Yield remaining rows
                        if batch:
                            yield self._format_stream_event("data_batch", {
                                "rows": batch,
                                "batch_size": len(batch),
                                "total_rows_so_far": row_count
                            })

                        yield self._format_stream_event("sql_complete", {
                            "total_rows": row_count,
                            "columns": columns
                        })
                    else:
                        # Non-SELECT query
                        yield self._format_stream_event("sql_complete", {
                            "rows_affected": cursor.rowcount,
                            "query_type": "modification"
                        })

        except Exception as e:
            logger.error(f"SQL streaming execution failed: {e}")
            yield self._format_stream_event("sql_error", {
                "error": str(e),
                "query": query
            })

    async def _stream_tool_execution(self, tool_name: str, arguments: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Stream tool execution"""
        try:
            yield self._format_stream_event("tool_start", {
                "tool": tool_name,
                "arguments": arguments
            })

            if tool_name == "execute_sql":
                query = arguments.get("query")
                if not query:
                    raise ValueError("Query is required for execute_sql tool")

                async for chunk in self._stream_sql_execution(query):
                    yield chunk
            else:
                # Handle other tools (non-streaming for now)
                result = await self._execute_tool(tool_name, arguments)
                yield self._format_stream_event("tool_result", {
                    "tool": tool_name,
                    "result": result
                })

        except Exception as e:
            logger.error(f"Tool streaming failed: {e}")
            yield self._format_stream_event("tool_error", {
                "tool": tool_name,
                "error": str(e)
            })

    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool non-streaming"""
        if tool_name == "execute_sql":
            query = arguments.get("query")
            if not query:
                raise ValueError("Query is required")

            config = get_db_config()
            with connect(**config) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)

                    if cursor.description is not None:
                        columns = [desc[0] for desc in cursor.description]
                        rows = cursor.fetchall()
                        return {
                            "columns": columns,
                            "rows": [dict(zip(columns, row)) for row in rows]
                        }
                    else:
                        return {"rows_affected": cursor.rowcount}
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _format_stream_event(self, event: str, data: Dict[str, Any]) -> str:
        """Format stream event as Server-Sent Events (SSE) format"""
        stream_event = StreamEvent(event=event, data=data)
        return f"event: {event}\ndata: {json.dumps(stream_event.dict())}\n\n"

    def run(self, host: str = "0.0.0.0", port: int = 8001, **kwargs):
        """Run the HTTP server"""
        logger.info(f"Starting MySQL MCP HTTP Streaming Server on {host}:{port}")
        uvicorn.run(self.app, host=host, port=port, **kwargs)

# Create server instance
server = MySQLMCPHTTPServer()
app = server.app

async def main():
    """Main entry point for HTTP server"""
    import argparse

    parser = argparse.ArgumentParser(description="MySQL MCP HTTP Streaming Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()

    logger.info("Starting MySQL MCP HTTP Streaming Server...")
    logger.info(f"Database config: {get_db_config()['host']}/{get_db_config()['database']}")

    server.run(host=args.host, port=args.port, reload=args.reload)

if __name__ == "__main__":
    asyncio.run(main())