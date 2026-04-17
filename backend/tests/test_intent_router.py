import unittest

from app.services.intent_router import ExecutionTarget, IntentLabel, IntentRouter


class DummyGroqService:
    def __init__(self, classify_result="NON_ACADEMIC", assistant_intent=None, analysis_result=None):
        self.classify_result = classify_result
        self.assistant_intent = assistant_intent
        self.analysis_result = analysis_result

    def is_obvious_academic_request(self, message: str) -> bool:
        normalized = (message or "").lower()
        return any(marker in normalized for marker in ["emploi", "plan", "absence", "salle", "prof", "cours", "enetcom"])

    def is_simple_conversation(self, message: str) -> bool:
        normalized = (message or "").strip().lower()
        return normalized in {"bonjour", "salut", "merci"}

    def classify_message_mode(self, message: str, history=None):
        return self.classify_result

    def classify_assistant_intent(self, message: str, history=None):
        return self.assistant_intent

    def analyze_user_message(self, message: str, history=None):
        return self.analysis_result


class DummyAgent:
    def _professor_confirmation_message(self, professor_name: str):
        if professor_name == "soulef":
            return "Voulez-vous dire le professeur 'FRIKHA Soulef' ?"
        return None


class FakeQueryResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeDb:
    def __init__(self, class_names=None, professor_names=None):
        self.class_names = class_names
        self.professor_names = professor_names or []

    def execute(self, query):
        query_text = str(query)
        if "FROM classes" in query_text:
            return FakeQueryResult([(class_name,) for class_name in (self.class_names or [])])
        return FakeQueryResult([(professor_name,) for professor_name in self.professor_names])


class IntentRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter(DummyGroqService())

    def test_university_question_returns_structured_decision(self):
        decision = self.router.route("plan detude de gii", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.UNIVERSITY_INFO.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.UNIVERSITY_SERVICE.value)
        self.assertEqual(decision.entities.university_topic, "study_plan")
        self.assertGreaterEqual(decision.confidence, 0.9)
        self.assertEqual(decision.to_dict()["entities"]["university_topic"], "study_plan")

    def test_plan_etude_without_preposition_is_routed_to_university_service(self):
        decision = self.router.route("plan etude gii", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.UNIVERSITY_INFO.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.UNIVERSITY_SERVICE.value)
        self.assertEqual(decision.entities.university_topic, "study_plan")

    def test_plural_study_plan_variant_is_routed_to_university_service(self):
        decision = self.router.route("plans etudes", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.UNIVERSITY_INFO.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.UNIVERSITY_SERVICE.value)

    def test_short_study_plan_followup_reuses_last_university_context(self):
        history = [
            {"role": "user", "content": "montre moi les plans d'etude"},
            {"role": "assistant", "content": "Voici les URLs des plans d'etudes ENET'Com."},
        ]

        decision = self.router.route("et pour gii ?", history=history, user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.UNIVERSITY_INFO.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.UNIVERSITY_SERVICE.value)
        self.assertEqual(decision.source, "conversation_state")
        self.assertEqual(decision.full_question, "plan etude gii")

    def test_router_uses_structured_state_for_pending_professor_confirmation(self):
        history = [
            {"role": "user", "content": "ou ce trouve mr ali khalfalah maintenant"},
            {"role": "assistant", "content": "Le nom 'ali khalfalah' ressemble a 'KHALFALLAH Ali'. Voulez-vous dire ce professeur ?"},
        ]

        decision = self.router.route("oui", history=history, user_class=None, agent=DummyAgent())

        self.assertEqual(decision.state.pending_slot, "professor")
        self.assertEqual(decision.intent, IntentLabel.PROF_LOCATION.value)
        self.assertEqual(decision.full_question, "ou se trouve KHALFALLAH Ali")
        self.assertEqual(decision.source, "conversation_state")

    def test_router_appends_known_class_for_class_schedule_followup(self):
        history = [
            {"role": "user", "content": "emploi de temps de 2gii3"},
            {"role": "assistant", "content": "Voici votre emploi du temps."},
        ]

        decision = self.router.route("j'ai quoi demain", history=history, user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.CLASS_SCHEDULE.value)
        self.assertEqual(decision.full_question, "j'ai quoi demain pour la classe 2 ING GII 3")
        self.assertEqual(decision.state.last_class, "2 ING GII 3")

    def test_short_day_followup_reuses_last_schedule_context(self):
        history = [
            {"role": "user", "content": "emploi de temps de 2gii3"},
            {"role": "assistant", "content": "Voici votre emploi du temps."},
        ]

        decision = self.router.route("et demain ?", history=history, user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.CLASS_SCHEDULE.value)
        self.assertEqual(decision.source, "conversation_state")
        self.assertEqual(decision.full_question, "emploi du temps de 2 ING GII 3 demain")

    def test_single_name_professor_schedule_triggers_confirmation(self):
        decision = self.router.route("emploi de temps de soulef", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.NEEDS_PROF_CONFIRMATION.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.CLARIFICATION.value)
        self.assertTrue(decision.needs_confirmation)
        self.assertIn("FRIKHA Soulef", decision.direct_response or "")

    def test_smalltalk_is_separated_from_academic_execution(self):
        decision = self.router.route("bonjour", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.CHAT_SMALLTALK.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.SMALLTALK.value)

    def test_low_confidence_model_academic_route_requests_clarification(self):
        router = IntentRouter(DummyGroqService(classify_result="ACADEMIC", assistant_intent="TIMETABLE"))
        decision = router.route("je veux savoir", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.execution_target, ExecutionTarget.CLARIFICATION.value)
        self.assertTrue(decision.needs_clarification)
        self.assertIn("reformuler", decision.direct_response or "")

    def test_model_detected_enetcom_info_goes_to_university_service(self):
        router = IntentRouter(DummyGroqService(assistant_intent="ENETCOM_INFO"))

        decision = router.route("comment fonctionne le club robotique", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.UNIVERSITY_INFO.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.UNIVERSITY_SERVICE.value)
        self.assertEqual(decision.source, "model_classification")

    def test_model_detected_greeting_goes_to_smalltalk(self):
        router = IntentRouter(DummyGroqService(assistant_intent="GREETING"))

        decision = router.route("wesh tu peux faire quoi", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.CHAT_SMALLTALK.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.SMALLTALK.value)
        self.assertEqual(decision.source, "model_classification")

    def test_structured_model_analysis_routes_professor_location(self):
        router = IntentRouter(
            DummyGroqService(
                analysis_result={
                    "intent": "PROF_LOCATION",
                    "answer_source": "DATABASE",
                    "confidence": 0.91,
                    "standalone_query": "ou se trouve KHALFALLAH Ali aujourd'hui",
                    "class_name": None,
                    "professor_name": "KHALFALLAH Ali",
                    "room_name": None,
                    "day_hint": "aujourd'hui",
                    "time_hint": "maintenant",
                    "university_topic": None,
                }
            )
        )

        decision = router.route("ou est ali maintenant", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.PROF_LOCATION.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.SQL_AGENT.value)
        self.assertEqual(decision.source, "model_analysis")
        self.assertEqual(decision.entities.professor_candidate, "KHALFALLAH Ali")
        self.assertEqual(decision.full_question, "ou se trouve KHALFALLAH Ali aujourd'hui")

    def test_structured_model_analysis_routes_enetcom_info(self):
        router = IntentRouter(
            DummyGroqService(
                analysis_result={
                    "intent": "ENETCOM_INFO",
                    "answer_source": "UNIVERSITY_SITE",
                    "confidence": 0.94,
                    "standalone_query": "clubs et vie associative a ENET'Com",
                    "class_name": None,
                    "professor_name": None,
                    "room_name": None,
                    "day_hint": None,
                    "time_hint": None,
                    "university_topic": "clubs",
                }
            )
        )

        decision = router.route("parle moi des clubs", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.UNIVERSITY_INFO.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.UNIVERSITY_SERVICE.value)
        self.assertEqual(decision.source, "model_analysis")
        self.assertEqual(decision.entities.university_topic, "clubs")
        self.assertEqual(decision.full_question, "clubs et vie associative a ENET'Com")

    def test_model_analysis_reinterprets_fake_class_as_professor_schedule(self):
        router = IntentRouter(
            DummyGroqService(
                analysis_result={
                    "intent": "CLASS_SCHEDULE",
                    "confidence": 0.8,
                    "class_name": "emploi",
                    "professor_name": "Ali Khalflah",
                    "room_name": None,
                    "day_hint": None,
                    "time_hint": None,
                    "university_topic": None,
                }
            )
        )

        decision = router.route("emploi ali khalflah", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.PROF_SCHEDULE.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.SQL_AGENT.value)
        self.assertIsNone(decision.entities.class_candidate)

    def test_model_analysis_with_fake_room_drops_to_clarification(self):
        router = IntentRouter(
            DummyGroqService(
                analysis_result={
                    "intent": "ROOM_CURRENT_TEACHER",
                    "confidence": 0.8,
                    "class_name": None,
                    "professor_name": None,
                    "room_name": "C11",
                    "day_hint": "demain",
                    "time_hint": "tomorrow",
                    "university_topic": None,
                }
            )
        )

        decision = router.route("qui sera basent demain", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.execution_target, ExecutionTarget.CLARIFICATION.value)
        self.assertTrue(decision.needs_clarification)

    def test_room_shorthand_is_detected_from_message(self):
        router = IntentRouter(
            DummyGroqService(
                analysis_result={
                    "intent": "ROOM_SCHEDULE",
                    "answer_source": "DATABASE",
                    "confidence": 0.9,
                    "standalone_query": "emploi du temps de salle C11",
                    "class_name": None,
                    "professor_name": None,
                    "room_name": "C11",
                    "day_hint": None,
                    "time_hint": None,
                    "university_topic": None,
                }
            )
        )

        decision = router.route("emploi c11", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.ROOM_SCHEDULE.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.SQL_AGENT.value)
        self.assertEqual(decision.entities.room_candidate, "C11")
        self.assertEqual(decision.full_question, "emploi du temps de salle C11")

    def test_self_identified_professor_has_course_question_is_routed_as_prof(self):
        router = IntentRouter(
            DummyGroqService(),
            db=FakeDb(class_names=[], professor_names=["KHALFALLAH Ali"]),
        )

        decision = router.route("je suis ali khalflah est ce jai cours demain", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.PROF_HAS_COURSE.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.SQL_AGENT.value)
        self.assertEqual(decision.entities.professor_candidate, "KHALFALLAH Ali")

    def test_model_professor_name_is_canonicalized_from_database(self):
        router = IntentRouter(
            DummyGroqService(
                analysis_result={
                    "intent": "PROF_SCHEDULE",
                    "answer_source": "DATABASE",
                    "confidence": 0.9,
                    "standalone_query": "emploi du temps de BEN SLIMA Mohamed",
                    "class_name": None,
                    "professor_name": "Mohamed Ben Slima",
                    "room_name": None,
                    "day_hint": None,
                    "time_hint": None,
                    "university_topic": None,
                }
            ),
            db=FakeDb(class_names=[], professor_names=["BEN SLIMA Mohamed"]),
        )

        decision = router.route("emploi de mohamed ben slima", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.PROF_SCHEDULE.value)
        self.assertEqual(decision.entities.professor_candidate, "BEN SLIMA Mohamed")
        self.assertEqual(decision.full_question, "emploi du temps de BEN SLIMA Mohamed")

    def test_noisy_professor_schedule_from_model_is_not_blocked_when_query_is_clear(self):
        router = IntentRouter(
            DummyGroqService(
                analysis_result={
                    "intent": "PROF_SCHEDULE",
                    "answer_source": "DATABASE",
                    "confidence": 0.55,
                    "standalone_query": "emploi du temps de KHALFALLAH Ali",
                    "class_name": None,
                    "professor_name": "KHALFALLAH Ali",
                    "room_name": None,
                    "day_hint": None,
                    "time_hint": None,
                    "university_topic": None,
                }
            ),
            db=FakeDb(class_names=[], professor_names=["KHALFALLAH Ali"]),
        )

        decision = router.route("emplois dee tmeps ali khalflah", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.PROF_SCHEDULE.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.SQL_AGENT.value)
        self.assertEqual(decision.full_question, "emploi du temps de KHALFALLAH Ali")

    def test_model_professor_schedule_is_rewritten_with_canonical_professor_name(self):
        router = IntentRouter(
            DummyGroqService(
                analysis_result={
                    "intent": "PROF_SCHEDULE",
                    "answer_source": "DATABASE",
                    "confidence": 0.8,
                    "standalone_query": "Quel est l'emploi du temps d'Ali Khalfalah",
                    "class_name": None,
                    "professor_name": "Ali Khalfalah",
                    "room_name": None,
                    "day_hint": None,
                    "time_hint": None,
                    "university_topic": None,
                }
            ),
            db=FakeDb(class_names=[], professor_names=["KHALFALLAH Ali"]),
        )

        decision = router.route("emploi de temps de ali khalfalah", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.PROF_SCHEDULE.value)
        self.assertEqual(decision.entities.professor_candidate, "KHALFALLAH Ali")
        self.assertEqual(decision.full_question, "emploi du temps de KHALFALLAH Ali")

    def test_model_professor_schedule_ignores_bad_standalone_query_shape(self):
        router = IntentRouter(
            DummyGroqService(
                analysis_result={
                    "intent": "PROF_SCHEDULE",
                    "answer_source": "DATABASE",
                    "confidence": 0.9,
                    "standalone_query": "emploi du temps de la classe de Mohamed Ben Slima",
                    "class_name": None,
                    "professor_name": "Mohamed Ben Slima",
                    "room_name": None,
                    "day_hint": None,
                    "time_hint": None,
                    "university_topic": None,
                }
            ),
            db=FakeDb(class_names=[], professor_names=["BEN SLIMA Mohamed"]),
        )

        decision = router.route("emploi de temps de mohamed ben slima", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.PROF_SCHEDULE.value)
        self.assertEqual(decision.entities.professor_candidate, "BEN SLIMA Mohamed")
        self.assertEqual(decision.full_question, "emploi du temps de BEN SLIMA Mohamed")

    def test_router_extracts_available_classes_from_database(self):
        router = IntentRouter(
            DummyGroqService(),
            db=FakeDb(["2 ING IA 1", "1 ING GII 2"]),
        )

        decision = router.route("emploi de temps de 2ia1", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.entities.class_candidate, "2 ING IA 1")
        self.assertEqual(decision.intent, IntentLabel.CLASS_SCHEDULE.value)
        self.assertEqual(decision.full_question, "emploi du temps de 2 ING IA 1")

    def test_router_extracts_available_professors_from_database(self):
        router = IntentRouter(
            DummyGroqService(),
            db=FakeDb(class_names=[], professor_names=["FRIKHA Soulef", "KHALFALLAH Ali"]),
        )

        decision = router.route("emploi de temps de soulef frikha", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.entities.professor_candidate, "FRIKHA Soulef")
        self.assertEqual(decision.intent, IntentLabel.PROF_SCHEDULE.value)

    def test_router_resolves_professor_typos_with_balanced_fuzzy_matching(self):
        router = IntentRouter(
            DummyGroqService(),
            db=FakeDb(class_names=[], professor_names=["LOUZ Adnen"]),
        )

        decision = router.route("emploi de tempss de adnen louuz", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.PROF_SCHEDULE.value)
        self.assertEqual(decision.entities.professor_candidate, "LOUZ Adnen")
        self.assertEqual(decision.full_question, "emploi du temps de LOUZ Adnen")

    def test_not_found_similar_professors_message_creates_pending_professor_state(self):
        router = IntentRouter(
            DummyGroqService(),
            db=FakeDb(class_names=[], professor_names=["BEN SLIMA Mohamed", "MASMOUDI SLIM"]),
        )
        history = [
            {"role": "user", "content": "emploi de temps de BEN SLIMA"},
            {
                "role": "assistant",
                "content": "Le professeur 'BEN SLIMA' n'existe pas dans la base de donnees. Voici des noms similaires : BEN SLIMA Mohamed, MASMOUDI SLIM.",
            },
        ]

        decision = router.route("BEN SLIMA Mohamed", history=history, user_class=None, agent=DummyAgent())

        self.assertEqual(decision.state.pending_slot, "professor")
        self.assertEqual(decision.intent, IntentLabel.PROF_SCHEDULE.value)
        self.assertEqual(decision.full_question, "emploi du temps de BEN SLIMA Mohamed")

    def test_bare_professor_name_reuses_last_professor_intent(self):
        router = IntentRouter(
            DummyGroqService(),
            db=FakeDb(class_names=[], professor_names=["BEN SLIMA Mohamed"]),
        )
        history = [
            {"role": "user", "content": "emploi de temps de BEN SLIMA Mohamed"},
            {"role": "assistant", "content": "Aucun cours trouve pour BEN SLIMA Mohamed dans la periode active S2/P2."},
        ]

        decision = router.route("BEN SLIMA Mohamed", history=history, user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.PROF_SCHEDULE.value)
        self.assertEqual(decision.full_question, "emploi du temps de BEN SLIMA Mohamed")

    def test_professor_similar_name_reply_stays_in_professor_flow(self):
        router = IntentRouter(
            DummyGroqService(),
            db=FakeDb(class_names=[], professor_names=["SMAOUI Souhail", "SMAOUI Soulaymen", "SALIMA Smaoui"]),
        )
        history = [
            {"role": "user", "content": "emploi de temps de smaoui souhaail"},
            {
                "role": "assistant",
                "content": "Le professeur 'smaoui souhaail' n'existe pas dans la base de donnees. Voici des noms similaires : SMAOUI Souhail, SMAOUI Soulaymen, SALIMA Smaoui.",
            },
        ]

        decision = router.route("SMAOUI Souhail", history=history, user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.PROF_SCHEDULE.value)
        self.assertEqual(decision.source, "conversation_state")

    def test_professor_class_confirmation_keeps_prof_class_intent(self):
        router = IntentRouter(
            DummyGroqService(),
            db=FakeDb(class_names=[], professor_names=["ELLOUZE Nebrasse", "ELLOUZE Adnene", "ELLOUZE Hanene"]),
        )
        history = [
            {"role": "user", "content": "dans quel classe existe nebrasse ellouz demain"},
            {
                "role": "assistant",
                "content": "Le nom 'Nebrasse Ellouz' est ambigu. Voulez-vous dire : ELLOUZE Nebrasse, ELLOUZE Adnene, ELLOUZE Hanene ?",
            },
        ]

        decision = router.route("ELLOUZE Nebrasse", history=history, user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.PROF_CLASS.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.SQL_AGENT.value)
        self.assertEqual(decision.full_question, "dans quelle classe se trouve ELLOUZE Nebrasse demain")

    def test_calendar_request_is_routed_without_falling_to_out_of_scope(self):
        decision = self.router.route("les jours ferier prochaines", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.CALENDAR.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.SQL_AGENT.value)
        self.assertEqual(decision.entities.university_topic, "calendar")

    def test_model_holidays_topic_overrides_university_site_to_calendar(self):
        router = IntentRouter(
            DummyGroqService(
                analysis_result={
                    "intent": "ENETCOM_INFO",
                    "answer_source": "UNIVERSITY_SITE",
                    "confidence": 0.9,
                    "standalone_query": "Quand sont les vacances ?",
                    "class_name": None,
                    "professor_name": None,
                    "room_name": None,
                    "day_hint": None,
                    "time_hint": None,
                    "university_topic": "vacances",
                }
            )
        )

        decision = router.route("il ya tils des vacances ?", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.CALENDAR.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.SQL_AGENT.value)
        self.assertEqual(decision.entities.university_topic, "calendar")
        self.assertEqual(decision.full_question, "Quand sont les vacances ?")

    def test_model_exam_calendar_topic_overrides_university_site_to_calendar(self):
        router = IntentRouter(
            DummyGroqService(
                analysis_result={
                    "intent": "ENETCOM_INFO",
                    "answer_source": "UNIVERSITY_SITE",
                    "confidence": 0.9,
                    "standalone_query": "calendrier des examens ENET'Com",
                    "class_name": None,
                    "professor_name": None,
                    "room_name": None,
                    "day_hint": None,
                    "time_hint": None,
                    "university_topic": "exams",
                }
            )
        )

        decision = router.route("calendrier des examens", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.CALENDAR.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.SQL_AGENT.value)
        self.assertEqual(decision.entities.university_topic, "calendar")
        self.assertEqual(decision.full_question, "calendrier des examens ENET'Com")

    def test_absent_question_is_routed_to_university_service_without_model(self):
        decision = self.router.route("qui est absent ?", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.UNIVERSITY_INFO.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.UNIVERSITY_SERVICE.value)
        self.assertEqual(decision.entities.university_topic, "absence")

    def test_all_classes_question_is_not_routed_to_university_general_info(self):
        router = IntentRouter(
            DummyGroqService(),
            db=FakeDb(class_names=["1 MP SE"], professor_names=["BEN SALAH LASSED"]),
        )

        decision = router.route("quels sont les classes existes dans enetcom", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.ALL_CLASSES.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.SQL_AGENT.value)
        self.assertIsNone(decision.entities.professor_candidate)

    def test_class_count_question_is_not_mistaken_for_professor(self):
        router = IntentRouter(
            DummyGroqService(),
            db=FakeDb(class_names=["1 MP SE"], professor_names=["BEN SALAH LASSED"]),
        )

        decision = router.route("combien de classe dans enetcom", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.ALL_CLASSES.value)
        self.assertIsNone(decision.entities.professor_candidate)

    def test_short_count_followup_reuses_all_classes_context(self):
        history = [
            {"role": "user", "content": "quelles classes existent dans enetcom"},
            {"role": "assistant", "content": "Voici les classes disponibles a ENET'Com :"},
        ]

        decision = self.router.route("combien ?", history=history, user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.ALL_CLASSES.value)
        self.assertEqual(decision.source, "conversation_state")
        self.assertEqual(decision.full_question, "combien de classes dans enetcom")

    def test_compact_class_name_is_canonicalized_for_sql_execution(self):
        router = IntentRouter(
            DummyGroqService(),
            db=FakeDb(["1 MP SE", "1 MP INF IND"]),
        )

        decision = router.route("emploi de temps de 1mpse", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.CLASS_SCHEDULE.value)
        self.assertEqual(decision.entities.class_candidate, "1 MP SE")
        self.assertEqual(decision.full_question, "emploi du temps de 1 MP SE")

    def test_bare_class_reply_reuses_last_class_schedule_intent(self):
        router = IntentRouter(
            DummyGroqService(),
            db=FakeDb(["1 MP INF IND"]),
        )
        history = [
            {"role": "user", "content": "emploi de temps 1 MPINF IND"},
            {"role": "assistant", "content": "Aucune donnee trouvee pour cette question."},
        ]

        decision = router.route("1 MP INF IND", history=history, user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.CLASS_SCHEDULE.value)
        self.assertEqual(decision.full_question, "emploi du temps de 1 MP INF IND")

    def test_non_professor_phrase_does_not_pollute_professor_context(self):
        history = [
            {"role": "user", "content": "les prochien devoirs"},
            {"role": "assistant", "content": "Aucune donnee trouvee pour cette question."},
        ]

        decision = self.router.route("emploi de temps de 1 MP SE", history=history, user_class=None, agent=DummyAgent())

        self.assertIsNone(decision.state.last_professor)

    def test_no_reply_cancels_pending_confirmation(self):
        history = [
            {"role": "user", "content": "emploi de temps de ali khalflah"},
            {"role": "assistant", "content": "Le nom 'ali khalflah' ressemble a 'KHALFALLAH Ali'. Voulez-vous dire ce professeur ?"},
        ]

        decision = self.router.route("non", history=history, user_class=None, agent=DummyAgent())

        self.assertEqual(decision.execution_target, ExecutionTarget.CLARIFICATION.value)
        self.assertTrue(decision.needs_clarification)
        self.assertIn("Reformulez", decision.direct_response or "")


if __name__ == "__main__":
    unittest.main()
