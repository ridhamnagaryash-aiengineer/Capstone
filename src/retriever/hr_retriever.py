# src/retriever/hr_retriever.py
import logging
from typing import List, Dict, Optional

from src.vector_db.milvus_client import milvus_client

logger = logging.getLogger(__name__)


class HRRetriever:
    """Simple retriever for unified Milvus collection."""

    def __init__(self):
        self.db = milvus_client

    async def retrieve(
        self,
        query: str,
        query_embedding: Optional[List[float]],
        top_k: int = 5
    ) -> List[Dict]:
        try:
            logger.info(f"[Retriever] Query='{query}'")

            results = await self.db.search_similar(
                query=query,
                query_embedding=query_embedding,
                category=None, 
                limit=top_k,
            )

            logger.info(f"[Retriever] Retrieved {len(results)} chunks")
            return results

        except Exception as e:
            logger.exception("[Retriever] retrieval failed")
            return []
