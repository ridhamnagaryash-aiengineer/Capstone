# src/agents/query_router_agent.py

import logging
from typing import List, Dict, Any, Optional
from langchain_core.runnables import RunnableLambda, RunnablePassthrough, RunnableMap



from src.llm.lite_client import lite_client
from src.retriever.hr_retriever import HRRetriever
from src.prompts_engineering.prompts_loader import prompt_loader

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class QueryRouterAgent:

    def __init__(self):
        self.llm = lite_client
        self.templates = prompt_loader
        self.retriever = HRRetriever()

        # Build runnable pipeline
        self.workflow = self._build()

        logger.info("QueryRouterAgent initialized using LangChain Runnable pipeline")

    # ----------- EMBEDDING -----------
    def _embedding(self, state: Dict) -> Dict:
        try:
            emb = self.llm.create_embedding(state["user_query"])
            state["query_embedding"] = list(emb)
        except Exception as e:
            logger.exception("Embedding error")
            state["query_embedding"] = []
            state["error"] = f"embedding_error: {e}"
        return state

    # ----------- RETRIEVAL -----------
    async def _search(self, state: Dict) -> Dict:
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
        return state

    # ----------- RESPONSE GEN -----------
    def _generate(self, state: Dict) -> Dict:
        docs = state.get("retrieved_chunks", [])

        if not docs:
            fallback = (
                f"The user asked: '{state['user_query']}'.\n"
                "No documents matched; provide best HR guidance."
            )
            out = self.llm.chat_completion([{"role": "user", "content": fallback}])
            state["llm_response"] = out
            state["sources"] = []
            state["success"] = True
            return state

        context = "\n\n".join(
            [f"[{d.get('filename')}] → {d.get('content')}" for d in docs]
        )

        template = self.templates.get("chat_response")
        prompt = template.format(
            context=context,
            question=state["user_query"],
            user_context=""
        )

        out = self.llm.chat_completion([{"role": "user", "content": prompt}])

        state["llm_response"] = out
        state["sources"] = docs
        state["success"] = True
        return state

    # ----------- BUILD RUNNABLE PIPELINE -----------
    def _build(self):
        return (
            RunnablePassthrough()  # input state
            | RunnableLambda(self._embedding)
            | RunnableLambda(lambda s: self._search(s))  # ASYNC handled in process_query
            | RunnableLambda(self._generate)
        )

    # ----------- PUBLIC API -----------
    async def process_query(self, user_query: str, chat_history: List[Dict], user_info=None):
        initial = {
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

        # Run the pipeline
        state = initial
        state = self._embedding(state)
        state = await self._search(state)
        state = self._generate(state)

        return {
            "response": state.get("llm_response"),
            "sources": state.get("sources"),
            "success": state.get("success"),
            "error": state.get("error"),
        }
query_router_agent = QueryRouterAgent()