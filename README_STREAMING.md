# MySQL MCP Streaming Server

A standalone HTTP/WebSocket server that replaces stdio communication with full streaming capabilities for real-time database operations.

## 🚀 New Features

### Multiple Interface Options
- **HTTP REST API**: Traditional request/response for simple operations
- **Server-Sent Events (SSE)**: Real-time streaming for long-running queries
- **WebSocket**: Bi-directional real-time communication
- **Legacy Compatibility**: Maintains backward compatibility with existing clients

### Streaming Capabilities
- Real-time query results as they're processed
- Progressive data delivery for large result sets
- Live query analysis and SQL generation feedback
- Connection status and health monitoring

## 📦 Installation

```bash
# Install additional dependencies
pip install fastapi uvicorn[standard] websockets

# Or install all requirements
pip install -r requirements.txt
```

## 🏃‍♂️ Running the Server

### Standalone Server (Recommended)
```bash
# Using the startup script
python start_standalone.py

# Direct execution
python standalone_server.py

# With custom configuration
python standalone_server.py --host 0.0.0.0 --port 8001 --reload
```

### HTTP-only Server
```bash
# Using package entry point
python -m mysql_mcp_server --http

# Direct execution
python -c "from mysql_mcp_server import main_http; main_http()"
```

### Traditional stdio (backward compatibility)
```bash
# Default behavior unchanged
python -m mysql_mcp_server
```

## 📡 API Endpoints

### Basic Information
- `GET /` - Server information and documentation
- `GET /info` - Detailed server status and configuration
- `GET /health` - Health check with database connectivity
- `GET /docs` - OpenAPI/Swagger documentation
- `GET /redoc` - ReDoc documentation

### Database Operations
- `POST /database/question` - Natural language database queries
- `POST /database/question/stream` - Streaming natural language queries (SSE)
- `POST /sql/execute` - Direct SQL execution
- `POST /sql/stream` - Streaming SQL execution (SSE)

### Resources and Tools
- `GET /resources` - List database tables and resources
- `POST /tools/call` - Execute MCP tools

### Legacy Compatibility
- `POST /mcp/database/question` - Backward compatible endpoint

## 🔌 WebSocket Interface

### Connection
```javascript
const ws = new WebSocket('ws://localhost:8001/ws?client_id=my-client&user_id=user123');
```

### Supported Message Types

#### Database Questions
```javascript
ws.send(JSON.stringify({
    type: 'database_question',
    request_id: 'req-123',
    question: 'Show me all doctors',
    user_context: {}
}));
```

#### SQL Execution
```javascript
ws.send(JSON.stringify({
    type: 'execute_sql',
    request_id: 'req-124',
    query: 'SELECT * FROM dokter LIMIT 10'
}));
```

#### Resource Listing
```javascript
ws.send(JSON.stringify({
    type: 'list_resources',
    request_id: 'req-125'
}));
```

#### Health Check
```javascript
ws.send(JSON.stringify({
    type: 'health_check',
    request_id: 'req-126'
}));
```

#### Ping/Pong
```javascript
ws.send(JSON.stringify({
    type: 'ping',
    request_id: 'req-127'
}));
```

## 📊 Server-Sent Events (SSE)

### Database Question Streaming
```bash
curl -X POST http://localhost:8001/database/question/stream \\
  -H "Content-Type: application/json" \\
  -d '{"question": "Show me recent patient data"}' \\
  --no-buffer
```

### SQL Execution Streaming
```bash
curl -X POST http://localhost:8001/sql/stream \\
  -H "Content-Type: application/json" \\
  -d '{"query": "SELECT * FROM large_table"}' \\
  --no-buffer
```

### Event Types
- `start` - Query processing begins
- `analysis` - Query analysis phase
- `plan` - Query execution plan
- `sql_generation` - SQL being generated
- `sql_generated` - SQL ready for execution
- `execution` - SQL execution starts
- `columns` - Column information
- `data_batch` - Batch of result rows
- `sql_complete` - Query execution finished
- `complete` - Entire process finished
- `error` - Error occurred

## 🌐 Example Usage

### Python Client (WebSocket)
```python
import asyncio
import websockets
import json

async def database_client():
    uri = "ws://localhost:8001/ws?client_id=python-client"

    async with websockets.connect(uri) as websocket:
        # Send database question
        await websocket.send(json.dumps({
            "type": "database_question",
            "request_id": "req-1",
            "question": "How many patients do we have?"
        }))

        # Listen for responses
        async for message in websocket:
            data = json.loads(message)
            print(f"Event: {data.get('type')}")
            print(f"Data: {data.get('data', data)}")

            if data.get('type') == 'database_question_complete':
                break

asyncio.run(database_client())
```

### JavaScript Client (Server-Sent Events)
```javascript
const eventSource = new EventSource('http://localhost:8001/database/question/stream', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        question: 'Show me doctor information',
        user_context: {}
    })
});

eventSource.addEventListener('data_batch', (event) => {
    const data = JSON.parse(event.data);
    console.log('Received batch:', data.rows);
});

eventSource.addEventListener('complete', (event) => {
    console.log('Query completed');
    eventSource.close();
});
```

### cURL Examples
```bash
# Simple database question
curl -X POST http://localhost:8001/database/question \\
  -H "Content-Type: application/json" \\
  -d '{"question": "Show me 5 doctors"}'

# SQL execution
curl -X POST http://localhost:8001/sql/execute \\
  -H "Content-Type: application/json" \\
  -d '{"query": "SELECT COUNT(*) FROM pasien"}'

# Health check
curl http://localhost:8001/health

# Server info
curl http://localhost:8001/info
```

## ⚙️ Configuration

The server uses the same environment variables as the original MCP server:

```bash
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=your_user
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=your_database
```

## 🔄 Migration from stdio

### Before (stdio)
```bash
# Client had to manage subprocess
python -m mysql_mcp_server
```

### After (HTTP streaming)
```bash
# Standalone server
python start_standalone.py
# Server runs independently, multiple clients can connect
```

### Client Code Changes
- **stdio clients**: Replace subprocess communication with HTTP requests
- **Existing HTTP clients**: No changes needed (backward compatible)
- **New clients**: Can use WebSocket or SSE for real-time features

## 🎛️ Advanced Features

### Connection Management
- Multiple concurrent clients
- User session tracking
- Automatic disconnection handling
- Connection status monitoring

### Performance Optimization
- Streaming large result sets
- Batched data delivery
- Configurable batch sizes
- Memory-efficient processing

### Development Features
- Auto-reload support
- Comprehensive logging
- Error handling and recovery
- Health monitoring

## 🧪 Testing

### Test WebSocket Connection
```bash
# Using websocat (install with: cargo install websocat)
echo '{"type":"ping","request_id":"test"}' | websocat ws://localhost:8001/ws?client_id=test
```

### Test SSE Streaming
```bash
curl -N -X POST http://localhost:8001/database/question/stream \\
  -H "Content-Type: application/json" \\
  -d '{"question": "SELECT * FROM dokter LIMIT 3"}'
```

### Load Testing
```bash
# Install hey: go install github.com/rakyll/hey@latest
hey -n 100 -c 10 -m POST -H "Content-Type: application/json" \\
  -d '{"question":"SELECT 1"}' \\
  http://localhost:8001/database/question
```

## 🚦 Server Status

Once running, the server provides detailed status information:

- **Active WebSocket connections**: Real-time count
- **Database connectivity**: Connection health
- **Performance metrics**: Response times and throughput
- **Error rates**: Failed requests and recovery

## 🔮 Future Enhancements

- Authentication and authorization
- Rate limiting and quotas
- Query caching and optimization
- Horizontal scaling support
- Metrics and monitoring integration
- GraphQL interface
- gRPC streaming support

---

The MySQL MCP Streaming Server transforms your database interface from a simple stdio tool into a comprehensive, real-time, multi-client database service ready for production use.