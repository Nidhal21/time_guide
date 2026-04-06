from __future__ import annotations

import os
import re
from datetime import date
from typing import Any, Dict, List

from sqlalchemy import select

from backend.app.models.db_config import SessionLocal
from backend.app.models.database import (
    Classe,
    EmploiEnseignantSeance,
    EmploiVersion,
    Groupe,
    Matiere,
    Periode,
    Professeur,
    Salle,
    Seance,
)
from backend.app.services.excel_parser import VerticalExcelParser


def _norm(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").strip().lower())


def _norm_periode_name(value: str) -> str:
    value = (value or "").strip().upper()
    return re.sub(r"\s+", "", value)


def _resolve_type_seance(session: Dict[str, Any]) -> str:
    session_type = (session.get("type_seance") or "").strip()
    if session_type in {"TP", "TD", "cours"}:
        return session_type

    matiere = (session.get("matiere") or "").strip().lower()
    if matiere.startswith("tp ") or " tp " in matiere or matiere.startswith("tp-"):
        return "TP"
    if matiere.startswith("td ") or " td " in matiere or matiere.startswith("td-"):
        return "TD"
    return "cours"


def _prepare_sessions_for_semester(db, sessions: List[Dict[str, Any]], semester_id: int) -> tuple[List[Dict[str, Any]], Dict[str, Periode]]:
    periodes = db.query(Periode).filter_by(semestre_id=semester_id).all()
    if not periodes:
        raise ValueError(f"Aucune periode n'a ete trouvee pour le semestre S{semester_id}.")

    periodes_by_nom = {_norm_periode_name(periode.nom): periode for periode in periodes if periode.nom}
    has_p1 = "P1" in periodes_by_nom
    has_p2 = "P2" in periodes_by_nom

    cleaned_sessions: List[Dict[str, Any]] = []
    for session in sessions:
        if not session.get("classe") or not session.get("matiere"):
            continue
        if not session.get("jour") or not session.get("heure_debut") or not session.get("heure_fin"):
            continue
        cleaned_sessions.append(dict(session))

    expanded_sessions: List[Dict[str, Any]] = []
    for session in cleaned_sessions:
        marker = _norm_periode_name(session.get("periode") or "")
        if marker in {"P1", "P2"}:
            session_copy = dict(session)
            session_copy["periode"] = marker
            expanded_sessions.append(session_copy)
            continue

        if has_p1 and has_p2:
            session_p1 = dict(session)
            session_p1["periode"] = "P1"
            session_p2 = dict(session)
            session_p2["periode"] = "P2"
            expanded_sessions.extend([session_p1, session_p2])
        else:
            expanded_sessions.append(dict(session))

    return expanded_sessions, periodes_by_nom


def _import_sessions_to_db(
    sessions: List[Dict[str, Any]],
    semester_id: int,
    clear_existing: bool = False,
    source_label: str = "emploi du temps",
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        print(f"\n{'=' * 80}")
        print(f"IMPORTATION {source_label.upper()}")
        print(f"{'=' * 80}\n")

        prepared_sessions, periodes_by_nom = _prepare_sessions_for_semester(db, sessions, semester_id)
        print(f"Parsed sessions retained: {len(prepared_sessions)}")

        if not prepared_sessions:
            print("No valid session to import. Nothing was changed.")
            return {
                "semester_id": semester_id,
                "source": source_label,
                "parsed_session_count": 0,
                "imported_session_count": 0,
                "class_count": 0,
            }

        def resolve_periode_id(session: Dict[str, Any]) -> int:
            marker = _norm_periode_name(session.get("periode") or "")
            if marker in periodes_by_nom:
                return periodes_by_nom[marker].id
            return next(iter(periodes_by_nom.values())).id

        classes_dict: Dict[str, int] = {}
        for classe in db.query(Classe).filter_by(semestre_id=semester_id).all():
            classes_dict[_norm(classe.nom)] = classe.id

        unique_classes = sorted({_norm(session["classe"]): session["classe"] for session in prepared_sessions}.items())
        for _, classe_name in unique_classes:
            key = _norm(classe_name)
            if key in classes_dict:
                continue
            classe = Classe(nom=classe_name.strip(), semestre_id=semester_id)
            db.add(classe)
            db.flush()
            classes_dict[key] = classe.id
        db.commit()

        classe_ids = list(classes_dict.values())
        classe_ids_sel = select(Classe.id).where(Classe.semestre_id == semester_id)

        if clear_existing:
            print(f"Cleaning previous sessions and versions for semester S{semester_id}...")
            deleted_seances = (
                db.query(Seance)
                .filter(Seance.classe_id.in_(classe_ids_sel))
                .delete(synchronize_session=False)
            )
            db.commit()
            print(f"  Deleted sessions: {deleted_seances}")

            deleted_versions = (
                db.query(EmploiVersion)
                .filter(EmploiVersion.classe_id.in_(classe_ids_sel))
                .delete(synchronize_session=False)
            )
            db.commit()
            print(f"  Deleted versions: {deleted_versions}")
        elif classe_ids:
            (
                db.query(EmploiVersion)
                .filter(EmploiVersion.classe_id.in_(classe_ids))
                .update({"actif": False}, synchronize_session=False)
            )
            db.commit()

        groupes_dict: Dict[tuple[int, str], int] = {}
        for groupe in db.query(Groupe).all():
            if groupe.classe_id:
                groupes_dict[(groupe.classe_id, _norm(groupe.nom or ""))] = groupe.id

        for session in prepared_sessions:
            classe_id = classes_dict.get(_norm(session["classe"]))
            if not classe_id:
                continue
            groupe_name = (session.get("groupe") or session["classe"]).strip()
            groupe_key = (classe_id, _norm(groupe_name))
            if groupe_key in groupes_dict:
                continue
            groupe = Groupe(nom=groupe_name, classe_id=classe_id)
            db.add(groupe)
            db.flush()
            groupes_dict[groupe_key] = groupe.id
        db.commit()

        profs_dict: Dict[str, int] = {_norm(prof.nom_complet): prof.id for prof in db.query(Professeur).all()}
        unique_profs = sorted(
            {_norm(session["professeur"]): session["professeur"] for session in prepared_sessions if session.get("professeur")}.items()
        )
        for _, prof_name in unique_profs:
            key = _norm(prof_name)
            if not key or key in profs_dict:
                continue
            professeur = Professeur(nom_complet=prof_name.strip())
            db.add(professeur)
            db.flush()
            profs_dict[key] = professeur.id
        db.commit()

        salles_dict: Dict[str, int] = {_norm(salle.nom): salle.id for salle in db.query(Salle).all()}
        unique_salles = sorted(
            {_norm(session["salle"]): session["salle"] for session in prepared_sessions if session.get("salle")}.items()
        )
        for _, salle_name in unique_salles:
            key = _norm(salle_name)
            if not key or key in salles_dict:
                continue
            salle = Salle(nom=salle_name.strip(), type="Salle")
            db.add(salle)
            db.flush()
            salles_dict[key] = salle.id
        db.commit()

        matieres_dict: Dict[str, int] = {_norm(matiere.nom): matiere.id for matiere in db.query(Matiere).all()}
        unique_matieres = sorted(
            {_norm(session["matiere"]): session["matiere"] for session in prepared_sessions if session.get("matiere")}.items()
        )
        for _, matiere_name in unique_matieres:
            key = _norm(matiere_name)
            if not key or key in matieres_dict:
                continue
            matiere = Matiere(nom=matiere_name.strip())
            db.add(matiere)
            db.flush()
            matieres_dict[key] = matiere.id
        db.commit()

        versions_by_classe_id: Dict[int, int] = {}
        for classe_id in classe_ids:
            version = EmploiVersion(version_date=date.today(), actif=True, classe_id=classe_id)
            db.add(version)
            db.flush()
            versions_by_classe_id[classe_id] = version.id
        db.commit()

        imported_session_count = 0
        for session in prepared_sessions:
            classe_id = classes_dict.get(_norm(session["classe"]))
            if not classe_id:
                continue

            matiere_name = (session.get("matiere") or "").strip()
            if not matiere_name:
                continue

            groupe_name = (session.get("groupe") or session["classe"]).strip()
            groupe_key = (classe_id, _norm(groupe_name))
            groupe_id = groupes_dict.get(groupe_key)
            if not groupe_id:
                groupe = Groupe(nom=groupe_name, classe_id=classe_id)
                db.add(groupe)
                db.flush()
                groupe_id = groupe.id
                groupes_dict[groupe_key] = groupe_id

            seance = Seance(
                version_id=versions_by_classe_id.get(classe_id),
                classe_id=classe_id,
                matiere_id=matieres_dict.get(_norm(matiere_name)),
                professeur_id=profs_dict.get(_norm(session.get("professeur", ""))) if session.get("professeur") else None,
                salle_id=salles_dict.get(_norm(session.get("salle", ""))) if session.get("salle") else None,
                groupe_id=groupe_id,
                periode_id=resolve_periode_id(session),
                jour=session["jour"],
                heure_debut=session["heure_debut"],
                heure_fin=session["heure_fin"],
                type_seance=_resolve_type_seance(session),
            )
            db.add(seance)
            imported_session_count += 1

            if imported_session_count % 300 == 0:
                db.commit()
                print(f"  Imported sessions: {imported_session_count}")

        db.commit()
        print(f"Import complete: {imported_session_count} sessions inserted.")

        return {
            "semester_id": semester_id,
            "source": source_label,
            "parsed_session_count": len(prepared_sessions),
            "imported_session_count": imported_session_count,
            "class_count": len(classes_dict),
            "version_count": len(versions_by_classe_id),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _sync_teacher_reference_table(
    sessions: List[Dict[str, Any]],
    semester_id: int,
    clear_existing: bool = False,
    source_file: str | None = None,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        prepared_sessions, periodes_by_nom = _prepare_sessions_for_semester(db, sessions, semester_id)

        if clear_existing:
            (
                db.query(EmploiEnseignantSeance)
                .filter(EmploiEnseignantSeance.semestre_id == semester_id)
                .delete(synchronize_session=False)
            )
            db.commit()

        inserted = 0
        for session in prepared_sessions:
            professeur = (session.get("professeur") or "").strip()
            classe = (session.get("classe") or "").strip()
            matiere = (session.get("matiere") or "").strip()
            if not professeur or not classe or not matiere:
                continue

            periode_name = _norm_periode_name(session.get("periode") or "")
            if not periode_name:
                periode_name = next(iter(periodes_by_nom.keys()))

            row = EmploiEnseignantSeance(
                semestre_id=semester_id,
                professeur_nom_complet=professeur,
                classe_nom=classe,
                matiere_nom=matiere,
                salle_nom=(session.get("salle") or "").strip() or None,
                jour=session["jour"],
                heure_debut=session["heure_debut"],
                heure_fin=session["heure_fin"],
                periode_nom=periode_name,
                type_seance=_resolve_type_seance(session),
                source_file=source_file,
            )
            db.add(row)
            inserted += 1

            if inserted % 500 == 0:
                db.commit()

        db.commit()
        return {
            "teacher_reference_count": inserted,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def import_emplois_du_temps(excel_file: str, semester_id: int, clear_existing: bool = False) -> Dict[str, Any]:
    parser = VerticalExcelParser()
    sessions = parser.parse_schedule_file(excel_file)
    return _import_sessions_to_db(
        sessions=sessions,
        semester_id=semester_id,
        clear_existing=clear_existing,
        source_label="emploi du temps etudiants",
    )


def import_teacher_emplois_du_temps(excel_file: str, semester_id: int, clear_existing: bool = False) -> Dict[str, Any]:
    parser = VerticalExcelParser()
    sessions = parser.parse_teacher_schedule_file(excel_file)
    db_summary = _import_sessions_to_db(
        sessions=sessions,
        semester_id=semester_id,
        clear_existing=clear_existing,
        source_label="emploi du temps enseignants",
    )
    reference_summary = _sync_teacher_reference_table(
        sessions=sessions,
        semester_id=semester_id,
        clear_existing=clear_existing,
        source_file=os.path.basename(excel_file),
    )
    return {
        **db_summary,
        **reference_summary,
    }


def import_room_emplois_du_temps(excel_file: str, semester_id: int, clear_existing: bool = False) -> Dict[str, Any]:
    parser = VerticalExcelParser()
    sessions = parser.parse_room_schedule_file(excel_file)
    return _import_sessions_to_db(
        sessions=sessions,
        semester_id=semester_id,
        clear_existing=clear_existing,
        source_label="emploi du temps salles",
    )


def import_all_excels(excel_dir: str = "public/excel_files"):
    excel_dir = os.path.abspath(excel_dir)
    if not os.path.isdir(excel_dir):
        raise FileNotFoundError(excel_dir)

    files = [os.path.join(excel_dir, filename) for filename in os.listdir(excel_dir) if filename.lower().endswith(".xlsx")]

    cleared_semesters = set()
    for path in sorted(files):
        base = os.path.basename(path)
        lower_base = base.lower()

        semester_id = None
        if re.search(r"(?:^|[^a-z0-9])s1(?:$|[^a-z0-9])", lower_base):
            semester_id = 1
        elif re.search(r"(?:^|[^a-z0-9])s2(?:$|[^a-z0-9])", lower_base):
            semester_id = 2

        if not semester_id:
            print(f"Semester not detected for {base}. File skipped.")
            continue

        clear_existing = semester_id not in cleared_semesters
        if "etudi" in lower_base:
            import_emplois_du_temps(path, semester_id=semester_id, clear_existing=clear_existing)
            cleared_semesters.add(semester_id)
        else:
            print(f"Unsupported file for seance import: {base}")


if __name__ == "__main__":
    import_all_excels("public/excel_files")
    print("\nImport finished.")
