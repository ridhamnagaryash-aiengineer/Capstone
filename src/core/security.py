# src/core/security.py
from src.models.user import User, UserRole

def get_current_active_user() -> User:
    return User(
        id=1,
        email="anonymous@example.com",
        username="anonymous",
        role=UserRole.EMPLOYEE,
        grade="standard"
    )

def get_current_admin() -> User:
    return User(
        id=1,
        email="admin@example.com",
        username="admin",
        role=UserRole.ADMIN,
        grade="admin"
    )

def get_current_employee() -> User:
    return get_current_active_user()
