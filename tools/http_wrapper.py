from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
import json
import sys
import os

# Add the src directory to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mysql_mcp_server.query_intelligence import query_intelligence
from mysql_mcp_server.server import get_db_config, list_resources
from mysql.connector import connect, Error

app = FastAPI(title="MCP MySQL HTTP Wrapper - Enhanced")

class MCPToolRequest(BaseModel):
    name: str
    arguments: dict

class DatabaseQuestionRequest(BaseModel):
    question: str
    user_context: dict = {}

@app.post("/mcp/tools/call")
async def call_mcp_tool(request: MCPToolRequest):
    """HTTP endpoint for calling MCP tools"""
    try:
        if request.name == "execute_sql":
            # Handle direct SQL execution
            config = get_db_config()
            query = request.arguments.get("query")
            if not query:
                raise ValueError("Query is required")

            with connect(**config) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)

                    if cursor.description is not None:
                        columns = [desc[0] for desc in cursor.description]
                        rows = cursor.fetchall()
                        result = [",".join(map(str, row)) for row in rows]
                        response = "\n".join([",".join(columns)] + result)
                    else:
                        response = f"Query executed successfully. Rows affected: {cursor.rowcount}"

            return {
                "success": True,
                "result": response,
                "tool": request.name
            }

        elif request.name == "answer_database_question":
            # Handle AI-powered database questions
            question = request.arguments.get("question")
            user_context = request.arguments.get("user_context", {})

            if not question:
                raise ValueError("Question is required")

            result = await query_intelligence.answer_database_question(question, user_context)
            return {
                "success": True,
                "result": result,
                "tool": request.name
            }

        else:
            raise ValueError(f"Unknown tool: {request.name}")

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "tool": request.name
        }

@app.post("/mcp/database/question")
async def answer_database_question(request: DatabaseQuestionRequest):
    """Simplified endpoint for database questions"""
    try:
        result = await query_intelligence.answer_database_question(
            request.question,
            request.user_context
        )

        # Parse the CSV data to return as structured JSON
        if result.get("success") and result.get("data"):
            lines = result["data"].strip().split('\n')
            if lines:
                headers = lines[0].split(',')
                data_rows = []
                for line in lines[1:]:
                    if line and line != "No data found":
                        values = line.split(',')
                        row_dict = dict(zip(headers, values))
                        data_rows.append(row_dict)

                # Return simplified response with just the data
                return {
                    "success": True,
                    "sql_query": result.get("sql_query"),
                    "rows_returned": len(data_rows),
                    "columns": headers,
                    "data": data_rows
                }

        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "question": request.question
        }

@app.get("/mcp/resources/list")
async def list_mcp_resources():
    """HTTP endpoint for listing MCP resources (tables)"""
    try:
        resources = await list_resources()
        return {
            "success": True,
            "resources": [
                {
                    "uri": str(resource.uri),
                    "name": resource.name,
                    "description": resource.description,
                    "table_name": str(resource.uri).split("://")[1].split("/")[0]
                } for resource in resources
            ]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "mcp-mysql-wrapper-enhanced"}

@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "MCP MySQL HTTP Wrapper - Enhanced",
        "version": "2.0",
        "endpoints": {
            "health": "/health",
            "mcp_tools": "/mcp/tools/call",
            "database_questions": "/mcp/database/question",
            "list_resources": "/mcp/resources/list"
        },
        "features": [
            "Natural language database queries",
            "AI-powered SQL generation",
            "Safe query execution",
            "Structured response format"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)