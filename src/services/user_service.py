# src/services/user_service.py
from sqlalchemy.orm import Session
from typing import Optional
from src.models.user import User


class UserService:
    """
    Minimal user utilities.
    No authentication.
    Users only exist for:
    - document ownership
    - admin vs employee roles
    """

    async def get_user_by_email(self, email: str, db: Session) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    async def create_user_admin_managed(
        self,
        email: str,
        username: str,
        full_name: str,
        grade: str,
        role: str,     # "admin" or "employee"
        db: Session
    ) -> User:

        existing = db.query(User).filter(
            (User.email == email) | (User.username == username)
        ).first()

        if existing:
            raise ValueError("User with this email or username already exists")

        user = User(
            email=email,
            username=username,
            full_name=full_name,
            hashed_password="",  # no authentication needed
            grade=grade,
            role=role,
            is_active=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)
        return user


user_service = UserService()
