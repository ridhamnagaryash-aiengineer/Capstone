import logging
import uuid
from pathlib import Path
from starlette.datastructures import UploadFile as StarletteUploadFile
from sqlalchemy.orm import Session

from ..services.document_service import document_service
from ..llm.lite_client import lite_client
from ..vector_db.milvus_client import milvus_client

logger = logging.getLogger(__name__)

KB_FOLDER = Path("knowledge_base")
KB_FOLDER.mkdir(exist_ok=True)


# ---------- simple chunker ----------
def chunk_text(text: str, size: int = 5000):
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i + size])
        i += size
    return chunks


async def load_initial_kb(db: Session):
    """
    Loads PDFs/DOCX/TXT from knowledge_base folder
    and inserts chunks ONE BY ONE into Milvus.
    This avoids content length errors and keeps milvus_client unchanged.
    """
    try:
        files = list(KB_FOLDER.glob("*"))

        if not files:
            logger.warning("⚠️ No KB files found in knowledge_base/")
            return

        logger.info(f"📚 Loading {len(files)} KB files...")

        for file_path in files:
            try:
                logger.info(f"📄 Processing KB file: {file_path.name}")

                # Prepare fake upload for extractor
                upload = StarletteUploadFile(
                    filename=file_path.name,
                    file=open(file_path, "rb")
                )

                # Extract content
                content = await document_service.extract_content(upload)

                # Chunk the content
                chunks = chunk_text(content)
                file_id = str(uuid.uuid4())
                filename = file_path.name
                category = "HR_POLICY"

                total_inserted = 0

                # ---- INSERT CHUNKS ONE BY ONE ----
                for chunk in chunks:
                    embedding = lite_client.create_embedding(chunk)

                    # Each call inserts a SINGLE chunk
                    inserted = await milvus_client.store_document_embeddings(
                        file_id=file_id,
                        filename=filename,
                        content="KB_CHUNK",
                        embeddings=[embedding],   # 1 embedding only
                        category=category
                    )

                    total_inserted += inserted

                logger.info(f"✅ KB file {file_path.name} loaded ({total_inserted} vectors)")

            except Exception as e:
                logger.error(f"❌ Failed to load KB file {file_path.name}: {e}")

    except Exception as e:
        logger.error(f"❌ KB Loader fatal error: {e}")
        raise
