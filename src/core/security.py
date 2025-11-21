# src/core/security.py
import bcrypt
import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from itsdangerous import URLSafeTimedSerializer

from .database import get_db
from ..models.user import User

# OAuth2 scheme
auth_scheme = HTTPBearer()

# Token serializer for password reset
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
ALGORITHM = os.getenv('ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '30'))
RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv('RESET_TOKEN_EXPIRE_MINUTES', '15'))

serializer = URLSafeTimedSerializer(SECRET_KEY)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against its hash using bcrypt directly.
    """
    try:
        # Handle both string and bytes input for hashed_password
        if isinstance(hashed_password, str):
            hashed_password = hashed_password.encode('utf-8')
        
        # Handle password length limitation (72 bytes max for bcrypt)
        password_bytes = plain_password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        
        return bcrypt.checkpw(password_bytes, hashed_password)
    except Exception as e:
        print(f"Password verification error: {str(e)}")
        return False

def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt directly.
    Handles the 72-byte limitation automatically.
    """
    try:
        # Handle password length limitation
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        
        # Generate salt and hash
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    except Exception as e:
        raise ValueError(f"Password hashing failed: {str(e)}")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_password_reset_token(email: str) -> str:
    """Create password reset token"""
    return serializer.dumps(email, salt='password-reset')

def verify_password_reset_token(token: str) -> Optional[str]:
    """Verify password reset token and return email"""
    try:
        email = serializer.loads(
            token,
            salt='password-reset',
            max_age=RESET_TOKEN_EXPIRE_MINUTES * 60
        )
        return email
    except Exception:
        return None

def verify_token(token: str) -> Optional[str]:
    """Verify JWT token and return email"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        return email
    except JWTError:
        return None

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current user from JWT token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Extract the actual token string from credentials
    token = credentials.credentials
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user - use this for protected routes"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# def require_role(allowed_roles: list[UserRole]):
#     """
#     Dependency factory to check if user has required role
#     Usage: Depends(require_role([UserRole.ADMIN]))
#     """
#     def role_checker(current_user: User = Depends(get_current_active_user)):
#         if current_user.role not in allowed_roles:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail=f"Access denied. Required roles: {[role.value for role in allowed_roles]}"
#             )
#         return current_user
#     return role_checker

def require_role(allowed_roles: list[str]):
    """
    Dependency factory to check if user has required role
    Usage: Depends(require_role(["admin", "manager"]))
    
    Args:
        allowed_roles: List of role strings (e.g., ["admin", "employee", "manager"])
    """
    def role_checker(current_user: User = Depends(get_current_active_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {allowed_roles}"
            )
        return current_user
    return role_checker


# Convenience dependencies
def get_current_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Require admin role"""
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

def get_current_employee(current_user: User = Depends(get_current_active_user)) -> User:
    """Require employee role"""
    if current_user.role != 'employee':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee access required"
        )
    return current_user