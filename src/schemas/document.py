from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

from src.models.document import DocumentCategory


class HRDocumentResponse(BaseModel):
    id: int
    file_id: str
    filename: str
    original_filename: str
    s3_url: str
    file_size: int
    category: DocumentCategory
    classification_confidence: Optional[float]
    uploaded_by_id: int
    uploaded_at: datetime
    processing_status: str
    vector_count: int

    class Config:
        from_attributes = True
        use_enum_values = True


class HRDocumentList(BaseModel):
    total: int
    documents: List[HRDocumentResponse]
