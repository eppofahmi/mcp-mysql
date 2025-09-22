#!/usr/bin/env python3
"""
Example WebSocket client for MySQL MCP Streaming Server
Demonstrates real-time database querying via WebSocket
"""

import asyncio
import json
import uuid
import time
import websockets
from websockets.exceptions import ConnectionClosedError

class MySQLMCPWebSocketClient:
    def __init__(self, server_url="ws://localhost:8001/ws"):
        self.server_url = server_url
        self.client_id = str(uuid.uuid4())
        self.websocket = None
        self.request_counter = 0

    async def connect(self, user_id=None):
        """Connect to the WebSocket server"""
        url = f"{self.server_url}?client_id={self.client_id}"
        if user_id:
            url += f"&user_id={user_id}"

        try:
            self.websocket = await websockets.connect(url)
            print(f"✅ Connected to server with client_id: {self.client_id}")

            # Listen for welcome message
            welcome_msg = await self.websocket.recv()
            welcome_data = json.loads(welcome_msg)
            print(f"🎉 Welcome: {welcome_data}")

        except Exception as e:
            print(f"❌ Connection failed: {e}")
            raise

    async def disconnect(self):
        """Disconnect from the WebSocket server"""
        if self.websocket:
            await self.websocket.close()
            print("👋 Disconnected from server")

    async def send_message(self, message_type, **kwargs):
        """Send a message to the server"""
        if not self.websocket:
            raise ConnectionError("Not connected to server")

        self.request_counter += 1
        request_id = f"req-{self.request_counter}"

        message = {
            "type": message_type,
            "request_id": request_id,
            **kwargs
        }

        await self.websocket.send(json.dumps(message))
        return request_id

    async def listen_for_responses(self, target_request_id=None, timeout=30):
        """Listen for responses from the server"""
        responses = []
        start_time = time.time()

        try:
            while True:
                if time.time() - start_time > timeout:
                    print(f"⏰ Timeout after {timeout} seconds")
                    break

                # Set a timeout for individual message reception
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    responses.append(data)

                    request_id = data.get('request_id')
                    event_type = data.get('type')

                    print(f"📨 [{event_type}] {request_id}: {self._format_response(data)}")

                    # Stop if we receive completion for our target request
                    if target_request_id and request_id == target_request_id:
                        if event_type in ['database_question_complete', 'sql_execution_complete', 'error']:
                            break

                    # Stop if we receive any completion message when no target specified
                    if not target_request_id and event_type in ['database_question_complete', 'sql_execution_complete']:
                        break

                except asyncio.TimeoutError:
                    # Check if we should continue waiting
                    if target_request_id:
                        continue
                    else:
                        break

        except ConnectionClosedError:
            print("🔌 Connection closed by server")
        except KeyboardInterrupt:
            print("⏹️  Interrupted by user")

        return responses

    def _format_response(self, data):
        """Format response data for display"""
        event_type = data.get('type')
        response_data = data.get('data', data)

        if event_type == 'welcome':
            return f"Client {data.get('client_id')} connected"
        elif event_type == 'query_plan':
            plan = response_data.get('query_plan', {})
            return f"Complexity: {plan.get('complexity', 'unknown')}"
        elif event_type == 'sql_generated':
            return f"SQL: {response_data.get('sql_query', 'N/A')}"
        elif event_type == 'columns':
            cols = response_data.get('columns', [])
            return f"Columns: {', '.join(cols[:5])}{'...' if len(cols) > 5 else ''}"
        elif event_type == 'data_batch':
            rows = response_data.get('rows', [])
            total = response_data.get('total_rows_so_far', 0)
            return f"Batch: {len(rows)} rows (total: {total})"
        elif event_type == 'sql_execution_complete':
            total_rows = response_data.get('total_rows', 0)
            return f"Complete: {total_rows} rows"
        elif event_type == 'error':
            return f"Error: {response_data.get('error', 'Unknown error')}"
        else:
            return str(response_data)

    async def ask_database_question(self, question, user_context=None):
        """Ask a natural language database question"""
        print(f"❓ Asking: {question}")

        request_id = await self.send_message(
            "database_question",
            question=question,
            user_context=user_context or {}
        )

        responses = await self.listen_for_responses(request_id)
        return responses

    async def execute_sql(self, query):
        """Execute a SQL query"""
        print(f"🔧 Executing SQL: {query}")

        request_id = await self.send_message(
            "execute_sql",
            query=query
        )

        responses = await self.listen_for_responses(request_id)
        return responses

    async def list_resources(self):
        """List database resources"""
        print("📋 Listing resources...")

        request_id = await self.send_message("list_resources")

        responses = await self.listen_for_responses(request_id)
        return responses

    async def health_check(self):
        """Perform health check"""
        print("🏥 Checking server health...")

        request_id = await self.send_message("health_check")

        responses = await self.listen_for_responses(request_id)
        return responses

    async def ping(self):
        """Send ping to server"""
        print("🏓 Pinging server...")

        request_id = await self.send_message("ping")

        responses = await self.listen_for_responses(request_id)
        return responses

async def demo_client():
    """Demonstration of the WebSocket client"""
    client = MySQLMCPWebSocketClient()

    try:
        # Connect to server
        await client.connect(user_id="demo-user")

        # Demo 1: Health check
        print("\\n" + "="*50)
        print("DEMO 1: Health Check")
        print("="*50)
        await client.health_check()

        # Demo 2: List resources
        print("\\n" + "="*50)
        print("DEMO 2: List Resources")
        print("="*50)
        await client.list_resources()

        # Demo 3: Natural language question
        print("\\n" + "="*50)
        print("DEMO 3: Natural Language Query")
        print("="*50)
        await client.ask_database_question("Show me 3 doctors from the database")

        # Demo 4: Direct SQL execution
        print("\\n" + "="*50)
        print("DEMO 4: Direct SQL Execution")
        print("="*50)
        await client.execute_sql("SELECT COUNT(*) as total_tables FROM information_schema.tables WHERE table_schema = DATABASE()")

        # Demo 5: Ping test
        print("\\n" + "="*50)
        print("DEMO 5: Ping Test")
        print("="*50)
        await client.ping()

        print("\\n🎉 All demos completed successfully!")

    except KeyboardInterrupt:
        print("\\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\\n❌ Demo failed: {e}")
    finally:
        await client.disconnect()

async def interactive_client():
    """Interactive client for manual testing"""
    client = MySQLMCPWebSocketClient()

    try:
        await client.connect(user_id="interactive-user")

        print("\\n🎮 Interactive MySQL MCP Client")
        print("Commands:")
        print("  ask <question>     - Ask natural language question")
        print("  sql <query>        - Execute SQL query")
        print("  resources          - List database resources")
        print("  health             - Check server health")
        print("  ping               - Ping server")
        print("  quit               - Exit client")
        print()

        while True:
            try:
                command = input("mcp> ").strip()

                if command.lower() in ['quit', 'exit']:
                    break
                elif command.lower() == 'health':
                    await client.health_check()
                elif command.lower() == 'resources':
                    await client.list_resources()
                elif command.lower() == 'ping':
                    await client.ping()
                elif command.startswith('ask '):
                    question = command[4:].strip()
                    if question:
                        await client.ask_database_question(question)
                    else:
                        print("❌ Please provide a question")
                elif command.startswith('sql '):
                    query = command[4:].strip()
                    if query:
                        await client.execute_sql(query)
                    else:
                        print("❌ Please provide a SQL query")
                elif command.strip() == '':
                    continue
                else:
                    print("❌ Unknown command. Type 'quit' to exit.")

            except KeyboardInterrupt:
                break
            except EOFError:
                break

    except Exception as e:
        print(f"❌ Interactive client failed: {e}")
    finally:
        await client.disconnect()

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="MySQL MCP WebSocket Client")
    parser.add_argument("--server", default="ws://localhost:8001/ws", help="WebSocket server URL")
    parser.add_argument("--demo", action="store_true", help="Run demonstration")
    parser.add_argument("--interactive", action="store_true", help="Run interactive mode")

    args = parser.parse_args()

    if args.demo:
        asyncio.run(demo_client())
    elif args.interactive:
        asyncio.run(interactive_client())
    else:
        print("Please specify --demo or --interactive mode")
        parser.print_help()

if __name__ == "__main__":
    main()