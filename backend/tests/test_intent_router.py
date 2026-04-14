import unittest

from app.services.intent_router import ExecutionTarget, IntentLabel, IntentRouter


class DummyGroqService:
    def __init__(self, classify_result="NON_ACADEMIC"):
        self.classify_result = classify_result

    def is_obvious_academic_request(self, message: str) -> bool:
        normalized = (message or "").lower()
        return any(marker in normalized for marker in ["emploi", "plan", "absence", "salle", "prof", "cours", "enetcom"])

    def is_simple_conversation(self, message: str) -> bool:
        normalized = (message or "").strip().lower()
        return normalized in {"bonjour", "salut", "merci"}

    def classify_message_mode(self, message: str, history=None):
        return self.classify_result


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
        router = IntentRouter(DummyGroqService(classify_result="ACADEMIC"))
        decision = router.route("je veux savoir", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.execution_target, ExecutionTarget.CLARIFICATION.value)
        self.assertTrue(decision.needs_clarification)
        self.assertIn("reformuler", decision.direct_response or "")

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

    def test_calendar_request_is_routed_without_falling_to_out_of_scope(self):
        decision = self.router.route("les jours ferier prochaines", history=[], user_class=None, agent=DummyAgent())

        self.assertEqual(decision.intent, IntentLabel.CALENDAR.value)
        self.assertEqual(decision.execution_target, ExecutionTarget.SQL_AGENT.value)
        self.assertEqual(decision.entities.university_topic, "calendar")

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
