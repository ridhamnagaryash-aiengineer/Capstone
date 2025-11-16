# src/agents/document_classifier_agent.py

import logging
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

from src.llm.lite_client import lite_client
from src.prompts_engineering.prompts_loader import prompt_loader

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def normalize_category(raw: str) -> str:
    t = (raw or "").lower()
    t = t.replace("-", " ").replace("_", " ").strip()

    # HR POLICY
    if any(k in t for k in [
        "policy", "hr", "leave", "attendance", "holiday",
        "probation", "onboarding", "exit", "transfer"
    ]):
        return "hr_policy"

    # PAYROLL
    if any(k in t for k in [
        "payroll", "salary", "compensation", "ctc", "slip",
        "bonus", "payout", "reimbursement"
    ]):
        return "payroll"

    # FACILITIES
    if any(x in t for x in [
        "facility", "facilities", "facility management", 
        "office facility", "office facilities",
        "maintenance", "building", "premises", 
        "canteen", "cafeteria", "workplace", "office admin"
    ]):
        return "facilities"

    # IT SUPPORT
    if any(k in t for k in [
        "it", "tech", "technical", "support", "helpdesk",
        "laptop", "vpn", "email", "hardware", "software", "reset"
    ]):
        return "it_support"
    

    return "uncategorized"



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
    def __init__(self):
        self.llm = lite_client
        self.templates = prompt_loader
        self.workflow = self._build_workflow()
        logger.info("DocumentClassifierAgent initialized")

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
            text = state.get("file_content") or ""
            state["extracted_text"] = text[:200_000]
            return state
        except Exception as e:
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

            response = self.llm.chat_completion([
                {"role": "user", "content": prompt}
            ])

            # parse
            raw_category = "uncategorized"
            confidence = 0.0

            for line in response.splitlines():
                l = line.strip().lower()
                if l.startswith("category:"):
                    raw_category = line.split(":", 1)[1].strip().lower()
                elif l.startswith("confidence:"):
                    try:
                        confidence = float(line.split(":", 1)[1].strip())
                    except:
                        confidence = 0.5

            # Apply strict normalization
            normalized = normalize_category(raw_category)

            state["category"] = normalized
            state["confidence"] = confidence
            logger.error(f"[CLASSIFIER DEBUG] RAW='{raw_category}' → NORMALIZED='{normalized}' → CONF={confidence}")

            return state

        except Exception as e:
            state["category"] = "uncategorized"
            state["confidence"] = 0.0
            state["error"] = f"classify_document_error: {e}"
            state["success"] = False
            return state

    # ---------------- Node 3 ----------------
    def generate_embeddings(self, state: DocumentState) -> DocumentState:
        state["current_node"] = "generate_embeddings"

        try:
            text = state.get("extracted_text") or ""
            if not text:
                state["chunks"] = []
                state["embeddings"] = []
                return state

            chunks = self._chunk_text(text)
            embeddings = []

            for ch in chunks:
                try:
                    emb = self.llm.create_embedding(ch)
                    embeddings.append(list(emb))
                except:
                    embeddings.append([0.0] * 768)

            state["chunks"] = chunks
            state["embeddings"] = embeddings
            return state

        except Exception as e:
            state["error"] = f"generate_embeddings_error: {e}"
            state["success"] = False
            return state

    # ---------------- Node 4 ----------------
    def finalize(self, state: DocumentState) -> DocumentState:
        state["current_node"] = "finalize"
        state["success"] = True
        return state

    # Utility
    def _chunk_text(self, text: str, chunk_size=1000, overlap=200):
        chunks = []
        start = 0
        while start < len(text):
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
            "category": "",
            "confidence": 0.0,
            "chunks": [],
            "embeddings": [],
            "current_node": "",
            "error": "",
            "success": False,
        }

        final = self.workflow.invoke(initial)
        return final



document_classifier_agent = DocumentClassifierAgent()
