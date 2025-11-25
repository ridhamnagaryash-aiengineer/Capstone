# src/routes/auth.py
from fastapi import APIRouter, HTTPException, status, Depends

from src.core.security import get_current_active_user
from src.models.user import User

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post("/signup")
async def signup_removed():
    """
    Signup is disabled — system does not handle user creation.
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Signup is disabled in this system."
    )


@auth_router.post("/login")
async def login_removed():
    """
    Login is disabled — no authentication flow exists.
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Login is disabled in this system."
    )


@auth_router.get("/me")
async def get_me(current_user: User = Depends(get_current_active_user)):
    """
    Returns a static default user because authentication is removed.
    Frontend uses this to check who is 'logged in'.
    """
    return current_user
