# src/agents/query_router_agent.py

import logging
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

from src.llm.lite_client import lite_client
from src.vector_db.milvus_client import milvus_client
from config.prompts_loader import prompt_loader

logger = logging.getLogger(__name__)


# ---------------- CATEGORY NORMALIZER ----------------
def normalize_category(raw: str) -> str:
    t = (raw or "").lower()

    if "payroll" in t or "salary" in t or "ctc" in t:
        return "payroll"

    if "facility" in t or "facilities" in t or "maintenance" in t:
        return "facilities"

    if "it" in t or "tech" in t or "support" in t or "helpdesk" in t:
        return "it_support"

    if "policy" in t or "hr" in t or "leave" in t or "attendance" in t:
        return "hr_policy"

    return "uncategorized"


# ---------------- QUERY STATE ----------------
class QueryState(TypedDict):
    user_query: str
    chat_history: List[Dict]
    query_category: str
    confidence: float
    query_embedding: List[float]
    retrieved_chunks: List[Dict]
    llm_response: str
    sources: List[Dict]
    current_node: str
    error: str
    success: bool
    user_info: Dict[str, Any]


# ---------------- AGENT ----------------
class QueryRouterAgent:
    def __init__(self):
        self.llm = lite_client
        self.db = milvus_client
        self.templates = prompt_loader
        self.workflow = self._build()

    # ---------------- GRAPH BUILD ----------------
    def _build(self):
        g = StateGraph(QueryState)

        g.add_node("classify_query", self.classify_query)
        g.add_node("generate_embedding", self.generate_embedding)
        g.add_node("search_milvus", self.search_milvus)
        g.add_node("generate_response", self.generate_response)

        g.set_entry_point("classify_query")
        g.add_edge("classify_query", "generate_embedding")
        g.add_edge("generate_embedding", "search_milvus")
        g.add_edge("search_milvus", "generate_response")
        g.add_edge("generate_response", END)

        return g.compile()

    # ---------------- NODE 1: CLASSIFY QUERY ----------------
    def classify_query(self, state: QueryState) -> QueryState:
        state["current_node"] = "classify_query"
        try:
            prompt = self.templates["query_classification"].format(
                query=state["user_query"]
            )
            response = self.llm.chat_completion(
                [{"role": "user", "content": prompt}]
            )

            raw_cat = "uncategorized"
            conf = 0.0

            for line in response.splitlines():
                low = line.strip().lower()
                if low.startswith("category:"):
                    raw_cat = line.split(":", 1)[1].strip()
                elif low.startswith("confidence:"):
                    try:
                        conf = float(line.split(":", 1)[1].strip())
                    except:
                        conf = 0.5

            # 🔥 strict normalizer to match Milvus collection names
            state["query_category"] = normalize_category(raw_cat)
            state["confidence"] = conf

            return state

        except Exception as e:
            state["query_category"] = "uncategorized"
            state["confidence"] = 0.0
            state["error"] = str(e)
            return state

    # ---------------- NODE 2: GENERATE EMBEDDING ----------------
    def generate_embedding(self, state: QueryState) -> QueryState:
        state["current_node"] = "generate_embedding"
        try:
            state["query_embedding"] = self.llm.create_embedding(state["user_query"])
            return state
        except Exception as e:
            state["error"] = f"embedding_error: {e}"
            return state

    # ---------------- NODE 3: SEARCH MILVUS ----------------
    async def search_milvus(self, state: QueryState) -> QueryState:
        state["current_node"] = "search_milvus"
        try:
            results = await self.db.search_similar(
                query=state["user_query"],
                category=state["query_category"],
                limit=5,
            )
            state["retrieved_chunks"] = results
            return state

        except Exception as e:
            state["retrieved_chunks"] = []
            state["error"] = str(e)
            return state

    # ---------------- NODE 4: GENERATE RESPONSE ----------------
    def generate_response(self, state: QueryState) -> QueryState:
        state["current_node"] = "generate_response"

        try:
            docs = state["retrieved_chunks"]

            # ---------------- PERSONALIZATION ----------------
            user_info = state.get("user_info") or {}
            username = user_info.get("username") or "User"
            grade = user_info.get("grade")

            user_context = f"User Name: {username}.\n"
            if grade:
                user_context += f"User Grade: {grade}.\n"
            user_context += (
                "Always address the user by name, and adapt tone based on their grade.\n"
                "Be warm, clear, and HR-friendly. Avoid jargon.\n"
            )

            # ---------------- FALLBACK: NO DOCUMENTS ----------------
            if not docs:
                fallback_prompt = (
                    f"{user_context}\n"
                    f"The user asked: '{state['user_query']}'.\n"
                    "Answer helpfully using HR-best practices.\n"
                    "Do NOT mention document retrieval or missing documents.\n"
                )

                answer = self.llm.chat_completion(
                    [{"role": "user", "content": fallback_prompt}]
                )

                state["llm_response"] = answer
                state["sources"] = []
                state["success"] = True
                return state

            # ---------------- NORMAL RAG MODE ----------------
            context = "\n\n".join(
                [f"[{d['filename']}]\n{d['content']}" for d in docs]
            )

            template = self.templates["chat_response"]

            prompt = template.format(
                context=context,
                question=state["user_query"],
                user_context=user_context,
            )

            answer = self.llm.chat_completion(
                [{"role": "user", "content": prompt}]
            )

            state["llm_response"] = answer
            state["sources"] = docs
            state["success"] = True
            return state

        except Exception as e:
            state["error"] = f"response_error: {e}"
            state["success"] = False
            return state

    # ---------------- PUBLIC ENTRY ----------------
    async def process_query(self, user_query, chat_history, user_info=None):
        initial: QueryState = {
            "user_query": user_query,
            "chat_history": chat_history or [],
            "query_category": "",
            "confidence": 0.0,
            "query_embedding": [],
            "retrieved_chunks": [],
            "llm_response": "",
            "sources": [],
            "current_node": "",
            "error": "",
            "success": False,
            "user_info": user_info or {},
        }

        final = await self.workflow.ainvoke(initial)

        return {
            "response": final["llm_response"],
            "sources": final["sources"],
            "category": final["query_category"],
            "confidence": final["confidence"],
            "success": final["success"],
            "error": final["error"],
        }


query_router_agent = QueryRouterAgent()
