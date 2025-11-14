import os
import logging
from typing import List, Dict, Any, Optional
from pymilvus import connections, Collection, utility

from ..llm.lite_client import lite_client

logger = logging.getLogger(__name__)

COLLECTIONS = {
    "hr_policy": "hrms_hr_policy",
    "payroll": "hrms_payroll",
    "it_support": "hrms_it_support",
    "facilities": "hrms_facilities",
    "uncategorized": "hrms_uncategorized"
}

class MilvusClient:
    def __init__(self):
        self.dim = 768
        self.collections: Dict[str, Collection] = {}
        self._connect()
        self._load_collections()

    def _connect(self):
        uri = os.getenv("MILVUS_URI")
        token = os.getenv("MILVUS_API_KEY")

        if not uri or not token:
            raise RuntimeError("MILVUS_URI or MILVUS_API_KEY missing from environment")

        connections.connect(alias="default", uri=uri, token=token)
        logger.info("Connected to Milvus")

    def _load_collections(self):
        for key, name in COLLECTIONS.items():
            try:
                if utility.has_collection(name):
                    col = Collection(name)
                    col.load()
                    self.collections[key] = col
                    logger.info(f"Loaded collection: {name}")
                else:
                    logger.warning(f"Collection not found in Milvus: {name}")
            except Exception as e:
                logger.error(f"Failed loading collection {name}: {e}")

    def _resolve(self, category: str) -> Optional[Collection]:
        category = (category or "").lower()

        if category not in COLLECTIONS:
            category = "uncategorized"

        return self.collections.get(category)

    async def store_document_embeddings(
        self,
        file_id: str,
        filename: str,
        content: str,
        embeddings: List[List[float]],
        category: str
    ) -> int:
        col = self._resolve(category)
        if not col:
            raise Exception(f"No collection for category: {category}")

        entities = []
        for idx, emb in enumerate(embeddings):
            entities.append([
                f"{file_id}_chunk_{idx}",
                file_id,
                filename,
                idx,
                category,
                content[:4000],
                emb
            ])

        col.insert(entities)
        col.flush()
        return len(entities)

    async def search_similar(
        self,
        query: str,
        category: Optional[str],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        col = self._resolve(category)
        if not col:
            return []

        emb = lite_client.create_embedding(query)

        results = col.search(
            data=[emb],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": 10}},
            limit=limit,
            output_fields=["file_id", "filename", "text", "category", "chunk_index"]
        )

        output = []
        for hit in results[0]:
            output.append({
                "id": hit.id,
                "score": hit.score,
                "content": hit.entity.get("text"),
                "filename": hit.entity.get("filename"),
                "file_id": hit.entity.get("file_id"),
                "chunk_index": hit.entity.get("chunk_index"),
                "category": hit.entity.get("category")
            })

        return output

milvus_client = MilvusClient()
