# src/agents/query_router_agent.py
import logging
from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, END

from src.llm.lite_client import lite_client
from src.vector_db.milvus_client import milvus_client
from config.prompts_loader import prompt_loader

logger = logging.getLogger(__name__)


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


class QueryRouterAgent:
    """LangGraph-based router using Gemini embeddings + prompt loader."""

    def __init__(self):
        self.llm = lite_client
        self.db = milvus_client
        self.templates = prompt_loader
        self.workflow = self._build()

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

    # ---------------- NODE 1 ----------------
    def classify_query(self, state: QueryState) -> QueryState:
        state["current_node"] = "classify_query"
        try:
            template = self.templates.get("query_classification")
            prompt = template.format(query=state["user_query"])

            response = self.llm.chat_completion([
                {"role": "user", "content": prompt}
            ])

            category = "uncategorized"
            confidence = 0.0

            for line in response.splitlines():
                low = line.strip().lower()
                if low.startswith("category:"):
                    category = line.split(":", 1)[1].strip().lower()
                elif low.startswith("confidence:"):
                    try:
                        confidence = float(line.split(":", 1)[1].strip())
                    except:
                        confidence = 0.5

            state["query_category"] = category
            state["confidence"] = confidence

            return state
        except Exception as e:
            logger.error(f"classify_query error: {e}")
            state["query_category"] = "uncategorized"
            state["confidence"] = 0.0
            state["error"] = str(e)
            return state

    # ---------------- NODE 2 ----------------
    def generate_embedding(self, state: QueryState) -> QueryState:
        state["current_node"] = "generate_embedding"
        try:
            emb = self.llm.create_embedding(state["user_query"])
            state["query_embedding"] = emb
            return state
        except Exception as e:
            state["error"] = f"embedding_error: {e}"
            logger.error(f"Embedding failure: {e}")
            return state

    # ---------------- NODE 3 ----------------
    async def search_milvus(self, state: QueryState) -> QueryState:
        state["current_node"] = "search_milvus"
        try:
            results = await self.db.search_similar(
                query=state["user_query"],
                category=state["query_category"],
                limit=5
            )
            state["retrieved_chunks"] = results
            return state
        except Exception as e:
            logger.error(f"search_milvus error: {e}")
            state["retrieved_chunks"] = []
            state["error"] = str(e)
            return state

    # ---------------- NODE 4 ----------------
    def generate_response(self, state: QueryState) -> QueryState:
        state["current_node"] = "generate_response"
        try:
            docs = state["retrieved_chunks"]

            if not docs:
                state["llm_response"] = (
                    f"No documents found for category '{state['query_category']}'."
                )
                state["sources"] = []
                state["success"] = True
                return state

            context = "\n\n".join([f"[{d['filename']}]\n{d['content']}" for d in docs])

            template = self.templates.get("chat_response")
            prompt = template.format(
                context=context,
                question=state["user_query"]
            )

            answer = self.llm.chat_completion([
                {"role": "user", "content": prompt}
            ])

            state["llm_response"] = answer
            state["sources"] = docs
            state["success"] = True

            return state

        except Exception as e:
            state["error"] = f"response_error: {e}"
            state["success"] = False
            return state

    # ---------------- PUBLIC RUNNER ----------------
    async def process_query(self, user_query: str, chat_history: List[Dict]) -> Dict:
        """This is what ChatService calls."""
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
            "success": False
        }

        final = await self.workflow.ainvoke(initial)

        return {
            "response": final.get("llm_response"),
            "sources": final.get("sources", []),
            "category": final.get("query_category"),
            "confidence": final.get("confidence"),
            "success": final.get("success", False),
            "error": final.get("error")
        }


query_router_agent = QueryRouterAgent()
