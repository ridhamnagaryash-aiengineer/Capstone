# app/models/chat.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.core.database import Base

class ChatSession(Base):
    """Store chat sessions for employees"""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", backref="chat_sessions")
    
    title = Column(String, default="New Chat")
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<ChatSession {self.session_id}>"

# app/models/chat.py
class ChatMessage(Base):
    """Store individual chat messages"""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("chat_sessions.session_id"), nullable=False)
    session = relationship("ChatSession", backref="messages")
    
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    
    # ✅ NEW: Add query category tracking
    query_category = Column(String, nullable=True)  # Category assigned to query
    category_confidence = Column(Float, nullable=True)  # Classification confidence
    
    # Metadata for RAG
    retrieved_chunks = Column(Integer, default=0)
    sources = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# class ChatMessage(Base):
#     """Store individual chat messages"""
#     __tablename__ = "chat_messages"
    
#     id = Column(Integer, primary_key=True, index=True)
#     session_id = Column(String, ForeignKey("chat_sessions.session_id"), nullable=False)
#     session = relationship("ChatSession", backref="messages")
    
#     role = Column(String, nullable=False)  # 'user' or 'assistant'
#     content = Column(Text, nullable=False)
    
#     # Metadata for RAG
#     retrieved_chunks = Column(Integer, default=0)  # Number of context chunks used
#     sources = Column(Text, nullable=True)  # JSON string of source documents
    
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
    
#     def __repr__(self):
#         return f"<ChatMessage {self.role}: {self.content[:50]}>"