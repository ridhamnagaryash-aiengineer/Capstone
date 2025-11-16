"""
LiveKit Voice Agent with HR Assistant Integration
Provides voice-enabled HR knowledge base retrieval and assistance
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# LiveKit imports
from livekit.agents import (
    JobContext,
    WorkerOptions,
    cli,
    Agent,
    AgentSession,
    RunContext,
    function_tool,
)
from livekit.plugins import deepgram, google, silero

# FastAPI imports
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Project imports
from src.llm.lite_client import lite_client
from src.retriever.hr_retriever import HRRetriever
from src.agents.query_router_agent import query_router_agent

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
TRANSCRIPTS_DIR = "/tmp/transcripts"

# Verify environment variables
REQUIRED_ENV_VARS = ['LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET', 'LIVEKIT_URL', 'GOOGLE_API_KEY']
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    logger.error(f"Missing required environment variables: {missing_vars}")
    raise ValueError(f"Missing environment variables: {missing_vars}")

# Ensure transcripts directory exists
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

# FastAPI app initialization
app = FastAPI(title="LiveKit Voice Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================
# Utility Functions
# =====================================================

def build_context_prompt(category: str, user_query: str, chunks: List[Dict[str, Any]]) -> str:
    """Build a prompt from retrieved knowledge base chunks"""
    cat_title = (category or "uncategorized").replace("_", " ").title()
    
    system_instr = (
        f"You are an intelligent HR assistant specialized in {cat_title}. "
        "Answer strictly based on provided documents. Cite sources. "
        "Be concise and professional."
    )
    
    if not chunks:
        return (
            f"{system_instr}\n\n"
            f"No relevant documents found in the {cat_title} knowledge base.\n"
            "If you cannot answer from documents, state that you'll escalate to HR.\n\n"
            f"Employee Question: {user_query}\n\nAnswer:"
        )
    
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        fname = chunk.get("filename") or chunk.get("file_name") or "unknown"
        text = chunk.get("content") or chunk.get("text") or chunk.get("chunk_text") or ""
        cat = chunk.get("category") or chunk.get("collection") or category
        
        # Truncate long text
        display_text = text if len(text) <= 2000 else f"{text[:2000]}..."
        part = f"[Source {i}] {fname} (category: {cat})\n{display_text}"
        context_parts.append(part)
    
    context = "\n\n".join(context_parts)
    prompt = (
        f"{system_instr}\n\n"
        f"Context from documents:\n{context}\n\n"
        f"Employee Question: {user_query}\n\n"
        f"Answer (cite sources where used):"
    )
    
    return prompt


# =====================================================
# LiveKit Function Tools
# =====================================================

@function_tool
async def search_knowledge_bases(context: RunContext, query: str) -> str:
    """
    Search HR knowledge bases and return grounded answers.
    
    Steps:
    1. Classify query into a category
    2. Create embeddings
    3. Retrieve relevant chunks from Milvus
    4. Generate LLM answer grounded in retrieved content
    """
    try:
        user_query = (query or "").strip()
        if not user_query:
            return "I didn't catch that. Could you repeat your question?"
        
        logger.info(f"[search_knowledge_bases] Processing query: {user_query}")
        
        try:
            classify_result = await query_router_agent.process_query(
                user_query=user_query,
                chat_history=[],
                user_info={}
            )
            category = classify_result.get("category") or "uncategorized"
            confidence = classify_result.get("confidence") or 0.0
            logger.info(f"Query classified as '{category}' (confidence: {confidence})")
        except Exception as e:
            logger.exception("Classification failed, using 'uncategorized'")
            category = "uncategorized"
        
        # Step 2: Create embedding (handled internally by retriever)
        
        # Step 3: Retrieve from Milvus
        retriever = HRRetriever()
        try:
            results = await retriever.retrieve(
                query=user_query,
                category=category,
                top_k=5
            )
            logger.info(f"Retrieved {len(results)} chunks from knowledge base")
        except Exception as e:
            logger.exception("Retrieval failed")
            results = []
        
        # Step 4: Build prompt and generate answer
        prompt = build_context_prompt(category, user_query, results)
        
        try:
            messages = [
                {"role": "system", "content": "You are a helpful HR assistant."},
                {"role": "user", "content": prompt}
            ]
            answer = lite_client.chat_completion(messages)
            logger.info("Generated LLM answer successfully")
        except Exception as e:
            logger.exception("Chat completion failed")
            answer = (
                "I'm sorry — I couldn't generate an answer right now. "
                "Please try again later or contact HR directly."
            )
        
        return answer
        
    except Exception as e:
        logger.exception("Unexpected error in search_knowledge_bases")
        return "Internal error in voice assistant. Please try again."


async def start_hr_session(ctx: JobContext):
    """Entry point for HR assistant sessions"""

    # Create agent with HR search tools
    agent = Agent(
        instructions=(
            "You are a voice-enabled HR assistant. Use the provided tools to answer "
            "employee questions accurately. Always cite your sources when answering "
            "from the knowledge base."
        ),
        tools=[search_knowledge_bases],
    )
    
    # Initialize session
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="en-US"),
        llm=google.LLM(model="gemini-2.0-flash"),
        tts=deepgram.TTS(),
        vad=silero.VAD.load(),
    )
    
    # Start session
    await session.start(agent=agent, room=ctx.room)
    
    # Generate initial greeting
    await session.generate_reply(
        instructions=f"Hello  How can I help you with HR today?"
    )
    
    logger.info("HR assistant session started successfully")


async def entrypoint(ctx: JobContext):
    """
    Main entry point for HR assistant voice sessions
    
    Expected metadata fields:
    - employee_id: Identifier for the employee
    - knowledge_base_category: (Optional) Specific category to focus on
    """
    try:
        # Connect to room
        await ctx.connect()
        
        # Wait for participant
        participant = await ctx.wait_for_participant()
        
        # Parse metadata
        # Add transcript saving callback
    
        
        # Start the HR session
        await start_hr_session(ctx)
        
    except Exception as e:
        logger.exception("Error in main entrypoint")
        raise


# =====================================================
# FastAPI Routes (Optional)
# =====================================================

class SessionRequest(BaseModel):
    employee_id: str
    knowledge_base_category: Optional[str] = "uncategorized"


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "livekit-voice-agent"}


@app.post("/api/sessions/create")
async def create_session(request: SessionRequest):
    """API endpoint to create a new HR voice session"""
    try:
        # This would typically create a LiveKit room token
        # Implementation depends on your LiveKit setup
        return {
            "status": "success",
            "employee_id": request.employee_id,
            "category": request.knowledge_base_category,
            "message": "Session creation endpoint - implement LiveKit token generation"
        }
    except Exception as e:
        logger.exception("Failed to create session")
        return {"status": "error", "detail": str(e)}


# =====================================================
# CLI Runner
# =====================================================

if __name__ == "__main__":
    logger.info("Starting LiveKit Voice Agent worker...")
    opts = WorkerOptions(entrypoint_fnc=entrypoint)
    cli.run_app(opts)