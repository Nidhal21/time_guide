from __future__ import annotations

import re
import shutil
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from import_calendar import import_calendar as import_calendar_excel
from load_data import import_emplois_du_temps, import_room_emplois_du_temps, import_teacher_emplois_du_temps


UPLOAD_ROOT = PROJECT_ROOT / "backend" / "uploads"
CLASS_OWNER_RE = re.compile(
    r"^(?:\d+\s+(?:ING|TIC|LTIC|MP|MR)\b.*|\d(?:GII|GEC|GT|IDSD|INFO|TELECOM)\d)$",
    re.IGNORECASE,
)
ROOM_OWNER_RE = re.compile(
    r"^(?:[A-Z]{1,4}\s*\d{1,3}|LAB(?:\s+\d+)?|INF[- ][A-Z0-9 ]+|TEL[- ][A-Z0-9 ]+|EL[- ][A-Z0-9 ]+|II[- ][A-Z0-9 ]+|PRIMATEC)$",
    re.IGNORECASE,
)
SEMESTER_RE = re.compile(r"\bsemestre\s*[-: ]*\s*([12])\b|\bS\s*([12])\b", re.IGNORECASE)
AUDIENCE_LABELS = {
    "etudiants": "emplois etudiants",
    "enseignants": "emplois enseignants",
    "salles": "emplois des salles",
    "calendrier": "calendrier universitaire",
}


@dataclass(frozen=True)
class UploadCategory:
    key: str
    label: str
    folder: str
    db_updates: bool
    audience: str
    semester_id: Optional[int] = None


UPLOAD_CATEGORIES: Dict[str, UploadCategory] = {
    "student_s1": UploadCategory(
        key="student_s1",
        label="Emplois des etudiants S1",
        folder="students/s1",
        db_updates=True,
        audience="etudiants",
        semester_id=1,
    ),
    "student_s2": UploadCategory(
        key="student_s2",
        label="Emplois des etudiants S2",
        folder="students/s2",
        db_updates=True,
        audience="etudiants",
        semester_id=2,
    ),
    "rooms_s1": UploadCategory(
        key="rooms_s1",
        label="Emplois des salles S1",
        folder="rooms/s1",
        db_updates=True,
        audience="salles",
        semester_id=1,
    ),
    "rooms_s2": UploadCategory(
        key="rooms_s2",
        label="Emplois des salles S2",
        folder="rooms/s2",
        db_updates=True,
        audience="salles",
        semester_id=2,
    ),
    "teachers_s1": UploadCategory(
        key="teachers_s1",
        label="Emplois des enseignants S1",
        folder="teachers/s1",
        db_updates=True,
        audience="enseignants",
        semester_id=1,
    ),
    "teachers_s2": UploadCategory(
        key="teachers_s2",
        label="Emplois des enseignants S2",
        folder="teachers/s2",
        db_updates=True,
        audience="enseignants",
        semester_id=2,
    ),
    "calendar": UploadCategory(
        key="calendar",
        label="Calendrier universitaire",
        folder="calendar",
        db_updates=True,
        audience="calendrier",
    ),
}


def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", filename or "upload.xlsx").strip()
    return cleaned or "upload.xlsx"


def _human_file_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def _extract_workbook_metadata(file_path: Path) -> Dict[str, object]:
    xls = pd.ExcelFile(file_path)
    return {
        "sheet_count": len(xls.sheet_names),
        "sheet_preview": xls.sheet_names[:4],
    }


def _compact_spaces(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _norm_cell(value: object) -> str:
    text_value = _compact_spaces(value)
    return "" if text_value.lower() in {"", "nan", "none"} else text_value


def _extract_named_header(sheet_df: pd.DataFrame, label: str) -> Optional[str]:
    max_r = min(25, sheet_df.shape[0])
    max_c = min(20, sheet_df.shape[1])
    for r in range(max_r):
        for c in range(max_c):
            value = _norm_cell(sheet_df.iat[r, c])
            if not value:
                continue
            match = re.search(rf"\b{label}\s*:\s*(.+)$", value, flags=re.IGNORECASE)
            if match:
                return _compact_spaces(match.group(1))
    return None


def _top_sheet_text(sheet_df: pd.DataFrame) -> str:
    max_r = min(12, sheet_df.shape[0])
    max_c = min(20, sheet_df.shape[1])
    values: List[str] = []
    for r in range(max_r):
        for c in range(max_c):
            value = _norm_cell(sheet_df.iat[r, c])
            if value:
                values.append(value)
    return "\n".join(values)


def _looks_like_class_owner(value: str) -> bool:
    return bool(CLASS_OWNER_RE.match(_compact_spaces(value)))


def _looks_like_room_owner(value: str) -> bool:
    cleaned = _compact_spaces(re.sub(r"^salle\s*:?\s*", "", value or "", flags=re.IGNORECASE))
    if not cleaned or _looks_like_class_owner(cleaned):
        return False
    return bool(ROOM_OWNER_RE.match(cleaned))


def _looks_like_professor_owner(value: str) -> bool:
    cleaned = _compact_spaces(re.sub(r"^professeur\s*:?\s*", "", value or "", flags=re.IGNORECASE))
    if not cleaned or _looks_like_class_owner(cleaned) or _looks_like_room_owner(cleaned):
        return False
    if re.search(r"\d", cleaned):
        return False
    alpha_tokens = [token for token in re.split(r"[\s'-]+", cleaned) if token and re.search(r"[A-Za-zÀ-ÿ]", token)]
    return len(alpha_tokens) >= 2


def _detect_semester_in_text(text_value: str) -> Optional[int]:
    for match in SEMESTER_RE.finditer(text_value or ""):
        captured = match.group(1) or match.group(2)
        if captured in {"1", "2"}:
            return int(captured)
    return None


def _detect_workbook_signature(file_path: Path, max_sheets: int = 3) -> Dict[str, object]:
    xls = pd.ExcelFile(file_path)
    sampled_sheets = xls.sheet_names[:max_sheets]
    scores = {"etudiants": 0, "enseignants": 0, "salles": 0}
    semester_hits: List[int] = []

    for sheet_name in sampled_sheets:
        sheet_df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
        if sheet_df is None or sheet_df.empty:
            continue

        top_text = _top_sheet_text(sheet_df)
        semester = _detect_semester_in_text(top_text) or _detect_semester_in_text(sheet_name)
        if semester:
            semester_hits.append(semester)

        class_header = _extract_named_header(sheet_df, "classe")
        professor_header = _extract_named_header(sheet_df, "professeur")
        room_header = _extract_named_header(sheet_df, "salle")

        if class_header:
            scores["etudiants"] += 8
        if professor_header:
            scores["enseignants"] += 8
        if room_header:
            scores["salles"] += 8

        candidate_values = [class_header, professor_header, room_header, sheet_name]
        for candidate in [value for value in candidate_values if value]:
            if _looks_like_class_owner(candidate):
                scores["etudiants"] += 3
            if _looks_like_professor_owner(candidate):
                scores["enseignants"] += 3
            if _looks_like_room_owner(candidate):
                scores["salles"] += 3

    detected_audience = None
    best_score = max(scores.values()) if scores else 0
    if best_score > 0:
        leaders = [audience for audience, score in scores.items() if score == best_score]
        if len(leaders) == 1:
            detected_audience = leaders[0]

    detected_semester = None
    if semester_hits:
        detected_semester = max(set(semester_hits), key=semester_hits.count)
    else:
        detected_semester = _detect_semester_in_text(file_path.name)

    return {
        "detected_audience": detected_audience,
        "detected_semester": detected_semester,
        "scores": scores,
        "sampled_sheets": sampled_sheets,
    }


def _validate_workbook_matches_category(saved_path: Path, category: UploadCategory) -> Dict[str, object]:
    if category.audience == "calendrier":
        return {
            "detected_audience": "calendrier",
            "detected_semester": None,
            "scores": {},
            "sampled_sheets": [],
        }

    detected = _detect_workbook_signature(saved_path)
    detected_audience = detected.get("detected_audience")
    detected_semester = detected.get("detected_semester")

    if detected_audience and detected_audience != category.audience:
        detected_label = AUDIENCE_LABELS.get(str(detected_audience), str(detected_audience))
        raise ValueError(
            f"Le fichier '{saved_path.name}' ressemble a {detected_label}, mais il a ete depose dans la categorie '{category.label}'."
        )

    if detected_semester and category.semester_id and int(detected_semester) != int(category.semester_id):
        raise ValueError(
            f"Le fichier '{saved_path.name}' correspond au semestre S{int(detected_semester)}, "
            f"mais il a ete depose dans la categorie '{category.label}'."
        )

    return detected


def _save_upload(upload, category: UploadCategory) -> Dict[str, object]:
    target_dir = UPLOAD_ROOT / category.folder
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = _safe_filename(getattr(upload, "filename", "upload.xlsx"))
    destination = target_dir / f"{timestamp}_{safe_name}"

    size = 0
    with destination.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    size = destination.stat().st_size

    return {
        "path": destination,
        "size_bytes": size,
        "size_label": _human_file_size(size),
    }


def _count(db: Session, table_name: str) -> int:
    return int(db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0)


def _get_active_context(db: Session) -> Dict[str, object]:
    row = db.execute(
        text(
            """
            SELECT
                au.id AS annee_id,
                au.libelle AS annee_libelle,
                au.date_debut AS annee_debut,
                au.date_fin AS annee_fin,
                s.nom AS semestre_nom,
                p.nom AS periode_nom,
                p.date_debut AS periode_debut,
                p.date_fin AS periode_fin
            FROM periodes p
            JOIN semestres s ON s.id = p.semestre_id
            JOIN annees_universitaires au ON au.id = s.annee_id
            WHERE :today BETWEEN p.date_debut AND p.date_fin
            ORDER BY p.date_debut DESC
            LIMIT 1
            """
        ),
        {"today": date.today()},
    ).mappings().first()

    if row:
        return dict(row)

    fallback = db.execute(
        text(
            """
            SELECT id AS annee_id, libelle AS annee_libelle, date_debut AS annee_debut, date_fin AS annee_fin
            FROM annees_universitaires
            ORDER BY COALESCE(date_fin, date_debut) DESC, id DESC
            LIMIT 1
            """
        )
    ).mappings().first()
    return dict(fallback) if fallback else {}


def _calendar_health_warning(db: Session, active_context: Dict[str, object]) -> Optional[str]:
    annee_id = active_context.get("annee_id")
    if not annee_id:
        return None

    span = db.execute(
        text(
            """
            SELECT MIN(date_debut) AS min_date, MAX(date_fin) AS max_date
            FROM vacances_jours_feries
            WHERE annee_id = :annee_id
            """
        ),
        {"annee_id": int(annee_id)},
    ).mappings().first()

    if not span or not span["min_date"] or not span["max_date"]:
        return "Aucun calendrier universitaire n'est encore importe pour l'annee active."

    start = active_context.get("annee_debut")
    end = active_context.get("annee_fin")
    if start and span["min_date"] < start:
        return "Le calendrier importe contient des dates anterieures a l'annee universitaire active."
    if end and span["max_date"] > end:
        return "Le calendrier importe contient des dates posterieures a l'annee universitaire active."
    return None


def _latest_uploaded_file(category: UploadCategory) -> Optional[Dict[str, object]]:
    folder = UPLOAD_ROOT / category.folder
    if not folder.exists():
        return None

    files = [path for path in folder.iterdir() if path.is_file()]
    if not files:
        return None

    latest = max(files, key=lambda path: path.stat().st_mtime)
    return {
        "filename": latest.name,
        "uploaded_at": datetime.fromtimestamp(latest.stat().st_mtime).isoformat(),
        "size_label": _human_file_size(latest.stat().st_size),
        "path": str(latest),
    }


def get_admin_dashboard_summary(db: Session) -> Dict[str, object]:
    active_context = _get_active_context(db)

    counts = {
        "classes": _count(db, "classes"),
        "seances": _count(db, "seances"),
        "professeurs": _count(db, "professeurs"),
        "salles": _count(db, "salles"),
        "matieres": _count(db, "matieres"),
        "versions_actives": int(
            db.execute(text("SELECT COUNT(*) FROM emplois_versions WHERE actif = true")).scalar() or 0
        ),
    }

    categories = []
    for category in UPLOAD_CATEGORIES.values():
        categories.append(
            {
                "key": category.key,
                "label": category.label,
                "db_updates": category.db_updates,
                "audience": category.audience,
                "semester_id": category.semester_id,
                "latest_file": _latest_uploaded_file(category),
            }
        )

    return {
        "active_context": active_context,
        "counts": counts,
        "calendar_warning": _calendar_health_warning(db, active_context),
        "categories": categories,
    }


def _apply_database_import(category: UploadCategory, saved_path: Path, db: Session) -> Dict[str, object]:
    if category.key == "calendar":
        active_context = _get_active_context(db)
        annee_id = active_context.get("annee_id")
        if not annee_id:
            raise ValueError("Aucune annee universitaire active n'est disponible pour importer le calendrier.")
        import_calendar_excel(str(saved_path), int(annee_id), clear_existing=True, dry_run=False)
        return {
            "parsed_session_count": None,
            "message": "Calendrier universitaire reimporte dans la base de donnees.",
        }

    if category.semester_id is None:
        return {
            "parsed_session_count": None,
            "message": "Fichier archive sans reimport BD.",
        }

    if category.audience == "enseignants":
        summary = import_teacher_emplois_du_temps(str(saved_path), semester_id=int(category.semester_id), clear_existing=True)
        return {
            "parsed_session_count": summary.get("imported_session_count"),
            "message": f"Semestre S{category.semester_id} reimporte depuis les emplois enseignants. {summary.get('imported_session_count', 0)} seances actives pour le chatbot.",
        }

    if category.audience == "salles":
        summary = import_room_emplois_du_temps(str(saved_path), semester_id=int(category.semester_id), clear_existing=True)
        return {
            "parsed_session_count": summary.get("imported_session_count"),
            "message": f"Semestre S{category.semester_id} reimporte depuis les emplois des salles. {summary.get('imported_session_count', 0)} seances actives pour le chatbot.",
        }

    summary = import_emplois_du_temps(str(saved_path), semester_id=int(category.semester_id), clear_existing=True)
    return {
        "parsed_session_count": summary.get("imported_session_count"),
        "message": f"Semestre S{category.semester_id} reimporte et active pour les reponses du chatbot.",
    }


def process_uploads(db: Session, uploads_by_key: Dict[str, object]) -> Dict[str, object]:
    results: List[Dict[str, object]] = []

    for key, upload in uploads_by_key.items():
        if not upload:
            continue

        category = UPLOAD_CATEGORIES[key]
        try:
            saved = _save_upload(upload, category)
            metadata = _extract_workbook_metadata(saved["path"])
            detected = _validate_workbook_matches_category(saved["path"], category)
            import_result = _apply_database_import(category, saved["path"], db)
            parsed_session_count = import_result.get("parsed_session_count")
            message = str(import_result["message"])

            results.append(
                {
                    "category": key,
                    "label": category.label,
                    "status": "success",
                    "filename": getattr(upload, "filename", None),
                    "saved_path": str(saved["path"]),
                    "size_label": saved["size_label"],
                    "sheet_count": metadata["sheet_count"],
                    "sheet_preview": metadata["sheet_preview"],
                    "detected_audience": detected.get("detected_audience"),
                    "detected_semester": detected.get("detected_semester"),
                    "db_updates": category.db_updates,
                    "parsed_session_count": parsed_session_count,
                    "message": message,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "category": key,
                    "label": category.label,
                    "status": "error",
                    "filename": getattr(upload, "filename", None),
                    "db_updates": category.db_updates,
                    "message": str(exc),
                }
            )

    if not results:
        raise ValueError("Aucun fichier Excel n'a ete fourni.")

    summary = get_admin_dashboard_summary(db)
    return {
        "processed_at": datetime.now().isoformat(),
        "results": results,
        "summary": summary,
    }
