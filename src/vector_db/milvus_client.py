# src/vector_db/milvus_client.py
import os
from dotenv import load_dotenv
load_dotenv()
import logging
from typing import List, Dict, Any, Optional
from pymilvus import (
    connections, FieldSchema, CollectionSchema,
    DataType, Collection, utility
)

from ..llm.lite_client import lite_client

logger = logging.getLogger(__name__)

# FIXED CATEGORY → COLLECTION NAME MAP
COLLECTIONS = {
    "hr_policy": "hrms_hr_policy",
    "payroll": "hrms_payroll",
    "it_support": "hrms_it_support",
    "facilities": "hrms_facilities",
    "uncategorized": "hrms_uncategorized"
}

DIMENSION = 768  # embedding dim from Gemini


class MilvusClient:
    def __init__(self):
        self.collections: Dict[str, Collection] = {}
        self._connect()
        self._ensure_all_collections()

    def _connect(self):
        uri = os.getenv("MILVUS_URI")
        token = os.getenv("MILVUS_API_KEY")

        if not uri or not token:
            raise RuntimeError("MILVUS_URI or MILVUS_API_KEY missing")

        connections.connect(alias="default", uri=uri, token=token)
        logger.info("Connected to Milvus")

    def _make_schema(self):
        return CollectionSchema(
            fields=[
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
                FieldSchema(name="file_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=255),
                FieldSchema(name="chunk_index", dtype=DataType.INT64),
                FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4096),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIMENSION),
            ],
            description="HRMS Vector Store"
        )

    def _ensure_all_collections(self):
        schema = self._make_schema()

        for key, name in COLLECTIONS.items():
            if not utility.has_collection(name):
                logger.info(f"Creating collection {name} ...")
                col = Collection(name, schema)
                col.create_index(
                    field_name="embedding",
                    index_params={"metric_type": "COSINE", "index_type": "IVF_FLAT", "params": {"nlist": 1024}}
                )
                logger.info(f"Created + Indexed collection: {name}")
            else:
                col = Collection(name)

            col.load()
            self.collections[key] = col
            logger.info(f"Ready collection: {name}")

    def _resolve(self, category: Optional[str]):
        """
        Resolve incoming category to correct Milvus collection. 
        Facilities is checked BEFORE IT support to avoid conflicts like 'facility support'.
        """
        if not category:
            cat = "uncategorized"
        else:
            cat = str(category).lower().strip()

        # ---- FACILITIES FIRST (Priority Fix) ----
        if any(x in cat for x in [
            "facility", "facilities", "facility management",
            "office facility", "workplace facility",
            "building maintenance", "maintenance",
            "premises", "canteen", "cafeteria", "workplace"
        ]):
            resolved = "facilities"

        # ---- PAYROLL ----
        elif any(x in cat for x in ["payroll", "salary", "compensation", "ctc"]):
            resolved = "payroll"

        # ---- HR POLICY ----
        elif any(x in cat for x in ["hr", "policy", "policies", "leave", "attendance", "probation"]):
            resolved = "hr_policy"

        # ---- IT SUPPORT (now after facilities) ----
        elif any(x in cat for x in ["it", "tech", "technical", "helpdesk", "support", "vpn", "laptop"]):
            resolved = "it_support"

        # ---- DEFAULT ----
        else:
            resolved = "uncategorized"

        col = self.collections.get(resolved)
        return resolved, col



    async def store_document_embeddings(
        self,
        file_id: str,
        filename: str,
        content: str,
        embeddings: List[List[float]],
        category: Optional[str],
        chunks: Optional[List[str]] = None,   # <-- NEW optional param
    ) -> int:

        key, col = self._resolve(category)
        if not col:
            raise RuntimeError(f"No collection found for category {key}")

        ids = []
        file_ids = []
        filenames = []
        chunk_indexes = []
        categories = []
        texts = []
        vectors = []

        for idx, emb in enumerate(embeddings):
            ids.append(f"{file_id}_chunk_{idx}")
            file_ids.append(file_id)
            filenames.append(filename)
            chunk_indexes.append(idx)
            categories.append(key)

            # Use per-chunk text if provided; otherwise fall back to content[:4000]
            if chunks and idx < len(chunks):
                chunk_text = chunks[idx][:4000]
            else:
                chunk_text = content[:4000]

            texts.append(chunk_text)
            vectors.append(emb)

        data = [ids, file_ids, filenames, chunk_indexes, categories, texts, vectors]

        col.insert(data)
        col.flush()

        logger.info(f"Inserted {len(embeddings)} vectors → {col.name}")
        return len(embeddings)
    
    def search(
        self,
        query_embedding: List[float],
        category: str,
        top_k: int = 5
    ) -> List[Dict]:
        """
        Search for similar vectors in category-specific collection
        
        Args:
            query_embedding: Query vector
            category: Category to search in
            top_k: Number of results to return
            
        Returns:
            List of search results with metadata
        """
        try:
            # Get collection name
            collection_name = COLLECTIONS.get(category, COLLECTIONS['uncategorized'])
            collection = Collection(collection_name)
            
            # # Load collection if not loaded
            # if not collection.is_loaded:
            #     collection.load()
            
            # Search parameters
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }
            
            # Perform search
            results = collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                output_fields=["file_id", "filename", "chunk_index", "text", "category"]
            )
            
            # Format results
            retrieved_chunks = []
            
            for hits in results:
                for hit in hits:
                    chunk_data = {
                        'id': hit.id,
                        'score': hit.distance,  # Cosine similarity score
                        'file_id': hit.entity.get('file_id'),
                        'filename': hit.entity.get('filename'),
                        'chunk_index': hit.entity.get('chunk_index'),
                        'text': hit.entity.get('text'),
                        'category': hit.entity.get('category')
                    }
                    retrieved_chunks.append(chunk_data)
            
            logger.info(f"🔍 Found {len(retrieved_chunks)} results in '{collection_name}'")
            
            return retrieved_chunks
            
        except Exception as e:
            logger.error(f"❌ Milvus search failed: {e}")
            return []

    async def search_similar(self, query: str, category: Optional[str], limit: int = 5):
        key, col = self._resolve(category)

        if not col:
            logger.warning(f"No collection resolved for category={category}")
            return []

        query_emb = lite_client.create_embedding(query)
        if not query_emb:
            return []

        try:
            results = col.search(
                data=[query_emb],
                anns_field="embedding",
                param={"metric_type": "COSINE", "params": {"nprobe": 10}},
                limit=limit,
                output_fields=["file_id", "filename", "text", "category", "chunk_index"]
            )
        except Exception as e:
            logger.error(f"Milvus search error: {e}")
            return []

        hits = results[0] if results else []
        out = []

        for hit in hits:
            ent = hit.entity
            out.append({
                "id": hit.id,
                "score": float(hit.score),
                "content": ent.get("text"),
                "filename": ent.get("filename"),
                "file_id": ent.get("file_id"),
                "chunk_index": ent.get("chunk_index"),
                "category": ent.get("category") or key,
                "collection": col.name,
            })

        return out


milvus_client = MilvusClient()

