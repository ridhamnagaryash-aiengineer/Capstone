# src/agents/document_classifier_agent.py
import logging
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

from src.llm.lite_client import lite_client
from src.models.document import DocumentCategory
from config.prompts_loader import prompt_loader

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DocumentState(TypedDict):
    file_id: str
    filename: str
    file_content: str
    file_type: str

    # outputs
    extracted_text: str
    category: str
    confidence: float
    chunks: List[str]
    embeddings: List[List[float]]

    # status
    current_node: str
    error: str
    success: bool


class DocumentClassifierAgent:
    """
    LangGraph agent that:
      1) Uses provided file_content (already extracted)
      2) Classifies document using configurable prompt template
      3) Generates embeddings for chunks using lite_client.create_embedding()
    """

    def __init__(self):
        self.llm = lite_client
        self.templates = prompt_loader
        self.workflow = self._build_workflow()
        logger.info("✅ DocumentClassifierAgent initialized")

    def _build_workflow(self) -> StateGraph:
        g = StateGraph(DocumentState)
        g.add_node("extract_content", self.extract_content)
        g.add_node("classify_document", self.classify_document)
        g.add_node("generate_embeddings", self.generate_embeddings)
        g.add_node("finalize", self.finalize)

        g.set_entry_point("extract_content")
        g.add_edge("extract_content", "classify_document")
        g.add_edge("classify_document", "generate_embeddings")
        g.add_edge("generate_embeddings", "finalize")
        g.add_edge("finalize", END)

        return g.compile()

    # ---------------- Node 1 ----------------
    def extract_content(self, state: DocumentState) -> DocumentState:
        state["current_node"] = "extract_content"
        try:
            # Use provided extracted content; enforce a size cap for safety
            text = state.get("file_content", "") or ""
            state["extracted_text"] = text[:200_000]  # safety cap
            logger.info(f"[extract_content] {state['filename']} length={len(state['extracted_text'])}")
            return state
        except Exception as e:
            logger.exception("extract_content failed")
            state["error"] = f"extract_content_error: {e}"
            state["success"] = False
            return state

    # ---------------- Node 2 ----------------
    def classify_document(self, state: DocumentState) -> DocumentState:
        state["current_node"] = "classify_document"
        try:
            text_sample = (state.get("extracted_text") or "")[:4000]
            template = self.templates.get("document_classification")
            prompt = template.format(content=text_sample)

            response = self.llm.chat_completion([{"role": "user", "content": prompt}])

            # tolerant parsing
            category = "uncategorized"
            confidence = 0.0
            for line in response.splitlines():
                line_l = line.strip().lower()
                if line_l.startswith("category:"):
                    category = line.split(":", 1)[1].strip().lower()
                elif line_l.startswith("confidence:"):
                    try:
                        confidence = float(line.split(":", 1)[1].strip())
                    except Exception:
                        confidence = 0.5

            # normalize & validate category against enum values
            valid_map = {c.value.lower(): c.value for c in DocumentCategory}
            cat_norm = (category or "").strip().lower()
            if cat_norm in valid_map:
                category = valid_map[cat_norm]
            else:
                logger.warning(f"[classify_document] invalid category '{category}', defaulting to 'uncategorized'")
                category = DocumentCategory.UNCATEGORIZED.value
                confidence = 0.0

            state["category"] = category
            state["confidence"] = float(confidence)
            logger.info(f"[classify_document] {state['filename']} -> {category} ({confidence:.2f})")
            return state

        except Exception as e:
            logger.exception("classify_document failed")
            state["error"] = f"classify_document_error: {e}"
            state["category"] = DocumentCategory.UNCATEGORIZED.value
            state["confidence"] = 0.0
            state["success"] = False
            return state

    # ---------------- Node 3 ----------------
    def generate_embeddings(self, state: DocumentState) -> DocumentState:
        state["current_node"] = "generate_embeddings"
        try:
            text = state.get("extracted_text", "") or ""
            if not text:
                state["chunks"] = []
                state["embeddings"] = []
                logger.warning("[generate_embeddings] empty text, skipping embeddings")
                return state

            chunks = self._chunk_text(text, chunk_size=1000, overlap=200)
            state["chunks"] = chunks
            embeddings: List[List[float]] = []

            for i, chunk in enumerate(chunks):
                try:
                    emb = self.llm.create_embedding(chunk)
                    embeddings.append(list(emb))
                except Exception as e:
                    logger.error(f"[generate_embeddings] embedding failed for chunk {i}: {e}")
                    # fallback zero vector sized to expected dim if known else empty
                    # try to get dimension from client if available
                    try:
                        dim = self.llm.get_embedding_dim() if hasattr(self.llm, "get_embedding_dim") else 768
                    except Exception:
                        dim = 768
                    embeddings.append([0.0] * dim)

            state["embeddings"] = embeddings
            logger.info(f"[generate_embeddings] generated {len(embeddings)} embeddings for {state['filename']}")
            return state

        except Exception as e:
            logger.exception("generate_embeddings failed")
            state["error"] = f"generate_embeddings_error: {e}"
            state["success"] = False
            return state

    # ---------------- Node 4 ----------------
    def finalize(self, state: DocumentState) -> DocumentState:
        state["current_node"] = "finalize"
        state["success"] = True
        logger.info(f"[finalize] completed for {state.get('filename')}")
        return state

    # ---------------- Utility ----------------
    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        chunks: List[str] = []
        start = 0
        n = len(text)
        while start < n:
            end = start + chunk_size
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += chunk_size - overlap
        return chunks

    # ---------------- Public runner ----------------
    def process_document(
        self,
        file_id: str,
        filename: str,
        file_content: str,
        file_type: str
    ) -> Dict[str, Any]:
        """Run the compiled LangGraph workflow synchronously and return final state dict."""
        initial_state: DocumentState = {
            "file_id": file_id,
            "filename": filename,
            "file_content": file_content,
            "file_type": file_type,
            "extracted_text": "",
            "category": "",
            "confidence": 0.0,
            "chunks": [],
            "embeddings": [],
            "current_node": "",
            "error": "",
            "success": False,
        }

        logger.info(f"🚀 DocumentClassifierAgent processing: {filename}")
        final_state = self.workflow.invoke(initial_state)

        if not final_state.get("success"):
            logger.error(f"[process_document] failure: {final_state.get('error')}")
        else:
            logger.info(f"[process_document] success: {filename} -> {final_state.get('category')}")

        return final_state


# Singleton instance
document_classifier_agent = DocumentClassifierAgent()
