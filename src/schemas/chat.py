from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict


class ChatMessageCreate(BaseModel):
    """Schema for creating a new chat message"""
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None


class ChatMessageResponse(BaseModel):
    """Represents a stored chat message"""
    id: int
    role: str
    content: str
    message_type: str = "text"  # NEW
    retrieved_chunks: int = 0
    sources: Optional[str] = None
    query_category: Optional[str] = None
    category_confidence: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    """Represents a chat session summary"""
    id: Optional[int]
    session_id: str
    title: str
    session_type: str = "text"  # NEW: 'text' or 'voice'
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    ended_at: Optional[datetime] = None  # NEW
    call_duration: Optional[int] = None  # NEW: Duration in seconds
    message_count: int = 0
    last_message_preview: str = ""

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    """Response model for chat queries"""
    session_id: str
    response: str
    sources: List[Dict] = Field(default_factory=list)
    message_id: Optional[int] = None
    category: Optional[str] = "uncategorized"
    confidence: Optional[float] = 0.0


class ChatHistoryResponse(BaseModel):
    """Full history for a chat session"""
    session: ChatSessionResponse
    messages: List[ChatMessageResponse]


# from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, ForeignKey
# from sqlalchemy.orm import relationship
# from sqlalchemy.sql import func
# from src.core.database import Base


# class ChatSession(Base):
#     """Chat session model - supports both text and voice"""
#     __tablename__ = "chat_sessions"
    
#     id = Column(Integer, primary_key=True, index=True)
#     session_id = Column(String(255), unique=True, index=True, nullable=False)
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
#     # Session metadata
#     title = Column(String(500), default="New Chat")
#     session_type = Column(String(50), default="text")  # 'text' or 'voice'
#     is_active = Column(Boolean, default=True)
    
#     # Voice-specific fields (NEW)
#     livekit_room_name = Column(String(255), nullable=True)
#     call_duration = Column(Integer, nullable=True)  # Duration in seconds
    
#     # Timestamps
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
#     ended_at = Column(DateTime(timezone=True), nullable=True)
    
#     # Relationships
#     user = relationship("User", back_populates="chat_sessions")
#     messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

#     def __repr__(self):
#         return f"<ChatSession(id={self.id}, session_id={self.session_id}, type={self.session_type})>"


# class ChatMessage(Base):
#     """Chat message model - supports both text and voice"""
#     __tablename__ = "chat_messages"
    
#     id = Column(Integer, primary_key=True, index=True)
#     session_id = Column(String(255), ForeignKey("chat_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    
#     role = Column(String(50), nullable=False)  # 'user' or 'assistant'
#     content = Column(Text, nullable=False)
    
#     # Metadata
#     message_type = Column(String(50), default="text")  # 'text' or 'voice_transcription' (NEW)
#     query_category = Column(String(100), nullable=True)  # Your existing field
#     category_confidence = Column(Float, nullable=True)  # Your existing field
#     retrieved_chunks = Column(Integer, default=0)
#     sources = Column(Text, nullable=True)  # JSON string
    
#     # Timestamps
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
    
#     # Relationships
#     session = relationship("ChatSession", back_populates="messages")

#     def __repr__(self):
#         return f"<ChatMessage(id={self.id}, role={self.role}, type={self.message_type})>"




# from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, ForeignKey
# from sqlalchemy.orm import relationship
# from sqlalchemy.sql import func
# from src.core.database import Base

# class ChatSession(Base):
#     """Chat session model - supports both text and voice"""
#     __tablename__ = "chat_sessions"
    
#     id = Column(Integer, primary_key=True, index=True)
#     session_id = Column(String(255), unique=True, index=True, nullable=False)
#     user_id = Column(Integer, nullable=False, index=True)  # From JWT
#     username = Column(String(255), nullable=False)
    
#     # Session metadata
#     title = Column(String(500), default="New Chat")
#     session_type = Column(String(50), default="text")  # 'text' or 'voice'
#     is_active = Column(Boolean, default=True)
    
#     # Voice-specific fields
#     livekit_room_name = Column(String(255), nullable=True)
#     call_duration = Column(Integer, nullable=True)  # Duration in seconds
    
#     # Timestamps
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), onupdate=func.now())
#     ended_at = Column(DateTime(timezone=True), nullable=True)
    
#     # Relationships
#     messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


# class ChatMessage(Base):
#     """Chat message model - supports both text and voice"""
#     __tablename__ = "chat_messages"
    
#     id = Column(Integer, primary_key=True, index=True)
#     session_id = Column(String(255), ForeignKey("chat_sessions.session_id"), nullable=False, index=True)
    
#     role = Column(String(50), nullable=False)  # 'user' or 'assistant'
#     content = Column(Text, nullable=False)
    
#     # Metadata
#     message_type = Column(String(50), default="text")  # 'text' or 'voice_transcription'
#     retrieved_chunks = Column(Integer, default=0)
#     sources = Column(Text, nullable=True)  # JSON string
#     category = Column(String(100), nullable=True)
#     confidence = Column(Float, nullable=True)
    
#     # Timestamps
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
    
#     # Relationships
#     session = relationship("ChatSession", back_populates="messages")

# from pydantic import BaseModel, Field
# from typing import Optional, List, Dict
# from datetime import datetime

# class ChatMessageCreate(BaseModel):
#     """Schema for creating a new chat message"""
#     message: str = Field(..., min_length=1, max_length=2000)
#     session_id: Optional[str] = None  # If None, creates a new chat session

# class ChatMessageResponse(BaseModel):
#     """Represents a stored chat message"""
#     id: int
#     role: str
#     content: str
#     retrieved_chunks: int
#     sources: Optional[str]
#     created_at: datetime

#     class Config:
#         from_attributes = True

# class ChatSessionResponse(BaseModel):
#     """Represents a chat session summary (improved for UI)"""
#     id: Optional[int]
#     session_id: str
#     title: str
#     is_active: bool
#     created_at: datetime
#     updated_at: Optional[datetime]
#     message_count: int = 0
#     last_message_preview: str = ""

#     class Config:
#         from_attributes = True

# class ChatResponse(BaseModel):
#     """Response model for chat queries"""
#     session_id: str
#     response: str
#     sources: List[Dict] = Field(default_factory=list)
#     message_id: Optional[int] = None
#     category: Optional[str] = "uncategorized"
#     confidence: Optional[float] = 0.0

# class ChatHistoryResponse(BaseModel):
#     """Full history for a chat session"""
#     session: ChatSessionResponse
#     messages: List[ChatMessageResponse]
