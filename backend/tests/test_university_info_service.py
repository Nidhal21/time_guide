import unittest
from unittest.mock import patch

import requests
from types import SimpleNamespace

from app.services.university_info_service import UniversityInfoService


class UniversityInfoServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = UniversityInfoService()

    def test_news_question_handles_upstream_http_error(self):
        with patch.object(
            self.service,
            "_fetch_page_html",
            side_effect=requests.HTTPError("503 Server Error: Service Unavailable"),
        ):
            response = self.service.answer_question("Quelles sont les dernières actualités de ENET’Com ?")

        self.assertIn("Je n'ai pas pu recuperer les dernieres actualites", response)
        self.assertIn(self.service.ACTUALITES_URL, response)

    def test_study_plan_question_returns_configured_urls(self):
        response = self.service.answer_question(
            "donne moi les plans d etudes IDSD, informatique industrielle, GEC et GT"
        )

        self.assertIn(self.service.STUDY_PLAN_URLS["idsd"], response)
        self.assertIn(self.service.STUDY_PLAN_URLS["gii"], response)
        self.assertIn(self.service.STUDY_PLAN_URLS["gec"], response)
        self.assertIn(self.service.STUDY_PLAN_URLS["gt"], response)

    def test_specific_study_plan_question_returns_only_requested_major(self):
        response = self.service.answer_question("donne moi le plan de etude gii")

        self.assertIn(self.service.STUDY_PLAN_URLS["gii"], response)
        self.assertNotIn(self.service.STUDY_PLAN_URLS["gec"], response)
        self.assertNotIn(self.service.STUDY_PLAN_URLS["gt"], response)
        self.assertNotIn(self.service.STUDY_PLAN_URLS["idsd"], response)

    def test_generic_study_plan_question_returns_all_default_links_in_expected_order(self):
        response = self.service.answer_question("donne moi le plan d'etude")

        gii_pos = response.index(self.service.STUDY_PLAN_URLS["gii"])
        gec_pos = response.index(self.service.STUDY_PLAN_URLS["gec"])
        gt_pos = response.index(self.service.STUDY_PLAN_URLS["gt"])
        idsd_pos = response.index(self.service.STUDY_PLAN_URLS["idsd"])
        self.assertTrue(gii_pos < gec_pos < gt_pos < idsd_pos)

    def test_absence_question_requires_extranet_login_when_login_page_is_returned(self):
        fake_response = SimpleNamespace(
            url="https://enetcom.rnu.tn/fr/login",
            text="<html><body>Se connecter a l'Espace Extranet</body></html>",
        )

        with patch.object(self.service._session, "get", return_value=fake_response):
            response = self.service.answer_question("est ce qu il y a des absences des profs")

        self.assertIn("Espace Extranet", response)
        self.assertIn(self.service.ABSENCES_URL, response)

    def test_absence_question_reports_no_teacher_absence(self):
        fake_response = SimpleNamespace(
            url=self.service.ABSENCES_URL,
            text="<html><body>Pas d'absence des enseignants</body></html>",
        )

        with patch.object(self.service._session, "get", return_value=fake_response):
            response = self.service.answer_question("donne moi les absences enseignants")

        self.assertIn("Il n'y a pas d'absence des enseignants", response)
        self.assertIn(self.service.ABSENCES_URL, response)

    def test_absence_question_extracts_absent_teachers_from_table(self):
        fake_response = SimpleNamespace(
            url=self.service.ABSENCES_URL,
            text="""
                <html><body>
                <table>
                    <tr><th>Enseignant</th><th>Date</th></tr>
                    <tr><td>BEN SLIMA Mounir</td><td>2026-04-13</td></tr>
                    <tr><td>TRABELSI Nesrine</td><td>2026-04-13</td></tr>
                </table>
                </body></html>
            """,
        )

        with patch.object(self.service._session, "get", return_value=fake_response):
            response = self.service.answer_question("les profs absents aujourd'hui")

        self.assertIn("BEN SLIMA Mounir", response)
        self.assertIn("TRABELSI Nesrine", response)
        self.assertIn(self.service.ABSENCES_URL, response)

    def test_absence_question_falls_back_to_page_excerpt_when_detailed_extraction_fails(self):
        fake_response = SimpleNamespace(
            url=self.service.ABSENCES_URL,
            text="<html><body><div>Absences des enseignants : mise a jour en cours pour l'Espace Extranet.</div></body></html>",
        )

        with patch.object(self.service._session, "get", return_value=fake_response):
            response = self.service.answer_question("est ce que le prof x est absant")

        self.assertIn("extrait de la page", response)
        self.assertIn("Absences des enseignants", response)
        self.assertIn(self.service.ABSENCES_URL, response)


if __name__ == "__main__":
    unittest.main()
