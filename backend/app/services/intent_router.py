from __future__ import annotations

from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from enum import Enum
import re
import unicodedata
from typing import Any, Optional

from sqlalchemy import text


class IntentLabel(str, Enum):
    UNIVERSITY_INFO = "UNIVERSITY_INFO"
    CALENDAR = "CALENDAR"
    ALL_CLASSES = "ALL_CLASSES"
    CLASS_SCHEDULE = "CLASS_SCHEDULE"
    CLASS_LOCATION = "CLASS_LOCATION"
    ROOM_SCHEDULE = "ROOM_SCHEDULE"
    ROOM_CURRENT_TEACHER = "ROOM_CURRENT_TEACHER"
    AVAILABLE_ROOMS = "AVAILABLE_ROOMS"
    PROF_SCHEDULE = "PROF_SCHEDULE"
    PROF_LOCATION = "PROF_LOCATION"
    PROF_CLASS = "PROF_CLASS"
    PROF_CURRENT_COURSE = "PROF_CURRENT_COURSE"
    PROF_HAS_COURSE = "PROF_HAS_COURSE"
    ACADEMIC_GENERIC = "ACADEMIC_GENERIC"
    CHAT_SMALLTALK = "CHAT_SMALLTALK"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    NEEDS_CLASS = "NEEDS_CLASS"
    NEEDS_PROF_CONFIRMATION = "NEEDS_PROF_CONFIRMATION"


class PendingSlot(str, Enum):
    CLASS = "class"
    PROFESSOR = "professor"


class ExecutionTarget(str, Enum):
    SQL_AGENT = "sql_agent"
    UNIVERSITY_SERVICE = "university_service"
    SMALLTALK = "smalltalk"
    OUT_OF_SCOPE = "out_of_scope"
    CLARIFICATION = "clarification"


@dataclass
class IntentEntities:
    class_candidate: Optional[str] = None
    professor_candidate: Optional[str] = None
    room_candidate: Optional[str] = None
    time_marker: Optional[str] = None
    day_marker: Optional[str] = None
    university_topic: Optional[str] = None


@dataclass
class ConversationState:
    last_intent: Optional[str] = None
    last_class: Optional[str] = None
    last_professor: Optional[str] = None
    last_university_topic: Optional[str] = None
    last_user_message: Optional[str] = None
    pending_slot: Optional[str] = None
    pending_original_question: Optional[str] = None
    pending_assistant_message: Optional[str] = None


@dataclass
class IntentDecision:
    intent: str
    execution_target: str
    source: str
    confidence: float
    normalized_message: str
    entities: IntentEntities = field(default_factory=IntentEntities)
    state: ConversationState = field(default_factory=ConversationState)
    full_question: Optional[str] = None
    direct_response: Optional[str] = None
    needs_confirmation: bool = False
    needs_clarification: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "execution_target": self.execution_target,
            "source": self.source,
            "confidence": self.confidence,
            "normalized_message": self.normalized_message,
            "entities": asdict(self.entities),
            "state": asdict(self.state),
            "full_question": self.full_question,
            "direct_response": self.direct_response,
            "needs_confirmation": self.needs_confirmation,
            "needs_clarification": self.needs_clarification,
        }


class IntentRouter:
    CLASS_SHORTHAND_CODES = {"GII", "GEC", "GT", "IDSD", "INFO", "TELECOM"}
    YES_MARKERS = {"oui", "yes", "ok", "daccord", "d accord", "d'accord"}
    NO_MARKERS = {"non", "no"}
    EXECUTION_CONFIDENCE_THRESHOLD = 0.75
    MODEL_EXECUTION_CONFIDENCE_THRESHOLD = 0.65
    MARKER_GROUPS = {
        "study_plan": (
            "plan d etude",
            "plan de etude",
            "plan etude",
            "plan detude",
            "plans d etude",
            "plans de etude",
            "plans etude",
            "plans etudes",
            "plans detudes",
            "plan des etudes",
            "plans des etudes",
            "programme d etude",
            "programme etude",
            "programme des etudes",
            "curriculum",
        ),
        "absence": (
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
        ),
        "general_info": (
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
        ),
        "calendar": (
            "vacance",
            "vacances",
            "jour ferie",
            "jours ferie",
            "jour ferier",
            "jours ferier",
            "fete",
            "aid",
            "ramadan",
            "examen",
            "examens",
            "devoir",
            "devoirs",
            "controle",
            "controles",
            "ds",
            "rattrap",
            "revision",
            "calendrier",
        ),
        "schedule": (
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

        ),
        "class_location": ("ou se trouve", "ou est", "dans quelle salle", "salle"),
        "professor_location": ("ou se trouve", "se trouve", "dans quelle salle", "est ou"),
        "professor_class": ("dans quelle classe", "quelle classe", "pour quelle classe", "classe se trouve"),
        "professor_current_course": ("quel cours", "quelle matiere", "fait", "enseigne"),
        "professor_has_course": ("a cours", "a un cours", "a t il cours", "a elle cours", "est ce qu il a cours", "est ce qu elle a cours"),
        "available_rooms": ("dispon", "diponn", "libre", "vide"),
        "room_current_teacher": ("qui enseigne",),
        "time_now": ("maintenant", "actuellement", "mtn", "en ce moment"),
        "day_relative": ("aujourd", "demain", "hier"),
        "days": ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"),
    }

    def __init__(self, groq_service_obj: Any, db: Any = None):
        self.groq_service = groq_service_obj
        self.db = db
        self._available_class_names = self._load_available_class_names_from_db()
        self._class_aliases = self._build_class_aliases(self._available_class_names)
        self._dynamic_shorthand_codes = self._build_dynamic_shorthand_codes(self._available_class_names)
        self._available_professor_names = self._load_available_professor_names_from_db()
        self._professor_aliases = self._build_professor_aliases(self._available_professor_names)

    def route(
        self,
        message: str,
        history: Optional[list] = None,
        user_class: Optional[str] = None,
        agent: Any = None,
    ) -> IntentDecision:
        normalized_message = self._normalize_text(message)
        resolved_user_class = self._extract_class_candidate(user_class or "") or self._clean_text(user_class)
        state = self._build_state(history or [], resolved_user_class)
        entities = self._extract_entities(message)

        if self._is_all_classes_question(normalized_message):
            decision = IntentDecision(
                intent=IntentLabel.ALL_CLASSES.value,
                execution_target=ExecutionTarget.SQL_AGENT.value,
                source="rule_based",
                confidence=0.97,
                normalized_message=normalized_message,
                entities=entities,
                state=state,
                full_question=message,
            )
            return self._apply_confidence_policy(self._finalize_academic_decision(decision, resolved_user_class, agent))

        if self._is_direct_university_question(normalized_message):
            return IntentDecision(
                intent=IntentLabel.UNIVERSITY_INFO.value,
                execution_target=ExecutionTarget.UNIVERSITY_SERVICE.value,
                source="rule_based",
                confidence=0.99,
                normalized_message=normalized_message,
                entities=entities,
                state=state,
                full_question=message,
            )

        pending_decision = self._resolve_pending_request(
            message=message,
            normalized_message=normalized_message,
            state=state,
            entities=entities,
        )
        if pending_decision:
            pending_decision.state = state
            pending_decision.entities = self._extract_entities(pending_decision.full_question or message)
            return self._apply_confidence_policy(
                self._finalize_academic_decision(pending_decision, resolved_user_class, agent)
            )

        contextual_followup_decision = self._resolve_short_contextual_followup(
            message=message,
            normalized_message=normalized_message,
            entities=entities,
            state=state,
        )
        if contextual_followup_decision:
            return self._apply_confidence_policy(
                self._finalize_academic_decision(contextual_followup_decision, resolved_user_class, agent)
            )

        if self._is_simple_conversation(message):
            return self._apply_confidence_policy(IntentDecision(
                intent=IntentLabel.CHAT_SMALLTALK.value,
                execution_target=ExecutionTarget.SMALLTALK.value,
                source="rule_based",
                confidence=0.98,
                normalized_message=normalized_message,
                entities=entities,
                state=state,
            ))

        explicit_professor_context_decision = self._direct_professor_context_decision(message, normalized_message, entities, state)
        if explicit_professor_context_decision:
            return self._apply_confidence_policy(self._finalize_academic_decision(explicit_professor_context_decision, resolved_user_class, agent))

        intent = self._infer_academic_intent(message, normalized_message, entities)
        if not intent:
            intent = self._infer_contextual_intent(normalized_message, entities, state, resolved_user_class)
        if intent:
            decision = IntentDecision(
                intent=intent,
                execution_target=ExecutionTarget.SQL_AGENT.value,
                source="rule_based",
                confidence=0.92,
                normalized_message=normalized_message,
                entities=entities,
                state=state,
                full_question=message,
            )
            return self._apply_confidence_policy(self._finalize_academic_decision(decision, resolved_user_class, agent))

        if self._is_obvious_academic_request(message):
            decision = IntentDecision(
                intent=IntentLabel.ACADEMIC_GENERIC.value,
                execution_target=ExecutionTarget.SQL_AGENT.value,
                source="rule_based",
                confidence=0.7,
                normalized_message=normalized_message,
                entities=entities,
                state=state,
                full_question=message,
            )
            return self._apply_confidence_policy(self._finalize_academic_decision(decision, resolved_user_class, agent))

        mode = self.groq_service.classify_message_mode(message, history)
        if mode == "ACADEMIC":
            decision = IntentDecision(
                intent=IntentLabel.ACADEMIC_GENERIC.value,
                execution_target=ExecutionTarget.SQL_AGENT.value,
                source="model_classification",
                confidence=0.58,
                normalized_message=normalized_message,
                entities=entities,
                state=state,
                full_question=message,
            )
            return self._apply_confidence_policy(self._finalize_academic_decision(decision, resolved_user_class, agent))

        return self._apply_confidence_policy(IntentDecision(
            intent=IntentLabel.OUT_OF_SCOPE.value,
            execution_target=ExecutionTarget.OUT_OF_SCOPE.value,
            source="model_classification" if mode == "NON_ACADEMIC" else "fallback",
            confidence=0.55 if mode == "NON_ACADEMIC" else 0.35,
            normalized_message=normalized_message,
            entities=entities,
            state=state,
        ))

    def _apply_confidence_policy(self, decision: IntentDecision) -> IntentDecision:
        if decision.execution_target != ExecutionTarget.SQL_AGENT.value:
            return decision
        threshold = self.MODEL_EXECUTION_CONFIDENCE_THRESHOLD if decision.source == "model_classification" else self.EXECUTION_CONFIDENCE_THRESHOLD
        if decision.confidence >= threshold:
            return decision
        decision.execution_target = ExecutionTarget.CLARIFICATION.value
        decision.needs_clarification = True
        decision.direct_response = (
            "Je ne suis pas encore assez sur de votre demande. "
            "Pouvez-vous reformuler en precisant la classe, le professeur, la salle ou le type d'information cherche ?"
        )
        return decision

    def _direct_professor_context_decision(
        self,
        message: str,
        normalized_message: str,
        entities: IntentEntities,
        state: ConversationState,
    ) -> Optional[IntentDecision]:
        prof_intents = {
            IntentLabel.PROF_SCHEDULE.value,
            IntentLabel.PROF_LOCATION.value,
            IntentLabel.PROF_CLASS.value,
            IntentLabel.PROF_CURRENT_COURSE.value,
            IntentLabel.PROF_HAS_COURSE.value,
        }
        if (
            entities.professor_candidate
            and state.last_intent in prof_intents
            and self._is_bare_professor_reply(normalized_message)
        ):
            return IntentDecision(
                intent=state.last_intent,
                execution_target=ExecutionTarget.SQL_AGENT.value,
                source="conversation_state",
                confidence=0.93,
                normalized_message=normalized_message,
                entities=entities,
                state=state,
                full_question=message,
            )
        return None

    def _finalize_academic_decision(
        self,
        decision: IntentDecision,
        user_class: Optional[str],
        agent: Any,
    ) -> IntentDecision:
        state = decision.state
        entities = decision.entities
        base_question = decision.full_question or ""
        full_question = self._augment_question(
            base_question,
            decision.intent,
            entities,
            state,
            user_class,
        )

        if decision.intent in {IntentLabel.CLASS_SCHEDULE.value, IntentLabel.CLASS_LOCATION.value}:
            class_value = entities.class_candidate or user_class or state.last_class
            if not class_value:
                decision.intent = IntentLabel.NEEDS_CLASS.value
                decision.execution_target = ExecutionTarget.CLARIFICATION.value
                decision.needs_clarification = True
                decision.direct_response = "Quelle est votre classe ? (ex: 2 ING GII 3, 1 TIC 2, 2 TIC-T, etc.)"
                decision.confidence = 0.99
                return decision

        prof_intents = {
            IntentLabel.PROF_SCHEDULE.value,
            IntentLabel.PROF_LOCATION.value,
            IntentLabel.PROF_CLASS.value,
            IntentLabel.PROF_CURRENT_COURSE.value,
            IntentLabel.PROF_HAS_COURSE.value,
        }
        if decision.intent in prof_intents and entities.professor_candidate and agent:
            confirmation = agent._professor_confirmation_message(entities.professor_candidate)
            if confirmation:
                decision.intent = IntentLabel.NEEDS_PROF_CONFIRMATION.value
                decision.execution_target = ExecutionTarget.CLARIFICATION.value
                decision.needs_confirmation = True
                decision.direct_response = confirmation
                decision.full_question = full_question
                decision.confidence = 0.96
                return decision

        decision.full_question = full_question or decision.full_question
        return decision

    def _augment_question(
        self,
        message: str,
        intent: str,
        entities: IntentEntities,
        state: ConversationState,
        user_class: Optional[str],
    ) -> str:
        if intent == IntentLabel.ACADEMIC_GENERIC.value:
            return message
        if intent == IntentLabel.CALENDAR.value:
            return message

        if intent in {IntentLabel.CLASS_SCHEDULE.value, IntentLabel.CLASS_LOCATION.value}:
            class_value = entities.class_candidate or user_class or state.last_class
            if class_value:
                day_suffix = self._day_suffix_from_entities(entities)
                if intent == IntentLabel.CLASS_SCHEDULE.value:
                    if entities.class_candidate:
                        return f"emploi du temps de {class_value}{day_suffix}"
                    return f"{message} pour la classe {class_value}"
                if entities.class_candidate:
                    return f"ou se trouve la classe {class_value}{day_suffix}"
                return f"{message} pour la classe {class_value}"
            return message

        prof_intents = {
            IntentLabel.PROF_SCHEDULE.value,
            IntentLabel.PROF_LOCATION.value,
            IntentLabel.PROF_CLASS.value,
            IntentLabel.PROF_CURRENT_COURSE.value,
            IntentLabel.PROF_HAS_COURSE.value,
        }
        if intent in prof_intents:
            professor_value = entities.professor_candidate or state.last_professor
            if professor_value:
                day_suffix = self._day_suffix_from_entities(entities)
                if intent == IntentLabel.PROF_SCHEDULE.value:
                    return f"emploi du temps de {professor_value}{day_suffix}"
                if intent == IntentLabel.PROF_LOCATION.value:
                    return f"ou se trouve {professor_value}{day_suffix}"
                if intent == IntentLabel.PROF_CLASS.value:
                    return f"dans quelle classe se trouve {professor_value}{day_suffix}"
                if intent == IntentLabel.PROF_CURRENT_COURSE.value:
                    return f"quel cours fait {professor_value}{day_suffix or ' maintenant'}"
                if intent == IntentLabel.PROF_HAS_COURSE.value:
                    return f"{professor_value} a cours{day_suffix or ' aujourd hui'}"

        return message

    def _resolve_pending_request(
        self,
        message: str,
        normalized_message: str,
        state: ConversationState,
        entities: IntentEntities,
    ) -> Optional[IntentDecision]:
        if not state.pending_slot or not state.pending_original_question or not state.pending_assistant_message:
            return None
        if normalized_message in self.NO_MARKERS:
            return IntentDecision(
                intent=IntentLabel.ACADEMIC_GENERIC.value,
                execution_target=ExecutionTarget.CLARIFICATION.value,
                source="conversation_state",
                confidence=0.99,
                normalized_message=normalized_message,
                direct_response="D'accord. Reformulez votre demande et je vous aiderai.",
                needs_clarification=True,
            )
        if self._looks_like_fresh_request(message, entities):
            return None

        if state.pending_slot == PendingSlot.CLASS.value:
            class_value = entities.class_candidate or self._clean_text(message) or state.last_class
            full_question = f"{state.pending_original_question} pour la classe {class_value}"
            intent = self._infer_academic_intent(
                full_question,
                self._normalize_text(full_question),
                self._extract_entities(full_question),
            ) or IntentLabel.CLASS_SCHEDULE.value
            return IntentDecision(
                intent=intent,
                execution_target=ExecutionTarget.SQL_AGENT.value,
                source="conversation_state",
                confidence=0.97,
                normalized_message=normalized_message,
                full_question=full_question,
            )

        selected_professor = self._extract_confirmed_professor(message, state.pending_assistant_message)
        full_question = self._replace_professor_in_question(state.pending_original_question, selected_professor or message)
        intent = self._infer_academic_intent(
            full_question,
            self._normalize_text(full_question),
            self._extract_entities(full_question),
        ) or IntentLabel.PROF_SCHEDULE.value
        return IntentDecision(
            intent=intent,
            execution_target=ExecutionTarget.SQL_AGENT.value,
            source="conversation_state",
            confidence=0.97,
            normalized_message=normalized_message,
            full_question=full_question,
        )

    def _resolve_short_contextual_followup(
        self,
        message: str,
        normalized_message: str,
        entities: IntentEntities,
        state: ConversationState,
    ) -> Optional[IntentDecision]:
        if not state.last_intent:
            return None

        if self._is_short_study_plan_followup(normalized_message, state):
            study_plan_key = self._extract_study_plan_followup_key(normalized_message)
            if study_plan_key:
                return IntentDecision(
                    intent=IntentLabel.UNIVERSITY_INFO.value,
                    execution_target=ExecutionTarget.UNIVERSITY_SERVICE.value,
                    source="conversation_state",
                    confidence=0.96,
                    normalized_message=normalized_message,
                    entities=entities,
                    state=state,
                    full_question=f"plan etude {study_plan_key}",
                )

        if self._is_short_count_followup(normalized_message, state):
            return IntentDecision(
                intent=IntentLabel.ALL_CLASSES.value,
                execution_target=ExecutionTarget.SQL_AGENT.value,
                source="conversation_state",
                confidence=0.95,
                normalized_message=normalized_message,
                entities=entities,
                state=state,
                full_question="combien de classes dans enetcom",
            )

        if self._is_short_day_followup(normalized_message, entities):
            question = self._build_day_followup_question(entities, state)
            if question:
                return IntentDecision(
                    intent=state.last_intent,
                    execution_target=ExecutionTarget.SQL_AGENT.value,
                    source="conversation_state",
                    confidence=0.95,
                    normalized_message=normalized_message,
                    entities=self._extract_entities(question),
                    state=state,
                    full_question=question,
                )

        return None

    def _build_state(self, history: list, user_class: Optional[str]) -> ConversationState:
        state = ConversationState(last_class=user_class)
        pending = self._extract_pending_request(history)
        if pending:
            state.pending_slot = pending[0]
            state.pending_original_question = pending[1]
            state.pending_assistant_message = pending[2]

        for message in reversed(history or []):
            role, content = self._history_message_parts(message)
            if role != "user":
                continue
            extracted_entities = self._extract_entities(content)
            inferred = self._infer_academic_intent(content, self._normalize_text(content), extracted_entities)
            if not state.last_user_message:
                state.last_user_message = content
            if not state.last_class:
                state.last_class = self._extract_class_candidate(content)
            if not state.last_professor and inferred in {
                IntentLabel.PROF_SCHEDULE.value,
                IntentLabel.PROF_LOCATION.value,
                IntentLabel.PROF_CLASS.value,
                IntentLabel.PROF_CURRENT_COURSE.value,
                IntentLabel.PROF_HAS_COURSE.value,
            }:
                extracted = extracted_entities.professor_candidate
                if extracted:
                    state.last_professor = extracted
            if not state.last_university_topic and inferred == IntentLabel.UNIVERSITY_INFO.value:
                state.last_university_topic = extracted_entities.university_topic
            if not state.last_intent:
                if inferred:
                    state.last_intent = inferred
            if state.last_class and state.last_professor and state.last_intent:
                break
        return state

    def _extract_entities(self, message: str) -> IntentEntities:
        normalized = self._normalize_text(message)
        return IntentEntities(
            class_candidate=self._extract_class_candidate(message),
            professor_candidate=self._extract_professor_candidate(message),
            room_candidate=self._extract_room_candidate(message),
            time_marker=self._extract_time_marker(normalized),
            day_marker=self._extract_day_marker(normalized),
            university_topic=self._extract_university_topic(normalized),
        )

    def _infer_academic_intent(
        self,
        message: str,
        normalized_message: str,
        entities: IntentEntities,
    ) -> Optional[str]:
        if self._is_all_classes_question(normalized_message):
            return IntentLabel.ALL_CLASSES.value
        if self._is_direct_university_question(normalized_message):
            return IntentLabel.UNIVERSITY_INFO.value
        if self._is_calendar_question(normalized_message):
            return IntentLabel.CALENDAR.value
        if self._is_room_current_teacher_question(normalized_message, entities):
            return IntentLabel.ROOM_CURRENT_TEACHER.value
        if self._is_available_rooms_question(normalized_message):
            return IntentLabel.AVAILABLE_ROOMS.value
        if self._is_room_schedule_question(normalized_message, entities):
            return IntentLabel.ROOM_SCHEDULE.value
        if self._is_prof_class_question(normalized_message, entities):
            return IntentLabel.PROF_CLASS.value
        if self._is_prof_location_question(normalized_message, entities):
            return IntentLabel.PROF_LOCATION.value
        if self._is_prof_current_course_question(normalized_message, entities):
            return IntentLabel.PROF_CURRENT_COURSE.value
        if self._is_prof_has_course_question(normalized_message, entities):
            return IntentLabel.PROF_HAS_COURSE.value
        if self._is_prof_schedule_question(normalized_message, entities):
            return IntentLabel.PROF_SCHEDULE.value
        if self._is_class_location_question(normalized_message, entities):
            return IntentLabel.CLASS_LOCATION.value
        if self._is_class_schedule_question(normalized_message, entities):
            return IntentLabel.CLASS_SCHEDULE.value
        return None

    def _infer_contextual_intent(
        self,
        normalized_message: str,
        entities: IntentEntities,
        state: ConversationState,
        user_class: Optional[str],
    ) -> Optional[str]:
        prof_intents = {
            IntentLabel.PROF_SCHEDULE.value,
            IntentLabel.PROF_LOCATION.value,
            IntentLabel.PROF_CLASS.value,
            IntentLabel.PROF_CURRENT_COURSE.value,
            IntentLabel.PROF_HAS_COURSE.value,
        }
        if (
            entities.professor_candidate
            and state.last_intent in prof_intents
            and not self._contains_any_marker(normalized_message, "schedule")
            and not self._contains_any_marker(normalized_message, "professor_location")
            and not self._contains_any_marker(normalized_message, "professor_class")
            and not self._contains_any_marker(normalized_message, "professor_current_course")
            and not self._contains_any_marker(normalized_message, "professor_has_course")
        ):
            return state.last_intent
        if (
            entities.class_candidate
            and state.last_intent in {IntentLabel.CLASS_SCHEDULE.value, IntentLabel.CLASS_LOCATION.value}
            and self._is_bare_class_reply(normalized_message, entities.class_candidate)
        ):
            return state.last_intent
        if self._is_calendar_question(normalized_message):
            return IntentLabel.CALENDAR.value
        if self._looks_like_schedule_request(normalized_message) and (entities.class_candidate or user_class or state.last_class):
            return IntentLabel.CLASS_SCHEDULE.value
        if self._looks_like_class_location_request(normalized_message) and (entities.class_candidate or user_class or state.last_class):
            return IntentLabel.CLASS_LOCATION.value
        if self._looks_like_professor_location_followup(normalized_message) and (entities.professor_candidate or state.last_professor):
            return IntentLabel.PROF_LOCATION.value
        if self._looks_like_professor_class_followup(normalized_message) and (entities.professor_candidate or state.last_professor):
            return IntentLabel.PROF_CLASS.value
        if self._looks_like_professor_current_course_followup(normalized_message) and (entities.professor_candidate or state.last_professor):
            return IntentLabel.PROF_CURRENT_COURSE.value
        if self._looks_like_professor_has_course_followup(normalized_message) and (entities.professor_candidate or state.last_professor):
            return IntentLabel.PROF_HAS_COURSE.value
        return None

    def _is_direct_university_question(self, normalized_message: str) -> bool:
        if self._contains_any_marker(normalized_message, "study_plan"):
            return True
        if self._contains_any_marker(normalized_message, "absence"):
            return True
        return self._contains_any_marker(normalized_message, "general_info")

    def _is_all_classes_question(self, normalized_message: str) -> bool:
        return (
            any(
                marker in normalized_message
                for marker in (
                    "toutes les classes disponibles",
                    "tous les classes disponibles",
                    "donner toutes les classes",
                    "liste des classes",
                    "quelles classes existent",
                    "quels sont les classes existes",
                    "classes disponibles",
                    "combien de classe",
                    "combien de classes",
                    "nombre de classes",
                )
            )
            and "ma classe" not in normalized_message
        )

    def _is_calendar_question(self, normalized_message: str) -> bool:
        if not normalized_message:
            return False
        if any(marker in normalized_message for marker in ("cours", "seance", "emploi", "edt", "planning", "horaire")):
            return False
        return self._contains_any_marker(normalized_message, "calendar")

    def _is_class_schedule_question(self, normalized_message: str, entities: IntentEntities) -> bool:
        if self._is_calendar_question(normalized_message):
            return False
        if entities.class_candidate and self._contains_any_marker(normalized_message, "schedule"):
            return True
        return bool(entities.class_candidate and entities.day_marker)

    def _is_class_location_question(self, normalized_message: str, entities: IntentEntities) -> bool:
        if not entities.class_candidate and "classe" not in normalized_message:
            return False
        return self._contains_any_marker(normalized_message, "class_location")

    def _is_prof_schedule_question(self, normalized_message: str, entities: IntentEntities) -> bool:
        return bool(entities.professor_candidate and self._contains_any_marker(normalized_message, "schedule"))

    def _is_prof_location_question(self, normalized_message: str, entities: IntentEntities) -> bool:
        if not entities.professor_candidate:
            return False
        return self._contains_any_marker(normalized_message, "professor_location")

    def _is_prof_class_question(self, normalized_message: str, entities: IntentEntities) -> bool:
        if not entities.professor_candidate:
            return False
        return self._contains_any_marker(normalized_message, "professor_class")

    def _is_prof_current_course_question(self, normalized_message: str, entities: IntentEntities) -> bool:
        if not entities.professor_candidate:
            return False
        return self._contains_any_marker(normalized_message, "professor_current_course") and entities.time_marker == "now"

    def _is_prof_has_course_question(self, normalized_message: str, entities: IntentEntities) -> bool:
        if not entities.professor_candidate:
            return False
        return self._contains_any_marker(normalized_message, "professor_has_course")

    def _is_room_current_teacher_question(self, normalized_message: str, entities: IntentEntities) -> bool:
        return bool(entities.room_candidate and self._contains_any_marker(normalized_message, "room_current_teacher") and entities.time_marker == "now")

    def _is_room_schedule_question(self, normalized_message: str, entities: IntentEntities) -> bool:
        return bool(entities.room_candidate and self._contains_any_marker(normalized_message, "schedule"))

    def _is_available_rooms_question(self, normalized_message: str) -> bool:
        has_room = "salle" in normalized_message
        has_availability = self._contains_any_marker(normalized_message, "available_rooms")
        return has_room and has_availability

    def _looks_like_schedule_request(self, normalized_message: str) -> bool:
        if self._contains_any_marker(normalized_message, "schedule"):
            return True
        return bool(self._extract_day_marker(normalized_message) or self._extract_time_marker(normalized_message))

    def _looks_like_class_location_request(self, normalized_message: str) -> bool:
        return ("classe" in normalized_message or "ma classe" in normalized_message or "mon classe" in normalized_message) and self._contains_any_marker(normalized_message, "class_location")

    def _looks_like_professor_location_followup(self, normalized_message: str) -> bool:
        return self._contains_any_marker(normalized_message, "professor_location")

    def _looks_like_professor_class_followup(self, normalized_message: str) -> bool:
        return self._contains_any_marker(normalized_message, "professor_class")

    def _looks_like_professor_current_course_followup(self, normalized_message: str) -> bool:
        return self._contains_any_marker(normalized_message, "professor_current_course") and self._extract_time_marker(normalized_message) == "now"

    def _looks_like_professor_has_course_followup(self, normalized_message: str) -> bool:
        return self._contains_any_marker(normalized_message, "professor_has_course")

    def _is_bare_professor_reply(self, normalized_message: str) -> bool:
        if not normalized_message:
            return False
        if self._contains_any_marker(normalized_message, "study_plan"):
            return False
        if self._contains_any_marker(normalized_message, "absence"):
            return False
        if self._contains_any_marker(normalized_message, "general_info"):
            return False
        if self._contains_any_marker(normalized_message, "schedule"):
            return False
        if self._contains_any_marker(normalized_message, "class_location"):
            return False
        if self._contains_any_marker(normalized_message, "professor_location"):
            return False
        if self._contains_any_marker(normalized_message, "professor_class"):
            return False
        if self._contains_any_marker(normalized_message, "professor_current_course"):
            return False
        if self._contains_any_marker(normalized_message, "professor_has_course"):
            return False
        if self._contains_any_marker(normalized_message, "available_rooms"):
            return False
        if self._contains_any_marker(normalized_message, "room_current_teacher"):
            return False
        return True

    def _is_bare_class_reply(self, normalized_message: str, class_candidate: Optional[str]) -> bool:
        if not normalized_message or not class_candidate:
            return False
        if self._contains_any_marker(normalized_message, "schedule"):
            return False
        if self._contains_any_marker(normalized_message, "class_location"):
            return False
        if self._contains_any_marker(normalized_message, "calendar"):
            return False
        return self._normalize_class_key(normalized_message) == self._normalize_class_key(class_candidate)

    def _is_short_day_followup(self, normalized_message: str, entities: IntentEntities) -> bool:
        if not normalized_message:
            return False
        if not (entities.day_marker or entities.time_marker):
            return False
        if entities.class_candidate or entities.professor_candidate or entities.room_candidate:
            return False
        stripped = re.sub(r"^(et|pour)\s+", "", normalized_message).strip()
        allowed_tokens = {"et", "pour", "demain", "aujourd", "aujourd hui", "hier", "maintenant", "actuellement"}
        if stripped in allowed_tokens:
            return True
        return stripped in self.MARKER_GROUPS["days"]

    def _is_short_study_plan_followup(self, normalized_message: str, state: ConversationState) -> bool:
        if state.last_intent != IntentLabel.UNIVERSITY_INFO.value or state.last_university_topic != "study_plan":
            return False
        if not normalized_message:
            return False
        return bool(self._extract_study_plan_followup_key(normalized_message))

    def _extract_study_plan_followup_key(self, normalized_message: str) -> Optional[str]:
        if any(marker in normalized_message for marker in ("gii", "informatique industrielle")):
            return "gii"
        if "gec" in normalized_message:
            return "gec"
        if re.search(r"\bgt\b", normalized_message) or "genie telecommunication" in normalized_message:
            return "gt"
        if "idsd" in normalized_message:
            return "idsd"
        return None

    def _is_short_count_followup(self, normalized_message: str, state: ConversationState) -> bool:
        if state.last_intent != IntentLabel.ALL_CLASSES.value:
            return False
        stripped = re.sub(r"^(et|pour)\s+", "", normalized_message).strip()
        return stripped in {"combien", "nombre", "combien de classes", "nombre de classes"}

    def _build_day_followup_question(self, entities: IntentEntities, state: ConversationState) -> Optional[str]:
        if not state.last_intent:
            return None

        day_suffix = self._day_suffix_from_entities(entities)
        if not day_suffix:
            return None

        if state.last_intent == IntentLabel.CLASS_SCHEDULE.value and state.last_class:
            return f"emploi du temps de {state.last_class}{day_suffix}"
        if state.last_intent == IntentLabel.CLASS_LOCATION.value and state.last_class:
            return f"ou se trouve la classe {state.last_class}{day_suffix}"
        if state.last_intent == IntentLabel.PROF_SCHEDULE.value and state.last_professor:
            return f"emploi du temps de {state.last_professor}{day_suffix}"
        if state.last_intent == IntentLabel.PROF_LOCATION.value and state.last_professor:
            return f"ou se trouve {state.last_professor}{day_suffix}"
        if state.last_intent == IntentLabel.PROF_CLASS.value and state.last_professor:
            return f"dans quelle classe se trouve {state.last_professor}{day_suffix}"
        if state.last_intent == IntentLabel.PROF_CURRENT_COURSE.value and state.last_professor:
            return f"quel cours fait {state.last_professor}{day_suffix or ' maintenant'}"
        if state.last_intent == IntentLabel.PROF_HAS_COURSE.value and state.last_professor:
            return f"{state.last_professor} a cours{day_suffix or ' aujourd hui'}"
        return None

    def _looks_like_bare_professor_name_input(self, message: str) -> bool:
        normalized_message = self._normalize_text(message)
        if not normalized_message or re.search(r"\d", normalized_message):
            return False
        if not re.fullmatch(r"[a-z\s'-]{3,}", normalized_message):
            return False
        return self._is_bare_professor_reply(normalized_message)

    def _looks_like_fresh_request(self, message: str, entities: IntentEntities) -> bool:
        normalized = self._normalize_text(message)
        if not normalized or normalized in self.YES_MARKERS or normalized in self.NO_MARKERS:
            return False
        return bool(
            self._infer_academic_intent(message, normalized, entities)
            or self._is_direct_university_question(normalized)
            or self._is_calendar_question(normalized)
        )

    def _extract_pending_request(self, history: list) -> Optional[tuple[str, str, str]]:
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
            "n existe pas dans la base de donnees",
            "voici des noms similaires",
        ]

        for i in range(len(history) - 1, -1, -1):
            role, content = self._history_message_parts(history[i])
            if role != "assistant":
                continue
            lowered = self._normalize_text(content or "")
            if any(trigger in lowered for trigger in class_triggers):
                prev_role, prev_content = self._history_message_parts(history[i - 1]) if i > 0 else ("", "")
                if prev_role == "user":
                    return (PendingSlot.CLASS.value, prev_content, content)
                break
            if any(trigger in lowered for trigger in professor_triggers):
                prev_role, prev_content = self._history_message_parts(history[i - 1]) if i > 0 else ("", "")
                if prev_role == "user":
                    return (PendingSlot.PROFESSOR.value, prev_content, content)
                break
        return None

    def _extract_confirmed_professor(self, message: str, assistant_message: str) -> Optional[str]:
        user_reply = self._clean_text(message)
        if not user_reply:
            return None
        if self._normalize_text(user_reply) in self.YES_MARKERS:
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

    def _replace_professor_in_question(self, original_question: str, professor_name: str) -> str:
        original_question = self._clean_text(original_question)
        professor_name = self._clean_text(professor_name)
        if not original_question or not professor_name:
            return original_question or professor_name

        normalized = self._normalize_text(original_question)
        day_suffix = ""
        if "demain" in normalized:
            day_suffix = " demain"
        elif "aujourd" in normalized:
            day_suffix = " aujourd'hui"
        elif "hier" in normalized:
            day_suffix = " hier"

        if self._is_prof_schedule_question(normalized, self._extract_entities(original_question)) or "emploi" in normalized:
            return f"emploi du temps de {professor_name}{day_suffix}"
        if "ou se trouve" in normalized or "dans quelle salle" in normalized or "ou est" in normalized:
            return f"ou se trouve {professor_name}{day_suffix}"
        if "quelle classe" in normalized or "dans quelle classe" in normalized:
            return f"dans quelle classe se trouve {professor_name}{day_suffix}"
        if "quel cours" in normalized or "quelle matiere" in normalized:
            return f"quel cours fait {professor_name}{day_suffix}"
        if "a cours" in normalized:
            return f"{professor_name} a cours{day_suffix or ' aujourd hui'}"

        existing_prof = self._extract_professor_candidate(original_question)
        if existing_prof:
            return re.sub(re.escape(existing_prof), professor_name, original_question, count=1, flags=re.IGNORECASE)
        return f"{original_question} pour le professeur {professor_name}"

    def _extract_professor_candidate(self, message: str) -> Optional[str]:
        q = self._clean_text(message)
        if not q or self._extract_class_candidate(q):
            return None

        def strip_trailing_time_words(value: str) -> str:
            return re.sub(
                r"\b(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|aujourd'hui|aujourdhui|demain|hier|maintenant|actuellement|mtn|en ce moment)\b.*$",
                "",
                value or "",
                flags=re.IGNORECASE,
            ).strip()

        title_match = re.search(
            r"\b(mr|mme|m\.|monsieur|madame)\s+([A-Za-zÀ-ÿ'\-]+(?:\s+[A-Za-zÀ-ÿ'\-]+){0,2})\b",
            q,
            re.IGNORECASE,
        )
        if title_match:
            candidate = strip_trailing_time_words(title_match.group(2).strip())
            return self._resolve_professor_candidate(candidate)

        schedule_match = re.search(
            r"\bemploi(?:s)?\s+(?:du|de)\s+temps+\s+de\s+([A-Za-zÀ-ÿ'\-]+(?:\s+[A-Za-zÀ-ÿ'\-]+){0,2})\s*$",
            q,
            re.IGNORECASE,
        )
        if schedule_match:
            candidate = strip_trailing_time_words(schedule_match.group(1).strip())
            return self._resolve_professor_candidate(candidate)

        location_match = re.search(
            r"(?:dans quelle classe se trouve|ou se trouve|pour quelle classe|quelle classe pour|quel cours fait|quelle matiere fait)\s+([A-Za-zÀ-ÿ'\-]+(?:\s+[A-Za-zÀ-ÿ'\-]+){0,2})$",
            q,
            re.IGNORECASE,
        )
        if location_match:
            candidate = strip_trailing_time_words(location_match.group(1).strip())
            return self._resolve_professor_candidate(candidate)

        if self._looks_like_bare_professor_name_input(q):
            exact_candidate = self._extract_db_professor_candidate(q)
            if exact_candidate:
                return exact_candidate
            return self._extract_fuzzy_db_professor_candidate(q)

        return None

    def _extract_room_candidate(self, message: str) -> Optional[str]:
        question_text = message or ""
        patterns = [
            r"\bsalle\s+([A-Za-z0-9][A-Za-z0-9\- ]*)\b",
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

    def _normalize_room_name(self, room_name: str) -> str:
        if not room_name:
            return ""
        room = re.sub(r"\s+", " ", room_name).strip().upper()
        room = re.sub(r"\b([A-Z])\s+(\d{2})\b", r"\1\2", room)
        room = re.sub(r"\b([A-Z])\s*0?(\d)\b", lambda match: f"{match.group(1)}{int(match.group(2)):02d}", room)
        room = re.sub(r"\bTEL-TCOM1\b", "TEL-TCOM 1", room)
        room = re.sub(r"\bEL-CI\s+AUTO\b", "EL-CI AUTO", room)
        room = re.sub(r"\s*/\s*", " / ", room)
        return room

    def _contains_any_marker(self, normalized_message: str, group_name: str) -> bool:
        return any(marker in normalized_message for marker in self.MARKER_GROUPS.get(group_name, ()))

    def _normalize_professor_token(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", self._normalize_text(value or ""))

    def _collapse_repeated_letters(self, value: str) -> str:
        return re.sub(r"([a-z0-9])\1{1,}", r"\1", value or "")

    def _professor_tokens_for_alias(self, value: str) -> list[str]:
        titles = {"mr", "mme", "m", "monsieur", "madame", "dr"}
        return [
            self._collapse_repeated_letters(token)
            for token in re.split(r"[\s/-]+", self._normalize_text(value or ""))
            if token and token not in titles
        ]

    def _load_available_professor_names_from_db(self) -> list[str]:
        if not self.db:
            return []
        try:
            rows = self.db.execute(
                text(
                    """
                    SELECT DISTINCT name
                    FROM (
                        SELECT p.nom_complet AS name FROM professeurs p
                        UNION
                        SELECT te.professeur_nom_complet AS name FROM emplois_enseignants_seances te
                    ) names
                    WHERE name IS NOT NULL AND TRIM(name) <> ''
                    ORDER BY name
                    """
                )
            ).fetchall()
        except Exception:
            return []
        return [str(row[0]).strip() for row in rows if row and str(row[0] or "").strip()]

    def _build_professor_aliases(self, professor_names: list[str]) -> dict[str, str]:
        aliases: dict[str, str] = {}
        single_token_candidates: dict[str, set[str]] = {}

        for professor_name in professor_names:
            normalized_name = re.sub(r"\s+", " ", professor_name).strip()
            if not normalized_name:
                continue
            tokens = self._professor_tokens_for_alias(normalized_name)
            if not tokens:
                continue

            alias_candidates = {
                " ".join(tokens),
                "".join(tokens),
            }
            if len(tokens) >= 2:
                alias_candidates.add(" ".join(list(reversed(tokens))))
                alias_candidates.add("".join(reversed(tokens)))

            for token in {tokens[0], tokens[-1]}:
                if len(token) >= 3:
                    single_token_candidates.setdefault(token, set()).add(normalized_name)

            for alias in alias_candidates:
                if alias:
                    aliases.setdefault(alias, normalized_name)

        for token, names in single_token_candidates.items():
            if len(names) == 1:
                aliases.setdefault(token, next(iter(names)))

        return aliases

    def _extract_db_professor_candidate(self, message: str) -> Optional[str]:
        if not self._professor_aliases:
            return None

        normalized_message = self._normalize_text(message or "")
        collapsed_message = self._collapse_repeated_letters(normalized_message)
        compact_message = re.sub(r"[\s/-]+", "", collapsed_message)
        best_match = None
        best_length = -1

        for alias, canonical_name in self._professor_aliases.items():
            if not alias:
                continue
            matched = False
            if " " in alias:
                if re.search(rf"\b{re.escape(alias)}\b", collapsed_message):
                    matched = True
            else:
                if re.search(rf"\b{re.escape(alias)}\b", collapsed_message) or alias in compact_message:
                    matched = True
            if matched and len(alias) > best_length:
                best_match = canonical_name
                best_length = len(alias)

        return best_match

    def _resolve_professor_candidate(self, candidate: Optional[str]) -> Optional[str]:
        cleaned_candidate = self._clean_text(candidate)
        if not self._is_valid_prof_candidate_text(cleaned_candidate):
            return None

        db_candidate = self._extract_db_professor_candidate(cleaned_candidate or "")
        if db_candidate:
            return db_candidate

        fuzzy_candidate = self._extract_fuzzy_db_professor_candidate(cleaned_candidate or "")
        if fuzzy_candidate:
            return fuzzy_candidate

        return cleaned_candidate

    def _extract_fuzzy_db_professor_candidate(self, candidate: str) -> Optional[str]:
        if not candidate or not self._available_professor_names:
            return None

        candidate_tokens = self._professor_tokens_for_alias(candidate)
        if not candidate_tokens:
            return None

        candidate_joined = "".join(candidate_tokens)
        scored_matches: list[tuple[float, str]] = []

        for professor_name in self._available_professor_names:
            professor_tokens = self._professor_tokens_for_alias(professor_name)
            if not professor_tokens:
                continue

            joined_score = SequenceMatcher(None, candidate_joined, "".join(professor_tokens)).ratio()
            token_scores = []
            for candidate_token in candidate_tokens:
                comparisons = [
                    SequenceMatcher(None, candidate_token, professor_token).ratio()
                    for professor_token in professor_tokens
                ]
                if comparisons:
                    token_scores.append(max(comparisons))

            average_token_score = sum(token_scores) / len(token_scores) if token_scores else 0.0
            score = max(joined_score, average_token_score, (joined_score * 0.45) + (average_token_score * 0.55))
            scored_matches.append((score, professor_name))

        if not scored_matches:
            return None

        scored_matches.sort(key=lambda item: (-item[0], item[1].lower()))
        best_score, best_name = scored_matches[0]
        second_score = scored_matches[1][0] if len(scored_matches) > 1 else 0.0

        if best_score >= 0.84 and (best_score - second_score) >= 0.05:
            return best_name
        return None

    def _load_available_class_names_from_db(self) -> list[str]:
        if not self.db:
            return []
        try:
            rows = self.db.execute(
                text(
                    """
                    SELECT DISTINCT c.nom
                    FROM classes c
                    WHERE c.nom IS NOT NULL AND TRIM(c.nom) <> ''
                    ORDER BY c.nom
                    """
                )
            ).fetchall()
        except Exception:
            return []
        return [str(row[0]).strip() for row in rows if row and str(row[0] or "").strip()]

    def _normalize_class_key(self, value: str) -> str:
        return re.sub(r"[\s/-]+", "", self._normalize_text(value or ""))

    def _build_class_aliases(self, class_names: list[str]) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for class_name in class_names:
            normalized_name = re.sub(r"\s+", " ", class_name).strip()
            if not normalized_name:
                continue
            alias_candidates = {self._normalize_class_key(normalized_name)}
            match = re.match(r"^(\d)\s+ING\s+([A-Z0-9\-]+)\s+(\d)$", normalized_name, flags=re.IGNORECASE)
            if match:
                year, specialty, group = match.group(1), match.group(2).upper(), match.group(3)
                alias_candidates.add(self._normalize_class_key(f"{year} {specialty} {group}"))
                alias_candidates.add(self._normalize_class_key(f"{year}{specialty}{group}"))
            for alias in alias_candidates:
                if alias:
                    aliases.setdefault(alias, normalized_name)
        return aliases

    def _build_dynamic_shorthand_codes(self, class_names: list[str]) -> set[str]:
        codes = set(self.CLASS_SHORTHAND_CODES)
        for class_name in class_names:
            match = re.match(r"^\d\s+ING\s+([A-Z0-9\-]+)\s+\d$", re.sub(r"\s+", " ", class_name).strip(), flags=re.IGNORECASE)
            if match:
                codes.add(match.group(1).upper())
        return codes

    def _extract_db_class_candidate(self, message: str) -> Optional[str]:
        if not self._class_aliases:
            return None
        compact_message = self._normalize_class_key(message or "")
        if not compact_message:
            return None
        for alias in sorted(self._class_aliases.keys(), key=len, reverse=True):
            if alias and alias in compact_message:
                return self._class_aliases[alias]
        return None

    def _extract_class_candidate(self, message: str) -> Optional[str]:
        q = (message or "").strip()
        if not q:
            return None

        db_candidate = self._extract_db_class_candidate(q)
        if db_candidate:
            return db_candidate

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
            if middle in self._dynamic_shorthand_codes:
                return f"{year} ING {middle} {group}"
            return f"{year} {middle} {group}"

        match = re.search(r"\b(\d)(GII|GEC|GT|IDSD|INFO|TELECOM)(\d)\b", q, flags=re.IGNORECASE)
        if match:
            year, specialty, group = match.group(1), match.group(2).upper(), match.group(3)
            return f"{year} ING {specialty} {group}"

        return None

    def _extract_time_marker(self, normalized_message: str) -> Optional[str]:
        if self._contains_any_marker(normalized_message, "time_now"):
            return "now"
        if "aujourd" in normalized_message:
            return "today"
        if "demain" in normalized_message:
            return "tomorrow"
        if "hier" in normalized_message:
            return "yesterday"
        return None

    def _extract_day_marker(self, normalized_message: str) -> Optional[str]:
        for day_name in self.MARKER_GROUPS["days"]:
            if re.search(rf"\b{day_name}\b", normalized_message):
                return day_name
        return None

    def _extract_university_topic(self, normalized_message: str) -> Optional[str]:
        topic_groups = {
            "study_plan": "study_plan",
            "absence": "absence",
            "general_info": "general_info",
            "calendar": "calendar",
        }
        for topic, group_name in topic_groups.items():
            if self._contains_any_marker(normalized_message, group_name):
                return topic
        if any(marker in normalized_message for marker in ["news", "annonce"]):
            return "news"
        return None

    def _is_obvious_academic_request(self, message: str) -> bool:
        return bool(self.groq_service.is_obvious_academic_request(message))

    def _is_simple_conversation(self, message: str) -> bool:
        return bool(self.groq_service.is_simple_conversation(message))

    def _normalize_text(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = normalized.lower().replace("'", " ")
        normalized = re.sub(r"[^\w\s/-]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        typo_fixes = {
            "maintement": "maintenant",
            "maintenent": "maintenant",
            "disponnible": "disponible",
            "feriee": "ferie",
            "feries": "ferie",
            "ferier": "ferie",
            "prochien": "prochain",
            "tempss": "temps",
            "lemploi": "emploi",
            "l emploi": "emploi",
            "ou ce trouve": "ou se trouve",
        }
        for source, target in typo_fixes.items():
            normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized)
        return normalized

    def _clean_text(self, value: Optional[str]) -> Optional[str]:
        cleaned = re.sub(r"\s+", " ", (value or "")).strip()
        return cleaned or None

    def _history_message_parts(self, item: Any) -> tuple[str, str]:
        role = getattr(item, "role", None)
        content = getattr(item, "content", None)
        if isinstance(item, dict):
            role = item.get("role", role)
            content = item.get("content", content)
        return str(role or "").strip(), str(content or "").strip()

    def _is_valid_prof_candidate_text(self, candidate: Optional[str]) -> bool:
        normalized_candidate = self._normalize_text(candidate or "")
        if not normalized_candidate:
            return False

        candidate_tokens = [token for token in re.split(r"\s+", normalized_candidate) if token]
        invalid_candidates = {
            "ma classe",
            "mon classe",
            "ma salle",
            "mon salle",
            "mon groupe",
            "ma groupe",
            "mon emploi",
            "mon edt",
            "mon planning",
            "cette annee",
            "donner lavis dabsence",
            "lavis dabsence",
            "avis dabsence",
            "avis d absence",
        }
        invalid_tokens = {
            "les",
            "des",
            "prochain",
            "prochaine",
            "prochains",
            "prochaines",
            "devoir",
            "devoirs",
            "controle",
            "controles",
            "j",
            "ai",
            "quoi",
            "lundi",
            "mardi",
            "mercredi",
            "jeudi",
            "vendredi",
            "samedi",
            "dimanche",
            "pour",
            "classe",
            "cours",
            "salle",
            "demain",
            "hier",
            "cette",
            "annee",
            "ferie",
            "vacance",
            "vacances",
            "jour",
            "jours",
            "directeur",
            "direction",
            "enetcom",
            "universite",
            "ecole",
            "adresse",
            "contact",
            "plan",
            "etude",
            "etudes",
            "programme",
            "curriculum",
            "actualite",
            "actualites",
            "emploi",
            "temps",
            "planning",
            "horaire",
            "edt",
            "absence",
            "absences",
            "avis",
            "lavis",
            "dabsence",
            "donner",
            "extranet",
            "login",
            "connexion",
        }
        return not (
            normalized_candidate in invalid_candidates
            or any(token in invalid_tokens for token in candidate_tokens)
        )

    def _day_suffix_from_entities(self, entities: IntentEntities) -> str:
        if entities.day_marker:
            return f" {entities.day_marker}"
        if entities.time_marker == "today":
            return " aujourd'hui"
        if entities.time_marker == "tomorrow":
            return " demain"
        if entities.time_marker == "yesterday":
            return " hier"
        return ""
