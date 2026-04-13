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

    def test_extract_class_candidate_supports_compact_shortcuts(self):
        self.assertEqual(self.agent._extract_class_candidate("emploi de temps de 2gii 3"), "2 ING GII 3")
        self.assertEqual(self.agent._extract_class_candidate("emploi de temps de 2gii3"), "2 ING GII 3")
        self.assertEqual(self.agent._extract_class_candidate("emploi de temps de 1gec2"), "1 ING GEC 2")
        self.assertEqual(self.agent._extract_class_candidate("emploi de temps de 1idsd2"), "1 ING IDSD 2")

    def test_is_class_schedule_question_supports_compact_shortcuts(self):
        self.assertTrue(self.agent._is_class_schedule_question("emploi de temps de 2 gii3"))
        self.assertTrue(self.agent._is_class_schedule_question("emploi de temps de 2gii3"))

    def test_class_schedule_sql_uses_normalized_compact_class_key(self):
        sql, params = self.agent._class_schedule_sql(
            "emploi de temps de 2gii3",
            {"periode_id": 4, "semestre": "S2", "jour_actuel": "Mercredi", "date_actuelle": "2026-03-26"},
        )
        self.assertIn("FROM seances s", sql)
        self.assertIn("REPLACE(REPLACE(LOWER(c.nom), ' ', ''), '-', '') = :class_key", sql)
        self.assertIn("s.periode_id = :periode_id", sql)
        self.assertEqual(params["class_key"], "2inggii3")
        self.assertEqual(params["periode_id"], 4)

    def test_extracts_professor_name_from_class_location_question(self):
        question = "dans quelle classe se trouve ben slima"
        self.assertEqual(self.agent._extract_prof_candidate(question), "ben slima")
        self.assertTrue(self.agent._is_prof_class_question(question))

    def test_extract_prof_candidate_ignores_trailing_time_words(self):
        question = "ou ce trouve mr ali khalfalah maintenant"
        self.assertEqual(self.agent._extract_prof_candidate(question), "ali khalfalah")

    def test_prof_location_question_supports_ou_ce_trouve_typo(self):
        question = "ou ce trouve mr ali khalfalah maintenant"
        self.assertTrue(self.agent._is_prof_location_question(question))

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

    def test_extract_schedule_prof_candidate_keeps_unknown_name_for_suggestions(self):
        self.assertEqual(
            self.agent._extract_schedule_prof_candidate("emploi de temps de ali khalfeoui"),
            "ali khalfeoui",
        )

    def test_detects_professor_schedule_question_without_title(self):
        self.agent._teacher_prof_exists_in_db = lambda name: name == "SMAOUI Ikram"
        self.agent._prof_exists_in_db = lambda name: name == "SMAOUI Ikram"
        self.assertTrue(self.agent._is_prof_schedule_question("emploi de temps de SMAOUI Ikram"))

    def test_detects_professor_schedule_question_with_single_name(self):
        self.assertTrue(self.agent._is_prof_schedule_question("emploi de temps de soulef"))

    def test_prof_not_found_message_lists_similar_names(self):
        self.agent._find_similar_professors = lambda name: ["ALI KHLFALLAH", "ALI KHALFEDIN"]
        message = self.agent._prof_not_found_message("ali khalfeoui")
        self.assertIn("ali khalfeoui", message)
        self.assertIn("ALI KHLFALLAH", message)
        self.assertIn("ALI KHALFEDIN", message)

    def test_professor_confirmation_message_for_partial_name(self):
        self.agent._find_exact_professor_names = lambda name: []
        self.agent._find_matching_professors = lambda name: ["BEN NASR Mounir"]
        message = self.agent._professor_confirmation_message("mounir")
        self.assertIn("Voulez-vous dire", message)
        self.assertIn("BEN NASR Mounir", message)

    def test_professor_confirmation_message_for_close_misspelling(self):
        self.agent._find_exact_professor_names = lambda name: []
        self.agent._find_matching_professors = lambda name: ["BEN NASR Mounir"]
        message = self.agent._professor_confirmation_message("ben naser")
        self.assertIn("ressemble", message)
        self.assertIn("BEN NASR Mounir", message)

    def test_resolve_professor_name_supports_reversed_order(self):
        self.agent._find_exact_professor_names = lambda name: ["NESRINE TRABELSI"]
        self.assertEqual(self.agent._resolve_professor_name("trabelsi nesrine"), "NESRINE TRABELSI")

    def test_candidate_professor_names_cleans_titles_and_split_values(self):
        self.agent._reference_professor_names = lambda: ["KHALFALLAH Ali", "MAKLOUFI Ali"]
        names = self.agent._candidate_professor_names("Mr KHALFALLAH A. / Mr MAKLOUFI A.")
        self.assertEqual(names, ["KHALFALLAH Ali", "MAKLOUFI Ali"])

    def test_exact_professor_match_condition_prefers_exact_normalized_equality(self):
        condition = self.agent._exact_professor_match_condition("KHALFALLAH Ali", "te.professeur_nom_complet")
        self.assertIn("=", condition)
        self.assertIn("khalfallahali", condition)

    def test_matching_professors_filters_irrelevant_first_name_only_matches(self):
        self.agent._all_professor_names_cache = [
            "KHALFALLAH Ali",
            "AMRI Ali",
            "BEN AYED MOHAMED ALI",
            "KAMOUN KALLE SOUROUR",
        ]
        matches = self.agent._find_matching_professors("ali khalaf")
        self.assertIn("KHALFALLAH Ali", matches)
        self.assertNotIn("AMRI Ali", matches)

    def test_room_alias_normalization_supports_single_digit_codes(self):
        self.assertEqual(self.agent._extract_room_candidate("emploi de temps de salle c1"), "C01")
        self.assertEqual(self.agent._extract_room_candidate("emploi de temps de c1"), "C01")
        self.assertEqual(self.agent._extract_room_candidate("emploi de temps de c12"), "C12")
        self.assertEqual(self.agent._normalize_room_name("c 1"), "C01")
        self.assertTrue(self.agent._is_room_schedule_question("emploi de temps de salle c1"))
        self.assertTrue(self.agent._is_room_schedule_question("emploi de temps de c01"))

    def test_room_schedule_sql_uses_normalized_room_key(self):
        sql, params = self.agent._room_schedule_sql(
            "emploi de temps de salle c1 lundi",
            {"periode_id": 4, "semestre_id": 2, "periode": "P2", "jour_actuel": "Jeudi", "date_actuelle": "2026-03-26"},
        )
        self.assertIn("FROM seances s", sql)
        self.assertIn("LOWER(s.jour) = LOWER(:target_day)", sql)
        self.assertEqual(params["room_name"], "c01")
        self.assertEqual(params["target_day"], "Lundi")
        self.assertEqual(params["periode_nom"], "P2")
        self.assertEqual(params["semester_id"], 2)

    def test_room_schedule_sql_without_day_does_not_force_active_period(self):
        sql, params = self.agent._room_schedule_sql(
            "emploi de temps de salle c1",
            {"periode_id": 4, "semestre_id": 2, "periode": "P2", "jour_actuel": "Jeudi", "date_actuelle": "2026-03-26"},
        )
        self.assertNotIn("s.periode_id =", sql)
        self.assertNotIn("periode_nom", params)

    def test_teacher_prof_schedule_sql_without_day_does_not_force_active_period(self):
        self.agent._extract_schedule_prof_candidate = lambda question: "BEN NACER MOUNIR"
        sql, params = self.agent._teacher_prof_schedule_sql(
            "emploi de temps de mr mounir ben nacer",
            {"semestre_id": 2, "periode": "P2", "jour_actuel": "Jeudi", "date_actuelle": "2026-03-26"},
        )
        self.assertIn("FROM emplois_enseignants_seances te", sql)
        self.assertNotIn("te.periode_nom", sql)
        self.assertNotIn("periode_nom", params)

    def test_teacher_prof_schedule_sql_for_day_keeps_current_period(self):
        self.agent._extract_schedule_prof_candidate = lambda question: "BEN NACER MOUNIR"
        sql, params = self.agent._teacher_prof_schedule_sql(
            "emploi de temps de mr mounir ben nacer lundi",
            {"semestre_id": 2, "periode": "P2", "jour_actuel": "Jeudi", "date_actuelle": "2026-03-26"},
        )
        self.assertIn("te.periode_nom", sql)
        self.assertEqual(params["periode_nom"], "P2")

    def test_prof_location_sql_now_orders_by_selected_alias_only(self):
        self.agent._extract_prof_candidate = lambda question: "NESRINE TRABELSI"
        self.agent._resolve_professor_name = lambda name: name
        self.agent._teacher_prof_exists_in_db = lambda name: True
        sql, params = self.agent._prof_location_sql(
            "ou se trouve madame nesrine trabelsi ?",
            {"semestre_id": 2, "periode": "P2", "jour_actuel": "Mardi", "date_actuelle": "2026-04-07"},
        )
        self.assertIn("SELECT DISTINCT te.salle_nom AS salle", sql)
        self.assertIn("ORDER BY salle;", sql)
        self.assertNotIn("ORDER BY te.heure_debut", sql)
        self.assertEqual(params["target_day"], "Mardi")

    def test_room_not_found_message_lists_similar_rooms(self):
        self.agent._find_similar_rooms = lambda room: ["C01", "C11"]
        message = self.agent._room_not_found_message("C99")
        self.assertIn("C99", message)
        self.assertIn("C01", message)
        self.assertIn("C11", message)

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
