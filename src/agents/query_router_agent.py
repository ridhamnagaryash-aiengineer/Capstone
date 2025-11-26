# src/agents/query_router_agent.py

import logging
from typing import List, Dict, Any

from src.llm.lite_client import lite_client
from src.retriever.hr_retriever import HRRetriever
from src.prompts_engineering.prompts_loader import prompt_loader

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class QueryRouterAgent:
    """
    Pure Python version.
    Exact same functionality, but no LangChain and no pipeline framework.
    """

    def __init__(self):
        self.llm = lite_client
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
            state["success"] = True
            return

        # Build context
        context = "\n\n".join(
            [f"[{d.get('filename')}] → {d.get('content')}" for d in docs]
        )

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
    async def process_query(
        self,
        user_query: str,
        chat_history: List[Dict],
        user_info=None
    ) -> Dict[str, Any]:

        state = {
            "user_query": user_query,
            "chat_history": chat_history or [],
            "query_embedding": [],
            "retrieved_chunks": [],
            "llm_response": "",
            "sources": [],
            "error": "",
            "success": False,
            "user_info": {},
        }

        # identical flow, but directly calling functions
        self._embedding(state)
        await self._search(state)
        self._generate(state)

        return {
            "response": state.get("llm_response"),
            "sources": state.get("sources"),
            "success": state.get("success"),
            "error": state.get("error"),
        }


# Singleton
query_router_agent = QueryRouterAgent()
