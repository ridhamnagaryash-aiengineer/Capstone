from dotenv import load_dotenv
load_dotenv()

import logging
import os
from typing import List, Dict
import google.generativeai as genai

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class LiteLLMClient:
    """
    Unified LLM client using ONLY Gemini:
      - Chat = Gemini 1.5 Flash
      - Embeddings = models/embedding-001

    No transformers, no torch, no sentence-transformers.
    """

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is missing.")

        genai.configure(api_key=api_key)

        # Chat model
        self.chat_model = genai.GenerativeModel("gemini-2.5-flash")

        logger.info("✅ LiteLLMClient initialized with Gemini chat + embeddings")

    # ---------------------------------------------------------
    #                     CHAT COMPLETION
    # ---------------------------------------------------------
    def chat_completion(self, messages: List[Dict]) -> str:
        """
        Chat using Gemini 1.5 Flash.
        Input messages = [{"role": ..., "content": ...}, ...]
        """
        try:
            # Convert messages to a single prompt
            user_prompt = messages[-1]["content"] if messages else ""

            response = self.chat_model.generate_content(user_prompt)
            txt = response.text if hasattr(response, "text") else str(response)

            return txt.strip()

        except Exception as e:
            logger.error(f"❌ Gemini chat failed: {e}")
            return f"Chat error: {e}"

    # ---------------------------------------------------------
    #                      EMBEDDINGS
    # ---------------------------------------------------------
    def create_embedding(self, text: str) -> List[float]:
        """
        Generate embeddings using Gemini models/embedding-001
        """
        try:
            text = text[:16000]  # safety trim
            result = genai.embed_content(
                model="models/embedding-001",
                content=text,
                task_type="retrieval_document",
            )

            emb = result.get("embedding")
            if not emb:
                raise RuntimeError("Gemini returned no embedding.")

            return emb

        except Exception as e:
            logger.error(f"❌ Embedding failed: {e}")
            raise RuntimeError(f"Embedding failed: {e}")

    # ---------------------------------------------------------
    #               HELPER — GET EMBEDDING DIMENSION
    # ---------------------------------------------------------
    def get_embedding_dim(self) -> int:
        """Quick dimension check."""
        emb = self.create_embedding("test")
        return len(emb)


# Singleton
lite_client = LiteLLMClient()
