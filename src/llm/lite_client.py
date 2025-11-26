from dotenv import load_dotenv
load_dotenv()

import logging
import os
from typing import List, Dict
from litellm import completion, embedding
from src.utils.obs import LLMUsageTracker
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class LiteLLMClient:
    """
    LiteLLM-powered unified client.
    """

    def __init__(self):
        self.chat_model = os.getenv("LLM_MODEL")
        self.embed_model = os.getenv("EMBED_MODEL", "gemini/text-embedding-004")
        logger.info("===============================================")
        logger.info("       LiteLLMClient initialized               ")
        logger.info(f" Chat Model      = {self.chat_model}")
        logger.info(f" Embedding Model = {self.embed_model}")
        logger.info("===============================================")

    # ----------------------------------------------------------------------
    # CHAT COMPLETION
    # ----------------------------------------------------------------------
    def chat_completion(self, messages: List[Dict], llm_params: Dict = None) -> str:
        try:
            if not messages:
                return ""

            # prevent mutation
            params = dict(llm_params or {})

            # extract token for tracker (kept for context inspection)
            auth_token = params.pop("auth_token", "")

            # dynamic model override
            model = params.pop("model", None) or self.chat_model

            response = completion(
                model=model,
                messages=messages,
                **params
            )

            try:
                # tracker = TokenTracker(model=model)

                tracker = TokenTracker(model=model)
                
                llm_result = LLMResult(
                    llm_output={
                        "token_usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens,
                            "completion_tokens_details": {
                                "reasoning_tokens": reasoning_tokens
                            } if reasoning_tokens else None
                        }
                    },
                    generations=[]
                )
                
                # Trigger the token tracking
                tracker.on_llm_end(llm_result, run_id=None)
                
                print(f"✅ Token usage - Prompt: {prompt_tokens}, ")
                print(f"Completion: {completion_tokens}, Total: {total_tokens}")
                print(f", Reasoning: {reasoning_tokens}" if reasoning_tokens else "")
            except Exception as e:
                logger.warning(f"Token tracking failed (non-fatal): {e}")

            # ---- return text ----
            content = (
                response.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return content.strip() if isinstance(content, str) else str(content)

        except Exception as e:
            logger.error(f"❌ LiteLLM chat_failed: {e}")
            return f"Chat error: {e}"

    # ----------------------------------------------------------------------
    # CREATE EMBEDDINGS FUNCTION
    # ----------------------------------------------------------------------
    def create_embedding(self, text: str) -> List[float]:
        try:
            safe_text = text[:16000] if isinstance(text, str) else str(text)
            response = embedding(
                model=self.embed_model,
                input=safe_text
            )
            return response["data"][0]["embedding"]
        except Exception as e:
            logger.error(f"❌ LiteLLM embedding_failed: {e}")
            raise RuntimeError(f"Embedding failed: {e}")

    # ----------------------------------------------------------------------
    # DIMENSION HELPER
    # ----------------------------------------------------------------------
    def get_embedding_dim(self) -> int:
        try:
            emb = self.create_embedding("dimension probe")
            return len(emb)
        except Exception:
            return 0


# Singleton
lite_client = LiteLLMClient()