
from fastapi import APIRouter, Depends, UploadFile, File,Form, BackgroundTasks
from sqlalchemy.orm import Session
from src.core.security import get_current_admin  
from src.core.database import get_db
from src.services.document_service import document_service
from src.schemas.document import HRDocumentResponse, HRDocumentList
admin_router = APIRouter(prefix="/admin", tags=["Admin"])


@admin_router.post("/documents", response_model=HRDocumentResponse)
async def upload_document(
    s3url: str = Form(..., min_length=1, max_length=2000),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
    current_user = Depends(get_current_admin)   
):

    return await document_service.process_document_upload(
        s3url=s3url,
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
        user_id=current_user.id, 
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
