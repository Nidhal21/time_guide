import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.services.auth_service import get_admin_user
from main import app


class AdminApiTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_admin_user] = lambda: {
            "id": "admin-1",
            "email": "admin@example.com",
            "role": "admin",
        }
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_status_endpoint_returns_service_summary(self):
        stub = {
            "active_context": {"annee_libelle": "2025-2026"},
            "counts": {"classes": 86, "seances": 3069, "professeurs": 509, "salles": 251, "matieres": 759, "versions_actives": 86},
            "calendar_warning": None,
            "categories": [],
        }

        with patch("app.routes.admin.get_admin_dashboard_summary", return_value=stub):
            response = self.client.get("/api/admin/imports/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["counts"]["classes"], 86)
        self.assertEqual(response.json()["active_context"]["annee_libelle"], "2025-2026")

    def test_upload_requires_at_least_one_file(self):
        response = self.client.post("/api/admin/imports/upload", files={})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Aucun fichier Excel", response.json()["detail"])

    def test_upload_endpoint_forwards_files_to_service(self):
        stub = {
            "processed_at": "2026-03-29T18:00:00",
            "results": [
                {
                    "category": "student_s1",
                    "label": "Emplois des etudiants S1",
                    "status": "success",
                    "filename": "s1.xlsx",
                    "message": "Semestre importe",
                    "db_updates": True,
                }
            ],
            "summary": {
                "active_context": {"annee_libelle": "2025-2026"},
                "counts": {"classes": 86, "seances": 3069, "professeurs": 509, "salles": 251, "matieres": 759, "versions_actives": 86},
                "calendar_warning": None,
                "categories": [],
            },
        }

        with patch("app.routes.admin.process_uploads", return_value=stub) as mocked:
            response = self.client.post(
                "/api/admin/imports/upload",
                files={
                    "student_s1": (
                        "s1.xlsx",
                        b"fake excel bytes",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["filename"], "s1.xlsx")
        mocked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
