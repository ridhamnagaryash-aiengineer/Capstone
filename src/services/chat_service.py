# src/services/chat_service.py
import logging
from typing import List, Dict

from src.agents.query_router_agent import query_router_agent

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ChatService:
    """Stateless HR chat wrapper. No user data, no history, no sessions."""

    def __init__(self):
        self.router = query_router_agent
        logger.info("ChatService initialized (stateless)")

    async def process_chat_query(self, user_query: str, llm_params: dict):
        """
        Returns only the assistant response + retrieved sources.
        Everything else is removed.
        """
        try:
            result = await self.router.process_query(
                user_query=user_query,
                chat_history=[],   # always empty
                user_info=None,     # no user context
                llm_params=llm_params
            )

            if not result.get("success"):
                raise Exception(result.get("error", "Unknown error"))

            return (
                result.get("response"),
                result.get("sources", [])
            )

        except Exception as e:
            logger.error(f"ChatService error: {e}")
            return (
                "An internal error occurred while processing your request.",
                []
            )


chat_service = ChatService()
