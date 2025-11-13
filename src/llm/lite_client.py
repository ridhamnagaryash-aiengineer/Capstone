import logging
from typing import List, Dict
from transformers import pipeline
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class LiteLLMClient:
    """Simple client for local, free Hugging Face models (chat + embeddings)."""

    def __init__(self):
        # ✅ Chat model (T5-based — handles longer prompts than Blenderbot)
        logger.info("🔄 Loading FLAN-T5 chat model...")
        self.chat_pipeline = pipeline("text2text-generation", model="google/flan-t5-base")
        logger.info("✅ Loaded chat model: google/flan-t5-base")

        # ✅ Embedding model (768-dimensional vectors)
        self.embedding_model_name = "sentence-transformers/all-mpnet-base-v2"
        self.embedder = SentenceTransformer(self.embedding_model_name)
        logger.info(f"✅ Loaded embedding model: {self.embedding_model_name}")

    def chat_completion(self, messages: List[Dict]) -> str:
        """Generate text-based chat response using FLAN-T5."""
        try:
            prompt = messages[-1]["content"] if messages else ""
            # Prevent overflow on very long prompts
            prompt = prompt[:512]
            response = self.chat_pipeline(prompt, max_length=256, do_sample=False)
            return response[0]["generated_text"].strip()
        except Exception as e:
            logger.error(f"❌ HF chat failed: {e}")
            return f"Error generating response: {e}"

    def create_embedding(self, text: str) -> List[float]:
        """Generate embeddings using SentenceTransformer (768D)."""
        try:
            embedding = self.embedder.encode(text, normalize_embeddings=True).tolist()
            return embedding
        except Exception as e:
            logger.error(f"❌ Embedding generation failed: {e}")
            raise

# Singleton instance
lite_client = LiteLLMClient()



