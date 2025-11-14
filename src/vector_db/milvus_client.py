import os
from dotenv import load_dotenv
load_dotenv()
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
                logger.exception(f"Failed loading collection {name}: {e}")

    def _resolve(self, category: Optional[str]):
        key = (category or "uncategorized").lower()
        # map some potential variants to keys (defensive)
        if key in ["hr", "hr_policy", "policy", "policies"]:
            key = "hr_policy"
        elif key in ["payroll", "salary", "compensation"]:
            key = "payroll"
        elif key in ["it", "it_support", "tech", "helpdesk", "support"]:
            key = "it_support"
        elif key in ["facility", "facilities", "maintenance", "cafeteria"]:
            key = "facilities"
        else:
            key = "uncategorized"

        col = self.collections.get(key)
        return key, col

    async def store_document_embeddings(
        self,
        file_id: str,
        filename: str,
        content: str,
        embeddings: List[List[float]],
        category: Optional[str],
    ) -> int:
        key, col = self._resolve(category)
        if not col:
            raise Exception(f"No collection for category: {key}")

        entities = []
        for idx, emb in enumerate(embeddings):
            entities.append([
                f"{file_id}_chunk_{idx}",
                file_id,
                filename,
                idx,
                category or key,
                content[:4000],
                emb
            ])

        col.insert(entities)
        col.flush()
        logger.info(f"Inserted {len(entities)} vectors into {col.name}")
        return len(entities)

    async def search_similar(
        self,
        query: str,
        category: Optional[str],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        key, col = self._resolve(category)
        if not col:
            logger.warning(f"search_similar: no collection resolved for category={category} (resolved key={key})")
            return []

        # create embedding (sync client)
        query_emb = lite_client.create_embedding(query)
        if not query_emb or len(query_emb) == 0:
            logger.warning("search_similar: got empty query embedding")
            return []

        search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
        try:
            results = col.search(
                data=[query_emb],
                anns_field="embedding",
                param=search_params,
                limit=limit,
                output_fields=["file_id", "filename", "text", "category", "chunk_index"]
            )
        except Exception as e:
            logger.exception(f"Milvus search error on {col.name}: {e}")
            return []

        output = []
        # results is list of hits lists: results[0]
        hits = results[0] if results else []
        for hit in hits:
            ent = hit.entity
            output.append({
                "id": hit.id,
                "score": float(hit.score),
                "content": ent.get("text"),
                "filename": ent.get("filename"),
                "file_id": ent.get("file_id"),
                "chunk_index": ent.get("chunk_index"),
                "category": ent.get("category") or key,
                "collection": col.name
            })

        logger.info(f"search_similar: found {len(output)} hits in collection {col.name} for key={key}")
        return output


# singleton
milvus_client = MilvusClient()

