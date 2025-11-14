# src/services/document_service.py

import uuid
import logging
import os
from typing import Tuple, List, Optional
from pathlib import Path

from fastapi import UploadFile, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

import fitz  # PyMuPDF
import docx

from ..llm.lite_client import lite_client
from ..vector_db.milvus_client import milvus_client
from ..agents.document_classifier_agent import document_classifier_agent
from ..models.document import HRDocument, DocumentCategory

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class DocumentService:
    """Handles document upload, processing, embedding, and storage."""

    def __init__(self):
        self.milvus = milvus_client
        self.llm = lite_client
        self.classifier_agent = document_classifier_agent
        logger.info("✅ DocumentService initialized")

    # ----------------------------------------------------------------------
    async def process_document_upload(
        self,
        file: UploadFile,
        user: any,
        db: Session,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> HRDocument:

        await self._validate_file(file)
        file_id = str(uuid.uuid4())

        # Save file locally
        local_path, file_size = await self._save_locally(file, file_id)

        # Create DB record
        document = await self._create_document_record(
            db=db,
            file=file,
            user=user,
            file_id=file_id,
            local_path=local_path,
            file_size=file_size
        )

        # Process in background
        if background_tasks:
            background_tasks.add_task(
                self._process_document_background,
                file_id,
                file,
                document.id,
                db
            )
        else:
            await self._process_document_background(file_id, file, document.id, db)

        return document

    # ----------------------------------------------------------------------
    async def _validate_file(self, file: UploadFile):
        """Validate uploaded file type."""
        allowed = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
        ]
        if file.content_type not in allowed:
            raise HTTPException(400, "Unsupported file. Use PDF, DOC, DOCX, TXT.")

    # ----------------------------------------------------------------------
    async def extract_content(self, file: UploadFile) -> str:
        """Extract text from PDF, DOCX, or TXT."""
        try:
            if file.content_type == "application/pdf":
                pdf_bytes = await file.read()
                tmp = UPLOAD_DIR / f"tmp_{uuid.uuid4().hex}.pdf"
                tmp.write_bytes(pdf_bytes)

                doc = fitz.open(str(tmp))
                text = "\n".join([p.get_text("text") for p in doc])
                doc.close()
                tmp.unlink(missing_ok=True)

                await file.seek(0)
                return text.strip()

            if file.content_type in (
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ):
                await file.seek(0)
                d = docx.Document(file.file)
                await file.seek(0)
                return "\n".join([p.text for p in d.paragraphs]).strip()

            if file.content_type == "text/plain":
                await file.seek(0)
                return (await file.read()).decode("utf-8", "ignore").strip()

            return ""

        except Exception as e:
            logger.exception("❌ Content extraction failed")
            raise HTTPException(400, f"Content extraction failed: {e}")

    # ----------------------------------------------------------------------
    async def _save_locally(self, file: UploadFile, file_id: str) -> Tuple[str, int]:
        """Save file to uploads/."""
        try:
            file_bytes = await file.read()
            size = len(file_bytes)

            if size > 50 * 1024 * 1024:
                raise HTTPException(400, "File exceeds 50MB limit")

            ext = (file.filename or "").split(".")[-1]
            fname = f"{file_id}.{ext}"
            path = UPLOAD_DIR / fname
            path.write_bytes(file_bytes)

            await file.seek(0)
            return str(path), size

        except Exception as e:
            logger.exception("❌ Local save failed")
            raise HTTPException(500, f"Local save failed: {e}")

    # ----------------------------------------------------------------------
    async def _create_document_record(
        self, db: Session, file: UploadFile, user, file_id, local_path, file_size
    ) -> HRDocument:

        try:
            doc = HRDocument(
                file_id=file_id,
                filename=os.path.basename(local_path),
                original_filename=file.filename,
                s3_url=local_path,
                s3_key=None,
                file_size=file_size,
                content_type=file.content_type,
                uploaded_by_id=user.id,
                processing_status="pending",
                category=DocumentCategory.UNCATEGORIZED
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            return doc

        except Exception as e:
            db.rollback()
            logger.exception("❌ DB record creation failed")
            raise

    # ----------------------------------------------------------------------
    async def _process_document_background(
        self, file_id: str, file: UploadFile, document_id: int, db: Session
    ):
        """Extract, classify, embed, and insert into correct Milvus collection."""
        try:
            doc = db.query(HRDocument).filter(HRDocument.id == document_id).first()
            if not doc:
                raise Exception("Document DB record not found")

            doc.processing_status = "processing"
            db.commit()

            # Extract content
            content = await self.extract_content(file)
            if not content:
                raise Exception("No extractable text")

            # Classification + chunking + embeddings
            result = self.classifier_agent.process_document(
                file_id=file_id,
                filename=file.filename,
                file_content=content,
                file_type=file.filename.split(".")[-1]
            )

            if not result.get("success"):
                raise Exception(result.get("error", "Classifier failed"))

            category = result["category"]
            confidence = float(result["confidence"])
            chunks = result["chunks"]
            embeddings = result["embeddings"]

            if not embeddings:
                raise Exception("No embeddings generated")

            # SINGLE CALL INSERT — ALL EMBEDDINGS AT ONCE
            total_vectors = await self.milvus.store_document_embeddings(
                file_id=file_id,
                filename=file.filename,
                content=content,
                embeddings=embeddings,
                category=category
            )

            # Update DB record
            doc.category = DocumentCategory(category)
            doc.classification_confidence = confidence
            doc.vector_count = total_vectors
            doc.processing_status = "completed"
            db.commit()

            logger.info(
                f"✅ Document processed: {file.filename} → {category} ({total_vectors} vectors)"
            )

        except Exception as e:
            logger.exception("❌ Background processing failed")

            try:
                doc = db.query(HRDocument).filter(HRDocument.id == document_id).first()
                if doc:
                    doc.processing_status = "failed"
                    doc.error_message = str(e)
                    db.commit()
            except:
                db.rollback()

    # ----------------------------------------------------------------------
    async def get_user_documents(self, user_id: int, db: Session):
        return (
            db.query(HRDocument)
            .filter(HRDocument.uploaded_by_id == user_id)
            .order_by(HRDocument.uploaded_at.desc())
            .all()
        )

    # ----------------------------------------------------------------------
    async def delete_document(self, file_id: str, user_id: int, db: Session):
        try:
            doc = (
                db.query(HRDocument)
                .filter(HRDocument.file_id == file_id, HRDocument.uploaded_by_id == user_id)
                .first()
            )
            if not doc:
                raise HTTPException(404, "Document not found")

            # delete local file
            p = Path(doc.s3_url)
            if p.exists():
                p.unlink()

            # delete from milvus
            deleted = await self.milvus.delete_by_file_id(file_id)

            db.delete(doc)
            db.commit()

            return {
                "message": f"Deleted '{doc.original_filename}'",
                "file_id": file_id,
                "vectors_deleted": deleted
            }

        except Exception as e:
            db.rollback()
            logger.exception("❌ Delete failed")
            raise HTTPException(500, f"Delete failed: {e}")


document_service = DocumentService()
