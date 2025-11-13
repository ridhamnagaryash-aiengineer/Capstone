from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


class ChatMessageCreate(BaseModel):
    """Schema for creating a new chat message"""
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None  # If None, creates a new chat session


class ChatMessageResponse(BaseModel):
    """Represents a stored chat message"""
    id: int
    role: str
    content: str
    retrieved_chunks: int
    sources: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    """Represents a chat session summary"""
    id: int
    session_id: str
    title: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    message_count: Optional[int] = 0

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
