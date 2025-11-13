# src/routes/employee.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import uuid, json

from ..core.database import get_db
from ..core.security import get_current_active_user
from ..schemas.chat import ChatMessageCreate, ChatResponse
from ..services.chat_service import chat_service
from ..models.user import User
from ..models.chat import ChatSession, ChatMessage  # ✅ Import ORM models

emp_router = APIRouter(prefix="/employee", tags=["Employee"])


@emp_router.post("/chat", response_model=ChatResponse)
async def chat_with_hr(
    chat_request: ChatMessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)):
    """
    Chat with the HR assistant.
    Uses QueryRouterAgent via ChatService for intelligent retrieval
    from Milvus + LLM response generation, while maintaining session history.
    """
    try:
        # ✅ Get or create chat session
        if chat_request.session_id:
            session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.session_id == chat_request.session_id,
                    ChatSession.user_id == current_user.id
                )
                .first()
            )
            if not session:
                raise HTTPException(status_code=404, detail="Chat session not found")
        else:
            # Create a new session
            session = ChatSession(
                session_id=str(uuid.uuid4()),
                user_id=current_user.id,
                title=chat_request.message[:50] + ("..." if len(chat_request.message) > 50 else "")
            )
            db.add(session)
            db.commit()
            db.refresh(session)

        # ✅ Fetch last few messages for context
        history_records = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(6)
            .all()
        )

        chat_history = [
            {"role": msg.role, "content": msg.content} for msg in reversed(history_records)
        ]

        # ✅ Store user message
        user_msg = ChatMessage(
            session_id=session.session_id,
            role="user",
            content=chat_request.message
        )
        db.add(user_msg)
        db.commit()

        # ✅ Process with ChatService (RAG + classification)
        response_text, sources, metadata = await chat_service.process_chat_query(
            user_query=chat_request.message,
            chat_history=chat_history
        )

        # ✅ Store assistant message
        assistant_msg = ChatMessage(
            session_id=session.session_id,
            role="assistant",
            content=response_text,
            query_category=metadata.get("category"),
            category_confidence=metadata.get("confidence"),
            retrieved_chunks=len(sources) if sources else 0,
            sources=json.dumps(sources or [])
        )
        db.add(assistant_msg)

        # ✅ Update session timestamp
        session.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(assistant_msg)

        # ✅ Return API response
        return ChatResponse(
            session_id=session.session_id,
            response=response_text,
            sources=sources or [],
            category=metadata.get("category"),
            confidence=metadata.get("confidence"),
            message_id=assistant_msg.id
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")
