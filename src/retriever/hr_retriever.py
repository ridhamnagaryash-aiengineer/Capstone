# src/retriever/hr_retriever.py
import logging
from typing import List, Dict, Optional

from src.vector_db.milvus_client import milvus_client

logger = logging.getLogger(__name__)


class HRRetriever:
    """Central retriever that routes to Milvus client and normalizes results."""

    def __init__(self):
        self.db = milvus_client

    async def retrieve(
        self,
        query: str,
        category: Optional[str],
        top_k: int = 5
    ) -> List[Dict]:
        try:
            logger.info(f"[Retriever] Query='{query}' → Category='{category}'")
            results = await self.db.search_similar(
                query=query,
                category=category,
                limit=top_k
            )
            logger.info(f"[Retriever] Retrieved {len(results)} chunks")
            return results
        except Exception as e:
            logger.exception(f"[Retriever] retrieval failed: {e}")
            return []
