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
logger.setLevel(logging.INFO)

COLLECTION_NAME = os.getenv("MILVUS_COLLECTION", "hrms_all")
DIMENSION = int(os.getenv("EMBED_DIMENSION", "768"))

class MilvusClient:
    def __init__(self):
        self.collection: Optional[Collection] = None
        self._connect()
        self._ensure_collection()

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
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=200),
                FieldSchema(name="file_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=255),
                FieldSchema(name="chunk_index", dtype=DataType.INT64),
                FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4096),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIMENSION),
            ],
            description="Unified HRMS Vector Store"
        )

    def _ensure_collection(self):
        if not utility.has_collection(COLLECTION_NAME):
            logger.info(f"Creating collection {COLLECTION_NAME} ...")
            schema = self._make_schema()
            col = Collection(COLLECTION_NAME, schema)
            col.create_index(
                field_name="embedding",
                index_params={"metric_type": "COSINE", "index_type": "IVF_FLAT", "params": {"nlist": 1024}}
            )
            col.load()
            self.collection = col
            logger.info(f"Created + Indexed collection: {COLLECTION_NAME}")
        else:
            col = Collection(COLLECTION_NAME)
            col.load()
            self.collection = col
            logger.info(f"Ready collection: {COLLECTION_NAME}")

    async def store_document_embeddings(
        self,
        file_id: str,
        filename: str,
        content: str,
        embeddings: List[List[float]],
        category: Optional[str] = None,
        chunks: Optional[List[str]] = None,
    ) -> int:
        """
        Insert embeddings into the single collection.
        Each vector stores its category (string) so you can filter later.
        """
        col = self.collection
        if not col:
            raise RuntimeError("Milvus collection not initialized")

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
            categories.append((category or "uncategorized"))

            if chunks and idx < len(chunks):
                chunk_text = chunks[idx][:4000]
            else:
                chunk_text = content[:4000]

            texts.append(chunk_text)
            vectors.append(emb)

        data = [ids, file_ids, filenames, chunk_indexes, categories, texts, vectors]

        col.insert(data)
        col.flush()

        logger.info(f"Inserted {len(embeddings)} vectors into {col.name}")
        return len(embeddings)

    async def search_similar(self, query: str, limit: int = 5, query_embedding: Optional[List[float]] = None, category: Optional[str] = None):
        """
        Search the single collection. Accepts a precomputed embedding (preferred).
        If `category` provided, results will be post-filtered by the stored 'category' field.
        """
        col = self.collection
        if not col:
            logger.warning("Milvus collection not ready")
            return []

        # Use provided embedding if present; otherwise create one
        query_emb = query_embedding
        if not query_emb:
            try:
                query_emb = lite_client.create_embedding(query)
            except Exception as e:
                logger.exception("Failed to create embedding for query")
                return []

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
                "category": ent.get("category"),
                "collection": col.name,
            })

        if category:
            cat_norm = (category or "").lower().strip()
            out = [r for r in out if (r.get("category") or "").lower().strip() == cat_norm]

        return out

    async def delete_by_file_id(self, file_id: str) -> int:
        """
        Delete vectors by file_id. Returns number of deleted rows if successful.
        Uses expression on the 'file_id' field.
        """
        col = self.collection
        if not col:
            logger.warning("Milvus collection not ready for delete")
            return 0

        # Expression format depends on Milvus version; use single quotes for string.
        expr = f"file_id == '{file_id}'"
        try:
            res = col.delete(expr)
            # col.flush() not strictly required for delete, but call to be safe
            col.flush()
            # pymilvus delete returns None; to be conservative, just return 1 (or you can query count)
            logger.info(f"Requested delete for file_id={file_id}")
            return 1
        except Exception as e:
            logger.exception(f"Milvus delete_by_file_id failed: {e}")
            return 0


milvus_client = MilvusClient()
