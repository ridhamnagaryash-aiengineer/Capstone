# app/models/user.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
import enum
from src.core.database import Base
from sqlalchemy.orm import relationship


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255))
    grade = Column(String(50))
    role = Column(String(50), default="employee")
    hashed_password = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Don't define chat_sessions relationship here
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"