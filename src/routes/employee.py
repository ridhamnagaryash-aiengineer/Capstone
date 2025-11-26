# src/routes/employee.py
from fastapi import APIRouter, HTTPException, Depends, Form, Request, Body
from typing import List
import json
from src.core.security import get_current_active_user
from src.schemas.chat import ChatMessageCreate, ChatResponse
from src.services.chat_service import chat_service
from src.models.user import User
from config.config import get_model_config
import logging

emp_router = APIRouter(prefix="/employee", tags=["Employee"])

# API for HR Chat
@emp_router.post("/chat", response_model=ChatResponse)
async def chat_with_hr(
    request: Request,
    message: str = Form(..., min_length=1, max_length=2000),
    user_metadata: str = Form(None)
):
    user_metadata = json.loads(user_metadata) if user_metadata else {}
    team_id = user_metadata.get("team_id")
    try:
        async with get_model_config() as config:
            # Get the team's model configuration
            team_config = await config.get_team_model_config(team_id)
            model = team_config["selected_model"]
            provider = team_config["provider"]
            provider_model = f"{provider}/{model}"
            model_config = team_config["config"]

            # Create LLM instance with the team's configuration
            llm_params = {
                "model": provider_model,
                **model_config  
            }
            auth_token = request.headers.get("Authorization")
            # llm_params.update({"auth_token": '123'})
    except Exception as e:
        logging.error(f"Error extracting attendees: {str(e)}")
        return []

    try:
        response_text, sources = await chat_service.process_chat_query(
            user_query=message,
            llm_params=llm_params
        )
        return ChatResponse(
            response=response_text,
            sources=sources,
            message_id=None
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
