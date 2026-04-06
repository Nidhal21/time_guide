import unittest
from pathlib import Path

from app.services.excel_parser import VerticalExcelParser


ROOT = Path(__file__).resolve().parents[2]
EXCEL_DIR = ROOT / "public" / "excel_files"


class VerticalExcelParserViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = VerticalExcelParser()

    def _show_examples(self, label: str, file_path: Path, sessions: list[dict], limit: int = 3):
        examples = []
        for session in sessions:
            if not session.get("classe") or not session.get("matiere"):
                continue
            examples.append(
                " | ".join(
                    [
                        f"jour={session.get('jour')}",
                        f"heure={session.get('heure_debut')}-{session.get('heure_fin')}",
                        f"classe={session.get('classe')}",
                        f"matiere={session.get('matiere')}",
                        f"prof={session.get('professeur') or '-'}",
                        f"salle={session.get('salle') or '-'}",
                        f"periode={session.get('periode') or 'commun'}",
                    ]
                )
            )
            if len(examples) >= limit:
                break

        print(f"\n[{label}] {file_path.name} -> {len(sessions)} seances parsees")
        for index, example in enumerate(examples, start=1):
            print(f"  exemple {index}: {example}")

    def test_student_workbooks_parse_real_files(self):
        files = [
            EXCEL_DIR / "Emplois_Etudiants_10-11-2025_S1_P2_V2.xlsx",
            EXCEL_DIR / "Emplois_Etudiants_S2_2025_2026_VF.xlsx",
        ]

        for file_path in files:
            sessions = self.parser.parse_schedule_file(str(file_path))
            self._show_examples("etudiants", file_path, sessions)
            self.assertGreater(len(sessions), 500, file_path.name)
            self.assertTrue(any(session["classe"] for session in sessions), file_path.name)
            self.assertTrue(any(session["professeur"] for session in sessions), file_path.name)
            self.assertTrue(any(session["salle"] for session in sessions), file_path.name)
            self.assertTrue(any(session["matiere"] for session in sessions), file_path.name)

    def test_teacher_workbooks_parse_real_files(self):
        files = [
            EXCEL_DIR / "Emplois_Enseignants_10-11-2025_S1_P2_V2 (2).xlsx",
            EXCEL_DIR / "Emplois_Enseignants_S2_2025_2026_VF.xlsx",
        ]

        for file_path in files:
            sessions = self.parser.parse_teacher_schedule_file(str(file_path))
            self._show_examples("enseignants", file_path, sessions)
            self.assertGreater(len(sessions), 700, file_path.name)
            self.assertTrue(any(session["classe"] for session in sessions), file_path.name)
            self.assertTrue(any(session["professeur"] for session in sessions), file_path.name)
            self.assertTrue(any(session["salle"] for session in sessions), file_path.name)
            self.assertTrue(any(session["matiere"] for session in sessions), file_path.name)

    def test_room_workbooks_parse_real_files(self):
        files = [
            EXCEL_DIR / "Emplois_Salles_10-11-2025_S1_P2_V2.xlsx",
            EXCEL_DIR / "Emplois_Salles_S2_2025_2026_VF.xlsx",
        ]

        for file_path in files:
            sessions = self.parser.parse_room_schedule_file(str(file_path))
            self._show_examples("salles", file_path, sessions)
            self.assertGreater(len(sessions), 700, file_path.name)
            self.assertTrue(any(session["classe"] for session in sessions), file_path.name)
            self.assertTrue(any(session["professeur"] for session in sessions), file_path.name)
            self.assertTrue(any(session["salle"] for session in sessions), file_path.name)
            self.assertTrue(any(session["matiere"] for session in sessions), file_path.name)


if __name__ == "__main__":
    unittest.main()
