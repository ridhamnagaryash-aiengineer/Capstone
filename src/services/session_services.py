from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from src.models.chat import ChatSession, ChatMessage
from typing import Optional, List
import uuid
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class SessionService:
    """Service for managing chat and voice sessions"""
    
    @staticmethod
    def create_session(
        db: Session,
        user_id: int,
        username: str,
        session_type: str = "text",
        title: Optional[str] = None,
        livekit_room_name: Optional[str] = None
    ) -> ChatSession:
        """Create a new chat/voice session"""
        session_id = str(uuid.uuid4())
        
        if not title:
            title = f"{'Voice Call' if session_type == 'voice' else 'Chat'} - {datetime.now().strftime('%b %d, %I:%M %p')}"
        
        new_session = ChatSession(
            session_id=session_id,
            user_id=user_id,
            title=title,
            session_type=session_type,
            livekit_room_name=livekit_room_name,
            is_active=True,
        )
        
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        logger.info(f"Created {session_type} session {session_id} for user {user_id}")
        return new_session
    
    @staticmethod
    def get_session(db: Session, session_id: str) -> Optional[ChatSession]:
        """Get session by ID"""
        return db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    
    @staticmethod
    def end_session(
        db: Session,
        session_id: str,
        call_duration: Optional[int] = None
    ) -> Optional[ChatSession]:
        """End a session and mark as inactive"""
        session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        
        if session:
            session.is_active = False
            session.ended_at = datetime.utcnow()
            if call_duration:
                session.call_duration = call_duration
            
            db.commit()
            db.refresh(session)
            logger.info(f"Ended session {session_id}, duration: {call_duration}s")
        
        return session
    
    @staticmethod
    def add_message(
        db: Session,
        session_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        retrieved_chunks: int = 0,
        sources: Optional[List] = None,
        category: Optional[str] = None,
        confidence: Optional[float] = None
    ) -> ChatMessage:
        """Add a message to a session"""
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            message_type=message_type,
            retrieved_chunks=retrieved_chunks,
            sources=json.dumps(sources) if sources else None,
            query_category=category,
            category_confidence=confidence,
        )
        
        db.add(message)
        
        # Update session title from first user message if needed
        session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if session and session.title.startswith(('Voice Call', 'Chat -')):
            user_messages_count = db.query(func.count(ChatMessage.id)).filter(
                ChatMessage.session_id == session_id,
                ChatMessage.role == "user"
            ).scalar()
            
            if user_messages_count == 1 and role == "user":
                session.title = content[:50] + ("..." if len(content) > 50 else "")
                session.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(message)
        
        return message


# Create singleton instance
session_service = SessionService()
