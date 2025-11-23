from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text, Enum as SQLEnum
from sqlalchemy.sql import func
from src.core.database import Base
from sqlalchemy.orm import relationship
import enum


class DocumentCategory(str, enum.Enum):
    PAYROLL = "payroll"
    HR_POLICY = "hr_policy"
    IT_SUPPORT = "it_support"
    FACILITIES = "facilities"
    UNCATEGORIZED = "uncategorized"


class HRDocument(Base):
    __tablename__ = "hr_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(String, unique=True, index=True, nullable=False)

    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)

    s3_url = Column(String, nullable=False)
    s3_key = Column(String, nullable=False)   # REQUIRED FOR S3 DELETION

    file_size = Column(Integer, nullable=False)
    content_type = Column(String, nullable=False)

    # Classification
    category = Column(SQLEnum(DocumentCategory), default=DocumentCategory.UNCATEGORIZED)
    classification_confidence = Column(Float, nullable=True)

    # No pinecone namespace—this project uses Milvus only
    vector_count = Column(Integer, default=0)

    # Audit
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    uploaded_by = relationship("User", backref="uploaded_documents")

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Processing
    processing_status = Column(String, default="pending")
    error_message = Column(Text, nullable=True)
