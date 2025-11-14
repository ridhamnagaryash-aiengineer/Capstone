import uuid
import logging
from typing import Tuple, List
from fastapi import UploadFile, HTTPException, BackgroundTasks
import fitz  # PyMuPDF
import docx
from sqlalchemy.orm import Session
from pathlib import Path
import os

# Project imports
from ..llm.lite_client import lite_client
from ..vector_db.milvus_client import milvus_client
from ..agents.document_classifier_agent import document_classifier_agent
from ..models.document import HRDocument, DocumentCategory
from ..schemas.document import HRDocumentResponse, HRDocumentList

logger = logging.getLogger(__name__)

# Local storage directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class DocumentService:
    """Handle document upload, processing, and local storage with LiteLLM + Milvus"""

    def __init__(self):
        self.milvus = milvus_client
        self.llm = lite_client
        self.classifier_agent = document_classifier_agent
        logger.info("✅ DocumentService initialized (Local Storage Mode)")

    # -------------------------------------------------------------------------
    async def process_document_upload(
        self,
        file: UploadFile,
        user: any,
        db: Session,
        background_tasks: BackgroundTasks
    ) -> HRDocumentResponse:
        """Single endpoint for document upload and processing"""
        try:
            await self.validate_file(file)
            file_id = str(uuid.uuid4())

            # Save file locally
            local_path, file_size = await self._save_locally(file, file_id)

            # Create DB record
            document = await self._create_document_record(
                db, file, user, file_id, local_path, file_size
            )

            # Background classification + embeddings
            background_tasks.add_task(
                self._process_document_background,
                file_id,
                file,
                document.id,
                db
            )

            return HRDocumentResponse.model_validate(document)

        except Exception as e:
            logger.error(f"❌ Document upload failed: {e}")
            raise HTTPException(status_code=500, detail=f"Document upload failed: {str(e)}")

    # -------------------------------------------------------------------------
    async def validate_file(self, file: UploadFile):
        """Validate uploaded file type"""
        allowed_types = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
        ]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Upload PDF, DOC, DOCX, or TXT only.",
            )

    # -------------------------------------------------------------------------
    async def extract_content(self, file: UploadFile) -> str:
        """Extract text, tables from PDF using PyMuPDF, and text from DOCX/TXT"""
        try:
            content = ""

            # -------------------- PDF Extraction --------------------
            if file.content_type == "application/pdf":
                pdf_bytes = await file.read()
                pdf_path = "temp_extract.pdf"

                # Save temp PDF
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)

                doc = fitz.open(pdf_path)
                extracted_text = []

                for page in doc:
                    # Extract raw text
                    extracted_text.append(page.get_text("text"))

                    # Try extracting tables
                    try:
                        tables = page.find_tables()
                        for tbl in tables:
                            df = tbl.to_pandas()
                            extracted_text.append(df.to_string())
                    except Exception:
                        pass

                content = "\n".join(extracted_text)

                doc.close()
                os.remove(pdf_path)
                await file.seek(0)
                return content.strip()

            # -------------------- DOC / DOCX Extraction --------------------
            elif file.content_type in [
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ]:
                doc_obj = docx.Document(file.file)
                for para in doc_obj.paragraphs:
                    content += para.text + "\n"

            # -------------------- TEXT Extraction --------------------
            elif file.content_type == "text/plain":
                content = (await file.read()).decode("utf-8")

            await file.seek(0)
            return content.strip()

        except Exception as e:
            logger.error(f"❌ Content extraction failed: {e}")
            raise HTTPException(status_code=400, detail=f"Could not extract content: {str(e)}")

    # -------------------------------------------------------------------------
    async def _save_locally(self, file: UploadFile, file_id: str) -> Tuple[str, int]:
        """Save file locally"""
        try:
            file_content = await file.read()
            file_size = len(file_content)

            max_size = 50 * 1024 * 1024  # 50 MB
            if file_size > max_size:
                raise HTTPException(status_code=400, detail="File size exceeds 50MB limit")

            ext = file.filename.split(".")[-1]
            local_filename = f"{file_id}.{ext}"
            local_path = UPLOAD_DIR / local_filename

            with open(local_path, "wb") as f:
                f.write(file_content)

            await file.seek(0)
            logger.info(f"✅ Saved locally: {local_path}")
            return str(local_path), file_size

        except Exception as e:
            logger.error(f"❌ Local save failed: {e}")
            raise HTTPException(status_code=500, detail=f"Local save failed: {str(e)}")

    # -------------------------------------------------------------------------
    async def _create_document_record(
        self,
        db: Session,
        file: UploadFile,
        user: any,
        file_id: str,
        local_path: str,
        file_size: int
    ) -> HRDocument:
        """Create database record for uploaded document"""
        try:
            document = HRDocument(
                file_id=file_id,
                filename=os.path.basename(local_path),
                original_filename=file.filename,
                s3_url=local_path,
                s3_key=None,
                file_size=file_size,
                content_type=file.content_type,
                uploaded_by_id=user.id,
                processing_status="pending",
                category=DocumentCategory.UNCATEGORIZED,
            )

            db.add(document)
            db.commit()
            db.refresh(document)
            logger.info(f"✅ Created document record: {file_id}")
            return document

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Failed to create document record: {e}")
            raise

    # -------------------------------------------------------------------------
    async def _process_document_background(
        self,
        file_id: str,
        file: UploadFile,
        document_id: int,
        db: Session
    ):
        """Background classification + embedding workflow"""
        try:
            document = db.query(HRDocument).filter(HRDocument.id == document_id).first()
            document.processing_status = "processing"
            db.commit()
            logger.info(f"⚙️ Background processing started for {file.filename}")

            # Extract file content
            content = await self.extract_content(file)

            # Classify document
            classification_result = self.classifier_agent.process_document(
                file_id=file_id,
                filename=file.filename,
                file_content=content,
                file_type=file.filename.split(".")[-1],
            )

            if not classification_result.get("success"):
                raise Exception(classification_result.get("error", "Classification failed"))

            # Store vectors in Milvus
            vector_count = await self.milvus.store_document_embeddings(
                file_id=file_id,
                filename=file.filename,
                content=content,
                embeddings=classification_result["embeddings"],
                category=classification_result["category"],
            )

            # Update DB
            document.category = DocumentCategory(classification_result["category"])
            document.classification_confidence = classification_result.get("confidence", 0.0)
            document.vector_count = vector_count
            document.processing_status = "completed"
            db.commit()

            logger.info(
                f"✅ Document processed: {file.filename} → "
                f"{classification_result['category']} (vectors: {vector_count})"
            )

        except Exception as e:
            logger.error(f"❌ Background processing failed: {e}")
            document = db.query(HRDocument).filter(HRDocument.id == document_id).first()
            document.processing_status = "failed"
            document.error_message = str(e)
            db.commit()

    # -------------------------------------------------------------------------
    async def get_user_documents(self, user_id: int, db: Session) -> HRDocumentList:
        """Get all documents uploaded by a user"""
        try:
            documents = (
                db.query(HRDocument)
                .filter(HRDocument.uploaded_by_id == user_id)
                .order_by(HRDocument.uploaded_at.desc())
                .all()
            )
            return HRDocumentList(
                total=len(documents),
                documents=[HRDocumentResponse.model_validate(doc) for doc in documents],
            )
        except Exception as e:
            logger.error(f"❌ Failed to fetch user documents: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve documents")

    # -------------------------------------------------------------------------
    async def delete_document(self, file_id: str, user_id: int, db: Session) -> dict:
        """Delete document + embeddings + local file"""
        try:
            document = (
                db.query(HRDocument)
                .filter(HRDocument.file_id == file_id, HRDocument.uploaded_by_id == user_id)
                .first()
            )

            if not document:
                raise HTTPException(status_code=404, detail="Document not found")

            # Delete local file
            local_path = Path(document.s3_url)
            if local_path.exists():
                local_path.unlink()
                logger.info(f"🗑️ Deleted local file: {local_path}")

            # Delete vectors
            milvus_deleted = await self.milvus.delete_by_file_id(file_id)

            db.delete(document)
            db.commit()

            return {
                "message": f"Document '{document.original_filename}' deleted successfully",
                "file_id": file_id,
                "vectors_deleted": milvus_deleted,
            }

        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Document deletion failed: {e}")
            raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

    # -------------------------------------------------------------------------
    def test_connections(self) -> dict:
        """Test Milvus connection"""
        milvus_ok = self._test_milvus_connection()
        return {"milvus": milvus_ok, "all_ok": milvus_ok}

    def _test_milvus_connection(self) -> bool:
        """Check Milvus health"""
        try:
            stats = self.milvus.get_collection_stats()
            logger.info(f"✅ Milvus connection OK (Vectors: {stats['total_vectors']})")
            return True
        except Exception as e:
            logger.error(f"❌ Milvus connection failed: {e}")
            return False


# Singleton instance
document_service = DocumentService()
