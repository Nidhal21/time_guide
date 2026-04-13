from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional, Tuple
import re
import unicodedata

from app.models.db_config import get_db
from app.services.groq_service import groq_service
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


CLASS_PATTERN = re.compile(
    r"\b(?:\d\s*(?:(?:ING|TIC|LTIC|MP|MR)\s*[A-Z0-9\-]*\s*\d?|(?:GII|GEC|GT|IDSD|INFO|TELECOM)\s*\d)|\d(?:GII|GEC|GT|IDSD|INFO|TELECOM)\d)\b",
    re.IGNORECASE,
)
PROF_PATTERN = re.compile(
    r"\b(?:mr|mme|m\.|monsieur|madame)\s+([A-Za-zÀ-ÿ'\-]+(?:\s+[A-Za-zÀ-ÿ'\-]+){1,2})\b",
    re.IGNORECASE,
)
CLASS_SHORTHAND_CODES = {"GII", "GEC", "GT", "IDSD", "INFO", "TELECOM"}


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower().replace("'", " ")
    normalized = re.sub(r"[^\w\s/-]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    typo_fixes = {
        "ou ce trouve": "ou se trouve",
    }
    for source, target in typo_fixes.items():
        normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized)
    return normalized


def _extract_class_candidate(message: str) -> Optional[str]:
    q = (message or "").strip()
    if not q:
        return None

    match = re.search(
        r"\b(\d)\s*(ING|TIC|LTIC|MP|MR)\b(?:\s+([A-Z0-9\-]+))?(?:\s+([A-Z0-9\-]+))?(?:\s+(\d))?\b",
        q,
        flags=re.IGNORECASE,
    )
    if match:
        parts = [part for part in match.groups() if part]
        return re.sub(r"\s+", " ", " ".join([parts[0]] + [part.upper() for part in parts[1:]])).strip()

    match = re.search(r"\b(\d)\s*([A-Za-z\-]{2,10})\s*(\d)\b", q, flags=re.IGNORECASE)
    if match:
        year, middle, group = match.group(1), match.group(2).upper(), match.group(3)
        if middle in CLASS_SHORTHAND_CODES:
            return f"{year} ING {middle} {group}"
        return f"{year} {middle} {group}"

    match = re.search(r"\b(\d)(GII|GEC|GT|IDSD|INFO|TELECOM)(\d)\b", q, flags=re.IGNORECASE)
    if match:
        year, specialty, group = match.group(1), match.group(2).upper(), match.group(3)
        return f"{year} ING {specialty} {group}"

    return None


def _extract_last_class(history: list) -> Optional[str]:
    for msg in reversed(history or []):
        if msg.role == "user":
            class_candidate = _extract_class_candidate(msg.content)
            if class_candidate:
                return class_candidate
    return None


def _extract_last_professor(history: list) -> Optional[str]:
    for msg in reversed(history or []):
        if msg.role == "user":
            match = PROF_PATTERN.search(msg.content or "")
            if match:
                return re.sub(r"\s+", " ", match.group(1)).strip()
    return None


def _extract_pending_request(history: list) -> Optional[Tuple[str, str, str]]:
    if not history or len(history) < 2:
        return None

    class_triggers = ["quelle est votre classe", "pour quelle classe"]
    professor_triggers = [
        "quel professeur",
        "voulez-vous dire",
        "je ne suis pas sur du professeur",
        "est ambigu",
        "ressemble a",
        "est proche de plusieurs professeurs",
    ]

    for i in range(len(history) - 1, -1, -1):
        msg = history[i]
        if msg.role != "assistant":
            continue
        content = (msg.content or "").lower()
        if any(trigger in content for trigger in class_triggers):
            if i > 0 and history[i - 1].role == "user":
                return ("class", history[i - 1].content, msg.content)
            break
        if any(trigger in content for trigger in professor_triggers):
            if i > 0 and history[i - 1].role == "user":
                return ("professor", history[i - 1].content, msg.content)
            break
    return None


def _message_has_class_reference(message: str) -> bool:
    return bool(_extract_class_candidate(message))


def _message_has_prof_reference(message: str) -> bool:
    return bool(PROF_PATTERN.search(message or ""))


def _normalize_for_intent(message: str) -> str:
    return _normalize_text(message)


def _is_direct_university_question(message: str) -> bool:
    q = _normalize_for_intent(message)
    if not q:
        return False

    study_plan_markers = [
        "plan d etude",
        "plan de etude",
        "plan detude",
        "plans d etude",
        "plans de etude",
        "plans detudes",
        "plan des etudes",
        "plans des etudes",
        "programme d etude",
        "programme des etudes",
        "curriculum",
    ]
    if any(marker in q for marker in study_plan_markers):
        return True

    absence_markers = [
        "avis d absence",
        "avis dabsence",
        "lavis d absence",
        "lavis dabsence",
        "absence",
        "absences",
        "prof absent",
        "profs absents",
        "enseignants absents",
        "est ce que le prof",
        "professeur absent",
        "extranet",
    ]
    if any(marker in q for marker in absence_markers):
        return True

    general_markers = [
        "actualite",
        "actualites",
        "enetcom",
        "ecole",
        "universite",
        "departement",
        "formation",
        "master",
        "licence",
        "doctorat",
        "contact",
    ]
    return any(marker in q for marker in general_markers)


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
        "j ai quoi",
        "jai quoi",
        "andi",
        "ghedwa",
        "tawa",
    ]
    if any(marker in q for marker in schedule_markers):
        return True

    day_markers = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche", "aujourd", "demain", "hier"]
    if _message_has_class_reference(message) and any(day in q for day in day_markers):
        return True
    return "classe" in q and any(day in q for day in day_markers)


def _likely_class_location_question(message: str) -> bool:
    q = _normalize_for_intent(message)
    if not q:
        return False
    location_markers = ["ou se trouve", "ou est", "dans quelle salle", "salle"]
    return ("classe" in q or "ma classe" in q or "mon classe" in q) and any(marker in q for marker in location_markers)


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


def _looks_like_fresh_request(message: str) -> bool:
    normalized = _normalize_for_intent(message)
    if not normalized:
        return False
    if normalized in {"oui", "non", "ok", "daccord", "d accord", "yes", "no"}:
        return False
    return _likely_schedule_question(message) or _likely_professor_followup(message) or _likely_class_location_question(message)


def _extract_confirmed_professor(message: str, assistant_message: str) -> Optional[str]:
    user_reply = re.sub(r"\s+", " ", (message or "")).strip()
    if not user_reply:
        return None

    if user_reply.lower() in {"oui", "yes", "ok", "daccord", "d'accord"}:
        assistant_text = assistant_message or ""
        resembles_match = re.search(r"ressemble a\s+'([^']+)'", assistant_text, flags=re.IGNORECASE)
        if resembles_match:
            return resembles_match.group(1).strip()
        direct_match = re.search(r"professeur\s+'([^']+)'", assistant_text, flags=re.IGNORECASE)
        if direct_match:
            return direct_match.group(1).strip()
        quoted = re.findall(r"'([^']+)'", assistant_text)
        if len(quoted) == 1:
            return quoted[0].strip()
        return None

    return user_reply


def _replace_professor_in_question(agent: SQLAgent, original_question: str, professor_name: str) -> str:
    original_question = re.sub(r"\s+", " ", (original_question or "")).strip()
    professor_name = re.sub(r"\s+", " ", (professor_name or "")).strip()
    if not original_question or not professor_name:
        return original_question or professor_name

    normalized = _normalize_for_intent(original_question)
    day_suffix = ""
    if "demain" in normalized:
        day_suffix = " demain"
    elif "aujourd" in normalized:
        day_suffix = " aujourd'hui"
    elif "hier" in normalized:
        day_suffix = " hier"
    if _likely_schedule_question(original_question):
        return f"emploi du temps de {professor_name}{day_suffix}"
    if "ou se trouve" in normalized or "dans quelle salle" in normalized or "ou est" in normalized:
        return f"ou se trouve {professor_name}{day_suffix}"
    if "quelle classe" in normalized or "dans quelle classe" in normalized:
        return f"dans quelle classe se trouve {professor_name}{day_suffix}"
    if "quel cours" in normalized or "quelle matiere" in normalized:
        return f"quel cours fait {professor_name}{day_suffix}"
    if "a cours" in normalized:
        return f"{professor_name} a cours{day_suffix or ' aujourd hui'}"

    existing_prof = agent._extract_schedule_prof_candidate(original_question) or agent._extract_prof_candidate(original_question)
    if existing_prof:
        return re.sub(re.escape(existing_prof), professor_name, original_question, count=1, flags=re.IGNORECASE)

    return f"{original_question} pour le professeur {professor_name}"


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    agent = SQLAgent(db)
    user_class = _extract_class_candidate(request.user_class or "") or re.sub(r"\s+", " ", (request.user_class or "")).strip() or None

    if _is_direct_university_question(request.message):
        response = university_info_service.answer_question(request.message)
        return ChatResponse(response=response)

    pending_request = _extract_pending_request(request.history)
    if pending_request and _looks_like_fresh_request(request.message):
        pending_request = None

    if pending_request:
        request_kind, original_question, assistant_message = pending_request
        if request_kind == "class":
            class_value = user_class or _extract_class_candidate(request.message) or request.message
            full_question = f"{original_question} pour la classe {class_value}"
        else:
            selected_professor = _extract_confirmed_professor(request.message, assistant_message)
            full_question = _replace_professor_in_question(agent, original_question, selected_professor or request.message)
    else:
        if user_class and not _message_has_class_reference(request.message) and (_likely_schedule_question(request.message) or _likely_class_location_question(request.message)):
            full_question = request.message if _message_has_class_reference(request.message) else f"{request.message} pour la classe {user_class}"
        else:
            last_class = _extract_last_class(request.history) or user_class
            if last_class and not _message_has_class_reference(request.message) and (_likely_schedule_question(request.message) or _likely_class_location_question(request.message)):
                full_question = request.message if _message_has_class_reference(request.message) else f"{request.message} pour la classe {last_class}"
            else:
                last_professor = _extract_last_professor(request.history)
                if last_professor and not _message_has_prof_reference(request.message) and _likely_professor_followup(request.message):
                    full_question = f"{request.message} pour le professeur {last_professor}"
                else:
                    if _looks_like_fresh_request(request.message) and (
                        _message_has_class_reference(request.message) or _message_has_prof_reference(request.message)
                    ):
                        full_question = request.message
                    else:
                        context_messages = request.history[-3:] if request.history else []
                        context_text = "\n".join([f"{msg.role}: {msg.content}" for msg in context_messages])
                        full_question = f"{context_text}\nuser: {request.message}" if context_text else request.message

    if not pending_request:
        conversational_response = groq_service.maybe_answer_conversational_message(
            request.message,
            request.history,
            user_class=user_class,
        )
        if conversational_response:
            return ChatResponse(response=conversational_response)

    response = agent.process_question(full_question)
    return ChatResponse(response=response)
