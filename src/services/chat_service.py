import logging
from typing import List, Dict, Tuple
from ..agents.query_router_agent import query_router_agent
from src.utils.finduser import extract_user_info

logger = logging.getLogger(__name__)


class ChatService:
    """Chat interface orchestrating QueryRouterAgent."""

    def __init__(self):
        self.router_agent = query_router_agent
        logger.info("✅ ChatService initialized with QueryRouterAgent (Gemini + Milvus)")

    async def process_chat_query(
        self,
        user_query: str,
        chat_history: List[Dict] = None,
        user_info=None
    ):
        """Process HR assistant chat query."""
        try:
            result = await self.router_agent.process_query(
                user_query=user_query,
                chat_history=chat_history,
                user_info=user_info
            )

            if not result.get("success"):
                raise Exception(result.get("error", "Unknown error"))

            # Correct unpacking
            return (
                result.get("response"),
                result.get("sources", []),
                {
                    "category": result.get("category"),
                    "confidence": result.get("confidence")
                }
            )

        except Exception as e:
            logger.error(f"❌ ChatService error: {e}")
            return (
                "An internal error occurred while processing your request.",
                [],
                {"category": "uncategorized", "confidence": 0.0}
            )


chat_service = ChatService()
