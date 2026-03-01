# load_data.py
from __future__ import annotations

import os
import re
from datetime import date
from typing import Dict, Any, List

from sqlalchemy import select

from backend.app.models.db_config import SessionLocal
from backend.app.services.excel_parser import VerticalExcelParser
from backend.app.models.database import (
    Classe, Professeur, Matiere, Salle, Seance, EmploiVersion, Periode, Groupe
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").strip().lower())


def _norm_periode_name(n: str) -> str:
    # "P 1" / " p1 " => "P1"
    n = (n or "").strip().upper()
    n = re.sub(r"\s+", "", n)
    return n


def import_emplois_du_temps(excel_file: str, semester_id: int, clear_existing: bool = False):
    db = SessionLocal()
    try:
        print(f"\n{'='*80}")
        print("IMPORTATION EMPLOIS DU TEMPS")
        print(f"{'='*80}\n")

        # 0) Load periods for semester
        periodes = db.query(Periode).filter_by(semestre_id=semester_id).all()
        if not periodes:
            print("❌ Périodes non trouvées pour ce semestre!")
            return

        periodes_by_nom = {_norm_periode_name(p.nom): p for p in periodes if p.nom}
        has_p1 = "P1" in periodes_by_nom
        has_p2 = "P2" in periodes_by_nom
        print(f"📌 Périodes DB: {sorted(periodes_by_nom.keys())}")

        # 1) Parse excel
        parser = VerticalExcelParser()
        sessions = parser.parse_schedule_file(excel_file)
        print(f"\n✅ {len(sessions)} séances parsées (brut)\n")

        if not sessions:
            print("⚠️  Aucune séance parsée: import ignoré (aucune suppression)")
            return

        # 2) Expand common sessions into both P1 and P2
        expanded: List[Dict[str, Any]] = []
        for s in sessions:
            marker = _norm_periode_name(s.get("periode") or "")
            if marker in {"P1", "P2"}:
                s2 = dict(s)
                s2["periode"] = marker
                expanded.append(s2)
            else:
                if has_p1 and has_p2:
                    s1 = dict(s); s1["periode"] = "P1"
                    s2 = dict(s); s2["periode"] = "P2"
                    expanded.extend([s1, s2])
                else:
                    expanded.append(s)

        sessions = expanded
        print(f"✅ Après expansion P1/P2: {len(sessions)} séances\n")

        def resolve_periode_id(sess: dict) -> int:
            marker = _norm_periode_name(sess.get("periode") or "")
            if marker in periodes_by_nom:
                return periodes_by_nom[marker].id
            return periodes[0].id

        def resolve_type_seance(sess: dict) -> str:
            t = (sess.get("type_seance") or "").strip()
            if t in {"TP", "TD", "cours"}:
                return t
            mat = (sess.get("matiere") or "").strip().lower()
            if mat.startswith("tp ") or " tp " in mat or mat.startswith("tp-"):
                return "TP"
            if mat.startswith("td ") or " td " in mat or mat.startswith("td-"):
                return "TD"
            return "cours"

        # 3) Ensure classes for this semester
        classes_dict: Dict[str, int] = {}
        for cls in db.query(Classe).filter_by(semestre_id=semester_id).all():
            classes_dict[_norm(cls.nom)] = cls.id

        unique_classes = sorted({_norm(s["classe"]): s["classe"] for s in sessions}.items())
        for _, classe_name in unique_classes:
            key = _norm(classe_name)
            if key not in classes_dict:
                classe = Classe(nom=classe_name.strip(), semestre_id=semester_id)
                db.add(classe)
                db.flush()
                classes_dict[key] = classe.id
        db.commit()
        print(f"\n✅ {len(classes_dict)} classes\n")

        # 4) Cleanup (séances + versions) for this semester
        if clear_existing:
            print("🧹 Nettoyage (séances + versions) pour ce semestre...")

            # select of class ids for this semester (avoids JOIN/delete errors + avoids SAWarning)
            classe_ids_sel = select(Classe.id).where(Classe.semestre_id == semester_id)

            deleted_seances = (
                db.query(Seance)
                .filter(Seance.classe_id.in_(classe_ids_sel))
                .delete(synchronize_session=False)
            )
            db.commit()
            print(f"  ✓ {deleted_seances} séances supprimées")

            # Important: delete versions AFTER seances (FK version_id)
            deleted_versions = (
                db.query(EmploiVersion)
                .filter(EmploiVersion.classe_id.in_(classe_ids_sel))
                .delete(synchronize_session=False)
            )
            db.commit()
            print(f"  ✓ {deleted_versions} versions supprimées")

        # 5) Ensure groups (1 per class by default)
        groupes_dict: Dict[tuple[int, str], int] = {}
        for g in db.query(Groupe).all():
            if g.classe_id:
                groupes_dict[(g.classe_id, _norm(g.nom))] = g.id

        for sess in sessions:
            classe_id = classes_dict.get(_norm(sess["classe"]))
            if not classe_id:
                raise ValueError(f"Classe introuvable pour session: {sess['classe']}")

            groupe_nom = (sess.get("groupe") or sess["classe"]).strip()
            gkey = (classe_id, _norm(groupe_nom))
            if gkey not in groupes_dict:
                g = Groupe(nom=groupe_nom, classe_id=classe_id)
                db.add(g)
                db.flush()
                groupes_dict[gkey] = g.id
        db.commit()
        print("✅ Groupes OK (aucun groupe_id NULL)\n")

        # 6) Professors
        profs_dict: Dict[str, int] = {_norm(p.nom_complet): p.id for p in db.query(Professeur).all()}
        unique_profs = sorted({_norm(s["professeur"]): s["professeur"] for s in sessions if s.get("professeur")}.items())
        for _, prof_name in unique_profs:
            key = _norm(prof_name)
            if key and key not in profs_dict:
                prof = Professeur(nom_complet=prof_name.strip())
                db.add(prof)
                db.flush()
                profs_dict[key] = prof.id
        db.commit()
        print(f"\n✅ {len(unique_profs)} professeurs\n")

        # 7) Rooms
        salles_dict: Dict[str, int] = {_norm(s.nom): s.id for s in db.query(Salle).all()}
        unique_salles = sorted({_norm(s["salle"]): s["salle"] for s in sessions if s.get("salle")}.items())
        for _, salle_name in unique_salles:
            key = _norm(salle_name)
            if key and key not in salles_dict:
                salle = Salle(nom=salle_name.strip(), type="Salle")
                db.add(salle)
                db.flush()
                salles_dict[key] = salle.id
        db.commit()
        print(f"\n✅ {len(unique_salles)} salles\n")

        # 8) Subjects
        matieres_dict: Dict[str, int] = {_norm(m.nom): m.id for m in db.query(Matiere).all()}
        unique_matieres = sorted({_norm(s["matiere"]): s["matiere"] for s in sessions if s.get("matiere")}.items())
        for _, mat_name in unique_matieres:
            key = _norm(mat_name)
            if key and key not in matieres_dict:
                mat = Matiere(nom=mat_name.strip())
                db.add(mat)
                db.flush()
                matieres_dict[key] = mat.id
        db.commit()
        print(f"✅ {len(unique_matieres)} matières\n")

        # 9) Create timetable version PER CLASS
        versions_by_classe_id: Dict[int, int] = {}
        for _, classe_id in classes_dict.items():
            v = EmploiVersion(version_date=date.today(), actif=True, classe_id=classe_id)
            db.add(v)
            db.flush()
            versions_by_classe_id[classe_id] = v.id
        db.commit()
        print(f"✅ Versions créées: {len(versions_by_classe_id)}\n")

        # 10) Import sessions
        print("📋 Importation des séances...")
        seances_count = 0

        for sess in sessions:
            try:
                classe_id = classes_dict.get(_norm(sess["classe"]))
                if not classe_id:
                    raise ValueError(f"Classe introuvable: {sess['classe']}")

                matiere_name = (sess.get("matiere") or "").strip()
                if not matiere_name:
                    continue

                groupe_nom = (sess.get("groupe") or sess["classe"]).strip()
                groupe_key = (classe_id, _norm(groupe_nom))
                groupe_id = groupes_dict.get(groupe_key)
                if not groupe_id:
                    g = Groupe(nom=groupe_nom, classe_id=classe_id)
                    db.add(g)
                    db.flush()
                    groupe_id = g.id
                    groupes_dict[groupe_key] = groupe_id

                matiere_id = matieres_dict.get(_norm(matiere_name))
                prof_id = profs_dict.get(_norm(sess.get("professeur", ""))) if sess.get("professeur") else None
                salle_id = salles_dict.get(_norm(sess.get("salle", ""))) if sess.get("salle") else None
                periode_id = resolve_periode_id(sess)
                type_seance = resolve_type_seance(sess)
                version_id = versions_by_classe_id.get(classe_id)

                seance = Seance(
                    version_id=version_id,
                    classe_id=classe_id,
                    matiere_id=matiere_id,
                    professeur_id=prof_id,
                    salle_id=salle_id,
                    groupe_id=groupe_id,
                    periode_id=periode_id,
                    jour=sess["jour"],
                    heure_debut=sess["heure_debut"],
                    heure_fin=sess["heure_fin"],
                    type_seance=type_seance,
                )
                db.add(seance)
                seances_count += 1

                if seances_count % 300 == 0:
                    db.commit()
                    print(f"  ... {seances_count} séances")

            except Exception as e:
                print(f"  ❌ Erreur: {e}")
                continue

        db.commit()
        print(f"\n✅ {seances_count} séances importées!\n")

    except Exception as e:
        print(f"❌ Erreur générale: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def import_all_excels(excel_dir: str = "public/excel_files"):
    excel_dir = os.path.abspath(excel_dir)
    if not os.path.isdir(excel_dir):
        raise FileNotFoundError(excel_dir)

    files = [os.path.join(excel_dir, f) for f in os.listdir(excel_dir) if f.lower().endswith(".xlsx")]

    cleared_semesters = set()
    for path in sorted(files):
        base = os.path.basename(path)

        if "etudi" not in base.lower():
            print(f"⚠️  Type de fichier non supporté pour import seances (ignore): {base}")
            continue

        semester_id = None
        if re.search(r"(?:^|[^A-Za-z0-9])S1(?:$|[^A-Za-z0-9])", base, flags=re.IGNORECASE):
            semester_id = 1
        elif re.search(r"(?:^|[^A-Za-z0-9])S2(?:$|[^A-Za-z0-9])", base, flags=re.IGNORECASE):
            semester_id = 2
        else:
            tokens = [t for t in re.split(r"[^A-Za-z0-9]+", base) if t]
            if any(t.upper() == "S1" for t in tokens):
                semester_id = 1
            elif any(t.upper() == "S2" for t in tokens):
                semester_id = 2

        if not semester_id:
            print(f"⚠️  Semestre non détecté pour: {base} (ignore)")
            continue

        clear_existing = semester_id not in cleared_semesters
        import_emplois_du_temps(path, semester_id=semester_id, clear_existing=clear_existing)
        cleared_semesters.add(semester_id)


if __name__ == "__main__":
    import_all_excels("public/excel_files")
    print("\n\n✨ IMPORTATION TERMINÉE!")