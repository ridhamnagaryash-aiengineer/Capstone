# from dotenv import load_dotenv
# load_dotenv()
# import logging
# import os
# from typing import List, Dict
# from litellm import completion, embedding
# from utils.obs import TokenTracker
# from langchain_core.outputs import LLMResult
 
# logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)
 
 
# class LiteLLMClient:
#     """
#     LiteLLM-powered unified client.
#     Structure mirrors Gemini LiteLLM client:
#     - Chat
#     - Embeddings
#     - Dimension helper
#     - Same public API
#     - Same function ordering
#     - No import changes in project
#     """
#     def __init__(self):
#         self.chat_model = os.getenv("LLM_MODEL")
#         self.embed_model = os.getenv("EMBED_MODEL", "gemini/text-embedding-004")
#         # Info logs 
#         logger.info("===============================================")
#         logger.info(" LiteLLMClient initialized ")
#         logger.info(f" Chat Model = {self.chat_model}")
#         logger.info(f" Embedding Model = {self.embed_model}")
#         logger.info("===============================================")
 
#     # ----------------------------------------------------------------------
#     #                          CHAT COMPLETION
#     # ----------------------------------------------------------------------
#     # def chat_completion(self, messages: List[Dict]) -> str:
#     #     """
#     #     Equivalent to old Gemini chat_completion.
#     #     Uses LiteLLM as Wrapper.
#     #     """
#     #     try:
#     #         if not messages:
#     #             return ""
#     #         response = completion(
#     #             model=self.chat_model,
#     #             messages=messages,
#     #         )
#     #         output = response["choices"][0]["message"]["content"]
#     #         if not isinstance(output, str):
#     #             output = str(output)
#     #         return output.strip()
 
#     #     except Exception as e:
#     #         logger.error(f"❌ LiteLLM chat_failed: {e}")
#     #         return f"Chat error: {e}"


#     # def chat_completion(self, messages: List[Dict], llm_params: Dict = None) -> str:
#     #     try:
#     #         if not messages:
#     #             return ""

#     #         llm_params = llm_params or {}

#     #         # dynamic override: if model passed in llm_params, respect it
#     #         model = llm_params.pop("model")
#     #         print(model,"model")

#     #         response = completion(
#     #             model=model,
#     #             messages=messages,
#     #             **llm_params  # temperature, max_tokens, extra configs
#     #         )

#     #         return response["choices"][0]["message"]["content"].strip()

# #         return f"Chat error: {e}"



# def chat_completion(self, messages: List[Dict], llm_params: Dict = None) -> str:
#     try:
#         if not messages:
#             return ""

#         # prevent mutation of caller params
#         params = dict(llm_params or {})

#         # extract auth_token for TokenTracker context (optional)
#         auth_token = params.pop("auth_token", "")

#         # determine model override or fallback
#         model = params.pop("model", None) or self.chat_model

#         # ---- call LLM ----
#         response = completion(
#             model=model,
#             messages=messages,
#             **params
#         )

#         # ---- TOKEN TRACKING VIA LANGCHAIN CALLBACK STYLE ----
#         try:
#             tracker = TokenTracker(model=model)

#             # Build a fake LLMResult for compatibility with your TokenTracker.on_llm_end()
#             fake_result = LLMResult(
#                 llm_output={
#                     "token_usage": response.get("usage", {}),
#                 },
#                 generations=[]  # not required for your implementation
#             )

#             # trigger token logging
#             tracker.on_llm_end(fake_result, run_id=None)
#         except Exception as e:
#             logger.warning(f"Token tracking failed (non-fatal): {e}")

#         # ---- RETURN NORMAL MODEL OUTPUT ----
#         # dict-style extraction (litellm default)
#         content = (
#             response.get("choices", [{}])[0]
#                     .get("message", {})
#                     .get("content", "")
#         )

#         return content.strip() if isinstance(content, str) else str(content)

#     except Exception as e:
#         logger.error(f"❌ LiteLLM chat_failed: {e}")
#         return f"Chat error: {e}"

#     # ----------------------------------------------------------------------
#     #                       CREATE EMBEDDINGS FUNCTION
#     # ----------------------------------------------------------------------
#     def create_embedding(self, text: str) -> List[float]:
#         """
#         Now uses LiteLLM embedding API same as Gemini Embedding Model.
#         """
#         try:
#             safe_text = text[:16000] if isinstance(text, str) else str(text)
#             response = embedding(
#                 model=self.embed_model,
#                 input=safe_text
#             )
 
#             emb = response["data"][0]["embedding"]
#             return emb
 
#         except Exception as e:
#             logger.error(f"❌ LiteLLM embedding_failed: {e}")
#             raise RuntimeError(f"Embedding failed: {e}")
 
#     # ----------------------------------------------------------------------
#     #                      DIMENSION HELPER
#     # ----------------------------------------------------------------------
#     def get_embedding_dim(self) -> int:
#         """
#         Same utility function:
#         quick embedding dimension probe.
#         """
#         try:
#             emb = self.create_embedding("dimension probe")
#             return len(emb)
#         except Exception:
#             return 0 
# # Singleton instance
# lite_client = LiteLLMClient()

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
        logger.info(" LiteLLMClient initialized ")
        logger.info(f" Chat Model = {self.chat_model}")
        logger.info(f" Embedding Model = {self.embed_model}")
        logger.info("===============================================")

    # ----------------------------------------------------------------------
    #                          CHAT COMPLETION
    # ----------------------------------------------------------------------
    def chat_completion(self, messages: List[Dict], llm_params: Dict = None) -> str:
        try:
            if not messages:
                return ""

            # prevent mutation
            params = dict(llm_params or {})

            # extract token for tracker
            auth_token = params.pop("auth_token", "")

            # dynamic model override
            model = params.pop("model", None) or self.chat_model

            # ---- actual LLM call ----
            response = completion(
                model=model,
                messages=messages,
                **params
            )

            # ---- token tracking ----
            try:
                # tracker = TokenTracker(model=model)

                fake_result = LLMResult(
                    llm_output={
                        "token_usage": response.get("usage", {}),
                    },
                    generations=[]
                )

                tracker.on_llm_end(fake_result, run_id=None)
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
    #                       CREATE EMBEDDINGS FUNCTION
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
    #                      DIMENSION HELPER
    # ----------------------------------------------------------------------
    def get_embedding_dim(self) -> int:
        try:
            emb = self.create_embedding("dimension probe")
            return len(emb)
        except Exception:
            return 0


# Singleton
lite_client = LiteLLMClient()
