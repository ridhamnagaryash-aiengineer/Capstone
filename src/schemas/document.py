# src/schemas/document.py

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class HRDocumentResponse(BaseModel):
    id: int
    file_id: str
    filename: str
    original_filename: str
    s3_url: str
    s3_key: str
    file_size: int
    content_type: str
    vector_count: int
    uploaded_by_id: int
    uploaded_at: datetime
    processing_status: str
    error_message: Optional[str]

    class Config:
        from_attributes = True


class HRDocumentList(BaseModel):
    total: int
    documents: List[HRDocumentResponse]
