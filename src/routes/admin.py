# src/routes/admin.py
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session

from ..core.security import get_current_admin
from ..core.database import get_db
from ..services.document_service import document_service
from ..schemas.document import HRDocumentResponse, HRDocumentList

admin_router = APIRouter(prefix="/admin", tags=["Admin"])

@admin_router.post("/documents", response_model=HRDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """Single endpoint for document upload and processing"""
    return await document_service.process_document_upload(
        file=file,
        user=current_user,
        db=db,
        background_tasks=background_tasks
    )

@admin_router.get("/documents", response_model=HRDocumentList)  
async def list_documents(
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get all documents"""
    return await document_service.get_user_documents(
        user_id=current_user.id, 
        db=db
    )

@admin_router.delete("/documents/{file_id}")
async def delete_document(
    file_id: str,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete document"""
    return await document_service.delete_document(
        file_id=file_id,
        user_id=current_user.id,
        db=db
    )