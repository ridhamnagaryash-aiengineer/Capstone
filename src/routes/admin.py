# src/routes/admin.py
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session

from src.core.security import get_current_admin   # static admin user (id=1)
from src.core.database import get_db
from src.services.document_service import document_service
from src.schemas.document import HRDocumentResponse, HRDocumentList

admin_router = APIRouter(prefix="/admin", tags=["Admin"])


@admin_router.post("/documents", response_model=HRDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
    current_user = Depends(get_current_admin)   
):
    return await document_service.process_document_upload(
        file=file,
        user=current_user,
        db=db,
        background_tasks=background_tasks
    )


@admin_router.get("/documents", response_model=HRDocumentList)
async def list_documents(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin)
):
    docs = await document_service.get_user_documents(
        user_id=current_user.id,  # always returns id=1
        db=db
    )
    return {
        "total": len(docs),
        "documents": docs
    }


@admin_router.delete("/documents/{file_id}")
async def delete_document(
    file_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin)
):
    return await document_service.delete_document(
        file_id=file_id,
        user_id=current_user.id,
        db=db
    )
