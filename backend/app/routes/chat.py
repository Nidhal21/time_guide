from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import re
from app.models.db_config import get_db
from app.services.sql_agent import SQLAgent

router = APIRouter()

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    user_role: str = "student"
    user_class: str = None
    history: Optional[List[Message]] = []

class ChatResponse(BaseModel):
    response: str

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    agent = SQLAgent(db)
    
    # Build context from history (last 3 messages)
    context_messages = request.history[-3:] if request.history else []
    context_text = "\n".join([f"{msg.role}: {msg.content}" for msg in context_messages])
    
    # Combine context with current message
    full_question = f"{context_text}\nuser: {request.message}" if context_text else request.message
    
    response = agent.process_question(full_question)
    return ChatResponse(response=response)
