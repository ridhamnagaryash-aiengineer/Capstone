import os
import logging
from typing import List, Dict, Any, Optional
from pymilvus import connections, Collection, utility

logger = logging.getLogger(__name__)

COLLECTIONS = {
    "hr_policy": "hrms_hr_policy",
    "payroll": "hrms_payroll",
    "it_support": "hrms_it_support",
    "facilities": "hrms_facilities",
    "uncategorized": "hrms_uncategorized"
}

DEFAULT_COLLECTION = "hrms_uncategorized"


class MilvusClient:
    """Milvus client using your existing HR collections."""

    def __init__(self):
        self.dim = 768
        self.collections: Dict[str, Collection] = {}
        self._connect()
        self._load_collections()

    def _connect(self):
        uri = os.getenv("MILVUS_URI")
        token = os.getenv("MILVUS_API_KEY")

        if not uri or not token:
            raise ValueError("MILVUS_URI or MILVUS_API_KEY not set")

        try:
            connections.connect(
                alias="default",
                uri=uri,
                token=token
            )
            logger.info("✅ Connected to Milvus/Zilliz")
        except Exception as e:
            logger.error(f"❌ Milvus connection failed: {e}")
            raise

    def _load_collections(self):
        for key, name in COLLECTIONS.items():
            try:
                if utility.has_collection(name):
                    col = Collection(name)
                    col.load()
                    self.collections[key] = col
                    logger.info(f"📌 Loaded collection: {name}")
                else:
                    logger.warning(f"⚠ Missing collection: {name}")
            except Exception as e:
                logger.error(f"❌ Failed loading collection {name}: {e}")

    def _resolve_collection(self, category: Optional[str]) -> Optional[Collection]:
        if not category:
            return self.collections.get("uncategorized")

        c = category.lower()
        if "policy" in c:
            return self.collections.get("hr_policy")
        if "payroll" in c:
            return self.collections.get("payroll")
        if "it" in c or "tech" in c:
            return self.collections.get("it_support")
        if "facility" in c:
            return self.collections.get("facilities")

        return self.collections.get("uncategorized")

    # -------------------------------------------------------------
    # CORRECT INSERT FORMAT (COLUMN-BASED)
    # -------------------------------------------------------------
    async def store_document_embeddings(
        self,
        file_id: str,
        filename: str,
        content: str,
        embeddings: List[List[float]],
        category: str
    ) -> int:
        try:
            col = self._resolve_collection(category)
            if not col:
                raise Exception(f"No Milvus collection for category={category}")

            # BUILD COLUMN-WISE DATA
            ids = []
            file_ids = []
            filenames = []
            chunk_indexes = []
            texts = []
            categories = []
            embed_vectors = []

            for i, emb in enumerate(embeddings):
                ids.append(f"{file_id}_chunk_{i}")
                file_ids.append(file_id)
                filenames.append(filename)
                chunk_indexes.append(i)
                texts.append(content[:4000])
                categories.append(category)
                embed_vectors.append(emb)

            # Column-wise insertion
            entities = [
                ids,
                file_ids,
                filenames,
                chunk_indexes,
                texts,
                categories,
                embed_vectors
            ]

            col.insert(entities)
            col.flush()

            logger.info(f"✅ Inserted {len(embeddings)} vectors into {col.name}")
            return len(embeddings)

        except Exception as e:
            logger.error(f"❌ Insert failed: {e}")
            raise

    # -------------------------------------------------------------
    # SEARCH
    # -------------------------------------------------------------
    async def search_similar(self, query: str, category: Optional[str], limit: int = 5):
        try:
            col = self._resolve_collection(category)
            if not col:
                return []

            from ..llm.lite_client import lite_client
            query_emb = lite_client.create_embedding(query)

            results = col.search(
                data=[query_emb],
                anns_field="embedding",
                limit=limit,
                param={"metric_type": "COSINE", "params": {"nprobe": 10}},
                output_fields=["file_id", "filename", "text", "chunk_index", "category"]
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
                    "category": hit.entity.get("category")
                })
            return formatted

        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            return []

    # -------------------------------------------------------------
    # DELETE
    # -------------------------------------------------------------
    async def delete_by_file_id(self, file_id: str) -> int:
        total = 0
        for col in self.collections.values():
            try:
                result = col.delete(f'file_id == "{file_id}"')
                total += result.delete_count
            except:
                pass
        return total


milvus_client = MilvusClient()
