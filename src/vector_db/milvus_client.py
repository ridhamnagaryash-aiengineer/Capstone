import os
import logging
from typing import List, Dict, Any, Optional
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from ..llm.lite_client import lite_client

logger = logging.getLogger(__name__)

class MilvusClient:
    """Milvus/Zilliz vector database client for storing and searching HR document embeddings."""

    def __init__(self):
        self.collection_name = "hr_documents"
        self.dim = 768
        self.collection = None
        self._connect()
        self._setup_collection()

    # ------------------------ CONNECTION ------------------------
    def _connect(self):
        """Connect to Zilliz Cloud or local Milvus."""
        try:
            uri = os.getenv("MILVUS_URI", "https://in03-28f34bee2591c4c.serverless.aws-eu-central-1.cloud.zilliz.com")
            token = os.getenv("MILVUS_API_KEY", "")
            connections.connect(alias="default", uri=uri, token=token)
            logger.info("✅ Connected to Zilliz/Milvus successfully")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Zilliz/Milvus: {e}")
            raise

    # ------------------------ COLLECTION SETUP ------------------------
    def _setup_collection(self):
        """Load or create HR collection schema."""
        try:
            if utility.has_collection(self.collection_name):
                self.collection = Collection(self.collection_name)
                logger.info(f"✅ Loaded existing collection: {self.collection_name}")
            else:
                self._create_collection()
        except Exception as e:
            logger.error(f"❌ Collection setup failed: {e}")
            raise

    def _create_collection(self):
        """Define schema and create new collection."""
        try:
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="file_id", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim)
            ]
            schema = CollectionSchema(fields=fields, description="HR Documents Vector Collection")
            self.collection = Collection(name=self.collection_name, schema=schema)

            index_params = {
                "index_type": "IVF_FLAT",
                "metric_type": "L2",
                "params": {"nlist": 128}
            }
            self.collection.create_index(field_name="embedding", index_params=index_params)
            logger.info(f"✅ Created new collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"❌ Collection creation failed: {e}")
            raise

    # ------------------------ EMBEDDING OPERATIONS ------------------------
    async def store_document_embeddings(
        self,
        file_id: str,
        filename: str,
        content: str,
        embeddings: List[List[float]],
        category: str
    ) -> int:
        """Insert document embeddings into Milvus."""
        try:
            # id is auto-generated, so we only insert the other 5 fields
            data = [
                [file_id] * len(embeddings),
                [filename] * len(embeddings),
                [content] * len(embeddings),
                [category] * len(embeddings),
                embeddings,  # already a list of lists
            ]

            self.collection.insert(data)
            self.collection.flush()

            logger.info(f"✅ Stored {len(embeddings)} vectors for {filename}")
            return len(embeddings)

        except Exception as e:
            logger.error(f"❌ Failed to store embeddings: {e}")
            raise

   
    async def search_similar(
        self,
        query: str,
        limit: int = 5,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search similar documents using Gemini embeddings."""
        try:
            query_embedding = lite_client.create_embedding(query)
            search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
            expr = f'category == "{category}"' if category else None

            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=limit,
                expr=expr,
                output_fields=["file_id", "filename", "content", "category"]
            )

            formatted_results = []
            for hits in results:
                for hit in hits:
                    formatted_results.append({
                        "file_id": hit.entity.get("file_id"),
                        "filename": hit.entity.get("filename"),
                        "content": hit.entity.get("content"),
                        "category": hit.entity.get("category"),
                        "score": hit.score
                    })

            logger.info(f"✅ Found {len(formatted_results)} matches in category={category}")
            return formatted_results
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            return []

    async def delete_by_file_id(self, file_id: str) -> int:
        """Delete all vectors for a given file_id."""
        try:
            expr = f'file_id == "{file_id}"'
            result = self.collection.delete(expr)
            logger.info(f"🗑️ Deleted vectors for file_id={file_id}")
            return result.delete_count
        except Exception as e:
            logger.error(f"❌ Delete failed: {e}")
            return 0

    # ------------------------ STATS / TEST ------------------------
    def get_collection_stats(self) -> Dict[str, Any]:
        try:
            stats = self.collection.num_entities
            return {"total_vectors": stats, "collection": self.collection_name}
        except Exception as e:
            logger.error(f"❌ Failed to get stats: {e}")
            return {"total_vectors": 0, "collection": self.collection_name}


milvus_client = MilvusClient()
