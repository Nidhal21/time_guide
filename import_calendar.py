import argparse
import os
import re
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd
import psycopg2


def _guess_type(label: str) -> str:
    l = (label or "").strip().lower()
    if "vacances" in l:
        return "vacances"
    if "examen" in l or "examens" in l or "ds" in l:
        return "examen"
    if "révision" in l or "revision" in l or "ratt" in l:
        return "revision"
    if "fête" in l or "fete" in l or "aid" in l or "nouvel" in l or "jour" in l or "journée" in l:
        return "jour_ferie"
    if l in {"p1", "p2"} or "p1" in l or "p2" in l:
        return "periode"
    return "evenement"


MONTHS = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}

WEEKDAY_TOKENS = {
    "lu", "ma", "me", "je", "ve", "sa", "di",  # FR
    "lun", "mar", "mer", "jeu", "ven", "sam", "dim",
}


def _clean_cell(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if not s or s.lower() == "nan":
        return ""
    return s


def _find_nearest_year(df: pd.DataFrame, r: int, c: int, max_up: int = 12) -> int | None:
    # search upward in same column, then a small window around column
    for up in range(0, max_up + 1):
        rr = r - up
        if rr < 0:
            break
        # same col
        s = _clean_cell(df.iat[rr, c])
        if re.fullmatch(r"20\d{2}", s):
            return int(s)
        # small horizontal neighborhood
        for cc in range(max(0, c - 6), min(df.shape[1], c + 7)):
            s2 = _clean_cell(df.iat[rr, cc])
            if re.fullmatch(r"20\d{2}", s2):
                return int(s2)
    return None


def _find_nearest_month(df: pd.DataFrame, r: int, c: int, max_up: int = 10) -> int | None:
    # search upward for a month header near this column
    for up in range(0, max_up + 1):
        rr = r - up
        if rr < 0:
            break
        for cc in range(max(0, c - 8), min(df.shape[1], c + 9)):
            s = _clean_cell(df.iat[rr, cc]).lower()
            if s in MONTHS:
                return MONTHS[s]
    return None


def _parse_dayish(cell_text: str):
    """
    Parses cells like:
      "1 Me"
      "25 Me DEL"
      "16 Lu P1 1"
      "3 Ve vacances d'hiver"
    Returns (day:int|None, label:str|None)
    """
    s = (cell_text or "").strip()
    if not s:
        return None, None

    # Day at start
    m = re.match(r"^\s*(\d{1,2})\s*(.*)$", s)
    if not m:
        return None, None

    day = int(m.group(1))
    tail = m.group(2).strip()

    # Remove weekday token if present at start of tail
    if tail:
        # token could be "Me" or "Mer" etc
        t0 = tail.split()[0].lower()
        if t0 in WEEKDAY_TOKENS:
            tail = tail[len(tail.split()[0]):].strip()

    label = tail.strip()
    if not label:
        return day, None

    # If label is just a number (like "1"), ignore
    if label.isdigit():
        return day, None

    return day, label


def _infer_range_from_neighbors(df: pd.DataFrame, r: int, c: int, year: int, month: int):
    """
    For merged/colored blocks like 'Vacances printemps' that appear without an explicit day,
    infer a date range by scanning up/down around the cell to find nearby day numbers.
    Returns (start_date, end_date) or (None, None) if not inferable.
    """
    # look up for nearest day number in neighborhood
    found_days = []

    def scan(rr, cc):
        txt = _clean_cell(df.iat[rr, cc])
        if not txt:
            return
        d, _ = _parse_dayish(txt)
        if d and 1 <= d <= 31:
            found_days.append(d)

    # scan a vertical window around (r,c)
    for rr in range(max(0, r - 10), min(df.shape[0], r + 11)):
        for cc in range(max(0, c - 3), min(df.shape[1], c + 4)):
            scan(rr, cc)

    if not found_days:
        return None, None

    try:
        start = datetime(year, month, min(found_days)).date()
        end = datetime(year, month, max(found_days)).date()
        return start, end
    except ValueError:
        return None, None


def _extract_from_grid(df: pd.DataFrame):
    """
    Extract events from the calendar grid:
    - uses nearest month/year headers
    - handles day in-cell ("1 Me P1") and adjacent label cells (day cell next to label cell)
    - attempts to infer ranges for merged blocks (vacances/examens/révision) without explicit day
    """
    events = []

    for r in range(df.shape[0]):
        for c in range(df.shape[1]):
            cell = _clean_cell(df.iat[r, c])
            if not cell:
                continue

            low = cell.lower()

            # Skip pure headers
            if low in MONTHS:
                continue
            if re.fullmatch(r"20\d{2}", cell):
                continue

            # Try parse "day + label" in the same cell
            day, inline_label = _parse_dayish(cell)

            year = _find_nearest_year(df, r, c)
            month = _find_nearest_month(df, r, c)

            # If we have a day but no month/year found, skip
            if day is not None and (year is None or month is None):
                continue

            # 1) Inline label in same cell
            if day is not None and inline_label:
                try:
                    d = datetime(year, month, day).date()
                except ValueError:
                    continue

                # Sometimes inline_label contains multiple tokens; keep full
                events.append(
                    {
                        "nom": inline_label,
                        "date_debut": d,
                        "date_fin": d,
                        "type": _guess_type(inline_label),
                    }
                )
                continue

            # 2) Day-only cell; check neighbor cell(s) for label (like P1/P2 in adjacent cell)
            if day is not None:
                try:
                    d = datetime(year, month, day).date()
                except ValueError:
                    continue

                neighbor_labels = []
                for dc in (1, -1, 2, -2):
                    cc = c + dc
                    if 0 <= cc < df.shape[1]:
                        nb = _clean_cell(df.iat[r, cc])
                        if not nb:
                            continue
                        # avoid capturing weekday-only or digits-only
                        nb_low = nb.lower().strip()
                        if nb_low in WEEKDAY_TOKENS or nb_low.isdigit():
                            continue
                        # if neighbor looks like another day cell, skip
                        nd, nlab = _parse_dayish(nb)
                        if nd is not None and nlab is None:
                            continue
                        # prefer textual labels
                        if nb_low and not re.fullmatch(r"\d+", nb_low):
                            neighbor_labels.append(nb.strip())

                # Add events for neighbor labels (dedup later)
                for lab in neighbor_labels:
                    events.append(
                        {
                            "nom": lab,
                            "date_debut": d,
                            "date_fin": d,
                            "type": _guess_type(lab),
                        }
                    )
                continue

            # 3) Block label without day: vacances / examens / révision / etc.
            # Try infer month/year and range from neighbors
            if year is None or month is None:
                continue

            # Only consider meaningful labels
            if any(k in low for k in ["vacances", "examen", "examens", "révision", "revision", "ratt", "ds", "p1", "p2", "aid", "fête", "fete"]):
                start, end = _infer_range_from_neighbors(df, r, c, year, month)
                if start and end:
                    events.append(
                        {
                            "nom": cell,
                            "date_debut": start,
                            "date_fin": end,
                            "type": _guess_type(cell),
                        }
                    )

    return events


def _extract_from_text_blocks(excel_path: str):
    """
    Keep your original extraction from textual lines like:
    - 09 septembre 2024 Journée d'intégration
    - 19-21 décembre 2024 examens ...
    - 09 et 16 octobre 2024 ...
    """
    events = []

    date_slash_re = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")

    date_fr_re = re.compile(
        r"\b(?P<days>\d{1,2}(?:\s*(?:-|,|et)\s*\d{1,2})*)\s+"
        r"(?P<month>janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\s+"
        r"(?P<year>\d{4})\b",
        flags=re.IGNORECASE,
    )

    date_fr_no_year_re = re.compile(
        r"\b(?P<days>\d{1,2}(?:\s*(?:-|,|et)\s*\d{1,2})*)\s+"
        r"(?P<month>janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\b",
        flags=re.IGNORECASE,
    )

    xls = pd.ExcelFile(excel_path)

    for sheet_name in xls.sheet_names:
        df = pd.read_excel(excel_path, sheet_name=sheet_name, header=None, dtype=str)
        current_year_context = None

        for row in df.itertuples(index=False):
            for cell in row:
                s = _clean_cell(cell)
                if not s:
                    continue

                # 1) dd/mm/yyyy
                m = date_slash_re.search(s)
                if m:
                    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    try:
                        d = datetime(year, month, day).date()
                    except ValueError:
                        continue

                    label = s[m.end():].strip(" -:;\t")
                    if not label:
                        continue

                    events.append(
                        {"nom": label, "date_debut": d, "date_fin": d, "type": _guess_type(label)}
                    )
                    continue

                # 2) French text dates (possibly multiple days or ranges)
                m2 = date_fr_re.search(s)
                active_match = None
                if m2:
                    days_raw = m2.group("days")
                    month_raw = m2.group("month").lower()
                    year = int(m2.group("year"))
                    active_match = m2
                    current_year_context = year
                else:
                    m3 = date_fr_no_year_re.search(s)
                    if not m3:
                        continue
                    days_raw = m3.group("days")
                    month_raw = m3.group("month").lower()
                    active_match = m3

                    # Infer year (best-effort)
                    if current_year_context is not None:
                        year = current_year_context
                    else:
                        fallback_start_year = 2024
                        mfile = re.search(r"(20\d{2})-(20\d{2})", os.path.basename(excel_path))
                        if mfile:
                            fallback_start_year = int(mfile.group(1))
                        month_num = MONTHS.get(month_raw)
                        if month_num is None:
                            continue
                        year = fallback_start_year if month_num >= 9 else (fallback_start_year + 1)

                month = MONTHS.get(month_raw)
                if not month:
                    continue

                normalized = re.sub(r"\bet\b", ",", days_raw, flags=re.IGNORECASE)
                parts = [p.strip() for p in normalized.split(",") if p.strip()]

                day_values = []
                for p in parts:
                    if "-" in p:
                        a, b = [x.strip() for x in p.split("-", 1)]
                        if a.isdigit() and b.isdigit():
                            day_values.extend(list(range(int(a), int(b) + 1)))
                    elif p.isdigit():
                        day_values.append(int(p))

                if not day_values:
                    continue

                try:
                    start = datetime(year, month, min(day_values)).date()
                    end = datetime(year, month, max(day_values)).date()
                except ValueError:
                    continue

                label = s[active_match.end():].strip(" -:;\t")
                if not label:
                    continue

                events.append(
                    {"nom": label, "date_debut": start, "date_fin": end, "type": _guess_type(label)}
                )

    return events


def extract_events_from_excel(excel_path: str):
    # 1) Grid extraction
    xls = pd.ExcelFile(excel_path)
    grid_events = []
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(excel_path, sheet_name=sheet_name, header=None, dtype=str)
        grid_events.extend(_extract_from_grid(df))

    # 2) Text blocks extraction (legend at bottom, etc.)
    text_events = _extract_from_text_blocks(excel_path)

    # 3) Merge + dedup
    all_events = grid_events + text_events

    dedup = {}
    for e in all_events:
        nom = (e.get("nom") or "").strip()
        if not nom:
            continue
        key = (nom.lower(), e["date_debut"].isoformat(), e["date_fin"].isoformat(), e["type"])
        dedup[key] = {
            "nom": nom,
            "date_debut": e["date_debut"],
            "date_fin": e["date_fin"],
            "type": e["type"],
        }

    return list(dedup.values())


def import_calendar(excel_path: str, annee_id: int, clear_existing: bool = True, dry_run: bool = False):
    excel_path = os.path.abspath(excel_path)
    if not os.path.exists(excel_path):
        raise FileNotFoundError(excel_path)

    events = extract_events_from_excel(excel_path)

    print(f"Fichier: {excel_path}")
    print(f"Événements détectés: {len(events)}")

    if dry_run:
        for e in sorted(events, key=lambda x: (x["date_debut"], x["nom"]))[:60]:
            print(f"- {e['date_debut']} -> {e['date_fin']} | {e['type']} | {e['nom']}")
        if len(events) > 60:
            print(f"... +{len(events) - 60} autres")
        return

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://emploi_user:emploi_temps@127.0.0.1:5432/emploi_temps",
    )
    parsed = urlparse(database_url)

    conn = psycopg2.connect(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 5432,
        database=(parsed.path or "").lstrip("/") or "emploi_temps",
        user=parsed.username or "emploi_user",
        password=parsed.password or "emploi_temps",
    )

    try:
        with conn.cursor() as cur:
            if clear_existing:
                cur.execute("DELETE FROM vacances_jours_feries WHERE annee_id = %s", (annee_id,))
                deleted = cur.rowcount
                conn.commit()
                print(f"Suppression existant (annee_id={annee_id}): {deleted} lignes")

            cur.executemany(
                """
                INSERT INTO vacances_jours_feries (nom, date_debut, date_fin, type, annee_id)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [(e["nom"], e["date_debut"], e["date_fin"], e["type"], annee_id) for e in events],
            )
            conn.commit()

        print(f"Import terminé: {len(events)} lignes insérées (annee_id={annee_id})")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file",
        default=os.path.join("public", "excel_files", "Calendrier universitaire 2024-2025 Modifié.xlsx"),
    )
    parser.add_argument("--annee-id", type=int, default=1)
    parser.add_argument("--no-clear", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import_calendar(
        excel_path=args.file,
        annee_id=args.annee_id,
        clear_existing=not args.no_clear,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()