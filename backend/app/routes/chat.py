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

CLASS_PATTERN = re.compile(
    r"\b(\d\s*(?:ING|TIC|LTIC|MP|MR)\s*[A-Z0-9\-]*\s*\d?)\b",
    re.IGNORECASE,
)
PROF_PATTERN = re.compile(
    r"\b(?:mr|mme|m\.|monsieur|madame)\s+([A-Za-zÀ-ÿ'\-]+(?:\s+[A-Za-zÀ-ÿ'\-]+){1,2})\b",
    re.IGNORECASE,
)

def _extract_last_class(history: list) -> Optional[str]:
    """Scan history in reverse to find the last class mentioned by the user."""
    for msg in reversed(history or []):
        if msg.role == "user":
            m = CLASS_PATTERN.search(msg.content)
            if m:
                return re.sub(r"\s+", " ", m.group(0)).strip()
    return None

def _extract_last_professor(history: list) -> Optional[str]:
    for msg in reversed(history or []):
        if msg.role == "user":
            m = PROF_PATTERN.search(msg.content or "")
            if m:
                return re.sub(r"\s+", " ", m.group(1)).strip()
    return None

def _extract_pending_intent(history: list) -> Optional[str]:
    """If the last assistant message was asking for a class/prof, return the original user question."""
    if not history or len(history) < 2:
        return None
    last_assistant = next((m.content for m in reversed(history) if m.role == "assistant"), None)
    if not last_assistant:
        return None
    ask_triggers = ["quelle est votre classe", "quel professeur", "pour quelle classe"]
    if any(t in last_assistant.lower() for t in ask_triggers):
        for i in range(len(history) - 1, -1, -1):
            if history[i].role == "assistant" and any(t in history[i].content.lower() for t in ask_triggers):
                if i > 0 and history[i - 1].role == "user":
                    return history[i - 1].content
    return None


def _message_has_class_reference(message: str) -> bool:
    content = (message or "").lower()
    return bool(CLASS_PATTERN.search(message or "")) or "ma classe" in content

def _message_has_prof_reference(message: str) -> bool:
    return bool(PROF_PATTERN.search(message or ""))

def _normalize_for_intent(message: str) -> str:
    content = (message or "").lower()
    content = re.sub(r"[^\w\s']", " ", content)
    content = re.sub(r"\s+", " ", content).strip()
    return content

def _likely_schedule_question(message: str) -> bool:
    q = _normalize_for_intent(message)
    if not q:
        return False

    schedule_markers = [
        "emploi du temps",
        "emploi",
        "edt",
        "planning",
        "horaire",
        "cours",
        "seance",
        "matiere",
        "tp",
        "td",
    ]
    if any(marker in q for marker in schedule_markers):
        return True

    day_markers = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche", "aujourd", "demain", "hier"]
    return "classe" in q and any(day in q for day in day_markers)

def _likely_professor_followup(message: str) -> bool:
    q = _normalize_for_intent(message)
    if not q:
        return False
    markers = [
        "ou est",
        "ou se trouve",
        "dans quelle salle",
        "quel cours",
        "quelle matiere",
        "enseigne",
        "a cours",
        "est ce qu il a cours",
        "est ce qu elle a cours",
    ]
    return any(marker in q for marker in markers)

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    agent = SQLAgent(db)
    user_class = re.sub(r"\s+", " ", (request.user_class or "")).strip() or None

    # If bot just asked for class and user replied with one
    pending_intent = _extract_pending_intent(request.history)
    if pending_intent:
        class_value = user_class or request.message
        full_question = f"{pending_intent} pour la classe {class_value}"
    else:
        # Prefer explicit user_class from the request, then recent history.
        if user_class and not CLASS_PATTERN.search(request.message) and _likely_schedule_question(request.message):
            full_question = request.message if _message_has_class_reference(request.message) else f"{request.message} pour la classe {user_class}"
        else:
            # Inject last known class into follow-up questions that lack one
            last_class = _extract_last_class(request.history)
            if last_class and not CLASS_PATTERN.search(request.message) and _likely_schedule_question(request.message):
                full_question = request.message if _message_has_class_reference(request.message) else f"{request.message} pour la classe {last_class}"
            else:
                last_professor = _extract_last_professor(request.history)
                if last_professor and not _message_has_prof_reference(request.message) and _likely_professor_followup(request.message):
                    full_question = f"{request.message} pour le professeur {last_professor}"
                else:
                    context_messages = request.history[-3:] if request.history else []
                    context_text = "\n".join([f"{msg.role}: {msg.content}" for msg in context_messages])
                    full_question = f"{context_text}\nuser: {request.message}" if context_text else request.message

    response = agent.process_question(full_question)
    return ChatResponse(response=response)
