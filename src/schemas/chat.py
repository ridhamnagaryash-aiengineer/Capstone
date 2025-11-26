from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class ChatMessageCreate(BaseModel):
    """Incoming chat message for stateless chat."""
    message: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    response: str
    sources: List[Dict] = []
    message_id: Optional[int] = None
