# main.py - Root level
import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from src.core.database import get_db, engine, Base
from src.core.security import get_current_active_user
from src.models.user import User
from src.routes.admin import admin_router
from src.routes.auth import auth_router
from src.routes.employee import emp_router

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="HR Assistant API",
    description="AI-powered HR Document Management and Chat System",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(emp_router)

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
    
    # Get port from environment variable, default to 8000 if not set
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port
    )