import logging
from typing import TypedDict, List, Dict, Any
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
    user_info: Dict[str, Any]


class QueryRouterAgent:
    """LangGraph-based router using embeddings + Milvus + prompt templates + user personalization."""

    def __init__(self):
        self.llm = lite_client
        self.db = milvus_client
        self.templates = prompt_loader
        self.workflow = self._build()

    # -------------------------------------------------
    # PERSONALIZATION SUPPORT
    # -------------------------------------------------
    def _format_user_context(self, user_info: Dict[str, Any]) -> str:
        """Inject user's name + grade into LLM prompt."""
        if not user_info:
            return ""

        username = user_info.get("username") or "User"
        grade = user_info.get("grade")

        ctx = f"User Name: {username}.\n"
        if grade:
            ctx += f"User Grade: {grade}.\n"

        ctx += "Use the user's name and grade to personalize the response.\n"
        return ctx

    # -------------------------------------------------
    # GRAPH BUILD
    # -------------------------------------------------
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

    # -------------------------------------------------
    # NODE 1 — QUERY CLASSIFICATION
    # -------------------------------------------------
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
            state["error"] = str(e)
            state["query_category"] = "uncategorized"
            state["confidence"] = 0.0
            return state

    # -------------------------------------------------
    # NODE 2 — EMBEDDING GENERATION
    # -------------------------------------------------
    def generate_embedding(self, state: QueryState) -> QueryState:
        state["current_node"] = "generate_embedding"
        try:
            embedding = self.llm.create_embedding(state["user_query"])
            state["query_embedding"] = embedding
            return state

        except Exception as e:
            logger.error(f"Embedding error: {e}")
            state["error"] = f"embedding_error: {e}"
            return state

    # -------------------------------------------------
    # NODE 3 — VECTOR SEARCH
    # -------------------------------------------------
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

    # -------------------------------------------------
    # NODE 4 — RESPONSE GENERATION (PERSONALIZED)
    # -------------------------------------------------
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

            # Build knowledge context
            context = "\n\n".join(
                [f"[{d['filename']}]\n{d['content']}" for d in docs]
            )

            # PERSONALIZATION LAYER
            user_context = self._format_user_context(state.get("user_info"))

            # Prompt template
            template = self.templates.get("chat_response")

            prompt = template.format(
                context=context,
                question=state["user_query"],
                user_context=user_context
            )

            answer = self.llm.chat_completion([
                {"role": "user", "content": prompt}
            ])

            state["llm_response"] = answer
            state["sources"] = docs
            state["success"] = True
            return state

        except Exception as e:
            logger.error(f"response_error: {e}")
            state["error"] = f"response_error: {e}"
            state["success"] = False
            return state

    # -------------------------------------------------
    # PUBLIC ENTRYPOINT (CALLED BY ChatService)
    # -------------------------------------------------
    async def process_query(self, user_query: str, chat_history: List[Dict], user_info=None) -> Dict:
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
            "user_info": user_info or {}
        }

        final = await self.workflow.ainvoke(initial)

        return {
            "response": final.get("llm_response"),
            "sources": final.get("sources", []),
            "category": final.get("query_category"),
            "confidence": final.get("confidence"),
            "success": final.get("success"),
            "error": final.get("error")
        }


query_router_agent = QueryRouterAgent()
