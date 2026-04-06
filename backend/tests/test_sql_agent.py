import unittest

from app.services.sql_agent import SQLAgent


class SQLAgentWeekdayTests(unittest.TestCase):
    def setUp(self):
        self.agent = SQLAgent(db=None)
        self.context = {
            "date_actuelle": "2026-03-26",
            "jour_actuel": "Jeudi",
        }

    def test_extract_requested_day_from_explicit_weekday(self):
        question = "Quels sont les cours de lundi pour 1 ING gec 3 ?"
        self.assertEqual(self.agent._extract_requested_day(question, self.context), "Lundi")

    def test_extract_requested_day_from_relative_day(self):
        self.assertEqual(
            self.agent._extract_requested_day("Quels sont mes cours aujourd'hui ?", self.context),
            "Jeudi",
        )
        self.assertEqual(
            self.agent._extract_requested_day("Quels sont mes cours demain ?", self.context),
            "Vendredi",
        )
        self.assertEqual(
            self.agent._extract_requested_day("Quels sont mes cours hier ?", self.context),
            "Mercredi",
        )

    def test_enforce_requested_day_filter_rewrites_lowercase_day_predicate(self):
        sql = "SELECT * FROM seances s WHERE s.jour = 'lundi' AND s.periode_id = 4;"
        fixed = self.agent._enforce_requested_day_filter(
            "Quels sont les cours de lundi pour 1 ING GII 2 ?",
            sql,
            self.context,
        )
        self.assertIn("LOWER(s.jour) = LOWER('Lundi')", fixed)
        self.assertNotIn("s.jour = 'lundi'", fixed)

    def test_enforce_requested_day_filter_injects_missing_predicate(self):
        sql = "SELECT * FROM seances s WHERE s.periode_id = 4 ORDER BY s.heure_debut;"
        fixed = self.agent._enforce_requested_day_filter(
            "Quels sont les cours de lundi pour 1 ING GII 2 ?",
            sql,
            self.context,
        )
        self.assertIn("LOWER(s.jour) = LOWER('Lundi')", fixed)
        self.assertIn("ORDER BY s.heure_debut", fixed)

    def test_strip_day_filter_removes_lower_day_variant(self):
        sql = (
            "SELECT * FROM seances s WHERE LOWER(s.jour) = LOWER('Lundi') "
            "AND s.periode_id = 4 ORDER BY s.heure_debut;"
        )
        fixed = self.agent._strip_day_filter(sql)
        self.assertNotIn("LOWER(s.jour)", fixed)
        self.assertIn("s.periode_id = 4", fixed)

    def test_strip_day_filter_removes_mixed_lower_day_variant(self):
        sql = (
            "SELECT * FROM seances s WHERE s.periode_id = 4 "
            "AND LOWER(s.jour) = 'lundi' ORDER BY s.heure_debut;"
        )
        fixed = self.agent._strip_day_filter(sql)
        self.assertNotIn("LOWER(s.jour)", fixed)
        self.assertIn("s.periode_id = 4", fixed)

    def test_repair_sql_removes_generated_department_filter(self):
        sql = (
            "SELECT * FROM seances s JOIN classes c ON c.id = s.classe_id "
            "WHERE s.periode_id = 4 "
            "AND c.departement_id IN (SELECT d.id FROM departements d WHERE d.id IN "
            "(SELECT c.departement_id FROM classes c WHERE c.semestre_id = 2)) "
            "ORDER BY s.heure_debut;"
        )
        fixed = self.agent._repair_sql(sql)
        self.assertNotIn("c.departement_id IN", fixed)
        self.assertIn("s.periode_id = 4", fixed)

    def test_full_schedule_request_skips_day_enforcement(self):
        sql = "SELECT * FROM seances s WHERE s.periode_id = 4;"
        fixed = self.agent._enforce_requested_day_filter(
            "Affiche l'emploi du temps complet P1 et P2 pour lundi",
            sql,
            self.context,
        )
        self.assertEqual(fixed, sql)

    def test_professor_match_condition_supports_abbreviated_db_names(self):
        condition = self.agent._professor_match_condition("nesrine zouri")
        self.assertIsNotNone(condition)
        self.assertIn("zouri", condition)
        self.assertIn("(^|[^a-z0-9])n([.\\s/-]|$)", condition)

    def test_detects_professor_course_question_with_typos(self):
        self.assertTrue(
            self.agent._is_prof_current_course_question("Quel cours fait Mr Ben Slima maintement ?")
        )

    def test_schedule_request_with_class_is_not_mistaken_for_professor(self):
        question = "emploi de temps de 2 ing gii 3"
        self.assertEqual(self.agent._extract_class_candidate(question), "2 ING GII 3")
        self.assertIsNone(self.agent._extract_prof_candidate(question))

    def test_extracts_professor_name_from_class_location_question(self):
        question = "dans quelle classe se trouve ben slima"
        self.assertEqual(self.agent._extract_prof_candidate(question), "ben slima")
        self.assertTrue(self.agent._is_prof_class_question(question))

    def test_detects_professor_schedule_question(self):
        self.assertTrue(self.agent._is_prof_schedule_question("emploi de temps de mr yaich mohamed"))
        self.assertFalse(self.agent._is_prof_schedule_question("emploi de temps de 2 ing gii 3"))

    def test_extract_schedule_prof_candidate_without_title(self):
        self.agent._teacher_prof_exists_in_db = lambda name: name == "SMAOUI Ikram"
        self.agent._prof_exists_in_db = lambda name: name == "SMAOUI Ikram"
        self.assertEqual(
            self.agent._extract_schedule_prof_candidate("emploi de temps de SMAOUI Ikram"),
            "SMAOUI Ikram",
        )

    def test_detects_professor_schedule_question_without_title(self):
        self.agent._teacher_prof_exists_in_db = lambda name: name == "SMAOUI Ikram"
        self.agent._prof_exists_in_db = lambda name: name == "SMAOUI Ikram"
        self.assertTrue(self.agent._is_prof_schedule_question("emploi de temps de SMAOUI Ikram"))

    def test_professor_match_condition_supports_reversed_name_with_initial_in_db(self):
        condition = self.agent._professor_match_condition("ZARAI Faouzi")
        self.assertIsNotNone(condition)
        self.assertIn("zarai", condition)
        self.assertIn("(^|[^a-z0-9])f([.\\s/-]|$)", condition)

    def test_professor_match_condition_collapses_repeated_letters_for_typos(self):
        condition = self.agent._professor_match_condition("ali khalfalah")
        self.assertIsNotNone(condition)
        self.assertIn("REGEXP_REPLACE", condition)
        self.assertIn("khalfalah", condition)

    def test_enforce_professor_matching_keeps_regex_backreferences_literal(self):
        sql = "SELECT * FROM seances s JOIN professeurs p ON p.id = s.professeur_id WHERE p.nom_complet = 'mr ali khalfalah';"
        fixed = self.agent._enforce_professor_matching("emploi de temps de mr ali khalfalah", sql)
        self.assertIn("REGEXP_REPLACE", fixed)
        self.assertNotIn("p.nom_complet = 'mr ali khalfalah'", fixed)

    def test_format_empty_response_for_professor_schedule_mentions_active_period(self):
        context = {"semestre": "S2", "periode": "P2", "jour_actuel": "Lundi", "date_actuelle": "2026-03-30"}
        message = self.agent._format_empty_response("emploi de temps de mr ali khalfalah", context)
        self.assertIn("ali khalfalah", message)
        self.assertIn("S2/P2", message)

    def test_teacher_prof_schedule_sql_targets_teacher_reference_table(self):
        self.agent._extract_prof_candidate = lambda question: "YAICH MOHAMED"
        sql, params = self.agent._teacher_prof_schedule_sql(
            "emploi de temps de mr YAICH MOHAMED",
            {"semestre_id": 2, "periode": "P2", "jour_actuel": "Lundi", "date_actuelle": "2026-03-30"},
        )
        self.assertIn("FROM emplois_enseignants_seances te", sql)
        self.assertEqual(params["semester_id"], 2)
        self.assertEqual(params["periode_nom"], "P2")

    def test_study_plan_question_is_routed_as_university_general_question(self):
        self.assertTrue(self.agent._is_university_general_question("Peux-tu me montrer les plans d'etude GII"))

    def test_calendar_scope_detects_upcoming_vacations(self):
        self.assertEqual(self.agent._calendar_scope("les vacances prochaines"), "upcoming")

    def test_calendar_scope_detects_generic_holiday_listing(self):
        self.assertEqual(self.agent._calendar_scope("les jours ferier"), "upcoming")

    def test_calendar_scope_detects_exam_date_question(self):
        self.assertEqual(self.agent._calendar_scope("le date dexamen"), "upcoming")


if __name__ == "__main__":
    unittest.main()
