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
