# backend/app/services/excel_parser.py
#!/usr/bin/env python3
"""
Vertical Excel Parser for EnetCom timetable workbooks.

Supported views:
- student workbooks   -> owner is the class
- teacher workbooks   -> owner is the professor
- room workbooks      -> owner is the room

Important behavior kept from the original parser:
- common cells without (P1)/(P2) remain periode=None
- cells tagged with (P1) or (P2) expose that marker
- mixed P1/P2 cells can emit multiple sessions
"""

from __future__ import annotations

import re
from datetime import time
from typing import Any, Dict, List, Optional

import pandas as pd


DAY_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

PERIODE_RE = re.compile(r"\((P1|P2)\)", re.IGNORECASE)
TIME_RANGE_RE = re.compile(
    r"(?P<h1>\d{1,2})\s*[h:]\s*(?P<m1>\d{2})\s*-\s*(?P<h2>\d{1,2})\s*[h:]\s*(?P<m2>\d{2})",
    re.IGNORECASE,
)
PROF_RE = re.compile(r"\b(mr|mme|mlle|dr|pr)\b", re.IGNORECASE)
CLASS_RE = re.compile(r"^\d+\s+(?:ING|TIC|LTIC|MP|MR)\b", re.IGNORECASE)
ROOM_RE = re.compile(r"^salle\b", re.IGNORECASE)


def _to_time(h: int, m: int) -> time:
    return time(int(h), int(m))


def _norm_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if text.strip().lower() in {"nan", "none"}:
        return ""
    return text.strip()


def _compact_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _clean_salle(value: str) -> str:
    if not value:
        return ""
    value = ROOM_RE.sub("", value).strip(" :")
    value = PERIODE_RE.sub("", value)
    return _compact_spaces(value)


def _extract_period_marker(text: str) -> Optional[str]:
    if not text:
        return None
    match = PERIODE_RE.search(text)
    return match.group(1).upper() if match else None


def _guess_type(text: str) -> str:
    lowered = (text or "").lower()
    if re.search(r"\btp\b", lowered):
        return "TP"
    if re.search(r"\btd\b", lowered):
        return "TD"
    return "cours"


def _extract_time_range(text: str) -> Optional[Dict[str, time]]:
    match = TIME_RANGE_RE.search(_norm_text(text))
    if not match:
        return None
    return {
        "start": _to_time(int(match.group("h1")), int(match.group("m1"))),
        "end": _to_time(int(match.group("h2")), int(match.group("m2"))),
    }


def _normalized_lines(block: str) -> List[str]:
    lines = [_compact_spaces(line) for line in (block or "").replace("\r\n", "\n").replace("\r", "\n").splitlines()]
    lines = [line for line in lines if line]
    if lines and TIME_RANGE_RE.search(lines[0]):
        lines = lines[1:]
    return lines


def _is_prof_line(line: str) -> bool:
    return bool(PROF_RE.search(line or ""))


def _is_class_line(line: str) -> bool:
    return bool(CLASS_RE.search(_compact_spaces(line)))


def _is_room_line(line: str) -> bool:
    return bool(ROOM_RE.search(_compact_spaces(line)))


def _extract_named_header(sheet_df: pd.DataFrame, label: str) -> Optional[str]:
    try:
        max_r = min(40, sheet_df.shape[0])
        max_c = min(20, sheet_df.shape[1])
        for r in range(max_r):
            for c in range(max_c):
                value = _norm_text(sheet_df.iat[r, c])
                if not value:
                    continue
                normalized = _compact_spaces(value).strip("| ")
                match = re.search(rf"{label}\s*:\s*(.+)$", normalized, flags=re.IGNORECASE)
                if match:
                    return _compact_spaces(match.group(1))
    except Exception:
        return None
    return None


def _extract_class_name_from_sheet(sheet_df: pd.DataFrame, sheet_name: str) -> str:
    return _extract_named_header(sheet_df, "classe") or _compact_spaces(sheet_name or "")


def _extract_professor_name_from_sheet(sheet_df: pd.DataFrame, sheet_name: str) -> str:
    return _extract_named_header(sheet_df, "professeur") or _compact_spaces(sheet_name or "")


def _extract_room_name_from_sheet(sheet_df: pd.DataFrame, sheet_name: str) -> str:
    room_name = _extract_named_header(sheet_df, "salle") or _compact_spaces(sheet_name or "")
    return _clean_salle(room_name)


def _find_day_rows(df: pd.DataFrame) -> Dict[int, str]:
    day_rows: Dict[int, str] = {}
    for column in [0, 1]:
        if df.shape[1] <= column:
            continue
        for row_idx in range(df.shape[0]):
            value = _compact_spaces(_norm_text(df.iat[row_idx, column]))
            if not value:
                continue
            for day_name in DAY_FR:
                if value.lower().startswith(day_name.lower()):
                    day_rows[row_idx] = day_name
                    break
        if day_rows:
            break
    return day_rows


def _split_into_period_blocks(cell_text: str) -> List[Dict[str, Optional[str]]]:
    text = _norm_text(cell_text)
    if not text:
        return []

    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n+", text) if chunk.strip()]
    if not chunks:
        chunks = [text]

    out: List[Dict[str, Optional[str]]] = []

    for chunk in chunks:
        markers = {match.group(1).upper() for match in PERIODE_RE.finditer(chunk)}

        if not markers:
            out.append({"text": chunk, "periode": None})
            continue
        if markers == {"P1"}:
            out.append({"text": chunk, "periode": "P1"})
            continue
        if markers == {"P2"}:
            out.append({"text": chunk, "periode": "P2"})
            continue

        raw_lines = [line.rstrip() for line in chunk.splitlines() if line.strip()]
        body_lines = raw_lines[1:] if raw_lines and TIME_RANGE_RE.search(raw_lines[0]) else raw_lines[:]

        room_end_indexes = [i for i, line in enumerate(body_lines) if _is_room_line(line)]
        if len(room_end_indexes) >= 2:
            start_idx = 0
            for end_idx in room_end_indexes:
                segment_lines = body_lines[start_idx:end_idx + 1]
                start_idx = end_idx + 1
                if not segment_lines:
                    continue
                segment_text = "\n".join(segment_lines).strip()
                segment_marker = _extract_period_marker(segment_text)
                if segment_marker:
                    out.append({"text": segment_text, "periode": segment_marker})
            if out:
                continue

        class_start_indexes = [i for i, line in enumerate(body_lines) if _is_class_line(line)]
        if len(class_start_indexes) >= 2:
            for idx, start_idx in enumerate(class_start_indexes):
                end_idx = class_start_indexes[idx + 1] if idx + 1 < len(class_start_indexes) else len(body_lines)
                segment_lines = body_lines[start_idx:end_idx]
                if not segment_lines:
                    continue
                segment_text = "\n".join(segment_lines).strip()
                segment_marker = _extract_period_marker(segment_text)
                if segment_marker:
                    out.append({"text": segment_text, "periode": segment_marker})
            if out:
                continue

        lines = [line.rstrip() for line in chunk.splitlines()]
        idx_p1 = [i for i, line in enumerate(lines) if "(P1" in line.upper()]
        idx_p2 = [i for i, line in enumerate(lines) if "(P2" in line.upper()]

        if idx_p1 and idx_p2:
            def grab_block(end_idx: int) -> str:
                start = max(0, end_idx - 3)
                return "\n".join(line for line in lines[start:end_idx + 1] if line.strip()).strip()

            out.append({"text": grab_block(idx_p1[-1]), "periode": "P1"})
            out.append({"text": grab_block(idx_p2[-1]), "periode": "P2"})
        else:
            out.append({"text": chunk, "periode": "P1"})
            out.append({"text": chunk, "periode": "P2"})

    return out


def _parse_student_entries(lines: List[str]) -> List[Dict[str, str]]:
    if not lines:
        return []

    room_indexes = [i for i, line in enumerate(lines) if _is_room_line(line)]
    if not room_indexes:
        matiere = lines[0] if lines else ""
        professeur = next((line for line in lines[1:] if _is_prof_line(line)), "")
        salle = next((line for line in lines[1:] if _is_room_line(line)), "")
        return [{
            "matiere": matiere,
            "professeur": professeur,
            "salle": _clean_salle(salle),
        }]

    entries: List[Dict[str, str]] = []
    previous_end = 0
    for room_idx in room_indexes:
        segment = lines[previous_end:room_idx + 1]
        previous_end = room_idx + 1
        if not segment:
            continue

        salle = segment[-1]
        professeur = ""
        matiere_parts: List[str] = []
        for line in segment[:-1]:
            if _is_prof_line(line) and not professeur:
                professeur = line
            else:
                matiere_parts.append(line)

        entries.append(
            {
                "matiere": _compact_spaces(" ".join(matiere_parts)),
                "professeur": professeur,
                "salle": _clean_salle(salle),
            }
        )
    return entries


def _parse_teacher_entries(lines: List[str]) -> List[Dict[str, str]]:
    if not lines:
        return []

    entries: List[Dict[str, str]] = []
    room_indexes = [i for i, line in enumerate(lines) if _is_room_line(line)]

    if room_indexes:
        previous_end = 0
        for room_idx in room_indexes:
            segment = lines[previous_end:room_idx + 1]
            previous_end = room_idx + 1
            if len(segment) < 2:
                continue
            classe = segment[0]
            matiere = _compact_spaces(" ".join(segment[1:-1]))
            salle = _clean_salle(segment[-1])
            entries.append({"classe": classe, "matiere": matiere, "salle": salle})
        return entries

    i = 0
    while i < len(lines):
        if i + 1 < len(lines) and _is_class_line(lines[i]):
            classe = lines[i]
            matiere = lines[i + 1]
            entries.append({"classe": classe, "matiere": matiere, "salle": ""})
            i += 2
            continue
        i += 1

    return entries


def _parse_room_entries(lines: List[str]) -> List[Dict[str, str]]:
    if not lines:
        return []

    entries: List[Dict[str, str]] = []
    i = 0
    while i < len(lines):
        if i + 2 < len(lines) and _is_class_line(lines[i]) and _is_prof_line(lines[i + 1]):
            entries.append(
                {
                    "classe": lines[i],
                    "professeur": lines[i + 1],
                    "matiere": lines[i + 2],
                }
            )
            i += 3
            continue
        i += 1

    if entries:
        return entries

    professor_indexes = [i for i, line in enumerate(lines) if _is_prof_line(line)]
    for prof_idx in professor_indexes:
        classe = lines[prof_idx - 1] if prof_idx - 1 >= 0 else ""
        matiere = lines[prof_idx + 1] if prof_idx + 1 < len(lines) else ""
        if classe or matiere:
            entries.append({"classe": classe, "professeur": lines[prof_idx], "matiere": matiere})

    return entries


class VerticalExcelParser:
    def _parse_sheet(
        self,
        df: pd.DataFrame,
        owner_name: str,
        owner_kind: str,
    ) -> List[Dict[str, Any]]:
        sessions: List[Dict[str, Any]] = []
        day_rows = _find_day_rows(df)
        if not day_rows:
            return sessions

        for row_idx, day_name in day_rows.items():
            for col_idx in range(df.shape[1]):
                cell = _norm_text(df.iat[row_idx, col_idx])
                if not cell:
                    continue

                time_range = _extract_time_range(cell)
                if not time_range:
                    continue

                period_blocks = _split_into_period_blocks(cell)
                for block in period_blocks:
                    lines = _normalized_lines(block["text"])
                    if owner_kind == "student":
                        entries = _parse_student_entries(lines)
                    elif owner_kind == "teacher":
                        entries = _parse_teacher_entries(lines)
                    else:
                        entries = _parse_room_entries(lines)

                    periode_marker = (
                        block["periode"]
                        or _extract_period_marker(cell)
                        or _extract_period_marker(owner_name)
                    )

                    for entry in entries:
                        base_session: Dict[str, Any] = {
                            "jour": day_name,
                            "heure_debut": time_range["start"],
                            "heure_fin": time_range["end"],
                            "periode": periode_marker,
                            "type_seance": _guess_type("\n".join(lines)),
                        }

                        if owner_kind == "student":
                            base_session.update(
                                {
                                    "classe": owner_name,
                                    "groupe": owner_name,
                                    "matiere": entry.get("matiere", ""),
                                    "professeur": entry.get("professeur", ""),
                                    "salle": entry.get("salle", ""),
                                }
                            )
                        elif owner_kind == "teacher":
                            base_session.update(
                                {
                                    "classe": entry.get("classe", ""),
                                    "groupe": entry.get("classe", ""),
                                    "matiere": entry.get("matiere", ""),
                                    "professeur": owner_name,
                                    "salle": entry.get("salle", ""),
                                }
                            )
                        else:
                            base_session.update(
                                {
                                    "classe": entry.get("classe", ""),
                                    "groupe": entry.get("classe", ""),
                                    "matiere": entry.get("matiere", ""),
                                    "professeur": entry.get("professeur", ""),
                                    "salle": owner_name,
                                }
                            )

                        if base_session.get("matiere"):
                            sessions.append(base_session)

        return sessions

    def parse_schedule_file(self, file_path: str) -> List[Dict[str, Any]]:
        xls = pd.read_excel(file_path, sheet_name=None, header=None)
        sessions: List[Dict[str, Any]] = []

        for sheet_name, df in xls.items():
            if df is None or df.empty:
                continue
            class_name = _extract_class_name_from_sheet(df, sheet_name)
            sessions.extend(self._parse_sheet(df, class_name, "student"))

        return sessions

    def parse_teacher_schedule_file(self, file_path: str) -> List[Dict[str, Any]]:
        xls = pd.read_excel(file_path, sheet_name=None, header=None)
        sessions: List[Dict[str, Any]] = []

        for sheet_name, df in xls.items():
            if df is None or df.empty:
                continue
            teacher_name = _extract_professor_name_from_sheet(df, sheet_name)
            sessions.extend(self._parse_sheet(df, teacher_name, "teacher"))

        return sessions

    def parse_room_schedule_file(self, file_path: str) -> List[Dict[str, Any]]:
        xls = pd.read_excel(file_path, sheet_name=None, header=None)
        sessions: List[Dict[str, Any]] = []

        for sheet_name, df in xls.items():
            if df is None or df.empty:
                continue
            room_name = _extract_room_name_from_sheet(df, sheet_name)
            sessions.extend(self._parse_sheet(df, room_name, "room"))

        return sessions
