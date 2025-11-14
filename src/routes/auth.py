# src/routes/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import (
    get_current_active_user,
    create_access_token,
    verify_password,
    get_password_hash
)
from ..schemas.user import UserCreate, UserResponse, Token, UserLogin
from ..models.user import User

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post("/signup", response_model=UserResponse)
async def signup(user: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    existing_user = db.query(User).filter(
        (User.email == user.email) | (User.username == user.username)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists"
        )

    # Create new user - employee by default
    hashed_password = get_password_hash(user.password)

    db_user = User(
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        hashed_password=hashed_password,
        grade=user.grade,
        # role is automatically employee (default from model)
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@auth_router.post("/login", response_model=Token)
async def login(login: UserLogin, db: Session = Depends(get_db)):

    # Accept JSON body with `email` and `password`
    user = db.query(User).filter(User.email == login.email).first()

    if not user or not verify_password(login.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    # IMPORTANT FIX:
    # JWT MUST contain "sub" for authentication to work
    token_payload = {
        "sub": user.email,               # REQUIRED for get_current_user()
        "email": user.email,
        "role": user.role.value,         # store role string: "admin" / "employee"
        "grade": user.grade,
        "username": user.username,
        "full_name": user.full_name
    }

    access_token = create_access_token(data=token_payload)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 3600,
        "role": user.role.value,
        "grade": user.grade,
        "username": user.username,
        "full_name": user.full_name
    }


@auth_router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user

