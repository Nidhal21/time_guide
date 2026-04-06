import unittest

from app.services.groq_service import GroqService


class GroqServiceFormattingTests(unittest.TestCase):
    def setUp(self):
        self.service = GroqService()
        self.service.enabled = True

    def test_room_lookup_uses_local_formatting(self):
        response = self.service.format_response(
            "Qui enseigne maintenant en salle C01 ?",
            [{"nom_complet": "Mr BEN SLIMA M."}],
            {"semestre": "S2", "periode": "P2", "date_actuelle": "2026-03-26"},
        )
        self.assertEqual(response, "En salle C01, c'est Mr BEN SLIMA M. qui enseigne actuellement.")

    def test_location_lookup_uses_local_formatting(self):
        response = self.service.format_response(
            "où se trouve madame x ?",
            [{"nom": "C24"}],
            {"semestre": "S2", "periode": "P2", "date_actuelle": "2026-03-26"},
        )
        self.assertEqual(response, "Ce professeur se trouve en salle C24.")

    def test_timetable_days_are_sorted_monday_to_saturday(self):
        response = self.service.format_response(
            "donner emploi de temps 2 ing gec 3",
            [
                {
                    "classe": "2 ING GEC 3",
                    "matiere": "PREP CERT SIX SIGMA",
                    "professeur": "Mme SAHNOUN H.",
                    "salle": "C17",
                    "jour": "Jeudi",
                    "heure_debut": "08:15:00",
                    "heure_fin": "09:45:00",
                },
                {
                    "classe": "2 ING GEC 3",
                    "matiere": "ELECT COMMUTATION",
                    "professeur": "Mme BEN SAIED A.",
                    "salle": "C05",
                    "jour": "Lundi",
                    "heure_debut": "08:15:00",
                    "heure_fin": "09:45:00",
                },
                {
                    "classe": "2 ING GEC 3",
                    "matiere": "ANGLAIS",
                    "professeur": "Mme KAMMOUN KALLEL S.",
                    "salle": "C05",
                    "jour": "Samedi",
                    "heure_debut": "08:15:00",
                    "heure_fin": "09:45:00",
                },
            ],
            {"semestre": "S2", "periode": "P2", "date_actuelle": "2026-03-26"},
        )
        self.assertLess(response.index("Lundi :"), response.index("Jeudi :"))
        self.assertLess(response.index("Jeudi :"), response.index("Samedi :"))

    def test_available_rooms_are_formatted_as_list(self):
        response = self.service.format_response(
            "quelles sont les salles disponibles maintenant ?",
            [{"salle": "C01"}, {"salle": "C02"}, {"salle": "C01"}],
            {"semestre": "S2", "periode": "P2", "date_actuelle": "2026-03-26"},
        )
        self.assertIn("2 salles disponibles", response)
        self.assertIn("- C01", response)
        self.assertIn("- C02", response)

    def test_available_rooms_normalize_room_variants(self):
        response = self.service.format_response(
            "quelles sont les salles disponibles maintenant ?",
            [{"salle": "C01"}, {"salle": "C 01"}, {"salle": "c01"}],
            {"semestre": "S2", "periode": "P2", "date_actuelle": "2026-03-26"},
        )
        self.assertIn("1 salle disponible", response)
        self.assertEqual(response.count("- C01"), 1)

    def test_professor_class_lookup_formats_class_list(self):
        response = self.service.format_response(
            "dans quelle classe se trouve ben slima",
            [{"classe": "2 ING GII 3"}, {"classe": "2 ING GII 1"}],
            {"semestre": "S2", "periode": "P2", "date_actuelle": "2026-03-26"},
        )
        self.assertIn("classes suivantes", response)
        self.assertIn("2 ING GII 3", response)

    def test_professor_location_for_specific_day_formats_schedule(self):
        response = self.service.format_response(
            "ou se trouve demain mr zarai faouzi",
            [
                {
                    "jour": "Mardi",
                    "heure_debut": "10:00:00",
                    "heure_fin": "11:30:00",
                    "classe": "1 ING GII 2",
                    "salle": "C14",
                }
            ],
            {"semestre": "S2", "periode": "P2", "date_actuelle": "2026-03-26"},
        )
        self.assertIn("Voici ou se trouve ce professeur", response)
        self.assertIn("1 ING GII 2", response)
        self.assertIn("C14", response)


if __name__ == "__main__":
    unittest.main()
