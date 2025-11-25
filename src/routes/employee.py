# src/routes/employee.py
from fastapi import APIRouter, HTTPException, Depends
from typing import List

from src.core.security import get_current_active_user
from src.schemas.chat import ChatMessageCreate, ChatResponse
from src.services.chat_service import chat_service
from src.models.user import User

emp_router = APIRouter(prefix="/employee", tags=["Employee"])


@emp_router.post("/chat", response_model=ChatResponse)
async def chat_with_hr(
    chat_request: ChatMessageCreate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Stateless HR chat endpoint.
    No sessions. No history. No DB.
    """
    try:
        response_text, sources = await chat_service.process_chat_query(
            user_query=chat_request.message
        )

        return ChatResponse(
            session_id="",
            response=response_text,
            sources=sources,
            message_id=None
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
