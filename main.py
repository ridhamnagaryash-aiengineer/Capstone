# main.py - Root level
import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from src.core.database import engine, Base
from src.routes.admin import admin_router
from src.routes.employee import emp_router

from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException as FastAPIHTTPException

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

# ---------------- EXCEPTION HANDLERS ----------------



@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

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
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

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
