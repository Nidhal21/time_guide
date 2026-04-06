import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import admin_import_service


class AdminImportServiceTests(unittest.TestCase):
    def test_teacher_and_room_categories_update_database(self):
        self.assertTrue(admin_import_service.UPLOAD_CATEGORIES["teachers_s1"].db_updates)
        self.assertTrue(admin_import_service.UPLOAD_CATEGORIES["teachers_s2"].db_updates)
        self.assertTrue(admin_import_service.UPLOAD_CATEGORIES["rooms_s1"].db_updates)
        self.assertTrue(admin_import_service.UPLOAD_CATEGORIES["rooms_s2"].db_updates)

    def test_apply_database_import_uses_teacher_importer(self):
        category = admin_import_service.UPLOAD_CATEGORIES["teachers_s1"]
        fake_path = Path("teachers_s1.xlsx")

        with patch(
            "app.services.admin_import_service.import_teacher_emplois_du_temps",
            return_value={"imported_session_count": 1486},
        ) as mocked:
            result = admin_import_service._apply_database_import(category, fake_path, db=None)

        mocked.assert_called_once_with(str(fake_path), semester_id=1, clear_existing=True)
        self.assertEqual(result["parsed_session_count"], 1486)
        self.assertIn("emplois enseignants", result["message"])

    def test_apply_database_import_uses_room_importer(self):
        category = admin_import_service.UPLOAD_CATEGORIES["rooms_s2"]
        fake_path = Path("rooms_s2.xlsx")

        with patch(
            "app.services.admin_import_service.import_room_emplois_du_temps",
            return_value={"imported_session_count": 826},
        ) as mocked:
            result = admin_import_service._apply_database_import(category, fake_path, db=None)

        mocked.assert_called_once_with(str(fake_path), semester_id=2, clear_existing=True)
        self.assertEqual(result["parsed_session_count"], 826)
        self.assertIn("emplois des salles", result["message"])


if __name__ == "__main__":
    unittest.main()
