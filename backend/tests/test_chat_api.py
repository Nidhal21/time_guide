import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.services.groq_service import groq_service
from app.services.sql_agent import SQLAgent
from main import app


class ChatApiWeekdaySmokeTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_lowercase_monday_sql_is_rewritten_and_returns_rows(self):
        sql = """
        SELECT s.id, c.nom AS class_name, m.nom AS matiere, p.nom_complet AS prof, sa.nom AS room, s.jour, s.heure_debut, s.heure_fin
        FROM seances s
        JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id
        JOIN classes c ON c.id = s.classe_id
        JOIN matieres m ON m.id = s.matiere_id
        JOIN professeurs p ON p.id = s.professeur_id
        JOIN salles sa ON sa.id = s.salle_id
        WHERE s.jour = 'lundi'
          AND REPLACE(LOWER(c.nom), ' ', '') LIKE '%' || REPLACE(LOWER('1 ING GII 2'), ' ', '') || '%'
          AND s.periode_id = 4;
        """.strip()

        original_enabled = getattr(groq_service, "enabled", False)
        groq_service.enabled = True

        try:
            with patch.object(groq_service, "generate_sql", return_value=sql), patch.object(
                groq_service,
                "format_response",
                side_effect=lambda question, data, context: f"{len(data)} lignes pour {data[0]['jour']}",
            ):
                response = self.client.post(
                    "/api/chat",
                    json={
                        "message": "Quels sont les cours de lundi pour 1 ING GII 2 ?",
                        "user_role": "student",
                        "history": [],
                    },
                )
        finally:
            groq_service.enabled = original_enabled

        self.assertEqual(response.status_code, 200)
        body = response.json()["response"]
        self.assertNotEqual(body, "Aucune donnée trouvée pour cette question.")
        self.assertRegex(body, r"\d+\s+lignes")
        self.assertIn("Lundi", body)

    def test_room_lookup_response_is_not_formatted_as_weekly_timetable(self):
        original_enabled = getattr(groq_service, "enabled", False)
        groq_service.enabled = True

        try:
            with patch(
                "app.services.sql_agent.SQLAgent._exec_and_format_v2",
                return_value="En salle C01, c'est Mr BEN SLIMA M. qui enseigne actuellement.",
            ):
                response = self.client.post(
                    "/api/chat",
                    json={
                        "message": "Qui enseigne maintenant en salle C01 ?",
                        "user_role": "student",
                        "history": [],
                    },
                )
        finally:
            groq_service.enabled = original_enabled

        self.assertEqual(response.status_code, 200)
        body = response.json()["response"]
        self.assertIn("En salle C01", body)
        self.assertNotIn("Lundi :", body)

    def test_unknown_professor_returns_explicit_not_found_message(self):
        original_enabled = getattr(groq_service, "enabled", False)
        groq_service.enabled = True

        try:
            response = self.client.post(
                "/api/chat",
                json={
                    "message": "ou se trouve madame nesrine zouri",
                    "user_role": "student",
                    "history": [],
                },
            )
        finally:
            groq_service.enabled = original_enabled

        self.assertEqual(response.status_code, 200)
        body = response.json()["response"]
        self.assertIn("Je ne trouve pas le professeur", body)

    def test_unknown_professor_schedule_returns_similar_names(self):
        with patch(
            "app.services.sql_agent.get_current_academic_context",
            return_value={"date_actuelle": "2026-03-30", "jour_actuel": "Lundi", "semestre": "S2", "periode": "P2"},
        ), patch.object(SQLAgent, "_prof_exists_in_db", return_value=False), patch.object(
            SQLAgent,
            "_find_similar_professors",
            return_value=["ALI KHLFALLAH", "ALI KHALFEDIN"],
        ):
            response = self.client.post(
                "/api/chat",
                json={
                    "message": "emploi de temps de mr ali khalfeoui",
                    "user_role": "student",
                    "history": [],
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()["response"]
        self.assertIn("ali khalfeoui", body.lower())
        self.assertIn("ALI KHLFALLAH", body)
        self.assertIn("ALI KHALFEDIN", body)

    def test_calendar_no_vacation_today_returns_explicit_negative_message(self):
        original_enabled = getattr(groq_service, "enabled", False)
        groq_service.enabled = True

        try:
            response = self.client.post(
                "/api/chat",
                json={
                    "message": "Y a-t-il des vacances aujourd'hui ?",
                    "user_role": "student",
                    "history": [],
                },
            )
        finally:
            groq_service.enabled = original_enabled

        self.assertEqual(response.status_code, 200)
        body = response.json()["response"]
        self.assertIn("il n'y a pas de vacances", body.lower())

    def test_calendar_year_holidays_lists_results(self):
        original_enabled = getattr(groq_service, "enabled", False)
        groq_service.enabled = True

        try:
            response = self.client.post(
                "/api/chat",
                json={
                    "message": "Quels sont les jours feries de cette annee ?",
                    "user_role": "student",
                    "history": [],
                },
            )
        finally:
            groq_service.enabled = original_enabled

        self.assertEqual(response.status_code, 200)
        body = response.json()["response"]
        self.assertNotIn("Je ne trouve pas le professeur", body)
        self.assertIn("Journée d'intégration", body)

    def test_available_rooms_for_day_does_not_ask_for_class(self):
        response = self.client.post(
            "/api/chat",
            json={
                "message": "quelles sont les salles disponibles lundi",
                "user_role": "student",
                "history": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()["response"]
        self.assertNotIn("Quelle est votre classe", body)
        self.assertIn("salles disponibles", body)

    def test_new_explicit_class_question_does_not_reuse_previous_pending_class(self):
        history = [
            {"role": "user", "content": "emploi de temps de 2gec3"},
            {"role": "assistant", "content": "Quelle est votre classe ?"},
        ]
        with patch("app.routes.chat.SQLAgent.process_question", side_effect=lambda self, question: question):
            response = self.client.post(
                "/api/chat",
                json={
                    "message": "emploi de temps de 1IDSD2",
                    "user_role": "student",
                    "history": history,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["response"], "emploi de temps de 1IDSD2")


if __name__ == "__main__":
    unittest.main()
