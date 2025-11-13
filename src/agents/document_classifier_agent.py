# src/agents/document_classifier_agent.py
import logging
from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, END

from ..llm.lite_client import lite_client
from ..models.document import DocumentCategory

# Configure logging
logger = logging.getLogger(__name__)

class DocumentState(TypedDict):
    """State for the document processing workflow"""
    file_id: str
    filename: str
    file_content: str
    file_type: str  # pdf, docx, txt
    
    # Node outputs
    extracted_text: str
    category: str
    confidence: float
    chunks: List[str]
    embeddings: List[List[float]]
    
    # Status
    current_node: str
    error: str
    success: bool

class DocumentClassifierAgent:
    """LangGraph agent for document classification and storage with LiteLLM"""
    
    def __init__(self):
        self.llm = lite_client
        
        # Category descriptions for better classification
        self.category_descriptions = {
            DocumentCategory.PAYROLL.value: """Payroll Data: Documents containing salary information, 
            wage slips, tax deductions, bonus structures, compensation details, payroll schedules, 
            salary increments, pay grades, or financial compensation information.""",
            
            DocumentCategory.HR_POLICY.value: """HR Policy Data: Documents about company policies, 
            employee handbooks, code of conduct, leave policies, attendance rules, performance reviews, 
            hiring procedures, onboarding guides, benefits policies, or workplace regulations.""",
            
            DocumentCategory.IT_SUPPORT.value: """IT Support Data: Documents about technical support, 
            IT infrastructure, software guidelines, hardware policies, network access, cybersecurity, 
            password policies, system administration, technical troubleshooting, or IT helpdesk procedures.""",
            
            DocumentCategory.FACILITIES.value: """Facilities Data: Documents about office management, 
            building maintenance, workspace allocation, safety procedures, parking policies, 
            security protocols, facility reservations, office supplies, or infrastructure maintenance."""
        }
        
        # Build the LangGraph workflow
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(DocumentState)
        
        # Add nodes
        workflow.add_node("extract_content", self.extract_content)
        workflow.add_node("classify_document", self.classify_document)
        workflow.add_node("generate_embeddings", self.generate_embeddings)
        workflow.add_node("finalize", self.finalize)
        
        # Define edges (workflow)
        workflow.set_entry_point("extract_content")
        workflow.add_edge("extract_content", "classify_document")
        workflow.add_edge("classify_document", "generate_embeddings")
        workflow.add_edge("generate_embeddings", "finalize")
        workflow.add_edge("finalize", END)
        
        return workflow.compile()
    
    def extract_content(self, state: DocumentState) -> DocumentState:
        """Node 1: Extract text content from document"""
        try:
            logger.info(f"📄 [Node 1] Processing content from {state['filename']}")
            state['current_node'] = "extract_content"
            
            # Content is already extracted by file processor, just use it
            state['extracted_text'] = state['file_content']
            
            logger.info(f"✅ [Node 1] Using extracted text ({len(state['extracted_text'])} characters)")
            
            return state
            
        except Exception as e:
            logger.error(f"❌ [Node 1] Content processing failed: {e}")
            state['error'] = f"Content processing failed: {str(e)}"
            state['success'] = False
            return state
    
    def classify_document(self, state: DocumentState) -> DocumentState:
        """Node 2: Classify document using LiteLLM"""
        try:
            logger.info(f"🏷️ [Node 2] Classifying document: {state['filename']}")
            state['current_node'] = "classify_document"
            
            # Prepare classification prompt
            text_sample = state['extracted_text'][:3000]  # Use first 3000 chars
            
            categories_list = "\n".join([
                f"- {cat}: {desc}" 
                for cat, desc in self.category_descriptions.items()
            ])
            
            classification_prompt = f"""You are a document classification expert. Analyze the following document and classify it into ONE of these categories:

{categories_list}

Document Content (sample):
{text_sample}

Instructions:
1. Read the document content carefully
2. Classify it into the most appropriate category
3. Provide a confidence score (0.0 to 1.0)
4. Respond in this exact format:
Category: <category_name>
Confidence: <score>
Reasoning: <brief explanation>

Your response:"""
            
            # Get classification from LiteLLM
            messages = [
                {"role": "system", "content": "You are a document classification expert."},
                {"role": "user", "content": classification_prompt}
            ]
            
            response = self.llm.chat_completion(messages)
            
            # Parse response
            category = DocumentCategory.UNCATEGORIZED.value
            confidence = 0.0
            
            for line in response.split('\n'):
                if line.startswith('Category:'):
                    category = line.split(':', 1)[1].strip().lower()
                elif line.startswith('Confidence:'):
                    try:
                        confidence = float(line.split(':', 1)[1].strip())
                    except:
                        confidence = 0.5
            
            # Validate category
            valid_categories = [cat.value for cat in DocumentCategory]
            if category not in valid_categories:
                logger.warning(f"⚠️ Invalid category '{category}', defaulting to uncategorized")
                category = DocumentCategory.UNCATEGORIZED.value
                confidence = 0.0
            
            state['category'] = category
            state['confidence'] = confidence
            
            logger.info(f"✅ [Node 2] Classified as '{category}' (confidence: {confidence:.2f})")
            
            return state
            
        except Exception as e:
            logger.error(f"❌ [Node 2] Classification failed: {e}")
            state['error'] = f"Classification failed: {str(e)}"
            state['category'] = DocumentCategory.UNCATEGORIZED.value
            state['confidence'] = 0.0
            return state
    
    def generate_embeddings(self, state: DocumentState) -> DocumentState:
        """Node 3: Generate embeddings for document chunks using LiteLLM"""
        try:
            logger.info(f"🔢 [Node 3] Generating embeddings for {state['filename']}")
            state['current_node'] = "generate_embeddings"
            
            text = state['extracted_text']
            
            # Chunk the text
            chunks = self._chunk_text(text, chunk_size=1000, overlap=200)
            state['chunks'] = chunks
            
            # Generate embeddings using LiteLLM
            embeddings = []
            for i, chunk in enumerate(chunks):
                try:
                    embedding = self.llm.create_embedding(chunk)
                    embeddings.append(embedding)
                    
                    if (i + 1) % 10 == 0:
                        logger.info(f"🔢 Generated {i + 1}/{len(chunks)} embeddings")
                        
                except Exception as e:
                    logger.error(f"❌ Embedding error for chunk {i}: {e}")
                    embeddings.append([0.0] * 768)  # Zero vector fallback
            
            state['embeddings'] = embeddings
            logger.info(f"✅ [Node 3] Generated {len(embeddings)} embeddings")
            
            return state
            
        except Exception as e:
            logger.error(f"❌ [Node 3] Embedding generation failed: {e}")
            state['error'] = f"Embedding generation failed: {str(e)}"
            return state
    
    def finalize(self, state: DocumentState) -> DocumentState:
        """Node 4: Finalize processing"""
        try:
            logger.info("✅ [Node 4] Finalizing document processing")
            state['current_node'] = "finalize"
            state['success'] = True
            
            return state
            
        except Exception as e:
            logger.error(f"❌ [Node 4] Finalization failed: {e}")
            state['error'] = f"Finalization failed: {str(e)}"
            state['success'] = False
            return state
    
    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks"""
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + chunk_size
            chunk = text[start:end]
            
            if chunk.strip():
                chunks.append(chunk.strip())
            
            start += chunk_size - overlap
        
        return chunks
    
    def process_document(
        self, 
        file_id: str,
        filename: str,
        file_content: str,
        file_type: str
    ) -> DocumentState:
        """
        Process a document through the LangGraph workflow
        
        Args:
            file_id: Unique document identifier
            filename: Original filename
            file_content: File content as string (already extracted)
            file_type: File extension (pdf, docx, txt)
            
        Returns:
            Final state after processing
        """
        # Initialize state
        initial_state: DocumentState = {
            'file_id': file_id,
            'filename': filename,
            'file_content': file_content,
            'file_type': file_type,
            'extracted_text': '',
            'category': '',
            'confidence': 0.0,
            'chunks': [],
            'embeddings': [],
            'current_node': '',
            'error': '',
            'success': False
        }
        
        # Run through workflow
        logger.info(f"🚀 Starting LangGraph workflow for: {filename}")
        final_state = self.workflow.invoke(initial_state)
        
        if final_state['success']:
            logger.info(f"✅ Document processing completed successfully")
        else:
            logger.error(f"❌ Document processing failed: {final_state.get('error', 'Unknown error')}")
        
        return final_state

# Singleton instance
document_classifier_agent = DocumentClassifierAgent()