import os
import logging
from typing import List, Dict, Any, Optional
from pymilvus import connections, Collection, utility

from ..llm.lite_client import lite_client

logger = logging.getLogger(__name__)

# Pre-existing collections in your Zilliz cluster
COLLECTIONS = {
    "hr_policy": "hrms_hr_policy",
    "payroll": "hrms_payroll",
    "it_support": "hrms_it_support",
    "facilities": "hrms_facilities",
    "uncategorized": "hrms_uncategorized"
}

DEFAULT_COLLECTION = "hrms_uncategorized"


class MilvusClient:
    """Milvus client using your 5 existing HR category collections."""

    def __init__(self):
        self.dim = 768
        self.collections: Dict[str, Collection] = {}
        self._connect()
        self._load_collections()

    # -------------------------------------------------------------
    # CONNECT TO ZILLIZ / MILVUS CLOUD
    # -------------------------------------------------------------
    def _connect(self):
        try:
            uri = os.getenv("MILVUS_URI")
            token = os.getenv("MILVUS_API_KEY")

            if not uri or not token:
                raise ValueError("MILVUS_URI or MILVUS_API_KEY not set in env.")

            connections.connect(
                alias="default",
                uri=uri,
                token=token
            )
            logger.info("✅ Connected to Milvus/Zilliz successfully")

        except Exception as e:
            logger.error(f"❌ Milvus connection failed: {e}")
            raise

    # -------------------------------------------------------------
    # LOAD EXISTING COLLECTIONS ONLY (NO CREATION)
    # -------------------------------------------------------------
    def _load_collections(self):
        for key, name in COLLECTIONS.items():
            try:
                if utility.has_collection(name):
                    col = Collection(name)
                    col.load()
                    self.collections[key] = col
                    logger.info(f"📌 Loaded existing collection: {name}")
                else:
                    logger.warning(f"⚠ Collection NOT found in cluster: {name}")

            except Exception as e:
                logger.error(f"❌ Failed to load collection {name}: {e}")

    # -------------------------------------------------------------
    # CATEGORY ROUTING → COLLECTION
    # -------------------------------------------------------------
    def _resolve_collection(self, category: Optional[str]) -> Optional[Collection]:
        if not category:
            return self.collections.get("uncategorized")

        category = category.lower()

        if "policy" in category:
            return self.collections.get("hr_policy")
        if "payroll" in category:
            return self.collections.get("payroll")
        if "it" in category or "tech" in category:
            return self.collections.get("it_support")
        if "facility" in category:
            return self.collections.get("facilities")

        return self.collections.get("uncategorized")

    # -------------------------------------------------------------
    # INSERT DOCUMENT CHUNKS + EMBEDDINGS
    # -------------------------------------------------------------
    async def store_document_embeddings(
        self,
        file_id: str,
        filename: str,
        content: str,
        embeddings: List[List[float]],
        category: str
    ) -> int:
        """Insert document embeddings into the correct existing collection."""
        try:
            col = self._resolve_collection(category)
            if not col:
                raise Exception(f"No collection found for category: {category}")

            entities = []
            for idx, emb in enumerate(embeddings):
                entities.append([
                    f"{file_id}_chunk_{idx}",     # id (VARCHAR)
                    file_id,                      # file_id
                    filename,                     # filename
                    idx,                          # chunk_index
                    category,                     # category
                    content[:4000],               # text (limit)
                    emb                           # embedding
                ])

            col.insert(entities)
            col.flush()

            logger.info(f"✅ Inserted {len(entities)} embeddings into {col.name}")
            return len(entities)

        except Exception as e:
            logger.error(f"❌ Insert failed: {e}")
            raise

    # -------------------------------------------------------------
    # SEARCH SIMILARITY (RAG)
    # -------------------------------------------------------------
    async def search_similar(
        self,
        query: str,
        category: Optional[str],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search the correct HR category collection for similar chunks."""
        try:
            col = self._resolve_collection(category)

            if not col:
                logger.error(f"❌ No matching collection for category={category}")
                return []

            query_embedding = lite_client.create_embedding(query)

            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }

            results = col.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=limit,
                output_fields=[
                    "file_id", "filename", "text",
                    "category", "chunk_index"
                ]
            )

            formatted = []
            for hit in results[0]:
                formatted.append({
                    "id": hit.id,
                    "score": hit.score,
                    "content": hit.entity.get("text"),
                    "filename": hit.entity.get("filename"),
                    "file_id": hit.entity.get("file_id"),
                    "chunk_index": hit.entity.get("chunk_index"),
                    "category": hit.entity.get("category"),
                })

            logger.info(f"🔍 Found {len(formatted)} matches in {col.name}")
            return formatted

        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            return []

    # -------------------------------------------------------------
    # DELETE BY FILE
    # -------------------------------------------------------------
    async def delete_by_file_id(self, file_id: str) -> int:
        """Delete all vectors across all collections for a file."""
        deleted_total = 0

        for col in self.collections.values():
            try:
                expr = f'file_id == "{file_id}"'
                result = col.delete(expr)
                deleted_total += result.delete_count
                logger.info(f"🗑️ Deleted {result.delete_count} from {col.name}")

            except Exception as e:
                logger.error(f"❌ Delete failed in {col.name}: {e}")

        return deleted_total

    # -------------------------------------------------------------
    # COLLECTION STATS
    # -------------------------------------------------------------
    def get_collection_stats(self) -> Dict[str, Any]:
        stats = {}
        for key, col in self.collections.items():
            try:
                stats[key] = col.num_entities
            except:
                stats[key] = 0
        return stats


milvus_client = MilvusClient()
