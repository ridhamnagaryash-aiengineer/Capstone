# src/routes/employee.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_active_user
from ..schemas.chat import ChatMessageCreate, ChatResponse
from ..services.chat_service import chat_service
from ..models.user import User

emp_router = APIRouter(prefix="/employee", tags=["Employee"])


@emp_router.post("/chat", response_model=ChatResponse)
async def chat_with_hr(
    chat_request: ChatMessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    
    """
    Chat with the HR assistant.
    Uses QueryRouterAgent via ChatService for intelligent retrieval
    from Milvus + LLM response generation.
    """
    try:
        # Process chat through ChatService
        response_text, sources, metadata = await chat_service.process_chat_query(
            user_query=chat_request.message
        )
        print(f"Chat response generated: {response_text[:100]}...")

        # Return structured ChatResponse
        return ChatResponse(
            session_id=chat_request.session_id or "temporary-session",
            response=response_text,
            sources=sources,
            category=metadata.get("category"),
            confidence=metadata.get("confidence"),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")
