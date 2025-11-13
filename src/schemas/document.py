# app/schemas/document.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
# app/schemas/document.py
from src.models.document import DocumentCategory

class HRDocumentResponse(BaseModel):
    id: int
    file_id: str
    filename: str
    original_filename: str
    s3_url: str
    file_size: int
    category: DocumentCategory  # ✅ NEW
    classification_confidence: Optional[float]  # ✅ NEW
    uploaded_by_id: int
    uploaded_at: datetime
    processing_status: str
    vector_count: int
    
    class Config:
        from_attributes = True

# class HRDocumentResponse(BaseModel):
#     id: int
#     file_id: str
#     filename: str
#     original_filename: str
#     s3_url: str
#     file_size: int
#     uploaded_by_id: int
#     uploaded_at: datetime
#     processing_status: str
#     vector_count: int
    
#     class Config:
#         from_attributes = True

class HRDocumentList(BaseModel):
    total: int
    documents: list[HRDocumentResponse]