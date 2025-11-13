# src/services/user_service.py
from sqlalchemy.orm import Session
from typing import Optional
from ..models.user import User
from ..core.security import get_password_hash, verify_password, create_access_token
from ..schemas.user import UserCreate

class UserService:
    async def create_user(
        self, 
        email: str, 
        username: str, 
        password: str, 
        full_name: str,
        db: Session
    ):
        # Check if user already exists
        existing_user = db.query(User).filter(
            (User.email == email) | (User.username == username)
        ).first()
        
        if existing_user:
            raise ValueError("User with this email or username already exists")
        
        # Create new user
        hashed_password = get_password_hash(password)
        user = User(
            email=email,
            username=username,
            hashed_password=hashed_password,
            full_name=full_name
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return user
    
    async def authenticate_user(self, email: str, password: str, db: Session):
        user = db.query(User).filter(User.email == email).first()
        
        if not user or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid credentials")
        
        if not user.is_active:
            raise ValueError("User account is disabled")
        
        # Create access token
        access_token = create_access_token(data={"sub": user.email})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user
        }

# Create instance
user_service = UserService()