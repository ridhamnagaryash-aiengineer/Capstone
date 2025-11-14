# src/routes/employee.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import json
import logging

from src.core.database import get_db
from src.core.security import get_current_active_user, get_current_employee
from src.schemas.chat import (
    ChatMessageCreate, ChatResponse, ChatHistoryResponse,
    ChatSessionResponse, ChatMessageResponse
)
from src.services.chat_service import chat_service
from src.models.user import User
from src.models.chat import ChatSession, ChatMessage
from src.utils.finduser import extract_user_info

logger = logging.getLogger(__name__)

emp_router = APIRouter(prefix="/employee", tags=["Employee"])


# =======================================================
# 1️⃣ CHAT WITH HR ASSISTANT  (UPDATED WITH USER INFO)
# =======================================================
@emp_router.post("/chat", response_model=ChatResponse)
async def chat_with_hr(
    request: Request,
    chat_request: ChatMessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    try:
        # --------------------------------------------
        # EXTRACT JWT TOKEN → USER INFO (Name + Grade)
        # --------------------------------------------
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip()
        user_info = extract_user_info(token)

        # --------------------------------------------
        # Chat session logic
        # --------------------------------------------
        if chat_request.session_id:
            session = db.query(ChatSession).filter(
                ChatSession.session_id == chat_request.session_id,
                ChatSession.user_id == current_user.id
            ).first()
            if not session:
                raise HTTPException(status_code=404, detail="Chat session not found")
        else:
            session = ChatSession(
                session_id=str(uuid.uuid4()),
                user_id=current_user.id,
                title=chat_request.message[:50] + ("..." if len(chat_request.message) > 50 else "")
            )
            db.add(session)
            db.commit()
            db.refresh(session)

        # --------------------------------------------
        # Load last 6 messages
        # --------------------------------------------
        history = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.session_id
        ).order_by(ChatMessage.created_at.desc()).limit(6).all()

        chat_history = [{"role": m.role, "content": m.content} for m in reversed(history)]

        # --------------------------------------------
        # Save user message
        # --------------------------------------------
        user_msg = ChatMessage(
            session_id=session.session_id,
            role="user",
            content=chat_request.message
        )
        db.add(user_msg)
        db.commit()

        # --------------------------------------------
        # Process via ChatService (NOW WITH user_info)
        # --------------------------------------------
        response_text, sources, meta = await chat_service.process_chat_query(
            user_query=chat_request.message,
            chat_history=chat_history,
            user_info=user_info
        )

        # --------------------------------------------
        # Save assistant message
        # --------------------------------------------
        assistant_msg = ChatMessage(
            session_id=session.session_id,
            role="assistant",
            content=response_text,
            query_category=meta.get("category"),
            category_confidence=meta.get("confidence"),
            retrieved_chunks=len(sources),
            sources=json.dumps(sources)
        )
        db.add(assistant_msg)
        session.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(assistant_msg)

        return ChatResponse(
            session_id=session.session_id,
            response=response_text,
            sources=sources,
            message_id=assistant_msg.id,
            category=meta.get("category"),
            confidence=meta.get("confidence")
        )

    except Exception as e:
        logger.error(f"Chat failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))



# =======================================================
# 2️⃣ GET CHAT SESSIONS
# =======================================================
@emp_router.get("/chat/sessions", response_model=list[ChatSessionResponse])
async def get_chat_sessions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.updated_at.desc()).all()

    result = []
    for s in sessions:
        session_info = ChatSessionResponse.model_validate(s)
        session_info.message_count = db.query(ChatMessage).filter(
            ChatMessage.session_id == s.session_id
        ).count()
        result.append(session_info)

    return result



# =======================================================
# 3️⃣ GET CHAT HISTORY
# =======================================================
@emp_router.get("/chat/sessions/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).all()

    session_info = ChatSessionResponse.model_validate(session)
    session_info.message_count = len(messages)

    return ChatHistoryResponse(
        session=session_info,
        messages=[ChatMessageResponse.model_validate(m) for m in messages]
    )



# =======================================================
# 4️⃣ DELETE CHAT SESSION
# =======================================================
@emp_router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.delete(session)
    db.commit()

    return {"message": "Chat session deleted", "session_id": session_id}



# =======================================================
# 5️⃣ ANALYZE DOCUMENT (FUTURE)
# =======================================================
@emp_router.post("/analyze-document")
async def analyze_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_employee)
):
    return {
        "message": f"Document '{file.filename}' analyzed",
        "analysis": "To be implemented",
        "user": current_user.email
    }



# =======================================================
# 6️⃣ SUMMARIZE PDF (FUTURE)
# =======================================================
@emp_router.post("/summarize-pdf")
async def summarize_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_employee)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    return {
        "filename": file.filename,
        "summary": "To be implemented",
        "processed_by": current_user.email
    }
