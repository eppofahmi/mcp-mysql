"""
WebSocket Server for MySQL MCP
Real-time WebSocket communication for database operations
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Set
from fastapi import WebSocket, WebSocketDisconnect, WebSocketException
from websockets.exceptions import ConnectionClosedError

from .server import get_db_config
from .query_intelligence import QueryIntelligenceService
from mysql.connector import connect, Error

logger = logging.getLogger("mysql_mcp_websocket")

class WebSocketConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_sessions: Dict[str, Set[str]] = {}

    async def connect(self, websocket: WebSocket, client_id: str, user_id: str = None):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections[client_id] = websocket

        if user_id:
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = set()
            self.user_sessions[user_id].add(client_id)

        logger.info(f"WebSocket client {client_id} connected (user: {user_id})")

    def disconnect(self, client_id: str):
        """Remove WebSocket connection"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]

        # Remove from user sessions
        for user_id, sessions in self.user_sessions.items():
            if client_id in sessions:
                sessions.remove(client_id)
                if not sessions:  # Remove empty sets
                    del self.user_sessions[user_id]
                break

        logger.info(f"WebSocket client {client_id} disconnected")

    async def send_personal_message(self, message: dict, client_id: str):
        """Send message to specific client"""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(json.dumps(message))
            except (WebSocketDisconnect, ConnectionClosedError):
                self.disconnect(client_id)

    async def send_to_user(self, message: dict, user_id: str):
        """Send message to all connections for a user"""
        if user_id in self.user_sessions:
            for client_id in list(self.user_sessions[user_id]):
                await self.send_personal_message(message, client_id)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for client_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, client_id)

class MySQLMCPWebSocketHandler:
    """WebSocket handler for MySQL MCP operations"""

    def __init__(self, connection_manager: WebSocketConnectionManager):
        self.connection_manager = connection_manager
        self.query_intelligence = QueryIntelligenceService()

    async def handle_connection(self, websocket: WebSocket, client_id: str):
        """Handle WebSocket connection lifecycle"""
        try:
            # Extract user_id from query parameters if available
            user_id = websocket.query_params.get("user_id")

            await self.connection_manager.connect(websocket, client_id, user_id)

            # Send welcome message
            await self.send_message(websocket, {
                "type": "welcome",
                "client_id": client_id,
                "user_id": user_id,
                "timestamp": time.time(),
                "capabilities": [
                    "database_questions",
                    "sql_execution",
                    "real_time_streaming",
                    "query_analysis"
                ]
            })

            # Listen for messages
            while True:
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    await self.handle_message(websocket, client_id, message)
                except WebSocketDisconnect:
                    break
                except json.JSONDecodeError as e:
                    await self.send_error(websocket, f"Invalid JSON: {str(e)}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
                    await self.send_error(websocket, f"Message handling error: {str(e)}")

        except WebSocketDisconnect:
            logger.info(f"WebSocket {client_id} disconnected")
        except Exception as e:
            logger.error(f"WebSocket error for {client_id}: {e}")
        finally:
            self.connection_manager.disconnect(client_id)

    async def handle_message(self, websocket: WebSocket, client_id: str, message: dict):
        """Handle incoming WebSocket messages"""
        message_type = message.get("type")
        request_id = message.get("request_id", "unknown")

        try:
            if message_type == "database_question":
                await self.handle_database_question(websocket, client_id, message, request_id)
            elif message_type == "execute_sql":
                await self.handle_sql_execution(websocket, client_id, message, request_id)
            elif message_type == "list_resources":
                await self.handle_list_resources(websocket, client_id, request_id)
            elif message_type == "health_check":
                await self.handle_health_check(websocket, client_id, request_id)
            elif message_type == "ping":
                await self.send_message(websocket, {
                    "type": "pong",
                    "request_id": request_id,
                    "timestamp": time.time()
                })
            else:
                await self.send_error(websocket, f"Unknown message type: {message_type}", request_id)

        except Exception as e:
            logger.error(f"Error handling {message_type}: {e}")
            await self.send_error(websocket, str(e), request_id)

    async def handle_database_question(self, websocket: WebSocket, client_id: str, message: dict, request_id: str):
        """Handle database question with streaming response"""
        question = message.get("question")
        user_context = message.get("user_context", {})

        if not question:
            await self.send_error(websocket, "Question is required", request_id)
            return

        # Send start event
        await self.send_message(websocket, {
            "type": "database_question_start",
            "request_id": request_id,
            "question": question,
            "timestamp": time.time()
        })

        try:
            # Analyze query
            await self.send_message(websocket, {
                "type": "analysis_start",
                "request_id": request_id,
                "status": "analyzing_question"
            })

            schema_context = await self.query_intelligence._get_complete_schema_context_cached()
            query_plan = self.query_intelligence._analyze_query_requirements(question, schema_context)

            await self.send_message(websocket, {
                "type": "query_plan",
                "request_id": request_id,
                "query_plan": query_plan
            })

            # Generate SQL
            await self.send_message(websocket, {
                "type": "sql_generation_start",
                "request_id": request_id
            })

            sql_query = await self.query_intelligence._generate_sql_with_ollama(question, schema_context)

            await self.send_message(websocket, {
                "type": "sql_generated",
                "request_id": request_id,
                "sql_query": sql_query
            })

            # Execute SQL with streaming
            await self.stream_sql_execution(websocket, client_id, sql_query, request_id)

            # Send completion
            await self.send_message(websocket, {
                "type": "database_question_complete",
                "request_id": request_id,
                "question": question,
                "timestamp": time.time()
            })

        except Exception as e:
            await self.send_error(websocket, f"Database question failed: {str(e)}", request_id)

    async def handle_sql_execution(self, websocket: WebSocket, client_id: str, message: dict, request_id: str):
        """Handle direct SQL execution"""
        query = message.get("query")

        if not query:
            await self.send_error(websocket, "SQL query is required", request_id)
            return

        await self.stream_sql_execution(websocket, client_id, query, request_id)

    async def stream_sql_execution(self, websocket: WebSocket, client_id: str, query: str, request_id: str):
        """Stream SQL execution results"""
        try:
            await self.send_message(websocket, {
                "type": "sql_execution_start",
                "request_id": request_id,
                "query": query
            })

            config = get_db_config()

            with connect(**config) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)

                    if cursor.description is not None:
                        # Send column information
                        columns = [desc[0] for desc in cursor.description]
                        await self.send_message(websocket, {
                            "type": "columns",
                            "request_id": request_id,
                            "columns": columns
                        })

                        # Stream rows in real-time
                        row_count = 0
                        batch_size = 5  # Smaller batches for real-time feel
                        batch = []

                        for row in cursor:
                            row_dict = dict(zip(columns, row))
                            batch.append(row_dict)
                            row_count += 1

                            if len(batch) >= batch_size:
                                await self.send_message(websocket, {
                                    "type": "data_batch",
                                    "request_id": request_id,
                                    "rows": batch,
                                    "batch_number": (row_count // batch_size),
                                    "total_rows_so_far": row_count
                                })
                                batch = []
                                # Small delay to simulate real-time streaming
                                await asyncio.sleep(0.1)

                        # Send remaining rows
                        if batch:
                            await self.send_message(websocket, {
                                "type": "data_batch",
                                "request_id": request_id,
                                "rows": batch,
                                "batch_number": -1,  # Final batch
                                "total_rows_so_far": row_count
                            })

                        await self.send_message(websocket, {
                            "type": "sql_execution_complete",
                            "request_id": request_id,
                            "total_rows": row_count,
                            "query_type": "select"
                        })
                    else:
                        # Non-SELECT query
                        await self.send_message(websocket, {
                            "type": "sql_execution_complete",
                            "request_id": request_id,
                            "rows_affected": cursor.rowcount,
                            "query_type": "modification"
                        })

        except Exception as e:
            await self.send_error(websocket, f"SQL execution failed: {str(e)}", request_id)

    async def handle_list_resources(self, websocket: WebSocket, client_id: str, request_id: str):
        """Handle resource listing"""
        try:
            from .server import list_resources
            resources = await list_resources()

            await self.send_message(websocket, {
                "type": "resources",
                "request_id": request_id,
                "resources": resources,
                "total": len(resources)
            })
        except Exception as e:
            await self.send_error(websocket, f"Failed to list resources: {str(e)}", request_id)

    async def handle_health_check(self, websocket: WebSocket, client_id: str, request_id: str):
        """Handle health check"""
        try:
            config = get_db_config()
            with connect(**config) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()

            await self.send_message(websocket, {
                "type": "health_check_result",
                "request_id": request_id,
                "status": "healthy",
                "database": "connected",
                "timestamp": time.time()
            })
        except Exception as e:
            await self.send_message(websocket, {
                "type": "health_check_result",
                "request_id": request_id,
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            })

    async def send_message(self, websocket: WebSocket, message: dict):
        """Send message via WebSocket"""
        try:
            await websocket.send_text(json.dumps(message))
        except (WebSocketDisconnect, ConnectionClosedError):
            logger.warning("Attempted to send message to disconnected WebSocket")

    async def send_error(self, websocket: WebSocket, error: str, request_id: str = None):
        """Send error message"""
        await self.send_message(websocket, {
            "type": "error",
            "request_id": request_id,
            "error": error,
            "timestamp": time.time()
        })

# Global connection manager
connection_manager = WebSocketConnectionManager()
websocket_handler = MySQLMCPWebSocketHandler(connection_manager)