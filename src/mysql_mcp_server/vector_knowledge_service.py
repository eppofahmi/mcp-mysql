#!/usr/bin/env python3
"""
Healthcare Knowledge Vector Database Service
Stores and retrieves healthcare database knowledge using MongoDB vector search
"""

import os
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import logging
from dataclasses import dataclass

import pymongo
from motor.motor_asyncio import AsyncIOMotorClient
import numpy as np
import httpx

# Make sentence-transformers completely optional
SentenceTransformer = None
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    pass  # SentenceTransformer remains None

logger = logging.getLogger(__name__)

@dataclass
class HealthcareKnowledge:
    """Represents a chunk of healthcare knowledge"""
    id: str
    content: str
    type: str  # 'table_schema', 'relationship', 'workflow', 'example'
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None

class VectorKnowledgeService:
    """
    Service for storing and searching healthcare knowledge using MongoDB vector database
    """

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self.knowledge_collection = None
        self.embeddings_collection = None
        self.encoder: Optional[SentenceTransformer] = None
        self.knowledge_cache: List[HealthcareKnowledge] = []

        # Configuration from environment
        self.mongo_uri = os.getenv('MONGO_DB_URI')
        self.db_name = os.getenv('MONGO_DB_NAME', 'loom4-db')
        self.knowledge_collection_name = os.getenv('HEALTHCARE_KNOWLEDGE_COLLECTION', 'healthcare_knowledge')
        self.embeddings_collection_name = os.getenv('HEALTHCARE_EMBEDDINGS_COLLECTION', 'healthcare_embeddings')
        self.vector_dimension = int(os.getenv('VECTOR_DIMENSION', '384'))
        self.similarity_threshold = float(os.getenv('SIMILARITY_THRESHOLD', '0.7'))

        # Remote embedding configuration
        self.use_remote_embeddings = os.getenv('USE_REMOTE_EMBEDDINGS', 'false').lower() == 'true'
        self.embedding_server_url = os.getenv('EMBEDDING_SERVER_URL', '').strip('"')

        self.initialized = False

    async def initialize(self):
        """Initialize MongoDB connection and embedding model"""
        if self.initialized:
            return

        try:
            # Initialize MongoDB connection
            if not self.mongo_uri:
                raise ValueError("MONGO_DB_URI not configured")

            # MongoDB Atlas connection with SSL handling
            # Add tlsAllowInvalidCertificates for development (not recommended for production)
            import ssl
            import certifi

            # Use certifi for SSL certificate verification
            self.client = AsyncIOMotorClient(
                self.mongo_uri,
                tlsCAFile=certifi.where()  # Use certifi's certificate bundle
            )
            self.db = self.client[self.db_name]
            self.knowledge_collection = self.db[self.knowledge_collection_name]
            self.embeddings_collection = self.db[self.embeddings_collection_name]

            # Test connection
            await self.client.admin.command('ping')
            logger.info(f"✅ Connected to MongoDB: {self.db_name}")

            # Initialize embedding service
            if self.use_remote_embeddings and self.embedding_server_url:
                logger.info(f"✅ Using remote embedding server: {self.embedding_server_url}")
                self.encoder = None  # Will use remote server
            else:
                if SentenceTransformer is None:
                    raise ImportError("sentence-transformers not installed and no remote server configured")
                self.encoder = SentenceTransformer('all-MiniLM-L6-v2')  # 384-dimensional embeddings
                logger.info("✅ Loaded local sentence transformer model")

            # Create vector search index if it doesn't exist
            await self._ensure_vector_index()

            self.initialized = True

        except Exception as e:
            logger.error(f"❌ Failed to initialize VectorKnowledgeService: {e}")
            raise

    async def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        """Get embeddings either from remote server or local model"""
        if self.use_remote_embeddings and self.embedding_server_url:
            # Use remote embedding server (be-loom4 format)
            dynamic_timeout = self._calculate_dynamic_timeout(len(texts))

            async with httpx.AsyncClient(timeout=dynamic_timeout) as client:
                try:
                    response = await client.post(
                        f"{self.embedding_server_url}/embed",
                        json={
                            "texts": texts,
                            "batch_size": 32,
                            "normalize_embeddings": False
                        }
                    )
                    if response.status_code == 200:
                        result = response.json()
                        embeddings = np.array(result['embeddings'])
                        logger.info(f"Generated {result['count']} embeddings via remote server in {result.get('processing_time', 0):.3f}s")
                        return embeddings
                    else:
                        logger.warning(f"Remote embedding failed: {response.status_code}, falling back to local")
                except Exception as e:
                    logger.warning(f"Remote embedding error: {e}, falling back to local")

            # Fallback to local if remote fails
            if self.encoder:
                return self.encoder.encode(texts, show_progress_bar=True)
            else:
                raise Exception("Remote embedding failed and no local model available")
        else:
            # Use local sentence transformer
            if self.encoder:
                return self.encoder.encode(texts, show_progress_bar=True)
            else:
                raise Exception("No embedding service available")

    def _calculate_dynamic_timeout(self, text_count: int) -> float:
        """Calculate dynamic timeout based on text count"""
        if text_count <= 10:
            return 30.0  # Small batches
        elif text_count <= 50:
            return 60.0  # Medium batches
        elif text_count <= 100:
            return 120.0  # Large batches
        else:
            return 180.0  # Very large batches

    async def _ensure_vector_index(self):
        """Ensure vector search index exists for embeddings collection"""
        try:
            # Check if index exists
            indexes = await self.embeddings_collection.list_indexes().to_list(None)
            vector_index_exists = any(
                idx.get('name') == 'vector_search_index'
                for idx in indexes
            )

            if not vector_index_exists:
                # Create vector search index
                index_spec = {
                    "name": "vector_search_index",
                    "definition": {
                        "fields": [
                            {
                                "type": "vector",
                                "path": "embedding",
                                "numDimensions": self.vector_dimension,
                                "similarity": "cosine"
                            },
                            {
                                "type": "filter",
                                "path": "type"
                            },
                            {
                                "type": "filter",
                                "path": "metadata.tables"
                            }
                        ]
                    }
                }

                # Note: In production MongoDB Atlas, you would create this via Atlas UI
                # For now, we'll use a simple index
                await self.embeddings_collection.create_index("embedding")
                logger.info("✅ Created vector search index")

        except Exception as e:
            logger.warning(f"⚠️ Could not create vector index: {e}")

    async def load_healthcare_knowledge(self, knowledge_path: str = "database_knowledge/"):
        """Load healthcare knowledge from files and store as vectors"""
        if not self.initialized:
            await self.initialize()

        logger.info("📚 Loading healthcare knowledge for vector storage...")

        knowledge_chunks = []
        knowledge_base = Path(knowledge_path)

        # 1. Load table schemas
        schema_file = knowledge_base / "schema" / "enhanced_database_schema.json"
        if schema_file.exists():
            with open(schema_file, 'r') as f:
                schema_data = json.load(f)

            # Chunk table schemas
            for table_name, table_info in schema_data.get('schema', {}).items():
                # Create table overview chunk
                table_overview = f"Table: {table_name}\n"
                table_overview += f"Description: {table_info.get('description', 'Healthcare database table')}\n"
                columns = table_info.get('columns', [])
                table_overview += f"Columns: {len(columns)}\n"
                table_overview += f"Primary Key: {', '.join(table_info.get('primary_keys', []))}\n"

                if table_info.get('foreign_keys'):
                    table_overview += "Relationships:\n"
                    for fk in table_info['foreign_keys']:
                        if isinstance(fk, dict):
                            table_overview += f"  - {fk['column']} → {fk['referenced_table']}.{fk['referenced_column']}\n"
                        else:
                            # Handle foreign_keys as list of column names
                            table_overview += f"  - {fk} (foreign key)\n"

                knowledge_chunks.append(HealthcareKnowledge(
                    id=f"table_{table_name}",
                    content=table_overview,
                    type="table_schema",
                    metadata={
                        "table": table_name,
                        "tables": [table_name],
                        "category": "schema"
                    }
                ))

                # Create column details chunk
                columns = table_info.get('columns', [])
                if columns:
                    columns_detail = f"Table {table_name} - Column Details:\n"
                    if isinstance(columns, list):
                        # Handle columns as list of dicts
                        for col in columns:
                            if isinstance(col, dict):
                                col_name = col.get('name', 'unknown')
                                col_type = col.get('type', 'unknown')
                                columns_detail += f"  - {col_name}: {col_type}\n"
                            else:
                                columns_detail += f"  - {col}\n"
                    else:
                        # Handle columns as dictionary
                        for col_name, col_info in columns.items():
                            if isinstance(col_info, dict):
                                columns_detail += f"  - {col_name}: {col_info.get('type', 'unknown')}\n"
                            else:
                                columns_detail += f"  - {col_name}: {col_info}\n"

                    knowledge_chunks.append(HealthcareKnowledge(
                        id=f"columns_{table_name}",
                        content=columns_detail,
                        type="table_columns",
                        metadata={
                            "table": table_name,
                            "tables": [table_name],
                            "category": "columns"
                        }
                    ))

        # 2. Load relationships
        relationships_file = knowledge_base / "analysis" / "relationship_analysis.json"
        if relationships_file.exists():
            with open(relationships_file, 'r') as f:
                relationships_data = json.load(f)

            # Chunk relationships by groups
            for rel in relationships_data.get('relationships', []):
                rel_content = f"Relationship: {rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']}\n"
                rel_content += f"Type: {rel.get('relationship_type', 'foreign_key')}\n"
                rel_content += f"Description: {rel.get('description', 'Database relationship')}\n"

                if rel.get('sql_pattern'):
                    rel_content += f"SQL Pattern: {rel['sql_pattern']}\n"

                knowledge_chunks.append(HealthcareKnowledge(
                    id=f"rel_{rel['from_table']}_{rel['to_table']}",
                    content=rel_content,
                    type="relationship",
                    metadata={
                        "from_table": rel['from_table'],
                        "to_table": rel['to_table'],
                        "tables": [rel['from_table'], rel['to_table']],
                        "category": "relationship"
                    }
                ))

        # 3. Load healthcare workflows
        workflows = {
            "patient_registration": {
                "tables": ["pasien", "reg_periksa", "dokter", "poliklinik"],
                "description": "Patient registration and appointment workflow",
                "flow": "pasien → reg_periksa → dokter → poliklinik",
                "sql_example": "SELECT p.nm_pasien, r.tgl_registrasi, d.nm_dokter FROM pasien p JOIN reg_periksa r ON p.no_rkm_medis = r.no_rkm_medis JOIN dokter d ON r.kd_dokter = d.kd_dokter"
            },
            "diagnosis_treatment": {
                "tables": ["pasien", "diagnosa_pasien", "icd10"],
                "description": "Patient diagnosis and ICD-10 coding workflow",
                "flow": "pasien → diagnosa_pasien → icd10",
                "sql_example": "SELECT p.nm_pasien, dp.prioritas, i.nm_penyakit FROM pasien p JOIN diagnosa_pasien dp ON p.no_rkm_medis = dp.no_rkm_medis JOIN icd10 i ON dp.kd_penyakit = i.kd_penyakit"
            },
            "medication_management": {
                "tables": ["pasien", "resep_obat", "detail_pemberian_obat", "databarang"],
                "description": "Prescription and medication dispensing workflow",
                "flow": "pasien → resep_obat → detail_pemberian_obat → databarang",
                "sql_example": "SELECT p.nm_pasien, r.tgl_peresepan, db.nama_brng FROM pasien p JOIN resep_obat r ON p.no_rkm_medis = r.no_rkm_medis JOIN detail_pemberian_obat dpo ON r.no_resep = dpo.no_resep JOIN databarang db ON dpo.kode_brng = db.kode_brng"
            }
        }

        for workflow_name, workflow_info in workflows.items():
            workflow_content = f"Healthcare Workflow: {workflow_name}\n"
            workflow_content += f"Description: {workflow_info['description']}\n"
            workflow_content += f"Tables involved: {', '.join(workflow_info['tables'])}\n"
            workflow_content += f"Flow: {workflow_info['flow']}\n"
            workflow_content += f"Example SQL: {workflow_info['sql_example']}\n"

            knowledge_chunks.append(HealthcareKnowledge(
                id=f"workflow_{workflow_name}",
                content=workflow_content,
                type="workflow",
                metadata={
                    "workflow": workflow_name,
                    "tables": workflow_info['tables'],
                    "category": "workflow"
                }
            ))

        # Store knowledge chunks with embeddings
        await self._store_knowledge_chunks(knowledge_chunks)
        logger.info(f"✅ Loaded {len(knowledge_chunks)} healthcare knowledge chunks")

    async def _store_knowledge_chunks(self, chunks: List[HealthcareKnowledge]):
        """Store knowledge chunks with embeddings in MongoDB"""
        if not chunks:
            return

        # Generate embeddings for all chunks
        contents = [chunk.content for chunk in chunks]
        embeddings = await self._get_embeddings(contents)

        # Prepare documents for insertion
        documents = []
        for chunk, embedding in zip(chunks, embeddings):
            doc = {
                "_id": chunk.id,
                "content": chunk.content,
                "type": chunk.type,
                "metadata": chunk.metadata,
                "embedding": embedding.tolist(),
                "created_at": "2024-01-01T00:00:00Z"  # You might want to use actual timestamp
            }
            documents.append(doc)

        # Insert/update documents
        try:
            # Use upsert to handle both insert and update
            for doc in documents:
                await self.embeddings_collection.replace_one(
                    {"_id": doc["_id"]},
                    doc,
                    upsert=True
                )

            logger.info(f"✅ Stored {len(documents)} knowledge chunks in MongoDB")

        except Exception as e:
            logger.error(f"❌ Failed to store knowledge chunks: {e}")
            raise

    async def search_relevant_knowledge(self, question: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant healthcare knowledge based on user question"""
        if not self.initialized:
            await self.initialize()

        # Generate embedding for the question
        question_embeddings = await self._get_embeddings([question])
        question_embedding = question_embeddings[0].tolist()

        try:
            # MongoDB Atlas Vector Search using $vectorSearch aggregation
            # This uses the Atlas Search index we'll create
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "healthcare_vector_index",
                        "path": "embedding",
                        "queryVector": question_embedding,
                        "numCandidates": limit * 10,  # Consider more candidates
                        "limit": limit
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "content": 1,
                        "type": 1,
                        "metadata": 1,
                        "score": {"$meta": "vectorSearchScore"}
                    }
                }
            ]

            # Try Atlas vector search first
            try:
                cursor = self.embeddings_collection.aggregate(pipeline)
                documents = await cursor.to_list(None)

                if documents:
                    logger.info(f"🔍 Atlas Vector Search found {len(documents)} relevant chunks")
                    return documents

            except Exception as atlas_error:
                # If Atlas vector search fails, fallback to client-side search
                logger.warning(f"Atlas vector search not available: {atlas_error}")
                logger.info("Falling back to client-side similarity search...")

            # Fallback: Client-side similarity search
            cursor = self.embeddings_collection.find({})
            documents = await cursor.to_list(None)

            # Calculate cosine similarity
            similarities = []
            for doc in documents:
                doc_embedding = doc.get('embedding', [])
                if doc_embedding:
                    similarity = self._cosine_similarity(question_embedding, doc_embedding)
                    if similarity >= self.similarity_threshold:
                        similarities.append({
                            'document': doc,
                            'similarity': similarity
                        })

            # Sort by similarity and limit results
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            relevant_docs = similarities[:limit]

            logger.info(f"🔍 Client-side search found {len(relevant_docs)} relevant chunks")

            return [item['document'] for item in relevant_docs]

        except Exception as e:
            logger.error(f"❌ Vector search failed: {e}")
            return []

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            vec1 = np.array(vec1)
            vec2 = np.array(vec2)

            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return dot_product / (norm1 * norm2)
        except:
            return 0.0

    async def build_context_from_search(self, question: str, max_context_length: int = 1000) -> str:
        """Build healthcare context from vector search results"""
        relevant_docs = await self.search_relevant_knowledge(question)

        if not relevant_docs:
            return "No specific healthcare knowledge found for this query."

        context = "# Relevant Healthcare Database Knowledge:\n\n"
        current_length = len(context)

        for doc in relevant_docs:
            doc_content = f"## {doc.get('type', 'knowledge').title()}\n{doc.get('content', '')}\n\n"

            if current_length + len(doc_content) > max_context_length:
                break

            context += doc_content
            current_length += len(doc_content)

        return context

    async def get_related_tables(self, question: str) -> List[str]:
        """Get tables related to the user question based on vector search"""
        relevant_docs = await self.search_relevant_knowledge(question, limit=10)

        tables = set()
        for doc in relevant_docs:
            metadata = doc.get('metadata', {})
            doc_tables = metadata.get('tables', [])
            if isinstance(doc_tables, list):
                tables.update(doc_tables)
            elif isinstance(doc_tables, str):
                tables.add(doc_tables)

        return list(tables)

    async def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("✅ Closed MongoDB connection")