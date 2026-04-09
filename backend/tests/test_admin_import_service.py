import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from app.services import admin_import_service


class AdminImportServiceTests(unittest.TestCase):
    def _write_workbook(self, rows, path: Path, sheet_name: str = "Feuil1"):
        df = pd.DataFrame(rows)
        with pd.ExcelWriter(path) as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)

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

    def test_validate_workbook_matches_student_category_and_semester(self):
        category = admin_import_service.UPLOAD_CATEGORIES["student_s2"]
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "student_s2.xlsx"
            self._write_workbook(
                [
                    ["EnetCom", "", "", "", "Emploi du Temps : Semestre 2- AU 2025/2026"],
                    ["", "", "", "", ""],
                    ["", "", "", "", "Classe : 1 MR STIC RNT"],
                ],
                path,
                sheet_name="1 MR STIC RNT",
            )

            detected = admin_import_service._validate_workbook_matches_category(path, category)

        self.assertEqual(detected["detected_audience"], "etudiants")
        self.assertEqual(detected["detected_semester"], 2)

    def test_validate_workbook_rejects_teacher_file_in_student_category(self):
        category = admin_import_service.UPLOAD_CATEGORIES["student_s1"]
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "teacher_s1.xlsx"
            self._write_workbook(
                [
                    ["EnetCom", "", "", "", "Emploi du Temps : Semestre 1- AU 2025/2026"],
                    ["", "", "", "", ""],
                    ["", "", "", "", "Professeur : BEN SLIMA Mohamed"],
                ],
                path,
                sheet_name="BEN SLIMA Mohamed",
            )

            with self.assertRaises(ValueError) as exc:
                admin_import_service._validate_workbook_matches_category(path, category)

        self.assertIn("emplois enseignants", str(exc.exception))
        self.assertIn("Emplois des etudiants S1", str(exc.exception))

    def test_validate_workbook_rejects_semester_mismatch(self):
        category = admin_import_service.UPLOAD_CATEGORIES["student_s1"]
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "student_s2.xlsx"
            self._write_workbook(
                [
                    ["EnetCom", "", "", "", "Emploi du Temps : Semestre 2- AU 2025/2026"],
                    ["", "", "", "", ""],
                    ["", "", "", "", "Classe : 1 ING GII 3"],
                ],
                path,
                sheet_name="1 ING GII 3",
            )

            with self.assertRaises(ValueError) as exc:
                admin_import_service._validate_workbook_matches_category(path, category)

        self.assertIn("semestre S2", str(exc.exception))
        self.assertIn("Emplois des etudiants S1", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
