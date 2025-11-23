import uuid
import logging
import os
from typing import Tuple, Optional
from pathlib import Path

from fastapi import UploadFile, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

import fitz
import docx
import boto3

from ..llm.lite_client import lite_client
from ..vector_db.milvus_client import milvus_client
from ..agents.document_classifier_agent import document_classifier_agent
from ..models.document import HRDocument, DocumentCategory

logger = logging.getLogger(__name__)

# ----------------------------- S3 CONFIG -----------------------------
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION")

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=AWS_REGION,
)

# Still needed for temp PDF extraction only
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

        # Upload file to S3 (returns s3_key only)
        s3_key, file_size = await self._upload_to_s3(file, file_id)

        # Create DB record (stores presigned URL + s3_key)
        document = await self._create_document_record(
            db=db,
            file=file,
            user=user,
            file_id=file_id,
            s3_key=s3_key,
            file_size=file_size
        )

        # Background processing
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
    async def _upload_to_s3(self, file: UploadFile, file_id: str) -> Tuple[str, int]:
        """Upload file to AWS S3. Returns S3 key + size."""
        try:
            file_bytes = await file.read()
            size = len(file_bytes)

            if size > 50 * 1024 * 1024:
                raise HTTPException(400, "File exceeds 50MB limit")

            ext = (file.filename or "").split(".")[-1]
            s3_key = f"documents/{file_id}.{ext}"

            s3.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=file_bytes,
                ContentType=file.content_type
            )

            await file.seek(0)
            return s3_key, size

        except Exception as e:
            logger.exception("❌ S3 upload failed")
            raise HTTPException(500, f"S3 upload failed: {e}")

    # ----------------------------------------------------------------------
    def generate_presigned_url(self, key: str, expires_in: int = 3600):
        """Generate a temporary access URL for S3 objects."""
        try:
            return s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": S3_BUCKET, "Key": key},
                ExpiresIn=expires_in
            )
        except Exception as e:
            logger.exception("❌ Failed to generate presigned URL")
            return None

    # ----------------------------------------------------------------------
    async def _create_document_record(
        self, db: Session, file: UploadFile, user, file_id, s3_key, file_size
    ) -> HRDocument:

        try:
            doc = HRDocument(
                file_id=file_id,
                filename=file.filename,
                original_filename=file.filename,
                s3_key=s3_key,
                s3_url=self.generate_presigned_url(s3_key),  # fresh presigned URL
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
        """Extract, classify, embed, and insert into Milvus."""
        try:
            doc = db.query(HRDocument).filter(HRDocument.id == document_id).first()
            if not doc:
                raise Exception("Document DB record not found")

            doc.processing_status = "processing"
            db.commit()

            content = await self.extract_content(file)
            if not content:
                raise Exception("No extractable text")

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

            total_vectors = await self.milvus.store_document_embeddings(
                file_id=file_id,
                filename=file.filename,
                content=content,
                embeddings=embeddings,
                category=category,
                chunks=chunks
            )

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
        docs = (
            db.query(HRDocument)
            .filter(HRDocument.uploaded_by_id == user_id)
            .order_by(HRDocument.uploaded_at.desc())
            .all()
        )

        # Refresh presigned URLs each time
        for d in docs:
            d.s3_url = self.generate_presigned_url(d.s3_key)

        return docs

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

            # Delete from S3
            try:
                s3.delete_object(Bucket=S3_BUCKET, Key=doc.s3_key)
            except Exception as e:
                logger.error(f"⚠ Could not delete S3 file: {e}")

            # Delete from Milvus
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
