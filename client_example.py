#!/usr/bin/env python3
"""
Example client for consuming MySQL MCP Server from external applications
Shows how to use both JSON-RPC and streaming responses
"""

import json
import asyncio
import httpx
from typing import AsyncGenerator

class MCPClient:
    """Client for interacting with MCP Streamable HTTP Server."""

    def __init__(self, base_url: str = "http://localhost:8002"):
        self.base_url = base_url
        self.session_id = None
        self.request_id = 0

    def _next_request_id(self) -> int:
        """Generate next request ID."""
        self.request_id += 1
        return self.request_id

    async def initialize(self) -> dict:
        """Initialize connection with MCP server."""
        async with httpx.AsyncClient() as client:
            request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "1.0.0",
                    "capabilities": {}
                },
                "id": self._next_request_id()
            }

            response = await client.post(
                f"{self.base_url}/mcp",
                json=request,
                headers={"Content-Type": "application/json"}
            )
            return response.json()

    async def execute_sql(self, query: str) -> dict:
        """Execute SQL query via JSON-RPC."""
        async with httpx.AsyncClient() as client:
            request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "execute_sql",
                    "arguments": {"query": query}
                },
                "id": self._next_request_id()
            }

            response = await client.post(
                f"{self.base_url}/mcp",
                json=request,
                headers={"Content-Type": "application/json"}
            )
            return response.json()

    async def ask_question(self, question: str, user_context: dict = None) -> dict:
        """Ask natural language question about database."""
        async with httpx.AsyncClient() as client:
            request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "answer_database_question",
                    "arguments": {
                        "question": question,
                        "user_context": user_context or {}
                    }
                },
                "id": self._next_request_id()
            }

            response = await client.post(
                f"{self.base_url}/mcp",
                json=request,
                headers={"Content-Type": "application/json"}
            )
            return response.json()

    async def ask_question_stream(self, question: str) -> AsyncGenerator[dict, None]:
        """Ask question with streaming response (SSE)."""
        async with httpx.AsyncClient() as client:
            request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "answer_database_question",
                    "arguments": {"question": question}
                },
                "id": self._next_request_id()
            }

            # Send request with SSE accept header
            async with client.stream(
                "POST",
                f"{self.base_url}/mcp/stream",
                json=request,
                headers={"Accept": "text/event-stream"}
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix
                        if data:
                            yield json.loads(data)

    async def list_resources(self) -> dict:
        """List available database resources (tables)."""
        async with httpx.AsyncClient() as client:
            request = {
                "jsonrpc": "2.0",
                "method": "resources/list",
                "params": {},
                "id": self._next_request_id()
            }

            response = await client.post(
                f"{self.base_url}/mcp",
                json=request,
                headers={"Content-Type": "application/json"}
            )
            return response.json()

    async def read_resource(self, uri: str) -> dict:
        """Read data from a specific resource (table)."""
        async with httpx.AsyncClient() as client:
            request = {
                "jsonrpc": "2.0",
                "method": "resources/read",
                "params": {"uri": uri},
                "id": self._next_request_id()
            }

            response = await client.post(
                f"{self.base_url}/mcp",
                json=request,
                headers={"Content-Type": "application/json"}
            )
            return response.json()


# Example usage for different programming languages
def print_examples():
    """Print examples for different programming languages."""

    print("\n=== JavaScript/Node.js Example ===")
    print("""
const axios = require('axios');

async function queryDatabase() {
    const response = await axios.post('http://localhost:8002/mcp', {
        jsonrpc: '2.0',
        method: 'tools/call',
        params: {
            name: 'answer_database_question',
            arguments: {
                question: 'How many patients are registered?'
            }
        },
        id: 1
    });

    console.log(response.data);
}
""")

    print("\n=== cURL Example ===")
    print("""
curl -X POST http://localhost:8002/mcp \\
  -H "Content-Type: application/json" \\
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "execute_sql",
        "arguments": {"query": "SELECT COUNT(*) FROM pasien"}
    },
    "id": 1
}'
""")

    print("\n=== Go Example ===")
    print("""
package main

import (
    "bytes"
    "encoding/json"
    "net/http"
)

type MCPRequest struct {
    JSONRPC string      `json:"jsonrpc"`
    Method  string      `json:"method"`
    Params  interface{} `json:"params"`
    ID      int         `json:"id"`
}

func queryDatabase() {
    request := MCPRequest{
        JSONRPC: "2.0",
        Method:  "tools/call",
        Params: map[string]interface{}{
            "name": "execute_sql",
            "arguments": map[string]string{
                "query": "SELECT * FROM pasien LIMIT 10",
            },
        },
        ID: 1,
    }

    jsonData, _ := json.Marshal(request)
    resp, _ := http.Post("http://localhost:8002/mcp",
                         "application/json",
                         bytes.NewBuffer(jsonData))
    // Handle response...
}
""")


async def main():
    """Demonstrate MCP client usage."""
    client = MCPClient()

    print("=== Python MCP Client Example ===\n")

    # Initialize connection
    print("1. Initializing connection...")
    result = await client.initialize()
    print(f"   Response: {result}\n")

    # Execute SQL query
    print("2. Executing SQL query...")
    result = await client.execute_sql("SELECT COUNT(*) FROM pasien")
    print(f"   Response: {result}\n")

    # Ask natural language question
    print("3. Asking natural language question...")
    result = await client.ask_question("How many doctors are in the system?")
    print(f"   Response: {result}\n")

    # Stream response for complex query
    print("4. Streaming complex query response...")
    async for event in client.ask_question_stream(
        "Show me patient registration trends this month"
    ):
        print(f"   Event: {event}")

    # List available resources
    print("\n5. Listing available resources...")
    result = await client.list_resources()
    print(f"   Tables: {result}\n")

    # Print examples for other languages
    print_examples()


if __name__ == "__main__":
    asyncio.run(main())