# main.py - Root level
import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from src.core.database import engine, Base
from src.routes.admin import admin_router
from src.routes.employee import emp_router
from src.handlers.error_handler import error_handler as CustomError
from src.models.document import HRDocument

# TEMP FIX – drop and recreate hr_documents
HRDocument.__table__.drop(engine, checkfirst=True)
Base.metadata.create_all(bind=engine)



app = FastAPI(
    title="HR Assistant API",
    description="AI-powered HR Document Management + Retrieval",
    version="2.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(admin_router)
app.include_router(emp_router)



# ---------------- HEALTH CHECKS ----------------

@app.get("/")
async def root():
    return {"message": "HR Assistant API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "HR Assistant API"}

# ---------------- LAUNCH ----------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 9000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )
