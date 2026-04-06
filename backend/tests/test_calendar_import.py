import sys
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from import_calendar import extract_events_from_excel


EXCEL_PATH = next((ROOT / "public" / "excel_files").glob("Calendrier universitaire *.xlsx"))


class CalendarImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = extract_events_from_excel(str(EXCEL_PATH))
        cls.event_keys = {
            (event["nom"], event["date_debut"], event["date_fin"], event["type"])
            for event in cls.events
        }

    def test_extracts_expected_footer_holidays(self):
        expected_holidays = {
            ("Jour de l'An", date(2025, 1, 1)),
            ("Fête de l'Indépendance", date(2025, 3, 20)),
            ("Aid El Fitr", date(2025, 3, 31)),
            ("Fête des Martyres", date(2025, 4, 9)),
            ("Fête du travail", date(2025, 5, 1)),
            ("Aid El Adha", date(2025, 6, 6)),
        }

        for holiday_name, holiday_date in expected_holidays:
            self.assertIn(
                (holiday_name, holiday_date, holiday_date, "jour_ferie"),
                self.event_keys,
            )

    def test_extracts_semester_part_markers(self):
        expected_periods = {
            ("S1 P1", date(2024, 9, 2), date(2024, 10, 20)),
            ("S1 P1", date(2024, 9, 9), date(2024, 10, 27)),
            ("S1 P2", date(2024, 10, 21), date(2024, 12, 8)),
            ("S1 P2", date(2024, 10, 28), date(2024, 12, 15)),
            ("S2 P1", date(2025, 1, 13), date(2025, 3, 2)),
            ("S2 P1", date(2025, 1, 20), date(2025, 3, 9)),
            ("S2 P2", date(2025, 3, 3), date(2025, 4, 20)),
            ("S2 P2", date(2025, 3, 10), date(2025, 4, 27)),
        }

        for period_name, start_date, end_date in expected_periods:
            self.assertIn(
                (period_name, start_date, end_date, "periode"),
                self.event_keys,
            )

    def test_extracts_vacations_and_revision_ranges(self):
        self.assertIn(
            ("vacances d'hiver", date(2024, 12, 23), date(2025, 1, 4), "vacances"),
            self.event_keys,
        )
        self.assertIn(
            ("Vacances printemps", date(2025, 3, 24), date(2025, 3, 30), "vacances"),
            self.event_keys,
        )
        self.assertIn(
            ("révision", date(2024, 12, 16), date(2024, 12, 18), "revision"),
            self.event_keys,
        )

    def test_extracts_real_calendar_dataset(self):
        self.assertGreaterEqual(len(self.events), 40)


if __name__ == "__main__":
    unittest.main()
