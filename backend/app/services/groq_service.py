from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional

import requests

SUSPICIOUS_MOJIBAKE_CHARS = ("Ã", "Â", "â", "€", "™", "œ", "�")
DAY_DISPLAY_ORDER = {
    "lundi": 1,
    "mardi": 2,
    "mercredi": 3,
    "jeudi": 4,
    "vendredi": 5,
    "samedi": 6,
    "dimanche": 7,
}
FRENCH_DAY_NAMES = tuple(DAY_DISPLAY_ORDER.keys())
CONVERSATION_MARKERS = (
    "bonjour",
    "bonsoir",
    "salut",
    "slt",
    "coucou",
    "hello",
    "hi",
    "hey",
    "salam",
    "slm",
    "aaslema",
    "aslema",
    "asslema",
    "ahla",
    "marhba",
    "mar7ba",
    "sbah khir",
    "sbah lkhir",
    "sbeh lkhir",
    "sbeh el khir",
    "msa lkhir",
    "masa lkhir",
    "cc",
)
THANKS_MARKERS = (
    "merci",
    "thanks",
    "thank you",
    "aaychek",
    "aychek",
    "3aychek",
    "barak allah fik",
)
HELP_MARKERS = (
    "aide",
    "help",
    "tu peux faire quoi",
    "que peux tu faire",
    "qu est ce que tu peux faire",
    "qui es tu",
    "t es qui",
)
QUESTION_STARTERS = (
    "quel",
    "quelle",
    "quels",
    "quelles",
    "combien",
    "comment",
    "pourquoi",
    "ou",
    "où",
    "c est quoi",
    "qu est ce que",
    "est ce que",
)
ACADEMIC_MARKERS = (
    "emploi",
    "edt",
    "planning",
    "horaire",
    "cours",
    "seance",
    "matiere",
    "prof",
    "professeur",
    "enseign",
    "classe",
    "salle",
    "semestre",
    "periode",
    "vacance",
    "ferie",
    "examen",
    "ds",
    "rattrap",
    "revision",
    "enetcom",
    "universite",
    "ecole",
    "formation",
    "plan",
    "etude",
    "etudes",
    "programme",
    "curriculum",
    "licence",
    "master",
    "mastere",
    "doctorat",
    "departement",
    "contact",
    "adresse",
    "telephone",
    "mail",
    "email",
    "absence",
    "absences",
    "extranet",
    "actualite",
    "news",
    "bibliotheque",
    "club",
    "stage",
    "pfe",
)

class GroqService:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"
        self._session = requests.Session()

        if not self.api_key:
            print("Warning: GROQ_API_KEY not found in environment")
            self.enabled = False
        else:
            self.enabled = True
            print(f"Groq API initialized with {self.model}")

    def _handle_auth_error(self, response: requests.Response, context: str) -> None:
        if response.status_code != 401:
            return
        print(f"{context}: invalid API key detected, disabling Groq service until restart.")
        self.enabled = False

    # --- Helpers ---

    def _repair_text_encoding(self, value: str) -> str:
        if not value:
            return ""

        repaired = value.replace("\xa0", " ").replace("�", "'").replace("`", "'")
        if any(ch in repaired for ch in SUSPICIOUS_MOJIBAKE_CHARS):
            for source_encoding in ("latin1", "cp1252"):
                try:
                    candidate = repaired.encode(source_encoding).decode("utf-8")
                except Exception:
                    continue
                if candidate and candidate != repaired:
                    repaired = candidate
                    break
        return repaired

    def _normalize_text(self, text: str) -> str:
        repaired = self._repair_text_encoding(text or "")
        normalized = unicodedata.normalize("NFKD", repaired)
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = normalized.replace("'", " ")
        normalized = re.sub(r"[^a-zA-Z0-9\s/-]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        normalized = normalized.lower()
        typo_fixes = {
            "maintement": "maintenant",
            "maintenent": "maintenant",
            "disponnible": "disponible",
            "feriee": "ferie",
            "feries": "ferie",
            "lemploi": "emploi",
            "l emploi": "emploi",
        }
        for source, target in typo_fixes.items():
            normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized)
        return normalized

    def _collapse_repeated_letters(self, value: str) -> str:
        return re.sub(r"([a-z])\1{1,}", r"\1", value or "")

    def _conversation_normalize(self, text: str) -> str:
        q = self._normalize_text(text)
        tokens = [self._collapse_repeated_letters(token) for token in q.split()]
        return " ".join(tokens).strip()

    def _contains_marker(self, normalized_text: str, markers: tuple[str, ...]) -> bool:
        normalized_markers = [self._conversation_normalize(marker) for marker in markers]
        return any(
            marker == normalized_text
            or normalized_text.startswith(f"{marker} ")
            or f" {marker} " in f" {normalized_text} "
            for marker in normalized_markers
        )

    def _history_as_text(self, history: Optional[list], limit: int = 4) -> str:
        if not history:
            return ""

        lines: List[str] = []
        for item in history[-limit:]:
            role = getattr(item, "role", None)
            content = getattr(item, "content", None)
            if isinstance(item, dict):
                role = item.get("role", role)
                content = item.get("content", content)
            role = str(role or "user").strip()
            content = str(content or "").strip()
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _is_obvious_academic_request(self, message: str) -> bool:
        q = self._normalize_text(message)
        if not q:
            return False

        if any(marker in q for marker in ACADEMIC_MARKERS):
            return True
        if any(day_name in q for day_name in FRENCH_DAY_NAMES):
            return True
        if any(marker in q for marker in ["aujourd", "demain", "hier", "maintenant", "actuellement"]):
            return True
        if re.search(r"\b\d\s*(ing|tic|ltic|mp|mr)\b", q):
            return True
        if re.search(r"\b(?:mr|mme|m|monsieur|madame|dr)\s+[a-z]", q):
            return True
        if re.search(r"\b[a-z]{1,6}\s*0?\d{1,2}\b", q) and "salle" in q:
            return True
        return False

    def is_obvious_academic_request(self, message: str) -> bool:
        return self._is_obvious_academic_request(message)

    def _is_simple_conversation(self, message: str) -> bool:
        q = self._conversation_normalize(message)
        if not q:
            return True

        compact = q.replace(" ", "")
        tokens = q.split()
        if compact in {"cv", "cava"} or "cv" in tokens or "cava" in tokens:
            return True
        if self._contains_marker(q, CONVERSATION_MARKERS):
            return True
        if self._contains_marker(q, THANKS_MARKERS):
            return True
        if self._contains_marker(q, HELP_MARKERS):
            return True
        return False

    def is_simple_conversation(self, message: str) -> bool:
        return self._is_simple_conversation(message)

    def _classify_message_mode(self, message: str, history: Optional[list] = None) -> Optional[str]:
        if not self.enabled:
            return None

        history_text = self._history_as_text(history)
        prompt = f"""Classify the last user message for an ENET'Com assistant.

Return exactly one label:
- NON_ACADEMIC: greeting, thanks, casual talk, asking what the assistant can do, or any request outside ENET'Com scope
- ACADEMIC: anything about timetable, classes, rooms, teachers, exams, holidays, ENET'Com information, news, contact, departments, studies, or student services

If the user message could reasonably be an academic request even with informal wording, return ACADEMIC.

Examples:
- "bonjour" -> NON_ACADEMIC
- "salut cv" -> NON_ACADEMIC
- "merci beaucoup" -> NON_ACADEMIC
- "tu peux m'aider ?" -> NON_ACADEMIC
- "j'ai quoi demain" -> ACADEMIC
- "ou est mr ben amor" -> ACADEMIC
- "salle libre maintenant" -> ACADEMIC
- "quelles sont les actualites" -> ACADEMIC
- "quel est le prix de l'or" -> NON_ACADEMIC

Recent history:
{history_text or "None"}

Last user message:
{message}
"""

        response = self._post_with_retry(
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You classify requests for an ENET'Com assistant. Return exactly one label: ACADEMIC or NON_ACADEMIC.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.0,
                "max_tokens": 10,
            },
            timeout=15,
        )
        if response is None or response.status_code != 200:
            if response is not None:
                self._handle_auth_error(response, "Groq intent classification error")
                print(f"Groq intent classification error: {response.status_code} - {response.text}")
            return None

        payload = self._safe_json(response)
        if not payload:
            return None

        raw = (payload.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip().upper()
        if "ACADEMIC" in raw:
            return "ACADEMIC"
        if "NON_ACADEMIC" in raw:
            return "NON_ACADEMIC"
        return None

    def _classify_assistant_intent(self, message: str, history: Optional[list] = None) -> Optional[str]:
        if not self.enabled:
            return None

        history_text = self._history_as_text(history)
        prompt = f"""Classify the intent of the last user message for an ENET'Com university assistant.

Return exactly ONE label from these options:
- GREETING: casual greetings, politeness, thanks, or meta-questions about what the assistant can do
- TIMETABLE: questions about class schedules, professor schedules, room availability, course timing, academic calendar events, or any schedule-related inquiry
- ENETCOM_INFO: questions about institutional information including departments, contact details, study programs, clubs, internships, PFE projects, university services, or official ENET'Com details
- OUT_OF_SCOPE: requests completely unrelated to ENET'Com or the assistant's purpose

Understanding rules:
1. Parse multilingual input: The message may be in French, Arabic, English, or mixed.
2. Tolerate bad writing: Users may write with typos, misspellings, missing accents, abbreviations, slang, Tunisian Darija, Arabizi, or poor grammar.
3. Infer missing context: Use the recent conversation history to understand incomplete follow-ups or pronouns.
4. Combine intent and real request: If the message mixes a greeting with an actual ENET'Com request, prioritize the real request, not GREETING.
5. Disambiguate TIMETABLE vs ENETCOM_INFO: Use TIMETABLE only when the core intent is about schedules, timing, rooms, or professors' classes. Otherwise use ENETCOM_INFO.

Return only the one-word label, nothing else.

Recent history:
{history_text or "None"}

Last user message:
{message}
"""

        response = self._post_with_retry(
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert multilingual intent classifier for a university assistant. You understand French, Arabic, English, and code-mixed messages. You handle typos, bad spelling, abbreviations, slang, and poor grammar. You deeply understand user intent despite imperfect writing. Always classify accurately and return only one label from the four categories provided.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.0,
                "max_tokens": 15,
            },
            timeout=15,
        )
        if response is None or response.status_code != 200:
            if response is not None:
                self._handle_auth_error(response, "Groq assistant intent classification error")
                print(f"Groq assistant intent classification error: {response.status_code} - {response.text}")
            return None

        payload = self._safe_json(response)
        if not payload:
            return None

        raw = (payload.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip().upper()
        for label in ("GREETING", "TIMETABLE", "ENETCOM_INFO", "OUT_OF_SCOPE"):
            if label in raw:
                return label
        return None

    def classify_assistant_intent(self, message: str, history: Optional[list] = None) -> Optional[str]:
        return self._classify_assistant_intent(message, history)

    def _extract_json_object(self, raw: str) -> Optional[Dict[str, Any]]:
        text = (raw or "").strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start:end + 1])
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    def _analyze_user_message(self, message: str, history: Optional[list] = None) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None

        history_text = self._history_as_text(history)
        prompt = f"""You are a powerful multilingual query analyzer for an ENET'Com university assistant system.

Core mission:
- Understand the MEANING of user queries, not literal spelling or grammar.
- Accept input in French, Arabic, English, Tunisian Darija, Arabizi/Franco-Arabic, or mixtures of these languages.
- Tolerate all forms of bad writing: typos, missing accents, abbreviations, slang, phonetic spelling, merged words, repeated letters, incomplete sentences, or casual grammar.
- Recover intended meaning from context, recent conversation history, and reasonable inference.
- Return exactly one JSON object that captures the user's true intent and what information they need.

ENET'Com domain scope:
- Schedule and timetable queries: any question about when classes happen, professor availability, room bookings, course timing
- Location queries: where professors are, where classes meet, which rooms are available
- Calendar queries: academic dates, holidays, exam periods, revision times, important dates
- Institutional queries: university services, study programs, departments, club information, internship details, PFE projects, official contact information, university news
- Students and staff: conversations about students, teacher schedules, class assignments
- Conversational: greetings, thanks, general questions about assistant capabilities

Valid intent values:
- GREETING
- CLASS_SCHEDULE
- CLASS_LOCATION
- PROF_SCHEDULE
- PROF_LOCATION
- PROF_CLASS
- PROF_CURRENT_COURSE
- PROF_HAS_COURSE
- ROOM_CURRENT_TEACHER
- ROOM_SCHEDULE
- AVAILABLE_ROOMS
- ENETCOM_INFO
- CALENDAR
- ALL_CLASSES
- OUT_OF_SCOPE
- UNKNOWN

Valid answer_source values:
- DATABASE
- UNIVERSITY_SITE
- SMALLTALK
- OUT_OF_SCOPE

Decision rules:
- Use recent history only to resolve omitted references or short follow-ups.
- If the latest message contains both small talk and a real request, choose the real request.
- Treat Tunisian Arabic, Arabizi, and mixed-language phrasing as semantically valid user language, not as noise.
- If the request is timetable/room/professor/class related, answer_source must be DATABASE.
- If the request is about holidays, vacations, exams, revision periods, or academic dates, intent must be CALENDAR and answer_source must be DATABASE.
- If the request is about official ENET'Com information, answer_source must be UNIVERSITY_SITE.
- If the request is casual conversation, answer_source must be SMALLTALK.
- If unrelated to ENET'Com, answer_source must be OUT_OF_SCOPE.

Intent rules:
- ROOM_CURRENT_TEACHER: user asks who teaches in a room now/currently.
- ROOM_SCHEDULE: user asks for the timetable/schedule of a room.
- AVAILABLE_ROOMS: user asks which rooms are free/available.
- CLASS_LOCATION: user asks where a class is located.
- PROF_LOCATION: user asks where a professor is located.
- PROF_CLASS: user asks which class a professor teaches or where that professor is teaching.
- PROF_CURRENT_COURSE: user asks what course a professor is teaching now.
- PROF_HAS_COURSE: user asks whether a professor has class/course on a given day/time.
- CALENDAR: holidays, exams, revision periods, academic dates.
- ENETCOM_INFO: institutional information outside the calendar.

Entity extraction rules:
- class_name: Extract only when the user is clearly asking about a specific class, group, or cohort. Be flexible with formatting variations and abbreviations.
- professor_name: Extract only when the user is asking about a specific person or teacher. Handle titles (Mr, Ms, Dr) and first/last name variations.
- room_name: Extract only when asking about a specific room or physical location. Accept all formatting variations.
- day_hint: Extract when the message references timing (today, tomorrow, Monday, next week, etc.) in any language or casual variation.
- time_hint: Extract when asking about specific clock times or time periods.
- university_topic: Extract when asking about institutional information (contact, programs, services, etc.).

Strict negative rules:
- Never invent a class, professor, room, or topic unsupported by the latest message plus necessary context.
- Never copy an entity from history if the new message points to a different target.
- For GREETING or OUT_OF_SCOPE, all entity fields must be null and standalone_query must be null.
- Never output professor_name if the request only supports a room or class target.
- Never output room_name if the request only supports a professor or class target.
- Never output class_name if the request only supports a professor or room target.
- Never choose a class-oriented interpretation when the target clearly looks like a person name.
- Never ask for a class implicitly if a professor_name is already recoverable from the message.
- Never classify holidays, vacances, exam dates, or revision periods as ENETCOM_INFO when they are calendar-related.

Ambiguity rules:
- If a timetable request is ambiguous, prefer:
  - PROF_* when the target looks like a person's name
  - ROOM_* when the target looks like a room code
  - CLASS_* when the target looks like a class/group code
- If the exact subtype is uncertain but the request is clearly timetable-related, choose the closest DATABASE intent and lower confidence.
- Prefer a low-confidence meaningful ENET'Com interpretation over OUT_OF_SCOPE when the intended meaning is reasonably recoverable.

Normalization rules:
- standalone_query: Rewrite the user's query as clean, grammatically correct French when it contains an actual ENET'Com request.
- PURPOSE: Clean up typos, abbreviations, slang, and bad grammar while preserving the original meaning.
- Always normalize to standard French vocabulary and spelling.
- Convert Tunisian/Arabizi wording into clear French meaning when possible, while preserving the user's real target and timeframe.
- Include resolved entities (class name, professor name, room, timing) in the normalized query.
- For DATABASE intents, prefer short canonical French forms such as:
  - "emploi du temps de <professeur>"
  - "emploi du temps de <classe>"
  - "emploi du temps de salle <salle>"
  - "ou se trouve <professeur>"
  - "dans quelle classe se trouve <professeur>"
  - "quels sont les examens prevus"
  - "quelles sont les vacances prevues"
- If the original message is just greeting, thanks, or completely out-of-scope: set standalone_query to null.

Confidence scoring:
- confidence: Floating point 0.0 to 1.0 representing how confident you are in the interpretation.
- 0.95-1.0: Message is crystal clear with no ambiguity.
- 0.7-0.95: Message is clear but required normalization or context inference.
- 0.5-0.7: Message is understandable but ambiguous or required significant normalization.
- 0.3-0.5: Message requires educated guessing based on context.
- Prefer confident meaningful interpretation over OUT_OF_SCOPE when possible.

Return only this JSON schema:
{{
  "intent": "ONE_OF_THE_VALUES_ABOVE",
  "answer_source": "DATABASE_OR_UNIVERSITY_SITE_OR_SMALLTALK_OR_OUT_OF_SCOPE",
  "confidence": 0.0,
  "standalone_query": null,
  "class_name": null,
  "professor_name": null,
  "room_name": null,
  "day_hint": null,
  "time_hint": null,
  "university_topic": null
}}

Recent history:
{history_text or "None"}

Last user message:
{message}
"""

        response = self._post_with_retry(
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a world-class multilingual query understanding system designed for a university timetable assistant. You understand queries in French, Arabic, English, and mixed languages. You expertly handle bad spelling, typos, abbreviations, slang, incomplete sentences—like ChatGPT or Claude. Your job is to understand what users really want when they ask about university timetables, professor schedules, room availability, or institutional information, regardless of how they write it. Extract the true intent and entities from messy, informal, or misspelled input. Return valid JSON with the exact schema requested.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.0,
                "max_tokens": 400,
                "response_format": {"type": "json_object"},
            },
            timeout=20,
        )
        if response is None or response.status_code != 200:
            if response is not None:
                self._handle_auth_error(response, "Groq structured analysis error")
                print(f"Groq structured analysis error: {response.status_code} - {response.text}")
            return None

        payload = self._safe_json(response)
        if not payload:
            return None

        raw = (payload.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
        parsed = self._extract_json_object(raw)
        if not parsed:
            return None

        intent = str(parsed.get("intent") or "").strip().upper()
        if not intent:
            return None
        parsed["intent"] = intent

        try:
            parsed["confidence"] = float(parsed.get("confidence", 0.0) or 0.0)
        except Exception:
            parsed["confidence"] = 0.0
        parsed["confidence"] = max(0.0, min(1.0, parsed["confidence"]))

        parsed["answer_source"] = str(parsed.get("answer_source") or "").strip().upper() or None

        for field in ("standalone_query", "class_name", "professor_name", "room_name", "day_hint", "time_hint", "university_topic"):
            value = parsed.get(field)
            parsed[field] = str(value).strip() if value not in (None, "", "null") else None

        return parsed

    def analyze_user_message(self, message: str, history: Optional[list] = None) -> Optional[Dict[str, Any]]:
        return self._analyze_user_message(message, history)

    def classify_message_mode(self, message: str, history: Optional[list] = None) -> Optional[str]:
        return self._classify_message_mode(message, history)

    def _fallback_conversational_response(self, message: str, user_class: Optional[str] = None) -> str:
        q = self._conversation_normalize(message)
        class_hint = f" Votre classe actuelle est {user_class}." if user_class else ""
        greeting_detected = self._contains_marker(q, CONVERSATION_MARKERS)
        thanks_detected = self._contains_marker(q, THANKS_MARKERS)
        help_detected = self._contains_marker(q, HELP_MARKERS)
        tokens = q.split()
        status_detected = (
            "ca va" in q
            or "comment vas tu" in q
            or "comment va tu" in q
            or q.replace(" ", "") in {"cv", "cava", "commentvastu"}
            or "cv" in tokens
            or "cava" in tokens
        )

        if not q:
            return "Bonjour. Je peux vous aider avec l'emploi du temps, les salles, les professeurs, les absences et les informations ENET'Com."
        if thanks_detected:
            return "Avec plaisir. Si vous voulez, dites-moi votre classe, une salle, un professeur ou une information ENET'Com."
        if help_detected:
            return (
                "Je peux vous aider avec l'emploi du temps, les cours du jour, les salles disponibles, les professeurs, "
                "les absences, le calendrier universitaire et les informations ENET'Com." + class_hint
            )
        if greeting_detected and status_detected:
            return "Bonjour. Je vais bien, merci. Je peux vous aider avec l'emploi du temps, les salles, les professeurs, les absences et les informations ENET'Com."
        if status_detected:
            return "Je vais bien, merci. Je peux vous aider avec l'emploi du temps, les salles, les professeurs, les absences et les informations ENET'Com."
        if greeting_detected:
            return "Bonjour. Je peux vous aider avec l'emploi du temps, les salles, les professeurs, les absences et les informations ENET'Com."
        return (
            "Je suis la pour vous aider. Dites-moi ce que vous cherchez, par exemple votre emploi du temps, une salle libre, "
            "un professeur ou une information sur ENET'Com."
        )

    def build_smalltalk_response(self, message: str, user_class: Optional[str] = None) -> str:
        if not self.enabled:
            return self._fallback_conversational_response(message, user_class)

        prompt = f"""Tu es un assistant conversationnel ENET'Com.

Le message utilisateur est une salutation, un remerciement, une formule de politesse ou un petit message conversationnel.

Consignes:
- Reponds naturellement, chaleureusement, et tres brievement.
- Comprends le francais, l'anglais, l'arabe, le tunisien, et l'arabizi.
- Si c'est une salutation ou un remerciement tunisien/darija/arabe romanise, reponds comme a une vraie formule de politesse.
- Tu peux rappeler en une phrase courte que tu aides sur l'emploi du temps, les salles, les professeurs, les absences et les infos ENET'Com.
- Pas de markdown.

Message utilisateur:
{message}
"""

        response = self._post_with_retry(
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Tu es un assistant conversationnel ENET'Com, chaleureux, naturel, concis, capable de comprendre le tunisien, l'arabizi, le francais, l'arabe et l'anglais.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 120,
            },
            timeout=20,
        )
        if response is None or response.status_code != 200:
            if response is not None:
                self._handle_auth_error(response, "Groq smalltalk error")
                print(f"Groq smalltalk error: {response.status_code} - {response.text}")
            return self._fallback_conversational_response(message, user_class)

        payload = self._safe_json(response)
        if not payload:
            return self._fallback_conversational_response(message, user_class)

        raw = (payload.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
        return self._postprocess_response(raw) if raw else self._fallback_conversational_response(message, user_class)

    def _fallback_out_of_scope_response(self, message: str) -> str:
        q = self._normalize_text(message)
        if any(q.startswith(marker) for marker in QUESTION_STARTERS) or "?" in (message or ""):
            return (
                "Je suis surtout l'assistant ENET'Com. Je peux vous aider pour l'emploi du temps, les salles, les professeurs, "
                "les absences, le calendrier universitaire et les informations de l'ecole."
            )
        return "Je suis surtout l'assistant ENET'Com. Posez-moi une question sur l'emploi du temps, les salles, les professeurs ou les services de l'ecole."

    def build_out_of_scope_response(
        self,
        message: str,
        history: Optional[list] = None,
        user_class: Optional[str] = None,
    ) -> str:
        if not self.enabled:
            return self._fallback_out_of_scope_response(message)

        history_text = self._history_as_text(history)
        prompt = f"""Tu es un assistant intelligent pour ENET'Com.

Le message de l'utilisateur n'entre pas clairement dans le perimetre ENET'Com.
Reponds naturellement et de facon utile, sans t'appuyer sur l'historique pour inventer une reponse hors sujet.

Consignes:
- Explique poliment si la demande est hors perimetre.
- Si la demande est vague, aide-le a formuler une question utile.
- Tu peux proposer tes capacites: emploi du temps, cours, professeurs, salles, absences, calendrier universitaire, informations ENET'Com.
- N'evoque pas inutilement les anciens messages, la classe ou un contexte precedent si cela n'aide pas la reponse.
- Reste bref, chaleureux, sans markdown.

Classe connue: {user_class or "inconnue"}
Historique recent:
{history_text or "Aucun"}

Dernier message utilisateur:
{message}
"""

        response = self._post_with_retry(
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Tu es un assistant conversationnel ENET'Com. Quand une demande est hors perimetre, dis-le poliment et recentre vers les sujets ENET'Com.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 220,
            },
            timeout=20,
        )
        if response is None or response.status_code != 200:
            if response is not None:
                self._handle_auth_error(response, "Groq conversation error")
                print(f"Groq conversation error: {response.status_code} - {response.text}")
            return self._fallback_out_of_scope_response(message)

        payload = self._safe_json(response)
        if not payload:
            return self._fallback_out_of_scope_response(message)

        raw = (payload.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
        return self._postprocess_response(raw) if raw else self._fallback_out_of_scope_response(message)

    def maybe_answer_conversational_message(
        self,
        message: str,
        history: Optional[list] = None,
        user_class: Optional[str] = None,
    ) -> Optional[str]:
        if self._is_obvious_academic_request(message):
            return None

        if self._is_simple_conversation(message):
            return self._fallback_conversational_response(message, user_class)

        mode = self._classify_message_mode(message, history)
        if mode == "ACADEMIC":
            return None

        if mode is None:
            return self._fallback_out_of_scope_response(message)

        if not self.enabled:
            return self._fallback_out_of_scope_response(message)

        history_text = self._history_as_text(history)
        prompt = f"""Tu es un assistant intelligent pour ENET'Com.

Le message de l'utilisateur n'entre pas clairement dans le perimetre ENET'Com.
Reponds naturellement et de facon utile, sans t'appuyer sur l'historique pour inventer une reponse hors sujet.

Consignes:
- Explique poliment si la demande est hors perimetre.
- Si la demande est vague, aide-le a formuler une question utile.
- Tu peux proposer tes capacites: emploi du temps, cours, professeurs, salles, absences, calendrier universitaire, informations ENET'Com.
- N'evoque pas inutilement les anciens messages, la classe ou un contexte precedent si cela n'aide pas la reponse.
- Reste bref, chaleureux, sans markdown.

Classe connue: {user_class or "inconnue"}
Historique recent:
{history_text or "Aucun"}

Dernier message utilisateur:
{message}
"""

        response = self._post_with_retry(
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Tu es un assistant conversationnel ENET'Com. Quand une demande est hors perimetre, dis-le poliment et recentre vers les sujets ENET'Com.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 220,
            },
            timeout=20,
        )
        if response is None or response.status_code != 200:
            if response is not None:
                self._handle_auth_error(response, "Groq conversation error")
                print(f"Groq conversation error: {response.status_code} - {response.text}")
            return self._fallback_out_of_scope_response(message)

        payload = self._safe_json(response)
        if not payload:
            return self._fallback_out_of_scope_response(message)

        raw = (payload.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
        return self._postprocess_response(raw) if raw else self._fallback_out_of_scope_response(message)

    def _normalize_room_name(self, value: Any) -> str:
        text = self._repair_text_encoding(str(value or ""))
        text = re.sub(r"\s+", " ", text).strip().upper()
        text = re.sub(r"\b([A-Z])\s+(\d{2})\b", r"\1\2", text)
        text = re.sub(r"\b([A-Z])\s*0?(\d)\b", lambda match: f"{match.group(1)}{int(match.group(2)):02d}", text)
        text = re.sub(r"\bTEL-TCOM1\b", "TEL-TCOM 1", text)
        text = re.sub(r"\bEL-CI\s+AUTO\b", "EL-CI AUTO", text)
        text = re.sub(r"\s*/\s*", " / ", text)
        return text

    def _room_key(self, value: Any) -> str:
        normalized = self._normalize_room_name(value).lower()
        return re.sub(r"[\s/-]+", "", normalized)

    def _extract_requested_day_label(self, question: str) -> Optional[str]:
        q = self._normalize_text(question)
        for day_name in FRENCH_DAY_NAMES:
            if re.search(rf"\b{re.escape(day_name)}\b", q):
                return day_name
        if "aujourd" in q:
            return "aujourd'hui"
        if "demain" in q:
            return "demain"
        if "hier" in q:
            return "hier"
        return None

    def _is_calendar_question(self, question: str) -> bool:
        q = self._normalize_text(question)
        keywords = [
            "vacance",
            "vacances",
            "jour ferie",
            "jours ferie",
            "fete",
            "aid",
            "ramadan",
            "examen",
            "examens",
            "ds",
            "rattrap",
            "ratt",
            "revision",
            "calendrier",
        ]
        return any(keyword in q for keyword in keywords)

    def _validate_select_only(self, sql: str) -> bool:
        if not sql:
            return False
        cleaned = sql.replace("```sql", "").replace("```", "").strip()
        return bool(re.match(r"^\s*select\b", cleaned, re.IGNORECASE))

    def _strip_sql_comments(self, sql: str) -> str:
        if not sql:
            return sql
        sql = re.sub(r"/\*[\s\S]*?\*/", " ", sql)
        sql = re.sub(r"--[^\n]*", " ", sql)
        return sql

    def _extract_one_select(self, raw: str) -> str:
        if not raw:
            return raw
        idx = raw.upper().find("SELECT")
        if idx >= 0:
            raw = raw[idx:].strip()
        if ";" in raw:
            raw = raw.split(";", 1)[0].strip()
        if not raw.endswith(";"):
            raw += ";"
        return raw

    def _clean_sql(self, raw: str) -> str:
        if not raw:
            return raw
        text = raw.replace("```sql", "").replace("```", "").strip()
        text = text.replace("\u200b", "").strip()
        if re.search(r"\bASK_CLASS\b", text):
            return "ASK_CLASS"
        if re.search(r"\bASK_PROF\b", text):
            return "ASK_PROF"
        text = self._strip_sql_comments(text)
        text = re.sub(r"\s+", " ", text).strip()
        return self._extract_one_select(text)

    def _safe_json(self, response: requests.Response) -> Optional[Dict[str, Any]]:
        try:
            return response.json()
        except Exception as e:
            print(f"Groq API JSON parse error: {e}")
            return None

    def _extract_room_name(self, question: str) -> Optional[str]:
        question_text = question or ""
        patterns = [
            r"\bsalle\s+([A-Za-z0-9][A-Za-z0-9 ]*)\b",
            r"\bemploi(?:s)?\s+(?:du|de)\s+temps\s+de\s+([A-Za-z]{1,6}\s*0?\d{1,2})\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, question_text, flags=re.IGNORECASE)
            if not match:
                continue
            candidate = re.sub(
                r"\b(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|aujourd'hui|aujourdhui|demain|hier|maintenant|actuellement|mtn)\b.*$",
                "",
                match.group(1),
                flags=re.IGNORECASE,
            ).strip()
            normalized = self._normalize_room_name(candidate)
            if re.fullmatch(r"[A-Z][0-9]{2}", normalized) or re.fullmatch(r"[A-Z]{2,}[0-9]{1,2}", normalized):
                return normalized
            if pattern == patterns[0]:
                return normalized
        return None

    def _format_lookup_response(self, question: str, data: list) -> Optional[str]:
        if not data:
            return None

        keys = list(data[0].keys())
        normalized_keys = {key.lower(): key for key in keys}
        q = self._normalize_text(question)

        if len(keys) == 1:
            key = keys[0]
            values = []
            for row in data:
                value = row.get(key)
                if value is None:
                    continue
                value_str = str(value).strip()
                if value_str and value_str not in values:
                    values.append(value_str)

            if not values:
                return None

            if key.lower() in {"nom_complet", "prof", "professeur"}:
                room_name = self._extract_room_name(question)
                if "qui enseigne" in q and room_name:
                    if len(values) == 1:
                        return f"En salle {room_name}, c'est {values[0]} qui enseigne actuellement."
                    return f"En salle {room_name}, les enseignants trouves sont : {', '.join(values)}."
                return values[0] if len(values) == 1 else ", ".join(values)

            if key.lower() in {"total_cours", "count"}:
                try:
                    total = int(values[0])
                except Exception:
                    return None
                if total <= 0:
                    return None
                if "aujourd" in q:
                    return f"Oui, ce professeur a {total} cours aujourd'hui."
                day_label = self._extract_requested_day_label(question)
                if day_label and day_label not in {"aujourd'hui", "demain", "hier"}:
                    return f"Oui, ce professeur a {total} cours {day_label}."
                return f"Oui, ce professeur a {total} cours prevus."

            if key.lower() == "total_classes":
                try:
                    total = int(values[0])
                except Exception:
                    return None
                return f"ENET'Com compte {total} classes dans la base de donnees."

            if key.lower() == "classe":
                if any(marker in q for marker in ["quelles classes", "liste des classes", "classes existent", "classes disponibles"]):
                    lines = ["Voici les classes disponibles a ENET'Com :"]
                    lines.extend(f"- {value}" for value in values[:80])
                    if len(values) > 80:
                        lines.append(f"... et {len(values) - 80} autres classes.")
                    return "\n".join(lines)

            if key.lower() in {"nom", "room", "salle"}:
                if any(token in q for token in ["dispon", "libre", "vide"]):
                    unique_values = []
                    seen = set()
                    for value in values:
                        display_value = self._normalize_room_name(value)
                        norm = self._room_key(display_value)
                        if norm in seen:
                            continue
                        seen.add(norm)
                        unique_values.append(display_value)
                    if not unique_values:
                        return None
                    room_label = "salle" if len(unique_values) == 1 else "salles"
                    if any(token in q for token in ["maintenant", "actuellement", "mtn", "en ce moment"]):
                        intro = f"Il y a {len(unique_values)} {room_label} disponible{'s' if len(unique_values) > 1 else ''} actuellement :"
                    else:
                        day_label = self._extract_requested_day_label(question)
                        if day_label == "aujourd'hui":
                            intro = f"Les {room_label} disponible{'s' if len(unique_values) > 1 else ''} aujourd'hui {'sont' if len(unique_values) > 1 else 'est'} :"
                        elif day_label == "demain":
                            intro = f"Les {room_label} disponible{'s' if len(unique_values) > 1 else ''} demain {'sont' if len(unique_values) > 1 else 'est'} :"
                        elif day_label and day_label != "hier":
                            intro = f"Les {room_label} disponible{'s' if len(unique_values) > 1 else ''} {day_label} {'sont' if len(unique_values) > 1 else 'est'} :"
                        else:
                            intro = f"Voici {len(unique_values)} {room_label} disponible{'s' if len(unique_values) > 1 else ''} :"
                    lines = [intro]
                    lines.extend(f"- {value}" for value in unique_values[:80])
                    if len(unique_values) > 80:
                        lines.append(f"... et {len(unique_values) - 80} autres salles.")
                    return "\n".join(lines)
                if "ou se trouve" in q:
                    class_name = self._extract_class_candidate(question)
                    if "classe" in q or class_name:
                        class_label = class_name or "votre classe"
                        if len(values) == 1:
                            return f"La classe {class_label} se trouve en salle {self._normalize_room_name(values[0])}."
                        normalized_values = [self._normalize_room_name(value) for value in values]
                        return f"La classe {class_label} se trouve dans plusieurs salles : {', '.join(normalized_values)}."
                    if len(values) == 1:
                        return f"Ce professeur se trouve en salle {self._normalize_room_name(values[0])}."
                    normalized_values = [self._normalize_room_name(value) for value in values]
                    return f"Ce professeur se trouve dans plusieurs salles : {', '.join(normalized_values)}."
                if len(values) == 1:
                    return f"Salle {self._normalize_room_name(values[0])}."
                normalized_values = [self._normalize_room_name(value) for value in values]
                return ", ".join(f"Salle {value}" for value in normalized_values)

            if key.lower() == "classe":
                if "quelle classe" in q or "dans quelle classe" in q or "pour quelle classe" in q:
                    if len(values) == 1:
                        return f"Ce professeur est dans la classe {values[0]}."
                    return "Ce professeur intervient dans les classes suivantes : " + ", ".join(values) + "."
                return values[0] if len(values) == 1 else ", ".join(values)

        if {"matiere", "heure_debut", "heure_fin"}.issubset(normalized_keys):
            first = data[0]
            matiere = str(first.get(normalized_keys["matiere"]) or "").strip()
            start = self._format_time(first.get(normalized_keys["heure_debut"]))
            end = self._format_time(first.get(normalized_keys["heure_fin"]))
            room_value = first.get(normalized_keys["salle"]) if "salle" in normalized_keys else first.get(normalized_keys["room"], "")
            room = self._normalize_room_name(room_value) if room_value else ""
            classe = str(first.get(normalized_keys["classe"]) or "").strip() if "classe" in normalized_keys else ""

            if any(marker in q for marker in ["quel cours", "quelle matiere", "fait il", "enseigne t il", "enseigne maintenant"]):
                details = [f"{matiere} ({start} - {end})"]
                if classe:
                    details.append(f"pour {classe}")
                if room:
                    details.append(f"en salle {room}")
                return "Le cours actuel est " + " ".join(details) + "."

        if {"jour", "heure_debut", "heure_fin"}.issubset(normalized_keys):
            if (
                "ou se trouve" in q
                and "salle" in normalized_keys
                and "classe" in normalized_keys
            ):
                lines = []
                for row in data:
                    day = str(row.get(normalized_keys["jour"]) or "").strip()
                    start = self._format_time(row.get(normalized_keys["heure_debut"]))
                    end = self._format_time(row.get(normalized_keys["heure_fin"]))
                    classe = str(row.get(normalized_keys["classe"]) or "").strip()
                    salle = self._normalize_room_name(row.get(normalized_keys["salle"]))
                    lines.append(f"- {day} {start}-{end} : {classe} en salle {salle}")
                if lines:
                    if "classe" in q:
                        return "Voici ou se trouve la classe :\n" + "\n".join(lines[:12])
                    return "Voici ou se trouve ce professeur :\n" + "\n".join(lines[:12])
            return None

        if len(data) == 1:
            row = data[0]
            parts = [f"{key}: {value}" for key, value in row.items() if value is not None]
            if parts:
                return "\n".join(parts)

        return None

    def _format_time(self, value: Any) -> str:
        if value is None:
            return "?"
        if hasattr(value, "strftime"):
            try:
                return value.strftime("%H:%M")
            except Exception:
                pass

        text = str(value).strip()
        if not text:
            return "?"
        match = re.match(r"^(\d{1,2}):(\d{2})", text)
        if match:
            return f"{int(match.group(1)):02d}:{match.group(2)}"
        return text

    def _format_timetable_response(self, data: list) -> Optional[str]:
        if not data:
            return None
        if not {"jour", "heure_debut", "heure_fin"}.issubset(data[0].keys()):
            return None

        class_names = []
        grouped: Dict[str, list] = {}
        seen_entries = set()
        for row in data:
            day = str(row.get("jour") or "").strip() or "Jour inconnu"
            class_name = str(row.get("classe") or "").strip()
            if class_name and class_name not in class_names:
                class_names.append(class_name)

            entry = {
                "time": f"{self._format_time(row.get('heure_debut'))} - {self._format_time(row.get('heure_fin'))}",
                "matiere": str(row.get("matiere") or "Cours").strip(),
                "professeur": str(row.get("professeur") or row.get("nom_complet") or "Non precise").strip(),
                "salle": self._normalize_room_name(row.get("salle") or row.get("room") or "Non precisee"),
            }
            dedupe_key = (day, entry["time"], entry["matiere"], entry["professeur"], entry["salle"])
            if dedupe_key in seen_entries:
                continue
            seen_entries.add(dedupe_key)

            grouped.setdefault(day, []).append(
                entry
            )

        title = f"Voici votre emploi du temps pour {class_names[0]} :" if len(class_names) == 1 else "Voici votre emploi du temps :"
        lines = [title]
        sorted_days = sorted(grouped.keys(), key=lambda day: (DAY_DISPLAY_ORDER.get(day.lower(), 99), day.lower()))
        for day in sorted_days:
            entries = sorted(grouped[day], key=lambda entry: entry["time"])
            lines.extend(["", f"{day} :", ""])
            for index, entry in enumerate(entries):
                lines.append(f"{entry['time']} | {entry['matiere']}")
                lines.append(f"Professeur : {entry['professeur']}")
                lines.append(f"Salle : {entry['salle']}")
                if index != len(entries) - 1:
                    lines.append("")
        return "\n".join(lines).strip()

    def _post_with_retry(self, payload: dict, timeout: int = 25) -> Optional[requests.Response]:
        for attempt in range(2):
            try:
                return self._session.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=timeout,
                )
            except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
                if attempt == 0:
                    print(f"Groq connection error (retrying): {e}")
                    self._session = requests.Session()
                    continue
                print(f"Groq API exception: {e}")
                return None
            except Exception as e:
                print(f"Groq API exception: {e}")
                return None
        return None

    # --- Missing info check ---

    def _extract_class_candidate(self, question: str) -> Optional[str]:
        match = re.search(
            r"\b(\d)\s*(ING|TIC|LTIC|MP|MR)\b(?:\s+([A-Z0-9\-]+))?(?:\s+([A-Z0-9\-]+))?(?:\s+(\d))?\b",
            (question or "").strip(),
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        parts = [part for part in match.groups() if part]
        return re.sub(r"\s+", " ", " ".join([parts[0]] + [part.upper() for part in parts[1:]])).strip()

    def check_missing_info(self, question: str) -> Optional[str]:
        if self._is_calendar_question(question):
            return None

        q = self._normalize_text(question)
        no_class_needed = any(
            [
                "professeur" in q,
                "prof " in q,
                re.search(r"\b(mr|mme|dr)\b", q),
                "quelles classes" in q,
                "liste" in q and "classe" in q,
                "classes existent" in q,
                "tous les prof" in q,
                "liste des prof" in q,
                "salle" in q and not any(token in q for token in ["cours", "emploi", "seance"]),
            ]
        )
        if no_class_needed:
            return None

        needs_class = any(
            [
                "emploi du temps" in q,
                "emplois du temps" in q,
                "edt" in q,
                "planning" in q,
                "horaire" in q,
                "quel cours" in q,
                "quels cours" in q,
                "cours" in q,
                "seance" in q,
                "tp" in q.split(),
                "mon cours" in q,
                "mes cours" in q,
                "j ai cours" in q,
                "demain" in q,
                "aujourd" in q,
                "hier" in q,
                any(day in q for day in ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]),
            ]
        )
        if not needs_class:
            return None
        if not self._extract_class_candidate(question):
            return "Quelle est votre classe ? (ex: 2 ING GII 3, 1 TIC 2, 2 TIC-T, etc.)"
        return None

    # --- SQL generation ---

    def generate_sql(self, question: str, context: dict, schema_info: str) -> Optional[str]:
        if not self.enabled:
            return None

        periode_id = context.get("periode_id")
        semestre_id = context.get("semestre_id")
        annee_id = context.get("annee_id", 1)
        today_day_name = context.get("jour_actuel") or context.get("jour_nom") or ""
        resolved_class = self._extract_class_candidate(question) or "MISSING"

        prompt = f"""You are a PostgreSQL expert. Return ONLY ONE SQL SELECT query, or ASK_CLASS / ASK_PROF.

DATABASE SCHEMA:
{schema_info}

CONTEXT:
- Current Periode ID: {periode_id if periode_id is not None else 'NULL'}
- Current Semestre ID: {semestre_id if semestre_id is not None else 'NULL'}
- Current Annee ID: {annee_id}
- Today date: {context.get('date_actuelle', 'unknown')}
- Today weekday name (French): {today_day_name if today_day_name else 'UNKNOWN'}
- Resolved class from the question: {resolved_class}

USER QUESTION (French):
{question}

STRICT RULES:
A) If the question is about timetable/seances AND the class is missing -> return exactly: ASK_CLASS
B) If the question is about timetable for a professor AND professor name is missing -> return exactly: ASK_PROF
C) Never output markdown. Never output explanations. ONLY the SQL (or ASK_*).
D) ALWAYS output ONE SELECT statement. No INSERT/UPDATE/DELETE/DDL.
E) NEVER use c.id directly to match the class.
F) If class is available, use:
   REPLACE(LOWER(c.nom), ' ', '') LIKE '%' || REPLACE(LOWER('{resolved_class}'), ' ', '') || '%'
G) Active timetable version:
   JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id
H) If you filter by day, use LOWER(s.jour) = LOWER('Lundi') style matching.
I) For rooms, use alias sa and sa.nom.
J) For calendar questions, use vacances_jours_feries (nom, date_debut, date_fin, type, annee_id).

SQL:"""

        response = self._post_with_retry(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a PostgreSQL expert. Return only ONE SELECT query or ASK_CLASS/ASK_PROF. No explanations. No markdown."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.0,
                "max_tokens": 2000,
            }
        )
        if response is None or response.status_code != 200:
            if response is not None:
                print(f"Groq API error: {response.status_code} - {response.text}")
            return None

        payload = self._safe_json(response)
        if not payload:
            return None

        raw = (payload.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
        print(f"[DEBUG] Raw SQL from Groq: {raw}")

        sql = self._clean_sql(raw)
        if sql in {"ASK_CLASS", "ASK_PROF"}:
            return sql
        if not self._validate_select_only(sql):
            print("[DEBUG] Groq returned non-SELECT.")
            return None

        print(f"[DEBUG] Cleaned SQL: {sql}")
        return sql

    # --- Response formatting ---

    def format_response(self, question: str, data: list, context: dict, use_llm: bool = True) -> Optional[str]:
        if not data:
            return "Aucune donnee trouvee pour cette question."

        if all(("date_debut" in row and "date_fin" in row and ("nom" in row or "Nom" in row)) for row in data):
            lines = []
            for row in data[:80]:
                nom = row.get("nom") or row.get("Nom") or ""
                event_type = row.get("type") or row.get("Type") or ""
                date_start = row.get("date_debut") or row.get("DateDebut")
                date_end = row.get("date_fin") or row.get("DateFin")
                lines.append(f"{date_start} -> {date_end} | {event_type} | {nom}")
            return "\n".join(lines).strip()

        lookup_response = self._format_lookup_response(question, data)
        if lookup_response:
            return lookup_response

        timetable_response = self._format_timetable_response(data)
        if timetable_response:
            return timetable_response

        if not use_llm:
            return None

        if not self.enabled:
            return None

        data_str = "\n".join([str(dict(row)) for row in data[:80]])
        prompt = f"""You are a professional French university assistant.

USER QUESTION: {question}
ACADEMIC CONTEXT:
- Semestre: {context.get('semestre')}
- Periode: {context.get('periode')}
- Date: {context.get('date_actuelle')}

SQL RESULTS ({len(data)} rows):
{data_str}

Return plain French text with line breaks and no markdown."""

        response = self._post_with_retry(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a professional French university assistant. Format responses clearly with line breaks. No markdown."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 1000,
            },
            timeout=30,
        )
        if response is None or response.status_code != 200:
            if response is not None:
                print(f"Groq format error: {response.status_code} - {response.text}")
            return None

        payload = self._safe_json(response)
        if not payload:
            return None

        raw = (payload.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
        return self._postprocess_response(raw)

    def format_response_deterministic(self, question: str, data: list, context: dict) -> Optional[str]:
        return self.format_response(question, data, context, use_llm=False)

    def _postprocess_response(self, text: str) -> str:
        if not text:
            return text
        text = text.replace("**", "")
        text = re.sub(r"\s*(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})\s*", r"\n\n\1 ", text).strip()
        text = re.sub(r"\s+(Professeur\s*:)\s*", r"\n\1 ", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+(Salle\s*:)\s*", r"\n\1 ", text, flags=re.IGNORECASE)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


groq_service = GroqService()
