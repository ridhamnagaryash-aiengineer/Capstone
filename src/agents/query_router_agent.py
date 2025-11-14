# src/agents/query_router_agent.py

import logging
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

from src.llm.lite_client import lite_client
from src.vector_db.milvus_client import milvus_client
from config.prompts_loader import prompt_loader

logger = logging.getLogger(__name__)


# Same normalizer as documents
def normalize_category(raw: str) -> str:
    t = (raw or "").lower()

    if "payroll" in t or "salary" in t:
        return "payroll"

    if "facility" in t or "facilities" in t or "maintenance" in t:
        return "facilities"

    if "it" in t or "tech" in t or "support" in t or "helpdesk" in t:
        return "it_support"

    if "policy" in t or "hr" in t or "leave" in t:
        return "hr_policy"

    return "uncategorized"


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


class QueryRouterAgent:
    def __init__(self):
        self.llm = lite_client
        self.db = milvus_client
        self.templates = prompt_loader
        self.workflow = self._build()

    # Build graph
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

    # ---------------- 1. classify ----------------
    def classify_query(self, state: QueryState) -> QueryState:
        state["current_node"] = "classify_query"
        try:
            prompt = self.templates["query_classification"].format(
                query=state["user_query"]
            )
            response = self.llm.chat_completion([{"role": "user", "content": prompt}])

            raw_cat = "uncategorized"
            conf = 0.0

            for line in response.splitlines():
                l = line.strip().lower()
                if l.startswith("category:"):
                    raw_cat = line.split(":", 1)[1].strip().lower()
                elif l.startswith("confidence:"):
                    try:
                        conf = float(line.split(":", 1)[1].strip())
                    except:
                        conf = 0.5

            # **STRICT NORMALIZATION**
            norm_cat = normalize_category(raw_cat)

            state["query_category"] = norm_cat
            state["confidence"] = conf
            return state

        except Exception as e:
            state["query_category"] = "uncategorized"
            state["confidence"] = 0.0
            state["error"] = str(e)
            return state

    # ---------------- 2. embedding ----------------
    def generate_embedding(self, state: QueryState) -> QueryState:
        state["current_node"] = "generate_embedding"
        try:
            state["query_embedding"] = self.llm.create_embedding(
                state["user_query"]
            )
            return state
        except Exception as e:
            state["error"] = f"embedding_error: {e}"
            return state

    # ---------------- 3. milvus search ----------------
    async def search_milvus(self, state: QueryState) -> QueryState:
        state["current_node"] = "search_milvus"
        try:
            results = await self.db.search_similar(
                query=state["user_query"],
                category=state["query_category"],  # NOW ALWAYS VALID
                limit=5,
            )
            state["retrieved_chunks"] = results
            return state

        except Exception as e:
            state["error"] = str(e)
            state["retrieved_chunks"] = []
            return state

    # ---------------- 4. response ----------------
    def generate_response(self, state: QueryState) -> QueryState:
        state["current_node"] = "generate_response"

        try:
            docs = state["retrieved_chunks"]
            user_context = ""

            if not docs:
                fallback = (
                    f"User asked: {state['user_query']}\n"
                    "No HR documents matched. Answer as per general HR knowledge."
                )
                out = self.llm.chat_completion([{"role": "user", "content": fallback}])
                state["llm_response"] = out
                state["sources"] = []
                state["success"] = True
                return state

            context = "\n\n".join(
                [f"[{d['filename']}]\n{d['content']}" for d in docs]
            )

            prompt = self.templates["chat_response"].format(
                context=context,
                question=state["user_query"],
                user_context=user_context,
            )

            answer = self.llm.chat_completion([{"role": "user", "content": prompt}])

            state["llm_response"] = answer
            state["sources"] = docs
            state["success"] = True
            return state

        except Exception as e:
            state["error"] = f"response_error: {e}"
            state["success"] = False
            return state

    # Entrypoint
    async def process_query(self, user_query, chat_history, user_info=None):
        initial: QueryState = {
            "user_query": user_query,
            "chat_history": chat_history,
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
