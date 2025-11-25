# src/agents/query_router_agent.py
import logging
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

from src.llm.lite_client import lite_client
from src.retriever.hr_retriever import HRRetriever
from src.prompts_engineering.prompts_loader import prompt_loader

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ---------------- STATE ----------------
class QueryState(TypedDict):
    user_query: str
    chat_history: List[Dict]
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
    """
    Stateless query router. No user context/personality is inserted into prompts.
    Flow: embedding -> search -> response generation (RAG)
    """

    def __init__(self):
        self.llm = lite_client
        self.templates = prompt_loader
        self.retriever = HRRetriever()
        self.workflow = self._build()
        logger.info("QueryRouterAgent initialized (stateless, no user context)")

    def _build(self):
        g = StateGraph(QueryState)

        g.add_node("generate_embedding", self.generate_embedding)
        g.add_node("search_milvus", self.search_milvus)
        g.add_node("generate_response", self.generate_response)

        g.set_entry_point("generate_embedding")
        g.add_edge("generate_embedding", "search_milvus")
        g.add_edge("search_milvus", "generate_response")
        g.add_edge("generate_response", END)

        return g.compile()

    # ---------------- 1. EMBEDDING ----------------
    def generate_embedding(self, state: QueryState) -> QueryState:
        state["current_node"] = "generate_embedding"
        try:
            emb = self.llm.create_embedding(state["user_query"])
            state["query_embedding"] = emb if isinstance(emb, list) else list(emb)
            return state
        except Exception as e:
            logger.exception("[Router] embedding error")
            state["error"] = f"embedding_error: {e}"
            state["query_embedding"] = []
            return state

    # ---------------- 2. MILVUS SEARCH ----------------
    async def search_milvus(self, state: QueryState) -> QueryState:
        state["current_node"] = "search_milvus"
        try:
            results = await self.retriever.retrieve(
            query=state["user_query"],
            query_embedding=state.get("query_embedding"),
            top_k=5)


            logger.info(f"[Router] Retrieved {len(results)} chunks")
            state["retrieved_chunks"] = results
            return state

        except Exception as e:
            logger.exception("[Router] search_milvus error")
            state["retrieved_chunks"] = []
            state["error"] = str(e)
            return state

    # ---------------- 3. RESPONSE GENERATION ----------------
    def generate_response(self, state: QueryState) -> QueryState:
        state["current_node"] = "generate_response"
        try:
            docs = state.get("retrieved_chunks") or []

            # Fallback: no RAG hits
            if not docs:
                fallback = (
                    f"The user asked: '{state['user_query']}'.\n"
                    "No documents matched; provide best HR guidance.\n"
                )
                out = self.llm.chat_completion([{"role": "user", "content": fallback}])
                state["llm_response"] = out
                state["sources"] = []
                state["success"] = True
                return state

            # RAG MODE (no personalization)
            context = "\n\n".join(
                [f"[{d.get('filename')}] → {d.get('content')}" for d in docs]
            )

            template = self.templates.get("chat_response")
            prompt = template.format(
                context=context,
                question=state["user_query"],
                user_context=""  # keep template compatibility but empty
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
            "query_embedding": [],
            "retrieved_chunks": [],
            "llm_response": "",
            "sources": [],
            "current_node": "",
            "error": "",
            "success": False,
            "user_info": {},  # not used
        }

        final = await self.workflow.ainvoke(initial)

        return {
            "response": final.get("llm_response"),
            "sources": final.get("sources", []),
            "success": final.get("success"),
            "error": final.get("error"),
        }


query_router_agent = QueryRouterAgent()
