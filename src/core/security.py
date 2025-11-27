
from src.models.user import User, UserRole


def get_current_admin() -> User:
    return User(
        id=1,
        email="admin@example.com",
        username="admin",
        role=UserRole.ADMIN,
        grade="admin"
    )
