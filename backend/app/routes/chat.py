from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
import re

from app.models.db_config import get_db
from app.services.groq_service import groq_service
from app.services.intent_router import ExecutionTarget, IntentRouter
from app.services.sql_agent import SQLAgent
from app.services.university_info_service import university_info_service

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
    intent_router = IntentRouter(groq_service, db=db)
    user_class = re.sub(r"\s+", " ", (request.user_class or "")).strip() or None

    decision = intent_router.route(
        message=request.message,
        history=request.history,
        user_class=user_class,
        agent=agent,
    )
    print(f"Intent router decision: {decision.to_dict()}")

    if decision.execution_target == ExecutionTarget.UNIVERSITY_SERVICE.value:
        response = university_info_service.answer_question(decision.full_question or request.message)
        return ChatResponse(response=response)

    if decision.execution_target == ExecutionTarget.CLARIFICATION.value:
        return ChatResponse(response=decision.direct_response or "")

    if decision.execution_target == ExecutionTarget.SMALLTALK.value:
        response = groq_service.build_smalltalk_response(request.message, user_class=user_class)
        return ChatResponse(response=response)

    if decision.execution_target == ExecutionTarget.OUT_OF_SCOPE.value:
        response = groq_service.build_out_of_scope_response(
            request.message,
            request.history,
            user_class=user_class,
        )
        return ChatResponse(response=response)

    response = agent.process_routed_question(
        decision.intent,
        decision.full_question or request.message,
        confidence=decision.confidence,
    )
    return ChatResponse(response=response)
