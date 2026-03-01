# backend/app/services/excel_parser.py
#!/usr/bin/env python3
"""
Vertical Excel Parser for Emploi du Temps (EnetCom style)

GOALS (your exact requirement):
- If a cell contains a course WITHOUT (P1)/(P2) -> it is COMMON -> should be imported into BOTH P1 and P2
  (this duplication is done in load_data.py, not here).
- If a cell contains (P1) or (P2) -> mark session["periode"] accordingly.
- If a cell contains BOTH a P1-block and a P2-block at the same slot -> output TWO sessions:
    one with periode="P1" and one with periode="P2".

This parser extracts:
- classe
- jour
- heure_debut / heure_fin (from "8h15-9h45" patterns in the cell)
- matiere
- professeur
- salle (cleaned without "(P1)/(P2)")
- periode (optional: "P1" or "P2")
- type_seance (TP/TD/cours)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import time
from typing import Dict, List, Optional, Any

import pandas as pd


DAY_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

PERIODE_RE = re.compile(r"\((P1|P2)\)", re.IGNORECASE)
TIME_RANGE_RE = re.compile(
    r"(?P<h1>\d{1,2})\s*[h:]\s*(?P<m1>\d{2})\s*-\s*(?P<h2>\d{1,2})\s*[h:]\s*(?P<m2>\d{2})",
    re.IGNORECASE,
)

# If the sheet uses 8h00, 8h30 headers etc, we don't rely on them.
# EnetCom blocks themselves contain "8h15-9h45", so we parse inside the cell text.


def _to_time(h: int, m: int) -> time:
    return time(int(h), int(m))


def _norm_text(s: Any) -> str:
    if s is None:
        return ""
    s = str(s)
    if s.strip().lower() in {"nan", "none"}:
        return ""
    return s.strip()


def _clean_salle(s: str) -> str:
    if not s:
        return ""
    s = PERIODE_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def _extract_period_marker(text: str) -> Optional[str]:
    if not text:
        return None
    m = PERIODE_RE.search(text)
    return m.group(1).upper() if m else None


def _guess_type(text: str) -> str:
    t = (text or "").lower()
    # strong signals
    if re.search(r"\btp\b", t):
        return "TP"
    if re.search(r"\btd\b", t):
        return "TD"
    return "cours"


def _parse_course_block(block: str) -> Dict[str, str]:
    """
    Parse a single block like:
    ROUTAGE AVANCE
    Mr ABBES T.
    Salle C27

    or:
    TP RÉS SANS FIL
    Mme HAMMAMI A.
    Salle TEL-RSF (P1)
    """
    lines = [ln.strip() for ln in (block or "").splitlines() if ln.strip()]
    # remove obvious time range line if present
    if lines and TIME_RANGE_RE.search(lines[0]):
        lines = lines[1:]

    matiere = ""
    professeur = ""
    salle = ""

    # Find salle line
    for ln in lines[::-1]:
        if ln.lower().startswith("salle"):
            salle = ln
            break

    # Remove "Salle " prefix
    if salle.lower().startswith("salle"):
        salle = salle.split(" ", 1)[1].strip() if " " in salle else salle

    # Find professeur line (often contains Mr/Mme/Dr/Pr)
    prof_idx = None
    for i, ln in enumerate(lines):
        if re.search(r"\b(mr|mme|mlle|dr|pr)\b", ln.lower()):
            professeur = ln.strip()
            prof_idx = i
            break

    # Matiere: usually first non-empty line (excluding salle/prof)
    # Prefer the line before professor if exists, else first line.
    if prof_idx is not None and prof_idx > 0:
        matiere = lines[prof_idx - 1].strip()
    else:
        # pick first line that is not salle
        for ln in lines:
            if ln.lower().startswith("salle"):
                continue
            matiere = ln.strip()
            break

    return {
        "matiere": matiere,
        "professeur": professeur,
        "salle": _clean_salle(salle),
        "type_seance": _guess_type("\n".join(lines)),
    }


def _split_into_period_blocks(cell_text: str) -> List[Dict[str, Optional[str]]]:
    """
    Handles these cases correctly:

    1) Common only (no (P1)/(P2)) -> one block with periode=None
    2) Only P1 or only P2 -> one block with periode="P1"/"P2"
    3) Mixed blocks in the same cell:
       - common + P1-only (your example)
       - common + P2-only
       - P1-only + P2-only
       - common + P1 + P2
    4) Rare: single paragraph containing both markers -> fallback to duplication.
    """
    text = _norm_text(cell_text)
    if not text:
        return []

    # Remove trailing spaces, normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()

    # Split into paragraphs (blocks) separated by blank lines
    # This matches typical EnetCom formatting where blocks are stacked vertically in one merged cell.
    chunks = [c.strip() for c in re.split(r"\n\s*\n+", text) if c.strip()]

    # If there are no blank lines, keep as single chunk
    if not chunks:
        chunks = [text]

    out: List[Dict[str, Optional[str]]] = []

    for ch in chunks:
        markers = {m.group(1).upper() for m in PERIODE_RE.finditer(ch)}

        if not markers:
            out.append({"text": ch, "periode": None})
            continue

        if markers == {"P1"}:
            out.append({"text": ch, "periode": "P1"})
            continue

        if markers == {"P2"}:
            out.append({"text": ch, "periode": "P2"})
            continue

        # If this chunk contains BOTH P1 and P2 markers, it's ambiguous:
        # - sometimes there are two blocks glued together without blank lines
        # Fallback: duplicate the chunk for both periods (safe) OR try salle-based split.
        # We'll try salle-based split first.
        lines = [ln.rstrip() for ln in ch.splitlines()]

        idx_p1 = [i for i, ln in enumerate(lines) if "(P1" in ln.upper()]
        idx_p2 = [i for i, ln in enumerate(lines) if "(P2" in ln.upper()]

        if idx_p1 and idx_p2:
            def grab_block(end_idx: int) -> str:
                start = max(0, end_idx - 3)
                return "\n".join(ln for ln in lines[start:end_idx + 1] if ln.strip()).strip()

            out.append({"text": grab_block(idx_p1[-1]), "periode": "P1"})
            out.append({"text": grab_block(idx_p2[-1]), "periode": "P2"})
        else:
            # ultimate fallback: duplicate
            out.append({"text": ch, "periode": "P1"})
            out.append({"text": ch, "periode": "P2"})

    # Merge tiny noise blocks if needed (optional). For now keep as-is.
    return out


def _extract_time_range(text: str) -> Optional[Dict[str, time]]:
    t = _norm_text(text)
    m = TIME_RANGE_RE.search(t)
    if not m:
        return None
    return {
        "start": _to_time(int(m.group("h1")), int(m.group("m1"))),
        "end": _to_time(int(m.group("h2")), int(m.group("m2"))),
    }


def _extract_class_name_from_sheet(sheet_df: pd.DataFrame, sheet_name: str) -> str:
    """
    Try to find 'Classe :' inside the sheet. If not found, fallback to sheet_name.
    """
    try:
        # Scan first ~40 rows and first ~20 columns for "Classe"
        max_r = min(40, sheet_df.shape[0])
        max_c = min(20, sheet_df.shape[1])
        for r in range(max_r):
            for c in range(max_c):
                v = _norm_text(sheet_df.iat[r, c])
                if not v:
                    continue
                if "classe" in v.lower():
                    # example: "Classe : 2 ING GT 1"
                    m = re.search(r"classe\s*:\s*(.+)$", v, flags=re.IGNORECASE)
                    if m:
                        return re.sub(r"\s+", " ", m.group(1).strip())
    except Exception:
        pass
    return re.sub(r"\s+", " ", (sheet_name or "").strip())


class VerticalExcelParser:
    """
    Parses EnetCom Excel sheets where each day is in the first column
    and course blocks are written as merged cells containing:
    - time range "8h15-9h45"
    - matiere
    - professeur
    - salle (optional "(P1)" / "(P2)")
    """

    def parse_schedule_file(self, file_path: str) -> List[Dict[str, Any]]:
        xls = pd.read_excel(file_path, sheet_name=None, header=None)

        sessions: List[Dict[str, Any]] = []

        for sheet_name, df in xls.items():
            if df is None or df.empty:
                continue

            classe_name = _extract_class_name_from_sheet(df, sheet_name)

            # Find rows containing a day label in col 0 (or near)
            day_rows: Dict[int, str] = {}
            for i in range(df.shape[0]):
                first = _norm_text(df.iat[i, 0]) if df.shape[1] > 0 else ""
                if not first:
                    continue
                first_clean = re.sub(r"\s+", " ", first).strip()
                for d in DAY_FR:
                    if first_clean.lower().startswith(d.lower()):
                        day_rows[i] = d
                        break

            if not day_rows:
                # Some files have day labels not in col0; try col1
                if df.shape[1] > 1:
                    for i in range(df.shape[0]):
                        first = _norm_text(df.iat[i, 1])
                        if not first:
                            continue
                        first_clean = re.sub(r"\s+", " ", first).strip()
                        for d in DAY_FR:
                            if first_clean.lower().startswith(d.lower()):
                                day_rows[i] = d
                                break

            if not day_rows:
                continue

            # For each day-row, scan all columns for cell blocks containing a time range
            for row_idx, day_name in day_rows.items():
                for col_idx in range(df.shape[1]):
                    cell = _norm_text(df.iat[row_idx, col_idx])
                    if not cell:
                        continue

                    # We only care about schedule blocks that contain "8h15-9h45" etc
                    tr = _extract_time_range(cell)
                    if not tr:
                        continue

                    # Split into P1/P2 blocks if both appear
                    blocks = _split_into_period_blocks(cell)
                    for blk in blocks:
                        parsed = _parse_course_block(blk["text"])
                        periode_marker = blk["periode"] or _extract_period_marker(cell) or _extract_period_marker(parsed.get("salle", ""))

                        sessions.append(
                            {
                                "classe": classe_name,
                                "jour": day_name,
                                "heure_debut": tr["start"],
                                "heure_fin": tr["end"],
                                "matiere": parsed.get("matiere", ""),
                                "professeur": parsed.get("professeur", ""),
                                "salle": parsed.get("salle", ""),
                                "type_seance": parsed.get("type_seance", "cours"),
                                "periode": periode_marker,  # "P1"/"P2"/None
                                "groupe": classe_name,  # default group name = classe name
                            }
                        )

        return sessions