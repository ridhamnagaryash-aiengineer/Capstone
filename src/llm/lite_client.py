from dotenv import load_dotenv
load_dotenv()
 
import logging
import os
from typing import List, Dict
 
from litellm import completion, embedding
 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
 
 
class LiteLLMClient:
    """
    LiteLLM-powered unified client.
 
    Structure mirrors your old Gemini client:
    - Chat
    - Embeddings
    - Dimension helper
    - Same public API
    - Same function ordering
    - No import changes in project
    """
 
    def __init__(self):
        # Read environment models (backward compatible)
        self.chat_model = os.getenv("LLM_MODEL", "gemini/gemini-2.5-flash-lite")
        self.embed_model = os.getenv("EMBED_MODEL", "gemini/text-embedding-004")
 
        # Info logs like before
        logger.info("===============================================")
        logger.info(" LiteLLMClient initialized ")
        logger.info(f" Chat Model = {self.chat_model}")
        logger.info(f" Embedding Model = {self.embed_model}")
        logger.info("===============================================")
 
    # ----------------------------------------------------------------------
    #                          CHAT COMPLETION
    # ----------------------------------------------------------------------
    def chat_completion(self, messages: List[Dict]) -> str:
        """
        Equivalent to old Gemini chat_completion.
        Uses LiteLLM under the hood.
        """
        try:
            if not messages:
                return ""
 
            # last user message is still supported
            response = completion(
                model=self.chat_model,
                messages=messages,
            )
 
            # Extract text
            output = response["choices"][0]["message"]["content"]
            if not isinstance(output, str):
                output = str(output)
 
            return output.strip()
 
        except Exception as e:
            logger.error(f"❌ LiteLLM chat_failed: {e}")
            return f"Chat error: {e}"
 
    # ----------------------------------------------------------------------
    #                               EMBEDDINGS
    # ----------------------------------------------------------------------
    def create_embedding(self, text: str) -> List[float]:
        """
        Equivalent to old Gemini embedContent.
        Now uses LiteLLM embedding API.
        """
        try:
            # Safety trim preserved
            safe_text = text[:16000] if isinstance(text, str) else str(text)
 
            response = embedding(
                model=self.embed_model,
                input=safe_text
            )
 
            emb = response["data"][0]["embedding"]
            return emb
 
        except Exception as e:
            logger.error(f"❌ LiteLLM embedding_failed: {e}")
            raise RuntimeError(f"Embedding failed: {e}")
 
    # ----------------------------------------------------------------------
    #                      DIMENSION HELPER
    # ----------------------------------------------------------------------
    def get_embedding_dim(self) -> int:
        """
        Same utility function:
        quick embedding dimension probe.
        """
        try:
            emb = self.create_embedding("dimension probe")
            return len(emb)
        except Exception:
            return 0
 
 
# Singleton instance
lite_client = LiteLLMClient()