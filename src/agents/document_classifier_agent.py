# src/agents/document_classifier_agent.py

import logging
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

from src.llm.lite_client import lite_client
from src.prompts_engineering.prompts_loader import prompt_loader

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ------------------------------------------------------
# STATE
# ------------------------------------------------------
class DocumentState(TypedDict):
    file_id: str
    filename: str
    file_content: str
    file_type: str

    extracted_text: str
    category: str
    confidence: float
    chunks: List[str]
    embeddings: List[List[float]]

    current_node: str
    error: str
    success: bool


# ------------------------------------------------------
# AGENT
# ------------------------------------------------------
class DocumentClassifierAgent:
    """
    Simplified document processor for single-collection workflows.
    Flow: extract_content -> generate_embeddings -> finalize
    NOTE: No per-document classification done at ingestion time.
    Documents get stored in the unified Milvus collection with a
    'category' field set to 'uncategorized' by default.
    """

    def __init__(self):
        self.llm = lite_client
        # prompt_loader kept for compatibility but not used for classification
        self.templates = prompt_loader
        self.workflow = self._build_workflow()
        logger.info("DocumentClassifierAgent initialized (classification removed)")

    def _build_workflow(self) -> StateGraph:
        g = StateGraph(DocumentState)

        g.add_node("extract_content", self.extract_content)
        g.add_node("generate_embeddings", self.generate_embeddings)
        g.add_node("finalize", self.finalize)

        g.set_entry_point("extract_content")
        g.add_edge("extract_content", "generate_embeddings")
        g.add_edge("generate_embeddings", "finalize")
        g.add_edge("finalize", END)

        return g.compile()

    # ---------------- Node 1 ----------------
    def extract_content(self, state: DocumentState) -> DocumentState:
        state["current_node"] = "extract_content"
        try:
            text = state.get("file_content") or ""
            # keep a sensible upper bound to avoid huge payloads
            state["extracted_text"] = text[:200_000]
            return state
        except Exception as e:
            state["error"] = f"extract_content_error: {e}"
            state["success"] = False
            return state

    # ---------------- Node 2 ----------------
    def generate_embeddings(self, state: DocumentState) -> DocumentState:
        state["current_node"] = "generate_embeddings"

        try:
            text = state.get("extracted_text") or ""
            if not text:
                # No text => no chunks/embeddings, but still return predictable structure
                state["chunks"] = []
                state["embeddings"] = []
                # Keep keys expected downstream
                state["category"] = "uncategorized"
                state["confidence"] = 0.0
                return state

            chunks = self._chunk_text(text)
            embeddings: List[List[float]] = []

            # determine safe embedding dimension from client if available
            try:
                dim = int(self.llm.get_embedding_dim() or 0)
            except Exception:
                dim = 0

            for ch in chunks:
                try:
                    emb = self.llm.create_embedding(ch)
                    # ensure list type
                    embeddings.append(list(emb))
                except Exception as embed_err:
                    logger.exception("Embedding failed for chunk; inserting zero vector")
                    if dim and dim > 0:
                        embeddings.append([0.0] * dim)
                    else:
                        # fallback fixed length (safe default)
                        embeddings.append([0.0] * 768)

            state["chunks"] = chunks
            state["embeddings"] = embeddings

            # No runtime classification — keep default neutral values so callers don't break
            state["category"] = "uncategorized"
            state["confidence"] = 0.0

            return state

        except Exception as e:
            state["error"] = f"generate_embeddings_error: {e}"
            state["success"] = False
            return state

    # ---------------- Node 3 ----------------
    def finalize(self, state: DocumentState) -> DocumentState:
        state["current_node"] = "finalize"
        state["success"] = True
        return state

    # Utility
    def _chunk_text(self, text: str, chunk_size=1000, overlap=200):
        chunks: List[str] = []
        start = 0
        length = len(text)
        while start < length:
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    def process_document(self, file_id, filename, file_content, file_type):
        initial: DocumentState = {
            "file_id": file_id,
            "filename": filename,
            "file_content": file_content,
            "file_type": file_type,
            "extracted_text": "",
            "category": "uncategorized",
            "confidence": 0.0,
            "chunks": [],
            "embeddings": [],
            "current_node": "",
            "error": "",
            "success": False,
        }

        final = self.workflow.invoke(initial)
        return final


# Singleton instance
document_classifier_agent = DocumentClassifierAgent()
