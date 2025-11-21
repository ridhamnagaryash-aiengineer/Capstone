# main.py - Root level
import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from src.core.database import get_db, engine, Base
from src.core.security import get_current_active_user
from src.models.user import User
from src.routes.admin import admin_router
from src.routes.auth import auth_router
from src.routes.employee import emp_router
from src.routes.livekit import livekit_router

from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException as FastAPIHTTPException
from src.handlers.error_handler import error_handler as CustomError
from contextlib import asynccontextmanager
import src.routes.livekit as livekit_module
from livekit import api

# Create database tables
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app"""
    
    # Startup: Initialize LiveKit API client
    print("Initializing LiveKit API client...")
    livekit_module.livekit_api = api.LiveKitAPI(
        url=os.getenv("LIVEKIT_URL"),
        api_key=os.getenv("LIVEKIT_API_KEY"),
        api_secret=os.getenv("LIVEKIT_API_SECRET")
    )
    print("LiveKit API client initialized successfully")
    
    yield  # App is running
    
    # Shutdown: Close LiveKit API client
    print("Closing LiveKit API client...")
    await livekit_module.livekit_api.aclose()
    print("LiveKit API client closed")

# PASS LIFESPAN HERE - This is the critical fix
app = FastAPI(
    title="HR Assistant API",
    description="AI-powered HR Document Management and Chat System",
    version="1.0.0",
    lifespan=lifespan  # ← ADD THIS LINE
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(emp_router)
app.include_router(livekit_router)

# Centralized exception handlers
@app.exception_handler(CustomError)
async def custom_error_handler(request: Request, exc: CustomError):
    return JSONResponse(
        status_code=getattr(exc, "status_code", 500),
        content={"detail": str(exc)},
        headers=getattr(exc, "headers", {})
    )

@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    def sanitize(obj):
        if isinstance(obj, bytes):
            try:
                return obj.decode("utf-8", errors="replace")
            except:
                return str(obj)
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize(v) for v in obj]
        return obj

    safe_errors = sanitize(exc.errors())
    return JSONResponse(status_code=422, content={"detail": safe_errors})

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

@app.get("/")
async def root():
    return {"message": "HR Assistant API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "HR Assistant API"}

@app.get("/protected-test")
async def protected_test(current_user: User = Depends(get_current_active_user)):
    return {"message": f"Hello {current_user.username}", "user_id": current_user.id}

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    
    # This will now work because lifespan is passed to FastAPI() above
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )