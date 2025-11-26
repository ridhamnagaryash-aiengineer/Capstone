# src/agents/query_router_agent.py

import logging
<<<<<<< HEAD
from typing import List, Dict, Any
=======
import litellm
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
>>>>>>> 79a00ecbeac271db366348878f9e85d7d9afea16

from src.llm.lite_client import lite_client
from src.retriever.hr_retriever import HRRetriever
from src.prompts_engineering.prompts_loader import prompt_loader

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


<<<<<<< HEAD
=======
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
    llm_params: Dict[str, Any]  # <‑‑ add this


# ---------------- AGENT ----------------
>>>>>>> 79a00ecbeac271db366348878f9e85d7d9afea16
class QueryRouterAgent:
    """
    Pure Python version.
    Exact same functionality, but no LangChain and no pipeline framework.
    """

    def __init__(self):
        # self.llm = lite_client
        self.templates = prompt_loader
        self.retriever = HRRetriever()

        logger.info("QueryRouterAgent initialized (pure Python pipeline)")

    # ------------------------------------------------------------
    # STEP 1 — CREATE EMBEDDING
    # ------------------------------------------------------------
    def _embedding(self, state: Dict) -> None:
        try:
            emb = self.llm.create_embedding(state["user_query"])
            state["query_embedding"] = list(emb)
        except Exception as e:
            logger.exception("Embedding error")
            state["query_embedding"] = []
            state["error"] = f"embedding_error: {e}"

    # ------------------------------------------------------------
    # STEP 2 — MILVUS SEARCH
    # ------------------------------------------------------------
    async def _search(self, state: Dict) -> None:
        try:
            chunks = await self.retriever.retrieve(
                query=state["user_query"],
                query_embedding=state.get("query_embedding"),
                top_k=5,
            )
            state["retrieved_chunks"] = chunks
        except Exception as e:
            logger.exception("Milvus search error")
            state["retrieved_chunks"] = []
            state["error"] = str(e)

<<<<<<< HEAD
    # ------------------------------------------------------------
    # STEP 3 — RESPONSE GENERATION
    # ------------------------------------------------------------
    def _generate(self, state: Dict) -> None:
        docs = state.get("retrieved_chunks", [])

        # No RAG hits → fallback HR guidance
        if not docs:
            fallback = (
                f"The user asked: '{state['user_query']}'.\n"
                "No documents matched; provide best HR guidance."
            )
            generated = self.llm.chat_completion(
                [{"role": "user", "content": fallback}]
            )
            state["llm_response"] = generated
            state["sources"] = []
=======
    # ---------------- 3. RESPONSE GENERATION ----------------
    def generate_response(self, state: QueryState) -> QueryState:
        state["current_node"] = "generate_response"
        try:
            docs = state.get("retrieved_chunks") or []
            llm_params = state.get("llm_params") or {}

            # Fallback: no RAG hits
            if not docs:
                fallback = (
                    f"The user asked: '{state['user_query']}'.\n"
                    "No documents matched; provide best HR guidance.\n"
                )
                messages = [{"role": "user", "content": fallback}]
                response = litellm.completion(
                    **llm_params,
                    messages=messages,
                )
                response_text = response.choices[0].message.content
                state["llm_response"] = response_text
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
                user_context="",  # keep template compatibility but empty
            )
            messages = [{"role": "user", "content": prompt}]
            response = litellm.completion(
                **llm_params,
                messages=messages,
            )
            response_text = response.choices[0].message.content
            state["llm_response"] = response_text
            state["sources"] = docs
>>>>>>> 79a00ecbeac271db366348878f9e85d7d9afea16
            state["success"] = True
            return

        # Build context
        context = "\n\n".join(
            [f"[{d.get('filename')}] → {d.get('content')}" for d in docs]
        )

<<<<<<< HEAD
        template = self.templates.get("chat_response")
        prompt = template.format(
            context=context,
            question=state["user_query"],
            user_context=""
        )

        generated = self.llm.chat_completion(
            [{"role": "user", "content": prompt}]
        )

        state["llm_response"] = generated
        state["sources"] = docs
        state["success"] = True

    # ------------------------------------------------------------
    # MAIN ENTRY POINT
    # ------------------------------------------------------------
=======
    # ---------------- PUBLIC ENTRY ----------------
>>>>>>> 79a00ecbeac271db366348878f9e85d7d9afea16
    async def process_query(
        self,
        user_query: str,
        chat_history: List[Dict],
<<<<<<< HEAD
        user_info=None
    ) -> Dict[str, Any]:

        state = {
=======
        user_info=None,
        llm_params: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        initial: QueryState = {
>>>>>>> 79a00ecbeac271db366348878f9e85d7d9afea16
            "user_query": user_query,
            "chat_history": chat_history or [],
            "query_embedding": [],
            "retrieved_chunks": [],
            "llm_response": "",
            "sources": [],
            "error": "",
            "success": False,
<<<<<<< HEAD
            "user_info": {},
        }

        # identical flow, but directly calling functions
        self._embedding(state)
        await self._search(state)
        self._generate(state)

=======
            "user_info": {},   # not used
            "llm_params": llm_params or {},  # <‑‑ store here
        }
        final = await self.workflow.ainvoke(initial)
>>>>>>> 79a00ecbeac271db366348878f9e85d7d9afea16
        return {
            "response": state.get("llm_response"),
            "sources": state.get("sources"),
            "success": state.get("success"),
            "error": state.get("error"),
        }


# Singleton
query_router_agent = QueryRouterAgent()
