# MongoDB Atlas Vector Search Setup Guide

This guide helps you set up vector search in MongoDB Atlas for the healthcare knowledge system.

## Prerequisites
- MongoDB Atlas cluster (M10 or higher recommended for vector search)
- Atlas account with admin privileges
- Connection string already configured in `.env`

## Step 1: Create Vector Search Index in Atlas

1. **Login to MongoDB Atlas** at [https://cloud.mongodb.com](https://cloud.mongodb.com)

2. **Navigate to your cluster** and click on "Browse Collections"

3. **Select the database**: `loom4-db`

4. **Select the collection**: `healthcare_embeddings`

5. **Click on "Search Indexes" tab**

6. **Click "Create Search Index"**

7. **Choose "JSON Editor" and paste this configuration**:

```json
{
  "name": "healthcare_vector_index",
  "type": "vectorSearch",
  "definition": {
    "fields": [
      {
        "type": "vector",
        "path": "embedding",
        "numDimensions": 384,
        "similarity": "cosine"
      },
      {
        "type": "filter",
        "path": "type"
      },
      {
        "type": "filter",
        "path": "metadata.tables"
      },
      {
        "type": "filter",
        "path": "metadata.category"
      }
    ]
  }
}
```

8. **Click "Create Search Index"** and wait for it to build (usually takes 1-2 minutes)

## Step 2: Initialize Healthcare Knowledge

Run the initialization script to populate the vector database:

```bash
# Install dependencies if not already installed
pip install pymongo motor sentence-transformers numpy

# Run initialization
python3 initialize_vector_database.py
```

## Step 3: Verify Setup

The initialization script will:
1. Connect to MongoDB Atlas
2. Load healthcare knowledge from `database_knowledge/`
3. Generate embeddings using sentence-transformers
4. Store vectorized knowledge in MongoDB Atlas
5. Test vector search functionality

## Step 4: Configure MCP Server

Ensure your `.env` file has these settings:

```env
# MongoDB Atlas Connection
MONGO_DB_URI=""
MONGO_DB_NAME=""

# Vector Search Configuration
ENABLE_VECTOR_SEARCH=true
HEALTHCARE_KNOWLEDGE_COLLECTION=healthcare_embeddings
VECTOR_DIMENSION=384
SIMILARITY_THRESHOLD=0.7
```

## Step 5: Start MCP Server

```bash
# Restart the server to use vector search
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

## How Vector Search Works

1. **User Question** → "Show me doctors with their patients"
2. **Embedding Generation** → Convert question to 384-dimensional vector
3. **Atlas Vector Search** → Find top 5 most similar knowledge chunks
4. **Context Building** → Combine relevant chunks (max 3000 chars)
5. **SQL Generation** → Send focused context to Ollama
6. **Query Execution** → Run generated SQL and return results

## Benefits Over Full Context

| Aspect | Full Context | Vector Search |
|--------|-------------|---------------|
| Context Size | 10,000+ chars | ~3000 chars |
| Ollama Timeout | Frequent on complex queries | Rare |
| Response Time | 30+ seconds | 5-10 seconds |
| Relevance | All 21 tables always | Only relevant tables |
| Scalability | Limited | Unlimited knowledge |

## Troubleshooting

### Vector Search Not Working
- Verify index is created and active in Atlas UI
- Check cluster tier (M10+ recommended)
- Ensure collection name matches: `healthcare_embeddings`

### Fallback to Client-Side Search
- The system automatically falls back to client-side similarity search if Atlas vector search isn't available
- This works but is slower for large datasets

### Connection Issues
- Verify MongoDB URI in `.env`
- Check network access in Atlas (whitelist your IP)
- Ensure database user has read/write permissions

## Testing Vector Search

Test with these queries after setup:

```python
# Simple query
"Show me 5 doctors"

# Complex relationship query
"Show patients with their diagnoses and treating doctors"

# Workflow query
"Display medication prescriptions with patient details"
```

Each query should:
1. Use vector search to find relevant context
2. Generate accurate SQL with proper JOINs
3. Return results without timeout

## Performance Optimization

For best performance:
- Use MongoDB Atlas M10 or higher tier
- Create indexes on frequently queried fields
- Monitor Atlas performance metrics
- Adjust `SIMILARITY_THRESHOLD` if needed (0.6-0.8 range)

## Additional Resources
- [MongoDB Atlas Vector Search Docs](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-overview/)
- [Sentence Transformers Models](https://www.sbert.net/docs/pretrained_models.html)
- [Atlas Search Index Management](https://www.mongodb.com/docs/atlas/atlas-search/create-index/)
