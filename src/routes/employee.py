from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, Body
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import json
import logging
from typing import List

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


# -----------------------
# Helpers
# -----------------------
def generate_session_title(message: str) -> str:
    """Create a short, clean session title from the user's first message."""
    if not message:
        return "New Chat"
    msg = message.strip()
    if len(msg) <= 30:
        return msg
    return msg[:30].rstrip() + "..."


# ============================================
# 1️⃣ Chat With HR Assistant (Main Endpoint)
# ============================================
@emp_router.post("/chat", response_model=ChatResponse)
async def chat_with_hr(
    request: Request,
    chat_request: ChatMessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Intelligent HR Chat Assistant (RAG + LLM)
    - Maintains chat sessions
    - Stores conversation history
    - Performs query classification, embedding, vector search, answer generation
    """
    try:
        # ---------------------------
        # Extract user claims from JWT (unverified payload allowed for personalization)
        # ---------------------------
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip()
        user_info = extract_user_info(token) if token else {}

        # ---------------------------
        # Session handling
        # ---------------------------
        if chat_request.session_id:
            session = db.query(ChatSession).filter(
                ChatSession.session_id == chat_request.session_id,
                ChatSession.user_id == current_user.id
            ).first()

            if not session:
                raise HTTPException(status_code=404, detail="Chat session not found")
        else:
            # Create new session with smarter title
            session = ChatSession(
                session_id=str(uuid.uuid4()),
                user_id=current_user.id,
                title=generate_session_title(chat_request.message)
            )
            db.add(session)
            db.commit()
            db.refresh(session)

        # ---------------------------
        # Load full messages (ordered asc) and derive last N for LLM context
        # ---------------------------
        all_messages: List[ChatMessage] = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.session_id
        ).order_by(ChatMessage.created_at.asc()).all()

        # Use last 6 messages for LLM context (preserve chronological order)
        last_n = 6
        history_slice = all_messages[-last_n:] if len(all_messages) >= last_n else all_messages
        chat_history = [{"role": m.role, "content": m.content} for m in history_slice]

        # ---------------------------
        # Save user message
        # ---------------------------
        user_msg = ChatMessage(
            session_id=session.session_id,
            role="user",
            content=chat_request.message
        )
        db.add(user_msg)
        db.commit()

        # ---------------------------
        # Process via ChatService (provide user_info for personalization)
        # ---------------------------
        response_text, sources, meta = await chat_service.process_chat_query(
            user_query=chat_request.message,
            chat_history=chat_history,
            user_info=user_info
        )

        # ---------------------------
        # Save assistant message
        # ---------------------------
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

        # Update session timestamp and persist
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 2️⃣ Get All Chat Sessions (with previews)
# ============================================
@emp_router.get("/chat/sessions", response_model=List[ChatSessionResponse])
async def get_chat_sessions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Return list of sessions for current user with:
      - message_count
      - last assistant message preview (first 60 chars)
    """
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.updated_at.desc()).all()

    result: List[ChatSessionResponse] = []

    for s in sessions:
        # count messages
        count = db.query(ChatMessage).filter(
            ChatMessage.session_id == s.session_id
        ).count()

        # preview of last assistant message
        last_assistant_msg = db.query(ChatMessage).filter(
            ChatMessage.session_id == s.session_id,
            ChatMessage.role == "assistant"
        ).order_by(ChatMessage.created_at.desc()).first()

        preview = ""
        if last_assistant_msg and last_assistant_msg.content:
            if len(last_assistant_msg.content) > 60:
                preview = last_assistant_msg.content[:60].rstrip() + "..."
            else:
                preview = last_assistant_msg.content

        session_info = ChatSessionResponse(
            id=s.id,
            session_id=s.session_id,
            title=s.title,
            is_active=s.is_active,
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=count,
            last_message_preview=preview
        )
        result.append(session_info)

    return result


# ============================================
# 3️⃣ Get Chat History for a Session
# ============================================
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

    session_info = ChatSessionResponse(
        id=session.id,
        session_id=session.session_id,
        title=session.title,
        is_active=session.is_active,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=len(messages),
        last_message_preview=(messages[-1].content[:60] + "...") if messages and messages[-1].role == "assistant" else ""
    )

    return ChatHistoryResponse(
        session=session_info,
        messages=[ChatMessageResponse.model_validate(m) for m in messages]
    )


# ============================================
# 4️⃣ Delete Chat Session
# ============================================
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


# ============================================
# 4b️⃣ Delete ALL Chat Sessions for current user
# ============================================
@emp_router.delete("/chat/sessions")
async def delete_all_sessions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id
    ).all()

    for s in sessions:
        db.query(ChatMessage).filter(ChatMessage.session_id == s.session_id).delete()
        db.delete(s)

    db.commit()
    return {"message": "All chat sessions deleted"}


# ============================================
# 5️⃣ Rename Session (small UI convenience)
# ============================================
@emp_router.put("/chat/sessions/{session_id}/rename")
async def rename_session(
    session_id: str,
    new_title: str = Body(..., embed=True, min_length=1, max_length=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.title = new_title[:100]
    session.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Session renamed", "session_id": session_id, "new_title": session.title}


# ============================================
# 6️⃣ Analyze Document (FUTURE)
# ============================================
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


# ============================================
# 7️⃣ Summarize PDF (FUTURE)
# ============================================
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
