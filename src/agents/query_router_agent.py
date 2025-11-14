# src/agents/query_router_agent.py

import logging
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

from src.llm.lite_client import lite_client
from src.retriever.hr_retriever import HRRetriever
from config.prompts_loader import prompt_loader

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ---------------- CATEGORY NORMALIZER ----------------
def normalize_category(raw: Optional[str]) -> str:
    t = (raw or "").lower()

    if "payroll" in t or "salary" in t or "compensation" in t:
        return "payroll"

    if "facility" in t or "facilities" in t or "maintenance" in t or "cafeteria" in t:
        return "facilities"

    if "it" in t or "tech" in t or "technical" in t or "support" in t or "helpdesk" in t:
        return "it_support"

    if "policy" in t or "hr" in t or "leave" in t or "attendance" in t:
        return "hr_policy"

    return "uncategorized"


# ---------------- STATE ----------------
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
        self.templates = prompt_loader
        self.retriever = HRRetriever()
        self.workflow = self._build()

    # WORKFLOW BUILD
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

    # ---------------- 1. CLASSIFICATION ----------------
    def classify_query(self, state: QueryState) -> QueryState:
        state["current_node"] = "classify_query"
        try:
            # FIXED — Correct template access
            template = self.templates.get("query_classification")
            prompt = template.format(query=state["user_query"])

            response = self.llm.chat_completion([{"role": "user", "content": prompt}])

            raw_cat = "uncategorized"
            conf = 0.0

            for line in response.splitlines():
                l = line.strip().lower()
                if l.startswith("category:"):
                    raw_cat = line.split(":", 1)[1].strip()
                elif l.startswith("confidence:"):
                    try:
                        conf = float(line.split(":", 1)[1].strip())
                    except:
                        conf = 0.5

            norm = normalize_category(raw_cat)

            logger.info(f"[Router] RAW CATEGORY → {raw_cat}")
            logger.info(f"[Router] NORMALIZED  → {norm}")

            state["query_category"] = norm
            state["confidence"] = conf
            return state

        except Exception as e:
            logger.exception("[Router] classify_query failed")
            state["query_category"] = "uncategorized"
            state["confidence"] = 0.0
            state["error"] = str(e)
            return state

    # ---------------- 2. EMBEDDING ----------------
    def generate_embedding(self, state: QueryState) -> QueryState:
        state["current_node"] = "generate_embedding"
        try:
            state["query_embedding"] = self.llm.create_embedding(
                state["user_query"]
            )
            return state
        except Exception as e:
            logger.exception("[Router] embedding error")
            state["error"] = f"embedding_error: {e}"
            return state

    # ---------------- 3. MILVUS SEARCH ----------------
    async def search_milvus(self, state: QueryState) -> QueryState:
        state["current_node"] = "search_milvus"
        try:
            results = await self.retriever.retrieve(
                query=state["user_query"],
                category=state["query_category"],
                top_k=5
            )

            logger.info(f"[Router] Retrieved {len(results)} chunks from category '{state['query_category']}'")

            state["retrieved_chunks"] = results
            return state

        except Exception as e:
            logger.exception("[Router] search_milvus error")
            state["retrieved_chunks"] = []
            state["error"] = str(e)
            return state

    # ---------------- 4. RESPONSE GENERATION ----------------
    def generate_response(self, state: QueryState) -> QueryState:
        state["current_node"] = "generate_response"

        try:
            docs = state.get("retrieved_chunks") or []

            # Personalization
            user_info = state.get("user_info") or {}
            username = user_info.get("username") or "User"
            grade = user_info.get("grade")

            user_context = f"User Name: {username}.\n"
            if grade:
                user_context += f"User Grade: {grade}.\n"
            user_context += "Always address the user by name.\n"

            # Fallback: no RAG hits
            if not docs:
                fallback = (
                    f"{user_context}\n"
                    f"The user asked: '{state['user_query']}'.\n"
                    "No documents matched; provide best HR guidance.\n"
                )
                out = self.llm.chat_completion([{"role": "user", "content": fallback}])
                state["llm_response"] = out
                state["sources"] = []
                state["success"] = True
                return state

            # RAG MODE
            context = "\n\n".join(
                [f"[{d.get('filename')}] → {d.get('content')}" for d in docs]
            )

            template = self.templates.get("chat_response")

            prompt = template.format(
                context=context,
                question=state["user_query"],
                user_context=user_context
            )

            answer = self.llm.chat_completion([{"role": "user", "content": prompt}])

            state["llm_response"] = answer
            state["sources"] = docs
            state["success"] = True
            return state

        except Exception as e:
            logger.exception("[Router] response error")
            state["error"] = f"response_error: {e}"
            state["success"] = False
            return state

    # ---------------- PUBLIC ENTRY ----------------
    async def process_query(self, user_query: str, chat_history: List[Dict], user_info=None) -> Dict[str, Any]:
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
            "response": final.get("llm_response"),
            "sources": final.get("sources", []),
            "category": final.get("query_category"),
            "confidence": final.get("confidence"),
            "success": final.get("success"),
            "error": final.get("error"),
        }


query_router_agent = QueryRouterAgent()
