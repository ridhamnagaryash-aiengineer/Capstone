# app/schemas/user.py
from pydantic import BaseModel
from typing import Optional


class Message(BaseModel):
    message: str
