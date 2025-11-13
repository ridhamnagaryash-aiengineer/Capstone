# src/services/document_service.py
from ..llm.lite_client import lite_client  # ✅ Use LiteLLM
from ..vector_db.milvus_client import milvus_client  # ✅ Use Milvus
from ..agents.document_classifier_agent import document_classifier_agent

class DocumentService:
    def __init__(self):
        self.llm = lite_client
        self.milvus = milvus_client
        self.classifier = document_classifier_agent
    
    async def process_document_upload(self, file, user, db, background_tasks):
        """Single method handling complete document processing"""
        # 1. Upload to S3 (existing logic)
        s3_data = await self._upload_to_s3(file)
        
        # 2. Create DB record (existing logic) 
        document = self._create_document_record(db, file, user, s3_data)
        
        # 3. Process in background using agent
        background_tasks.add_task(
            self._process_document_background,
            document.file_id,
            file,
            db
        )
        
        return document
    
    async def _process_document_background(self, file_id, file, db):
        """Background processing - existing logic with LiteLLM"""
        content = await self._extract_content(file)
        
        # ✅ Use classifier agent (already uses LiteLLM)
        classification = await self.classifier.process_document(
            file_id=file_id,
            filename=file.filename, 
            file_content=content,
            file_type=file.filename.split('.')[-1]
        )
        
        # ✅ Store in Milvus
        await self.milvus.store_document_embeddings(
            file_id=file_id,
            filename=file.filename,
            content=content,
            embeddings=classification['embeddings'],
            category=classification['category']
        )
        
        # Update DB record
        self._update_document_record(db, file_id, classification)

# Global instance
document_service = DocumentService()