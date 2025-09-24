#!/usr/bin/env python3
"""
Complete LLM Integration Example with MCP Server
Shows the full workflow from user question to LLM response with MCP data

Workflow:
1. User asks question in frontend
2. Backend calls MCP to get data
3. MCP converts natural language to SQL
4. MCP executes query and returns data
5. Backend sends MCP data + user question to LLM
6. LLM generates response using the data context
7. Response sent back to user
"""

import asyncio
import json
from typing import Dict, Any, Optional
import httpx
from datetime import datetime

# Configuration
MCP_SERVER_URL = "http://localhost:8002"
LLM_API_URL = "http://localhost:11434/api/generate"  # Ollama or your LLM endpoint
LLM_MODEL = "llama2"  # or your preferred model

class MCPLLMIntegration:
    """Integrates MCP data retrieval with LLM response generation"""

    def __init__(self):
        self.mcp_url = MCP_SERVER_URL
        self.llm_url = LLM_API_URL
        self.request_id = 0

    def _next_id(self) -> int:
        """Generate next request ID for JSON-RPC"""
        self.request_id += 1
        return self.request_id

    async def query_mcp_for_data(self, user_question: str) -> Dict[str, Any]:
        """
        Step 2-5: Query MCP server for data based on user question

        Args:
            user_question: Natural language question from user

        Returns:
            MCP response with SQL query and data
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Prepare JSON-RPC request to MCP
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "answer_database_question",
                    "arguments": {
                        "question": user_question,
                        "user_context": {
                            "timestamp": datetime.now().isoformat(),
                            "request_type": "llm_integration"
                        }
                    }
                },
                "id": self._next_id()
            }

            print(f"📡 Calling MCP with question: {user_question}")

            # Send request to MCP
            response = await client.post(
                self.mcp_url,
                json=mcp_request,
                headers={"Content-Type": "application/json"}
            )

            result = response.json()

            if "error" in result:
                print(f"❌ MCP Error: {result['error']}")
                return {"error": result["error"]}

            mcp_data = result.get("result", {})
            print(f"✅ MCP returned data with {len(mcp_data.get('data', ''))} characters")

            return mcp_data

    async def generate_llm_response(self, user_question: str, mcp_data: Dict[str, Any]) -> str:
        """
        Step 6-7: Generate LLM response using MCP data as context

        Args:
            user_question: Original user question
            mcp_data: Data retrieved from MCP

        Returns:
            LLM generated response
        """
        # Prepare context for LLM
        context = self._prepare_llm_context(user_question, mcp_data)

        # For Ollama API
        llm_request = {
            "model": LLM_MODEL,
            "prompt": context,
            "stream": False
        }

        print("🤖 Generating LLM response with data context...")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    self.llm_url,
                    json=llm_request
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("response", "No response generated")
                else:
                    # If Ollama is not available, use a mock response
                    return self._generate_mock_llm_response(user_question, mcp_data)

        except Exception as e:
            print(f"⚠️ LLM API not available, using mock response: {e}")
            return self._generate_mock_llm_response(user_question, mcp_data)

    def _prepare_llm_context(self, user_question: str, mcp_data: Dict[str, Any]) -> str:
        """Prepare context prompt for LLM with MCP data"""

        # Extract relevant information from MCP response
        sql_query = mcp_data.get("sql_query", "N/A")
        data = mcp_data.get("data", "No data")
        formatted_response = mcp_data.get("formatted_response", "")

        # Build context prompt
        context = f"""You are a helpful healthcare data analyst assistant.

USER QUESTION: {user_question}

DATABASE QUERY EXECUTED: {sql_query}

DATA RETRIEVED:
{data}

FORMATTED DATA:
{formatted_response}

Please provide a helpful, natural language response to the user's question based on the data above.
Be specific about the numbers and provide insights where appropriate.

Your response:"""

        return context

    def _generate_mock_llm_response(self, user_question: str, mcp_data: Dict[str, Any]) -> str:
        """Generate a mock LLM response when LLM API is not available"""

        # Parse the data
        data = mcp_data.get("data", "")
        sql_query = mcp_data.get("sql_query", "")

        # Generate appropriate response based on question type
        response_parts = ["Based on the database query results:\n"]

        if "how many" in user_question.lower():
            # Extract count from data
            if "COUNT" in data:
                lines = data.split("\n")
                if len(lines) > 1:
                    count = lines[1].strip()
                    response_parts.append(f"• The total count is: **{count}**")

        elif "show" in user_question.lower() or "list" in user_question.lower():
            response_parts.append(f"• Query executed: `{sql_query}`")
            response_parts.append(f"• Results:\n```\n{data[:500]}...\n```")

        else:
            response_parts.append(f"• The database returned the following data:\n{data[:200]}")

        response_parts.append(f"\n• SQL Query used: `{sql_query}`")
        response_parts.append(f"• Query successful: ✅")

        return "\n".join(response_parts)

    async def process_user_request(self, user_question: str) -> Dict[str, Any]:
        """
        Complete workflow: Process user request through MCP and LLM

        Args:
            user_question: Natural language question from user

        Returns:
            Complete response with data and LLM answer
        """
        print("\n" + "="*60)
        print(f"🔄 Processing request: {user_question}")
        print("="*60)

        # Step 2-5: Get data from MCP
        mcp_data = await self.query_mcp_for_data(user_question)

        if "error" in mcp_data:
            return {
                "success": False,
                "error": mcp_data["error"],
                "user_question": user_question
            }

        # Step 6-7: Generate LLM response with data context
        llm_response = await self.generate_llm_response(user_question, mcp_data)

        # Prepare final response
        final_response = {
            "success": True,
            "user_question": user_question,
            "mcp_data": {
                "sql_query": mcp_data.get("sql_query"),
                "row_count": len(mcp_data.get("data", "").split("\n")) - 1,
                "raw_data": mcp_data.get("data")[:200] + "..." if len(mcp_data.get("data", "")) > 200 else mcp_data.get("data", "")
            },
            "llm_response": llm_response,
            "timestamp": datetime.now().isoformat()
        }

        return final_response


# FastAPI Backend Example
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="LLM + MCP Integration API")

# Add CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize integration
integration = MCPLLMIntegration()

class UserRequest(BaseModel):
    question: str

class UserResponse(BaseModel):
    success: bool
    question: str
    answer: str
    data_summary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@app.post("/api/ask", response_model=UserResponse)
async def handle_user_question(request: UserRequest):
    """
    Step 1 & 8: Frontend endpoint for user questions

    Complete workflow:
    1. Receive user question
    2-5. Query MCP for data
    6-7. Generate LLM response with data context
    8. Return response to user
    """
    try:
        result = await integration.process_user_request(request.question)

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error"))

        return UserResponse(
            success=True,
            question=request.question,
            answer=result["llm_response"],
            data_summary=result.get("mcp_data")
        )

    except Exception as e:
        return UserResponse(
            success=False,
            question=request.question,
            answer="",
            error=str(e)
        )

@app.get("/")
async def root():
    """API information"""
    return {
        "service": "LLM + MCP Integration",
        "endpoints": {
            "/api/ask": "POST - Ask a question (handles MCP + LLM)",
            "/health": "GET - Health check"
        },
        "workflow": [
            "1. User asks question",
            "2. MCP converts to SQL",
            "3. MCP executes query",
            "4. MCP returns data",
            "5. LLM uses data as context",
            "6. LLM generates response",
            "7. User gets answer"
        ]
    }

@app.get("/health")
async def health_check():
    """Check if MCP server is accessible"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{MCP_SERVER_URL}/health")
            mcp_health = response.json()

        return {
            "status": "healthy",
            "mcp_server": mcp_health.get("status", "unknown"),
            "llm_configured": LLM_MODEL
        }
    except:
        return {
            "status": "degraded",
            "mcp_server": "unreachable",
            "llm_configured": LLM_MODEL
        }


# Example usage scenarios
async def example_scenarios():
    """Demonstrate various use cases"""

    integration = MCPLLMIntegration()

    # Example questions
    questions = [
        "How many patients are registered in the database?",
        "What is the total number of doctors?",
        "Show me the latest patient registrations",
        "How many patients visited this month?",
        "What are the most common diagnoses?"
    ]

    for question in questions:
        print(f"\n{'='*60}")
        print(f"Question: {question}")
        print('='*60)

        result = await integration.process_user_request(question)

        if result["success"]:
            print(f"\n✅ Success!")
            print(f"SQL Query: {result['mcp_data']['sql_query']}")
            print(f"Data rows: {result['mcp_data']['row_count']}")
            print(f"\n📝 LLM Response:")
            print(result['llm_response'])
        else:
            print(f"❌ Error: {result.get('error')}")


# HTML Frontend Example
HTML_FRONTEND = """
<!DOCTYPE html>
<html>
<head>
    <title>Healthcare Data Assistant</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .input-group {
            display: flex;
            margin: 20px 0;
        }
        input {
            flex: 1;
            padding: 12px;
            font-size: 16px;
            border: 2px solid #ddd;
            border-radius: 5px 0 0 5px;
        }
        button {
            padding: 12px 30px;
            font-size: 16px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 0 5px 5px 0;
            cursor: pointer;
        }
        button:hover {
            background: #0056b3;
        }
        .response {
            margin-top: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 5px;
            min-height: 100px;
        }
        .loading {
            text-align: center;
            color: #666;
        }
        .error {
            color: #dc3545;
        }
        .success {
            color: #28a745;
        }
        .sql-query {
            background: #272822;
            color: #f8f8f2;
            padding: 10px;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏥 Healthcare Data Assistant</h1>
        <p>Ask questions about your healthcare database in natural language</p>

        <div class="input-group">
            <input
                type="text"
                id="question"
                placeholder="e.g., How many patients are registered?"
                onkeypress="if(event.key==='Enter') askQuestion()"
            />
            <button onclick="askQuestion()">Ask</button>
        </div>

        <div id="response" class="response">
            <p style="color: #666;">Your answer will appear here...</p>
        </div>
    </div>

    <script>
        async function askQuestion() {
            const questionInput = document.getElementById('question');
            const responseDiv = document.getElementById('response');
            const question = questionInput.value.trim();

            if (!question) {
                alert('Please enter a question');
                return;
            }

            // Show loading
            responseDiv.innerHTML = '<div class="loading">🔄 Processing your question...</div>';

            try {
                const response = await fetch('http://localhost:8003/api/ask', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ question: question })
                });

                const data = await response.json();

                if (data.success) {
                    responseDiv.innerHTML = `
                        <h3 class="success">✅ Answer:</h3>
                        <p>${data.answer}</p>
                        ${data.data_summary ? `
                            <div class="sql-query">
                                SQL: ${data.data_summary.sql_query}
                            </div>
                            <p><small>Retrieved ${data.data_summary.row_count} rows</small></p>
                        ` : ''}
                    `;
                } else {
                    responseDiv.innerHTML = `
                        <h3 class="error">❌ Error:</h3>
                        <p>${data.error || 'Something went wrong'}</p>
                    `;
                }
            } catch (error) {
                responseDiv.innerHTML = `
                    <h3 class="error">❌ Connection Error:</h3>
                    <p>Could not connect to the server. Make sure the API is running on port 8003.</p>
                `;
            }
        }
    </script>
</body>
</html>
"""

@app.get("/frontend", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the HTML frontend"""
    return HTMLResponse(content=HTML_FRONTEND)


if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*60)
    print("🚀 LLM + MCP Integration Server")
    print("="*60)
    print("📡 Starting server on http://localhost:8003")
    print("🌐 Frontend available at http://localhost:8003/frontend")
    print("📚 API docs at http://localhost:8003/docs")
    print("="*60)
    print("\nWorkflow:")
    print("1. User asks question → 2. MCP converts to SQL → 3. Execute query")
    print("4. Get data → 5. LLM processes with context → 6. Return answer")
    print("="*60)

    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=8003, reload=False)