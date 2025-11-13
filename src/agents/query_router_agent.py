import logging
from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, END
from ..llm.lite_client import lite_client
from ..vector_db.milvus_client import milvus_client

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
    """LangGraph-based router using Gemini + Milvus for HR query classification and retrieval."""

    def __init__(self):
        self.llm = lite_client
        self.milvus = milvus_client
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        workflow = StateGraph(QueryState)
        workflow.add_node("classify_query", self.classify_query)
        workflow.add_node("generate_embedding", self.generate_embedding)
        workflow.add_node("search_milvus", self.search_milvus)
        workflow.add_node("generate_response", self.generate_response)
        workflow.set_entry_point("classify_query")
        workflow.add_edge("classify_query", "generate_embedding")
        workflow.add_edge("generate_embedding", "search_milvus")
        workflow.add_edge("search_milvus", "generate_response")
        workflow.add_edge("generate_response", END)
        return workflow.compile()

    # ----------------- Node 1 -----------------
    def classify_query(self, state: QueryState) -> QueryState:
        try:
            logger.info(f"🏷️ [Node1] Classifying query: {state['user_query'][:80]}...")
            categories = ["payroll", "hr_policy", "it_support", "facilities", "uncategorized"]
            prompt = f"""
Classify the following employee query into one of these categories:
{', '.join(categories)}

Query: {state['user_query']}

Respond in format:
Category: <category>
Confidence: <0.0-1.0>
"""
            response = self.llm.chat_completion([{"role": "user", "content": prompt}])
            category, confidence = "uncategorized", 0.0
            for line in response.split("\n"):
                if "Category:" in line:
                    category = line.split(":")[1].strip().lower()
                if "Confidence:" in line:
                    try:
                        confidence = float(line.split(":")[1].strip())
                    except:
                        confidence = 0.5
            state["query_category"], state["confidence"] = category, confidence
            logger.info(f"✅ Classified as '{category}' ({confidence:.2f})")
            return state
        except Exception as e:
            state["error"] = str(e)
            state["query_category"] = "uncategorized"
            logger.error(f"❌ Classification failed: {e}")
            return state

    # ----------------- Node 2 -----------------
    def generate_embedding(self, state: QueryState) -> QueryState:
        try:
            logger.info("🔢 [Node2] Generating embedding via Gemini...")
            state["query_embedding"] = self.llm.create_embedding(state["user_query"])
            return state
        except Exception as e:
            state["error"] = f"Embedding failed: {e}"
            logger.error(f"❌ Embedding generation failed: {e}")
            return state

    # ----------------- Node 3 -----------------
    async def search_milvus(self, state: QueryState) -> QueryState:
        """Node 3: Search Milvus for similar HR documents"""
        try:
            logger.info("🔍 [Node3] Searching Milvus...")
            results = await self.milvus.search_similar(
                query=state["user_query"],
                category=state["query_category"],
                limit=5
            )
            state["retrieved_chunks"] = results
            logger.info(f"✅ Retrieved {len(results)} results from Milvus")
            return state
        except Exception as e:
            state["error"] = str(e)
            state["retrieved_chunks"] = []
            logger.error(f"❌ Search failed: {e}")
            return state

    # ----------------- Node 4 -----------------
    def generate_response(self, state: QueryState) -> QueryState:
        try:
            logger.info("💬 [Node4] Generating HR answer via Gemini...")
            docs = state.get("retrieved_chunks", [])
            if not docs:
                state["llm_response"] = (
                    f"No {state['query_category']} documents found. Please contact HR."
                )
                state["sources"], state["success"] = [], True
                return state

            context = "\n\n".join([f"[{d['filename']}] {d['content']}" for d in docs])
            messages = [
                {"role": "system", "content": f"You are an HR assistant answering {state['query_category']} queries."},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion:\n{state['user_query']}\n\nAnswer clearly."}
            ]
            answer = self.llm.chat_completion(messages)
            sources = [
                {"file_id": d["file_id"], "filename": d["filename"], "score": d["score"], "category": d["category"]}
                for d in docs
            ]
            state["llm_response"], state["sources"], state["success"] = answer, sources, True
            logger.info("✅ Response generated successfully.")
            return state
        except Exception as e:
            state["error"] = str(e)
            state["success"] = False
            state["llm_response"] = "I encountered an error generating the answer."
            logger.error(f"❌ Response generation failed: {e}")
            return state

    # ----------------- EXECUTION -----------------
    async def process_query(self, user_query: str, chat_history: List[Dict] = None) -> Dict:
        """Run the LangGraph workflow asynchronously."""
        initial_state: QueryState = {
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
        logger.info("🚀 Running LangGraph workflow for query.")
        final_state = await self.workflow.ainvoke(initial_state)
        return {
            "response": final_state["llm_response"],
            "sources": final_state["sources"],
            "category": final_state["query_category"],
            "confidence": final_state["confidence"],
            "success": final_state["success"],
            "error": final_state.get("error", "")
        }


query_router_agent = QueryRouterAgent()
