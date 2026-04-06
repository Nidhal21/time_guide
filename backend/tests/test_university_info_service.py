import unittest
from unittest.mock import patch

import requests

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


if __name__ == "__main__":
    unittest.main()
