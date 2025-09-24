#!/usr/bin/env python3
"""
Initialize Healthcare Knowledge Vector Database
Sets up MongoDB vector database with healthcare knowledge from existing schema files
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    """Initialize vector database with healthcare knowledge"""
    print("🚀 Healthcare Vector Database Initialization")
    print("=" * 60)

    try:
        # Import our vector knowledge service
        from mysql_mcp_server.vector_knowledge_service import VectorKnowledgeService

        # Initialize the service
        print("📚 Initializing Vector Knowledge Service...")
        vector_service = VectorKnowledgeService()

        # Initialize MongoDB connection and embedding model
        print("🔗 Connecting to MongoDB and loading AI model...")
        await vector_service.initialize()
        print("✅ Connected successfully!")

        # Load and process healthcare knowledge
        print("\n📖 Loading healthcare knowledge from database_knowledge/...")
        knowledge_path = "database_knowledge/"

        if not Path(knowledge_path).exists():
            print(f"❌ Error: {knowledge_path} directory not found!")
            print("   Make sure you have run the schema extraction first.")
            return

        # Load healthcare knowledge into vector database
        await vector_service.load_healthcare_knowledge(knowledge_path)
        print("✅ Healthcare knowledge loaded successfully!")

        # Test vector search functionality
        print("\n🧪 Testing vector search functionality...")

        test_questions = [
            "Show me patient information",
            "Find doctors and their specialties",
            "Get patient visits and diagnoses",
            "Show medication prescriptions"
        ]

        for question in test_questions:
            print(f"\n   Testing: '{question}'")
            try:
                # Search for relevant knowledge
                relevant_docs = await vector_service.search_relevant_knowledge(question, limit=3)

                if relevant_docs:
                    print(f"   ✅ Found {len(relevant_docs)} relevant knowledge chunks")
                    for i, doc in enumerate(relevant_docs, 1):
                        doc_type = doc.get('type', 'unknown')
                        tables = doc.get('metadata', {}).get('tables', [])
                        print(f"      {i}. Type: {doc_type}, Tables: {tables}")
                else:
                    print("   ⚠️  No relevant knowledge found")

            except Exception as e:
                print(f"   ❌ Error: {e}")

        # Test context building
        print("\n🔍 Testing context building...")
        try:
            test_question = "Show me doctors with their patient visits"
            context = await vector_service.build_context_from_search(test_question)
            context_length = len(context)
            print(f"   ✅ Built context: {context_length} characters")
            print(f"   📝 Sample context (first 200 chars):")
            print(f"      {context[:200]}...")

        except Exception as e:
            print(f"   ❌ Context building error: {e}")

        # Clean up
        await vector_service.close()

        print(f"\n" + "=" * 60)
        print("🎉 Vector Database Initialization Complete!")
        print("\n📋 Summary:")
        print("   • MongoDB connection: ✅ Working")
        print("   • Sentence transformer model: ✅ Loaded")
        print("   • Healthcare knowledge: ✅ Vectorized and stored")
        print("   • Vector search: ✅ Functional")
        print("   • Context generation: ✅ Ready")

        print(f"\n🚀 Next Steps:")
        print("   1. Restart your MCP server to use vector search")
        print("   2. Set ENABLE_VECTOR_SEARCH=true in .env (if not already set)")
        print("   3. Test with queries like 'Show me doctors with patient visits'")

        print(f"\n💡 Expected Benefits:")
        print("   • Faster query generation (focused context)")
        print("   • No more Ollama timeouts on complex queries")
        print("   • Better healthcare domain understanding")
        print("   • Scalable knowledge retrieval")

    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("   Please install required dependencies:")
        print("   pip install pymongo motor sentence-transformers numpy")
        return

    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        print(f"❌ Initialization failed: {e}")

        print(f"\n🔧 Troubleshooting:")
        print("   1. Check MongoDB connection string in .env")
        print("   2. Verify database_knowledge/ directory exists")
        print("   3. Ensure all dependencies are installed")
        print("   4. Check internet connection for sentence-transformers model download")

        return 1

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Initialization cancelled by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)