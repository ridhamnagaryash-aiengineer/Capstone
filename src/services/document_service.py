# src/services/document_service.py

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
from src.llm.lite_client import lite_client
from src.vector_db.milvus_client import milvus_client
from src.models.document import HRDocument

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ----------------------------- S3 -----------------------------
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION")

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=AWS_REGION,
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ----------------------------- Chunker -----------------------------
def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


class DocumentService:
    """Upload → Extract → Chunk → Embed → Store in Milvus."""

    def __init__(self):
        self.milvus = milvus_client
        self.llm = lite_client
        logger.info("DocumentService initialized (clean + no classifier)")

    # -------------------- Upload Entry --------------------
    async def process_document_upload(
        self,
        file: UploadFile,
        user: any,
        db: Session,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> HRDocument:

        await self._validate_file(file)
        file_id = str(uuid.uuid4())

        s3_key, file_size = await self._upload_to_s3(file, file_id)

        document = await self._create_document_record(
            db=db,
            file=file,
            user=user,
            file_id=file_id,
            s3_key=s3_key,
            file_size=file_size
        )

        # Make a safe copy for background processing
        file.file.seek(0)
        file_bytes = await file.read()

        if background_tasks:
            background_tasks.add_task(
                self._process_background,
                file_id,
                file.filename,
                file.content_type,
                file_bytes,
                document.id,
                db
            )
        else:
            await self._process_background(
                file_id,
                file.filename,
                file.content_type,
                file_bytes,
                document.id,
                db
            )

        return document

    # -------------------- Validation --------------------
    async def _validate_file(self, file: UploadFile):
        allowed = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
        ]
        if file.content_type not in allowed:
            raise HTTPException(400, "Unsupported file type.")

    # -------------------- Extract --------------------
    def extract_content_from_bytes(self, file_bytes: bytes, content_type: str) -> str:
        try:
            if content_type == "application/pdf":
                tmp = UPLOAD_DIR / f"tmp_{uuid.uuid4().hex}.pdf"
                tmp.write_bytes(file_bytes)
                doc = fitz.open(str(tmp))
                text = "\n".join([p.get_text() for p in doc])
                doc.close()
                tmp.unlink(missing_ok=True)
                return text.strip()

            if content_type in (
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ):
                tmp = UPLOAD_DIR / f"tmp_{uuid.uuid4().hex}.docx"
                tmp.write_bytes(file_bytes)
                d = docx.Document(str(tmp))
                tmp.unlink(missing_ok=True)
                return "\n".join([p.text for p in d.paragraphs]).strip()

            if content_type == "text/plain":
                return file_bytes.decode("utf-8", "ignore").strip()

            return ""

        except Exception as e:
            raise HTTPException(400, f"Content extraction failed: {e}")

    # -------------------- S3 --------------------
    async def _upload_to_s3(self, file: UploadFile, file_id: str) -> Tuple[str, int]:
        file_bytes = await file.read()
        size = len(file_bytes)

        if size > 50 * 1024 * 1024:
            raise HTTPException(400, "File > 50MB")

        ext = (file.filename or "").split(".")[-1]
        s3_key = f"documents/{file_id}.{ext}"

        try:
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=file_bytes,
                ContentType=file.content_type
            )
            return s3_key, size
        except Exception as e:
            raise HTTPException(500, f"S3 upload failed: {e}")

    # -------------------- DB --------------------
    async def _create_document_record(
        self, db: Session, file: UploadFile, user, file_id, s3_key, file_size
    ):
        doc = HRDocument(
            file_id=file_id,
            filename=file.filename,
            original_filename=file.filename,
            s3_key=s3_key,
            s3_url=self.generate_presigned_url(s3_key),
            file_size=file_size,
            content_type=file.content_type,
            uploaded_by_id=user.id,
            processing_status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc

    def generate_presigned_url(self, key: str, expires_in: int = 3600):
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=expires_in
        )

    # -------------------- Background Processing --------------------
    async def _process_background(
        self,
        file_id: str,
        filename: str,
        content_type: str,
        file_bytes: bytes,
        document_id: int,
        db: Session
    ):
        try:
            doc = db.query(HRDocument).filter(HRDocument.id == document_id).first()
            if not doc:
                raise Exception("Document not found in DB")

            doc.processing_status = "processing"
            db.commit()

            # Extract text
            content = self.extract_content_from_bytes(file_bytes, content_type)
            if not content:
                raise Exception("Empty text after extraction")

            # Chunk
            chunks = chunk_text(content)

            # Embed
            embeddings = []
            for ch in chunks:
                emb = self.llm.create_embedding(ch)
                embeddings.append(emb)

            # Store in Milvus
            vector_count = await self.milvus.store_document_embeddings(
                file_id=file_id,
                filename=filename,
                content=content,
                embeddings=embeddings,
                category=None,
                chunks=chunks
            )

            doc.vector_count = vector_count
            doc.processing_status = "completed"
            db.commit()

        except Exception as e:
            doc = db.query(HRDocument).filter(HRDocument.id == document_id).first()
            if doc:
                doc.processing_status = "failed"
                doc.error_message = str(e)
                db.commit()

    # -------------------- Get & Delete --------------------
    async def get_user_documents(self, user_id: int, db: Session):
        docs = db.query(HRDocument).filter(
            HRDocument.uploaded_by_id == user_id
        ).all()

        for d in docs:
            d.s3_url = self.generate_presigned_url(d.s3_key)

        return docs

    async def delete_document(self, file_id: str, user_id: int, db: Session):
        doc = db.query(HRDocument).filter(
            HRDocument.file_id == file_id,
            HRDocument.uploaded_by_id == user_id
        ).first()

        if not doc:
            raise HTTPException(404, "Document not found")

        # Delete S3
        try:
            s3.delete_object(Bucket=S3_BUCKET, Key=doc.s3_key)
        except:
            pass

        # Delete from Milvus
        deleted = await self.milvus.delete_by_file_id(file_id)

        db.delete(doc)
        db.commit()

        return {"message": "Document deleted", "vectors_deleted": deleted}


document_service = DocumentService()
