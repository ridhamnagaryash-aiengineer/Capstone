from livekit.agents import JobContext, cli, WorkerOptions, AgentSession, Agent, function_tool, RunContext
from livekit.plugins import google
from livekit import rtc
import asyncio
import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session as DBSession
from src.core.database import SessionLocal
from src.services.session_services import SessionService
from src.llm.lite_client import lite_client
from src.vector_db.milvus_client import milvus_client


logger = logging.getLogger(__name__)

# Store active sessions
active_sessions = {}


@function_tool
async def search_knowledge_bases(
    context: RunContext,
    query: str
):
    """Search all knowledge bases and return relevant context"""
    user_query = query 
    
    category_descriptions = {
        "payroll": """Payroll queries: Questions about salary, wages, tax deductions, 
        bonuses, compensation, pay slips, salary increments, pay schedules, or financial payments.""",
        
        "hr_policy": """HR Policy queries: Questions about leave policies, attendance rules, 
        company policies, employee handbook, code of conduct, performance reviews, benefits, 
        holidays, work hours, or HR procedures.""",
        
        "it_support": """IT Support queries: Questions about technical issues, software, 
        hardware, network access, passwords, IT systems, cybersecurity, computers, 
        laptops, or technical assistance.""",
        
        "facilities": """Facilities queries: Questions about office space, building maintenance, 
        parking, security, workspace allocation, meeting rooms, office supplies, 
        or infrastructure.""",
        
        "uncategorized": """General or unclear queries that don't fit other categories."""
    }
    
    categories_list = "\n".join([
        f"- {cat}: {desc}" 
        for cat, desc in category_descriptions.items()
    ])
    
    classification_prompt = f"""You are a query classification expert for an HR chatbot system.

Available Categories:
{categories_list}

Current Employee Query: {user_query}

Instructions:
1. Analyze the query carefully
2. Classify into ONE category: payroll, hr_policy, it_support, facilities, or uncategorized
3. Respond ONLY in this format:

Category: <category_name>
Confidence: <score>

Your response:"""
    
    try:
        # Classify query
        messages = [
            {"role": "system", "content": "You are a helpful HR assistant."},
            {"role": "user", "content": classification_prompt}
        ]
        response_text = lite_client.chat_completion(messages)
        logger.info(f"Classification result: {response_text}")
        
        # Extract category
        knowledge_base_category = "uncategorized"
        for line in response_text.split('\n'):
            if line.startswith('Category:'):
                knowledge_base_category = line.split(':', 1)[1].strip().lower()
                break
        
        # Generate embedding and search
        query_embedding = lite_client.embedding(user_query)
        retrieved_chunks = milvus_client.search(
            query_embedding=query_embedding,
            category=knowledge_base_category,
            top_k=5
        )
        
        category_name = knowledge_base_category.replace('_', ' ').title()
        
        if not retrieved_chunks:
            return (
                f"I couldn't find specific information about your query in our {category_name} documents. "
                f"Please contact the HR department directly for assistance."
            )
        
        # Build context
        context = ""
        for i, chunk in enumerate(retrieved_chunks, 1):
            context += f"\n\n[Source {i}: {chunk['filename']} - Category: {chunk['category']}]\n{chunk['text']}\n"
        
        # Generate response
        full_prompt = f"""You are an HR assistant specializing in {knowledge_base_category}.

Context from {category_name} Documents:
{context}

Employee Question: {user_query}

Provide a concise answer (2-3 sentences) based on the documents above. Answer in English only."""
        
        messages = [
            {"role": "system", "content": "You are a helpful HR assistant."},
            {"role": "user", "content": full_prompt}
        ]
        response_text = lite_client.chat_completion(messages)
        logger.info("Generated answer successfully")
        
        return response_text
        
    except Exception as e:
        logger.exception("Search knowledge base failed")
        return "I encountered an error searching for information. Please try again or contact HR directly."


async def entrypoint(ctx: JobContext):
    """Main agent entrypoint with session management"""
    
    # Parse metadata
    metadata = json.loads(ctx.job.metadata) if ctx.job.metadata else {}
    user_id = metadata.get("user_id", 0)
    username = metadata.get("username", "unknown")
    room_name = ctx.room.name
    
    logger.info(f"🚀 Agent starting for user {username} in room {room_name}")
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Create new chat session in database
        chat_session = SessionService.create_session(
            db=db,
            user_id=user_id,
            username=username,
            session_type="voice",
            livekit_room_name=room_name
        )
        
        session_id = chat_session.session_id
        logger.info(f"✅ Created chat session: {session_id}")
        
        # Store session info for tracking
        active_sessions[room_name] = {
            "session_id": session_id,
            "start_time": datetime.now(),
            "db": db,
        }
        
        # Create agent
        agent = Agent(
            instructions=(
                f"You are a professional HR voice assistant. "
                f"Session ID: {session_id}. "
                "CRITICAL RULES:\n"
                "1. ALWAYS respond in English language ONLY\n"
                "2. Always search queries using the search_knowledge_bases tool\n"
                "3. Keep responses concise and professional (2-3 sentences)"
            ),
            tools=[search_knowledge_bases],
        )
        
        # Create session
        session = AgentSession(
            llm=google.beta.realtime.RealtimeModel(
                model="gemini-2.0-flash-exp",
                voice="Puck",
                temperature=0.5,
                instructions="You are a helpful HR assistant. Always respond in English only.",
                language="en-US",
            ),
            preemptive_generation=True,
            user_away_timeout=30.0,
        )
        
        # FIXED: Use synchronous callbacks with asyncio.create_task for async operations
        def on_agent_speech_sync(msg):
            """Synchronous wrapper for agent speech"""
            logger.info(f"🤖 Agent: {msg.content[:100]}...")
            
            if room_name in active_sessions:
                session_data = active_sessions[room_name]
                
                # Create task for async database operation
                async def save_message():
                    try:
                        SessionService.add_message(
                            db=session_data["db"],
                            session_id=session_data["session_id"],
                            role="assistant",
                            content=msg.content,
                            message_type="voice_transcription"
                        )
                    except Exception as e:
                        logger.error(f"Failed to save agent message: {e}")
                
                asyncio.create_task(save_message())
        
        def on_user_speech_sync(msg):
            """Synchronous wrapper for user speech"""
            logger.info(f"👤 User: {msg.content[:100]}...")
            
            if room_name in active_sessions:
                session_data = active_sessions[room_name]
                
                # Create task for async database operation
                async def save_message():
                    try:
                        SessionService.add_message(
                            db=session_data["db"],
                            session_id=session_data["session_id"],
                            role="user",
                            content=msg.content,
                            message_type="voice_transcription"
                        )
                    except Exception as e:
                        logger.error(f"Failed to save user message: {e}")
                
                asyncio.create_task(save_message())
        
        # Register SYNCHRONOUS event handlers
        session.on("agent_speech_committed", on_agent_speech_sync)
        session.on("user_speech_committed", on_user_speech_sync)
        
        # Start session
        await session.start(agent=agent, room=ctx.room)
        
        # Set agent metadata
        try:
            await ctx.room.local_participant.set_metadata(
                json.dumps({
                    "role": "assistant",
                    "type": "agent",
                    "session_id": session_id,
                })
            )
        except Exception as e:
            logger.warning(f"Failed to set metadata: {e}")
        
        logger.info("✅ HR assistant session started successfully")
        
        # Greet user
        await session.generate_reply(
            instructions="Greet the user warmly in English and ask what HR queries they have regarding hr policy, leaves. Keep it brief."
        )
        
    except Exception as e:
        logger.error(f"❌ Error in agent entrypoint: {e}", exc_info=True)
        raise
    finally:
        # Cleanup on disconnect
        if room_name in active_sessions:
            session_data = active_sessions[room_name]
            
            # Calculate call duration
            duration = int((datetime.now() - session_data["start_time"]).total_seconds())
            
            # End session in database
            try:
                SessionService.end_session(
                    db=session_data["db"],
                    session_id=session_data["session_id"],
                    call_duration=duration
                )
                logger.info(f"✅ Session {session_data['session_id']} ended. Duration: {duration}s")
            except Exception as e:
                logger.error(f"Failed to end session: {e}")
            
            # Close database connection
            try:
                session_data["db"].close()
            except Exception as e:
                logger.error(f"Failed to close database: {e}")
            
            # Remove from active sessions
            del active_sessions[room_name]


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            load_threshold=0.9,
        )
    )
