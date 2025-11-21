from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from livekit import api
import os
from dotenv import load_dotenv
import logging
import jwt
from pydantic import BaseModel
from typing import Optional

from src.core.database import get_db
from src.core.security import get_current_active_user
from src.models.user import User
from src.services.session_services import SessionService
from src.schemas.chat import ChatSessionResponse, ChatHistoryResponse, ChatMessageResponse
from typing import List

load_dotenv()
logger = logging.getLogger(__name__)

livekit_router = APIRouter(prefix="/livekit", tags=["LiveKit"])

# LiveKit configuration
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
ALGORITHM = os.getenv('ALGORITHM', 'HS256')

def get_current_user(token: str):
    """Extract user from JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # email: str = payload.get("sub")
        # payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return {
            "username": payload.get("username"),
            "email": payload.get("email"),
            "name": payload.get("name"),
            "grade": payload.get("grade"),
            "full_name": payload.get("full_name"),
            "role": payload.get("role")
        }
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    

class LiveKitTokenRequest(BaseModel):
    """Request model for LiveKit token generation"""
    participant_identity: str
    participant_name: str
    room_name: str
    metadata: Optional[dict] = None


class LiveKitTokenResponse(BaseModel):
    """Response model for LiveKit token"""
    token: str
    url: str
    room_name: str
    participant_identity: str


@livekit_router.post("/token", response_model=LiveKitTokenResponse)
async def create_livekit_token(
    request: LiveKitTokenRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate LiveKit access token for voice chat
    """
    try:
        # Validate LiveKit configuration
        if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LiveKit credentials not configured"
            )
        
        logger.info(f"Creating LiveKit token for user {current_user.username} in room {request.room_name}")
        
        # Prepare metadata
        import json
        metadata = request.metadata or {}
        metadata.update({
            "user_id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "grade": current_user.grade,
            "role": "user",
        })
        
        # Create token with NEW API (v2.x)
        token = api.AccessToken(
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
        ) \
        .with_identity(request.participant_identity) \
        .with_name(request.participant_name) \
        .with_metadata(json.dumps(metadata)) \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=request.room_name,
            can_publish=True,
            can_subscribe=True,
        ))
        
        # Generate JWT token
        jwt_token = token.to_jwt()
        
        logger.info(f"✅ LiveKit token created for {current_user.username}")
        
        return LiveKitTokenResponse(
            token=jwt_token,
            url=LIVEKIT_URL,
            room_name=request.room_name,
            participant_identity=request.participant_identity
        )
        
    except Exception as e:
        logger.error(f"Failed to create LiveKit token: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create LiveKit token: {str(e)}"
        )


@livekit_router.post("/agent/dispatch")
async def dispatch_agent(
    room_name: str,
    session_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Dispatch LiveKit agent to join room
    """
    try:
        import httpx
        import json
        
        # Agent service URL
        AGENT_SERVICE_URL = os.getenv("AGENT_SERVICE_URL", "http://localhost:8001")
        
        logger.info(f"Dispatching agent to room {room_name} for user {current_user.username}")
        
        # Prepare metadata for agent
        metadata = {
            "user_id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "session_id": session_id,
        }
        
        # Call agent dispatch endpoint
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{AGENT_SERVICE_URL}/dispatch",
                json={
                    "room_name": room_name,
                    "metadata": json.dumps(metadata),
                }
            )
            response.raise_for_status()
        
        logger.info(f"✅ Agent dispatched to room {room_name}")
        
        return {
            "success": True,
            "room_name": room_name,
            "message": "Agent dispatched successfully"
        }
        
    except httpx.HTTPError as e:
        logger.error(f"Failed to dispatch agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent service unavailable"
        )
    except Exception as e:
        logger.error(f"Error dispatching agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to dispatch agent: {str(e)}"
        )
    

@livekit_router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_sessions(
    session_type: str = None,  # 'text' or 'voice' or None for all
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all chat sessions for current user"""
    sessions = SessionService.get_user_sessions(
        db=db,
        user_id=current_user["user_id"],
        session_type=session_type
    )
    
    # Convert to response format
    response = []
    for session in sessions:
        message_count = len(session.messages)
        last_message = session.messages[-1].content if session.messages else ""
        
        response.append(ChatSessionResponse(
            id=session.id,
            session_id=session.session_id,
            title=session.title,
            is_active=session.is_active,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=message_count,
            last_message_preview=last_message[:100] if last_message else ""
        ))
    
    return response


@livekit_router.get("/sessions/{session_id}", response_model=ChatHistoryResponse)
async def get_session_history(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get full history for a specific session"""
    session_data = SessionService.get_session_with_messages(db=db, session_id=session_id)
    
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = session_data["session"]
    
    # Verify user owns this session
    if session.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    messages = [
        ChatMessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            retrieved_chunks=msg.retrieved_chunks,
            sources=msg.sources,
            created_at=msg.created_at
        )
        for msg in session_data["messages"]
    ]
    
    return ChatHistoryResponse(
        session=ChatSessionResponse(
            id=session.id,
            session_id=session.session_id,
            title=session.title,
            is_active=session.is_active,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=len(messages),
            last_message_preview=""
        ),
        messages=messages
    )


@livekit_router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a session"""
    session = SessionService.get_session(db=db, session_id=session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    db.delete(session)
    db.commit()
    
    return {"message": "Session deleted successfully"}