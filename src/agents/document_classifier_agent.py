# src/agents/document_classifier_agent.py

import logging
from typing import TypedDict, List, Dict, Any
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
# AGENT (NO LANGCHAIN)
# ------------------------------------------------------
class DocumentClassifierAgent:
    """
    Simple document processor — no LangChain, no LangGraph, no magic.
    Straight sequential function calls.
    """

    def __init__(self):
        self.llm = lite_client
        self.templates = prompt_loader
        logger.info("DocumentClassifierAgent initialized (pure Python pipeline)")

    # ---------------- Step 1 ----------------
    def extract_content(self, state: DocumentState) -> None:
        state["current_node"] = "extract_content"
        try:
            text = state.get("file_content") or ""
            state["extracted_text"] = text[:200_000]
        except Exception as e:
            state["error"] = f"extract_content_error: {e}"
            state["success"] = False

    # ---------------- Step 2 ----------------
    def generate_embeddings(self, state: DocumentState) -> None:
        state["current_node"] = "generate_embeddings"

        try:
            text = state.get("extracted_text") or ""

            # Empty case
            if not text:
                state["chunks"] = []
                state["embeddings"] = []
                state["category"] = "uncategorized"
                state["confidence"] = 0.0
                return

            chunks = self._chunk_text(text)
            embeddings: List[List[float]] = []

            # detect embedding dimension
            try:
                dim = int(self.llm.get_embedding_dim() or 0)
            except Exception:
                dim = 0

            for ch in chunks:
                try:
                    emb = self.llm.create_embedding(ch)
                    embeddings.append(list(emb))
                except Exception:
                    logger.exception("Embedding failed; using zero vector")
                    if dim and dim > 0:
                        embeddings.append([0.0] * dim)
                    else:
                        embeddings.append([0.0] * 768)

            state["chunks"] = chunks
            state["embeddings"] = embeddings
            state["category"] = "uncategorized"
            state["confidence"] = 0.0

        except Exception as e:
            state["error"] = f"generate_embeddings_error: {e}"
            state["success"] = False

    # ---------------- Step 3 ----------------
    def finalize(self, state: DocumentState) -> None:
        state["current_node"] = "finalize"
        state["success"] = True

    # ---------------- Main entry ----------------
    def process_document(self, file_id, filename, file_content, file_type):
        state: DocumentState = {
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

        # Ordered pipeline (same as your former graph)
        self.extract_content(state)
        self.generate_embeddings(state)
        self.finalize(state)

        return state

    # ---------------- Helpers ----------------
    def _chunk_text(self, text: str, chunk_size=1000, overlap=200):
        chunks: List[str] = []
        start = 0
        length = len(text)
        while start < length:
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks


# Singleton
document_classifier_agent = DocumentClassifierAgent()
