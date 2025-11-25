from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text
from sqlalchemy.sql import func
from src.core.database import Base
from sqlalchemy.orm import relationship


class HRDocument(Base):
    __tablename__ = "hr_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(String, unique=True, index=True, nullable=False)

    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)

    s3_url = Column(String, nullable=False)
    s3_key = Column(String, nullable=False)

    file_size = Column(Integer, nullable=False)
    content_type = Column(String, nullable=False)

    # Removed category + confidence
    vector_count = Column(Integer, default=0)

    uploaded_by_id = Column(Integer, nullable=True)   # no FK


    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    processing_status = Column(String, default="pending")
    error_message = Column(Text, nullable=True)
