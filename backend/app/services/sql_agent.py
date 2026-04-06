# backend/app/services/sql_agent.py
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text

from .groq_service import groq_service
from .university_info_service import university_info_service


def get_current_academic_context(db: Session) -> dict:
    today = date.today()

    try:
        result = db.execute(
            text(
                """
                SELECT 
                    au.id as annee_id,
                    au.libelle as annee_libelle,
                    s.id as semestre_id,
                    s.nom as semestre_nom,
                    p.id as periode_id,
                    p.nom as periode_nom,
                    p.date_debut,
                    p.date_fin
                FROM periodes p
                JOIN semestres s ON p.semestre_id = s.id
                JOIN annees_universitaires au ON s.annee_id = au.id
                WHERE :today BETWEEN p.date_debut AND p.date_fin
                LIMIT 1
                """
            ),
            {"today": today},
        )

        row = result.first()
        if row:
            return {
                "annee_id": row[0],
                "annee": row[1],
                "semestre_id": row[2],
                "semestre": row[3],
                "periode_id": row[4],
                "periode": row[5],
                "date_debut_periode": row[6],
                "date_fin_periode": row[7],
                "date_actuelle": str(today),
                "jour_actuel": None,
            }
    except Exception as e:
        print(f"Erreur lors de la récupération du contexte: {e}")

    return {"date_actuelle": str(today), "message": "Aucune période active trouvée"}


SCHEMA_INFO = """
Tables disponibles:
- annees_universitaires (id, libelle, date_debut, date_fin)
- semestres (id, nom, annee_id)
- periodes (id, nom, semestre_id, date_debut, date_fin)
- departements (id, nom)
- classes (id, nom, departement_id, semestre_id)
- professeurs (id, nom_complet, grade, specialite)
- emplois_enseignants_seances (id, semestre_id, professeur_nom_complet, classe_nom, matiere_nom, salle_nom, jour, heure_debut, heure_fin, periode_nom, type_seance, source_file)
- matieres (id, nom, code)
- salles (id, nom, type, capacite)  -- alias sa, sa.nom for room name
- groupes (id, nom, classe_id)
- emplois_versions (id, classe_id, version_date, actif)
- seances (id, version_id, classe_id, matiere_id, professeur_id, salle_id, groupe_id, periode_id, jour, heure_debut, heure_fin, type_seance)
- vacances_jours_feries (id, nom, date_debut, date_fin, type, annee_id)

IMPORTANT:
- For any timetable query on seances, you MUST filter by the ACTIVE version:
  JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id
"""


DAY_MAP_ISO = {
    1: "Lundi",
    2: "Mardi",
    3: "Mercredi",
    4: "Jeudi",
    5: "Vendredi",
    6: "Samedi",
    7: "Dimanche",
}

DAY_NAME_MAP = {day.lower(): day for day in DAY_MAP_ISO.values()}


class SQLAgent:
    def __init__(self, db: Session):
        self.db = db
        self._exec_and_format = self._exec_and_format_v2

    # ---------------------------------------------------------------------
    #  Keep only last user message if history injected
    # ---------------------------------------------------------------------
    def _keep_last_user_message(self, raw: str) -> str:
        if not raw:
            return raw
        users = re.findall(r"(?:^|\n)\s*user\s*:\s*(.+)", raw, flags=re.IGNORECASE)
        if users:
            return users[-1].strip()
        return raw.strip()

    # ---------------------------------------------------------------------
    # Utils
    # ---------------------------------------------------------------------
    def _normalize_text(self, text_value: str) -> str:
        if not text_value:
            return ""
        repaired = (text_value or "").replace("\xa0", " ").replace("’", "'").replace("`", "'")
        if any(ch in repaired for ch in ("Ã", "Â", "â", "€", "™", "œ", "�")):
            for source_encoding in ("latin1", "cp1252"):
                try:
                    candidate = repaired.encode(source_encoding).decode("utf-8")
                except Exception:
                    continue
                if candidate and candidate != repaired:
                    repaired = candidate
                    break
        normalized = unicodedata.normalize("NFKD", repaired)
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = normalized.replace("'", " ")
        normalized = re.sub(r"[^a-zA-Z0-9\s/-]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        normalized = normalized.lower()
        typo_fixes = {
            "maintement": "maintenant",
            "maintenent": "maintenant",
            "disponnible": "disponible",
            "feriee": "ferie",
            "feries": "ferie",
            "lemploi": "emploi",
            "l emploi": "emploi",
        }
        for source, target in typo_fixes.items():
            normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized)
        return normalized

    def _norm(self, s: str) -> str:
        return re.sub(r"\s+", "", self._normalize_text(s))

    def _context_date(self, context: dict) -> date:
        da = context.get("date_actuelle")
        if da:
            try:
                return datetime.strptime(str(da), "%Y-%m-%d").date()
            except Exception:
                pass
        return date.today()

    def _is_day_token(self, token: str) -> bool:
        t = self._normalize_text(token).strip()
        return t in {
            "lundi",
            "mardi",
            "mercredi",
            "jeudi",
            "vendredi",
            "samedi",
            "dimanche",
            "aujourdhui",
            "aujourd'hui",
            "demain",
            "hier",
        }

    def _question_mentions_day(self, question: str) -> bool:
        q = self._normalize_text(question)
        if any(
            re.search(rf"\b{d}\b", q)
            for d in ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        ):
            return True
        if "aujourd" in q or "demain" in q or "hier" in q:
            return True
        return False

    def _extract_requested_day(self, question: str, context: dict) -> Optional[str]:
        q = self._normalize_text(question)

        for day_key, canonical_day in DAY_NAME_MAP.items():
            if re.search(rf"\b{re.escape(day_key)}\b", q):
                return canonical_day

        base = self._context_date(context)
        if "aujourd" in q:
            return context.get("jour_actuel") or DAY_MAP_ISO[base.isoweekday()]
        if "demain" in q:
            return DAY_MAP_ISO[(base + timedelta(days=1)).isoweekday()]
        if "hier" in q:
            return DAY_MAP_ISO[(base - timedelta(days=1)).isoweekday()]
        return None

    # ✅ better intent detection (handles typos like "lempoi")
    def _is_schedule_intent(self, question: str) -> bool:
        q = self._normalize_text(question)
        markers = [
            "emploi",
            "edt",
            "planning",
            "horaire",
            "emploi du temps",
            "emploi de temps",
            "emplois du temps",
            "emplois de temps",
        ]
        if any(m in q for m in markers):
            return True
        if "emp" in q and ("temps" in q or "planning" in q or "horaire" in q):
            return True
        return False

    def _is_full_schedule_request(self, question: str) -> bool:
        q = self._normalize_text(question)
        return any(
            marker in q
            for marker in [
                "p1 et p2",
                "p1 and p2",
                "emploi du temps complet",
                "tous les cours",
                "toute la periode",
                "toute la période",
                "complet",
            ]
        )

    def _is_all_classes_request(self, question: str) -> bool:
        q = self._normalize_text(question)
        return any(
            marker in q
            for marker in [
                "toutes les classes disponibles",
                "tous les classes disponibles",
                "donner toutes les classes",
                "liste des classes",
                "quelles classes existent",
                "classes disponibles",
            ]
        ) and "ma classe" not in q

    def _all_classes_sql(self) -> Tuple[str, Dict[str, Any]]:
        sql = """
        SELECT DISTINCT c.nom AS classe
        FROM classes c
        ORDER BY classe;
        """
        return sql, {}

    def _is_university_general_question(self, question: str) -> bool:
        q = self._normalize_text(question)
        if not q:
            return False
        if any(marker in q for marker in ["plan d etude", "plans d etude", "plan des etudes", "plans des etudes", "programme des etudes"]):
            return True
        if self._is_calendar_question(question):
            return False
        if self._is_schedule_intent(question):
            return False
        if self._is_all_classes_request(question):
            return False
        if self._is_room_current_teacher_question(question):
            return False
        if self._extract_class_candidate(question):
            return False
        if self._extract_prof_candidate(question):
            return False

        keywords = [
            "enetcom",
            "universite",
            "ecole",
            "actualite",
            "actualites",
            "nouveaute",
            "nouveautes",
            "annonce",
            "annonces",
            "news",
            "departement",
            "formation",
            "master",
            "mastere",
            "licence",
            "doctorat",
            "directeur",
            "adresse",
            "contact",
            "telephone",
            "mail",
            "email",
            "bourse",
            "recherche",
            "laboratoire",
            "stage",
            "pfe",
            "bibliotheque",
            "club",
            "sport",
            "preinscription",
            "inscription",
            "international",
            "partenariat",
            "presentation",
            "organigramme",
            "4c",
        ]
        starters = [
            "c est quoi",
            "qu est ce que",
            "qui est",
            "quelle est l adresse",
            "ou se trouve",
            "comment contacter",
            "quelles sont les formations",
        ]
        return any(keyword in q for keyword in keywords) or any(starter in q for starter in starters)

    # ---------------------------------------------------------------------
    # Class extraction
    # ---------------------------------------------------------------------
    def _extract_class_candidate(self, question: str) -> Optional[str]:
        q = (question or "").strip()

        m = re.search(
            r"\b(\d)\s*(ING|TIC|LTIC|MP|MR)\b(?:\s+([A-Z0-9\-]+))?(?:\s+([A-Z0-9\-]+))?(?:\s+(\d))?\b",
            q,
            flags=re.IGNORECASE,
        )
        if m:
            parts = [p for p in m.groups() if p]
            parts = [p for p in parts if p and not self._is_day_token(p)]
            if not parts:
                return None
            cls = " ".join([parts[0]] + [p.upper() for p in parts[1:]])
            cls = re.sub(r"\s+", " ", cls).strip()
            if len(cls.split()) < 2:
                return None
            return cls

        m2 = re.search(r"\b(\d)\s*([A-Za-z\-]{2,10})\s*(\d)\b", q)
        if m2:
            a, mid, b = m2.group(1), m2.group(2), m2.group(3)
            mid_u = mid.upper()
            if mid_u in {"GII", "GEC", "GT", "INFO", "TELECOM"}:
                return f"{a} ING {mid_u} {b}"
            return f"{a} {mid_u} {b}"

        return None

    def _normalize_class_aliases(self, class_name: str, context: dict) -> str:
        if not class_name:
            return class_name
        sem = (context.get("semestre") or "").upper().strip()
        if sem == "S2":
            class_name = re.sub(r"\bLTIC\b", "TIC", class_name, flags=re.IGNORECASE)
        return class_name.strip()

    def _class_exists_in_db(self, class_name: str, context: dict) -> bool:
        if not class_name or not context.get("semestre_id"):
            return False
        sem_id = int(context["semestre_id"])
        key = self._norm(class_name)
        row = self.db.execute(
            text(
                """
                SELECT 1
                FROM classes
                WHERE semestre_id = :sem_id
                  AND REPLACE(LOWER(nom), ' ', '') LIKE '%' || :key || '%'
                LIMIT 1
                """
            ),
            {"sem_id": sem_id, "key": key},
        ).first()
        return bool(row)

    def _professor_match_condition(self, prof_name: str, field_sql: str = "p.nom_complet") -> Optional[str]:
        if not prof_name:
            return None

        tokens = [
            re.sub(r"[^a-z0-9]", "", token.lower())
            for token in re.split(r"[\s\-]+", prof_name)
            if token.strip()
        ]
        tokens = [token for token in tokens if token]
        if not tokens:
            return None

        expr = "REPLACE(REPLACE(REPLACE(LOWER(p.nom_complet), ' ', ''), '.', ''), '-', '')"
        full_key = "".join(tokens)
        conditions = [f"{expr} LIKE '%{full_key}%'"]

        surname = tokens[-1]
        if len(tokens) >= 2 and len(surname) >= 3:
            first_initial = tokens[0][0]
            conditions.append(f"({expr} LIKE '%{surname}%' AND {expr} LIKE '%{first_initial}%')")
        elif len(surname) >= 3:
            conditions.append(f"{expr} LIKE '%{surname}%'")

        if len(tokens) >= 2:
            ordered_tokens = " AND ".join(f"{expr} LIKE '%{token}%'" for token in tokens if len(token) >= 3)
            if ordered_tokens:
                conditions.append(f"({ordered_tokens})")

        return "(" + " OR ".join(dict.fromkeys(conditions)) + ")"

    def _prof_exists_in_db(self, prof_name: str) -> bool:
        condition = self._professor_match_condition(prof_name)
        if not condition:
            return False

        row = self.db.execute(
            text(f"SELECT 1 FROM professeurs p WHERE {condition} LIMIT 1")
        ).first()
        return bool(row)

    # ---------------------------------------------------------------------
    # Prof extraction + SQL enforcement
    # ---------------------------------------------------------------------
    def _extract_prof_candidate(self, question: str) -> Optional[str]:
        q = (question or "").strip()

        m = re.search(
            r"\b(mr|mme|m\.|monsieur|madame)\s+([A-Za-zÀ-ÿ'\-]+\s+[A-Za-zÀ-ÿ'\-]+(?:\s+[A-Za-zÀ-ÿ'\-]+)?)\b",
            q,
            re.IGNORECASE,
        )
        if m:
            return m.group(2).strip()

        m2 = re.search(r"\bde\s+([A-Za-zÀ-ÿ'\-]+\s+[A-Za-zÀ-ÿ'\-]+)\b", q, re.IGNORECASE)
        if m2:
            candidate = m2.group(1).strip()
            candidate_lower = candidate.lower()
            candidate_tokens = [token for token in re.split(r"[\s\-]+", candidate_lower) if token]
            invalid_candidates = {
                "ma classe",
                "mon classe",
                "ma salle",
                "mon salle",
                "mon groupe",
                "ma groupe",
                "mon emploi",
                "mon edt",
                "mon planning",
            }
            if candidate_lower in invalid_candidates:
                return None
            invalid_tokens = {
                "lundi",
                "mardi",
                "mercredi",
                "jeudi",
                "vendredi",
                "samedi",
                "dimanche",
                "pour",
                "classe",
                "cours",
                "salle",
                "aujourd'hui",
                "aujourdhui",
                "demain",
                "hier",
            }
            if any(token in invalid_tokens for token in candidate_tokens):
                return None
            return candidate

        return None

    def _enforce_professor_matching(self, question: str, sql_query: str) -> str:
        prof = self._extract_prof_candidate(question)
        if not prof:
            return sql_query

        condition = self._professor_match_condition(prof)
        if not condition:
            return sql_query

        fixed = sql_query

        fixed = re.sub(
            r"p\.nom_complet\s*=\s*'[^']*'",
            lambda _: condition,
            fixed,
            flags=re.IGNORECASE,
        )
        return fixed

    # ---------------------------------------------------------------------
    # Periode enforcement
    # ---------------------------------------------------------------------
    def _user_requested_specific_periode(self, question: str) -> bool:
        q = (question or "").lower()
        return bool(re.search(r"\bp\s*1\b", q) or re.search(r"\bp\s*2\b", q))

    def _question_is_day_specific(self, question: str) -> bool:
        # Only force current period when question is day/date specific
        q = (question or "").lower()
        if self._question_mentions_day(question):
            return True
        # explicit date patterns
        if re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", q):
            return True
        if re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", q):
            return True
        return False

    def _enforce_current_periode_default(self, question: str, sql_query: str, context: dict) -> str:
        """
        ✅ Smarter default:
        - If user didn't ask P1/P2 explicitly,
        - AND question is day/date specific (today/tomorrow/day name),
        then force current periode_id.
        Otherwise (weekly/general timetable), do NOT force P2.
        """
        if self._user_requested_specific_periode(question):
            return sql_query
        if not self._question_is_day_specific(question):
            return sql_query

        current_pid = context.get("periode_id")
        if not current_pid:
            return sql_query

        fixed = sql_query

        if re.search(r"\bs\.periode_id\s*=", fixed, flags=re.IGNORECASE):
            fixed = re.sub(
                r"\bs\.periode_id\s*=\s*\d+",
                f"s.periode_id = {int(current_pid)}",
                fixed,
                flags=re.IGNORECASE,
            )
            return fixed

        m = re.search(r"\bwhere\b", fixed, flags=re.IGNORECASE)
        if m:
            pos = m.end()
            fixed = fixed[:pos] + f" s.periode_id = {int(current_pid)} AND " + fixed[pos:]
        else:
            fixed = fixed.rstrip().rstrip(";") + f" WHERE s.periode_id = {int(current_pid)};"

        return fixed

    def _enforce_periode_marker(self, question: str, sql_query: str, context: dict) -> str:
        q = (question or "").lower()
        want_p1 = bool(re.search(r"\bp\s*1\b", q))
        want_p2 = bool(re.search(r"\bp\s*2\b", q))

        if not (want_p1 or want_p2):
            return sql_query

        sem_id = context.get("semestre_id")
        if not sem_id:
            return sql_query

        if want_p1 and want_p2:
            return sql_query

        marker = "P1" if want_p1 else "P2"

        row = self.db.execute(
            text(
                """
                SELECT id
                FROM periodes
                WHERE semestre_id = :sid AND UPPER(nom) = :p
                LIMIT 1
                """
            ),
            {"sid": int(sem_id), "p": marker},
        ).first()
        if not row:
            return sql_query

        target_id = int(row[0])
        fixed = re.sub(
            r"\bs\.periode_id\s*=\s*\d+",
            f"s.periode_id = {target_id}",
            sql_query,
            flags=re.IGNORECASE,
        )

        if not re.search(r"\bs\.periode_id\b", fixed, flags=re.IGNORECASE):
            m = re.search(r"\bwhere\b", fixed, flags=re.IGNORECASE)
            if m:
                pos = m.end()
                fixed = fixed[:pos] + f" s.periode_id = {target_id} AND " + fixed[pos:]
            else:
                fixed = fixed.rstrip().rstrip(";") + f" WHERE s.periode_id = {target_id};"
        return fixed

    # ---------------------------------------------------------------------
    # Calendar routing
    # ---------------------------------------------------------------------
    def _is_calendar_question(self, question: str) -> bool:
        q = (question or "").lower()
        if any(k in q for k in ["cours", "séance", "seance", "emploi", "edt", "planning", "horaire"]):
            return False

        calendar_markers = [
            "vacance",
            "vacances",
            "jours féri",
            "jour féri",
            "jours ferie",
            "jour ferie",
            "fête",
            "fete",
            "aid",
            "ramadan",
            "examen",
            "examens",
            "ds",
            "rattrap",
            "ratt",
            "révision",
            "revision",
            "calendrier",
        ]
        return any(k in q for k in calendar_markers)

    def _parse_explicit_date(self, question: str) -> Optional[date]:
        m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", question)
        if m:
            try:
                return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                return None

        m = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", question)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                return None

        q = question.lower()
        if "aujourd" in q:
            return date.today()
        if "demain" in q:
            return date.today() + timedelta(days=1)
        if "hier" in q:
            return date.today() - timedelta(days=1)
        return None

    def _calendar_type_filter(self, question: str) -> Optional[str]:
        q = (question or "").lower()
        if "vacance" in q:
            return "vacances"
        if "jours féri" in q or "jour féri" in q or "jours ferie" in q or "jour ferie" in q or "fête" in q or "fete" in q or "aid" in q:
            return "jour_ferie"
        if "révision" in q or "revision" in q:
            return "revision"
        if "examen" in q or "ds" in q or "ratt" in q:
            return "examen"
        if "periode" in q or "période" in q:
            return "periode"
        return None

    def _calendar_scope(self, question: str) -> str:
        q = (question or "").lower()
        if any(token in q for token in ["cette année", "cette annee", "de cette année", "de cette annee", "toute l'année", "toute l'annee"]):
            return "year"
        return "day"

    def _calendar_sql(self, question: str, context: dict) -> Tuple[str, Dict[str, Any]]:
        d = self._parse_explicit_date(question) or date.today()
        t = self._calendar_type_filter(question)
        scope = self._calendar_scope(question)

        sql = """
        SELECT nom, date_debut, date_fin, type
        FROM vacances_jours_feries
        WHERE annee_id = :annee_id
        """
        params: Dict[str, Any] = {"d": d, "annee_id": context.get("annee_id", 1)}

        if scope == "day":
            sql += " AND :d BETWEEN date_debut AND date_fin\n"
        elif scope == "upcoming":
            sql += " AND date_fin >= :d\n"

        if t:
            sql += " AND LOWER(type) = LOWER(:t)\n"
            params["t"] = t

        sql += " ORDER BY date_debut, nom"
        if scope == "upcoming":
            sql += "\n LIMIT 10"
        sql += ";"
        return sql, params

    # ---------------------------------------------------------------------
    # SQL repairs / validation
    # ---------------------------------------------------------------------
    def _repair_sql(self, sql_query: str) -> str:
        if not sql_query:
            return sql_query

        repairs = {
            r"\bs\.matie_re_id\b": "s.matiere_id",
            r"\bs\.matier(e)?_id\b": "s.matiere_id",
            r"\bs\.profeseur_id\b": "s.professeur_id",
            r"\bs\.professeurid\b": "s.professeur_id",
            r"\bs\.salleid\b": "s.salle_id",
            r"\bs\.classeid\b": "s.classe_id",
        }

        fixed = sql_query
        for pattern, replacement in repairs.items():
            fixed = re.sub(pattern, replacement, fixed, flags=re.IGNORECASE)

        fixed = re.sub(r"\bp\.nom\b", "p.nom_complet", fixed, flags=re.IGNORECASE)
        fixed = re.sub(r"\bp\.nomcomplet\b", "p.nom_complet", fixed, flags=re.IGNORECASE)
        fixed = self._normalize_timetable_select_aliases(fixed)
        return fixed

    def _normalize_timetable_select_aliases(self, sql_query: str) -> str:
        match = re.search(r"^\s*select\s+(.*?)\s+from\s", sql_query, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return sql_query

        select_clause = match.group(1)
        replacements = [
            (r"\bc\.nom\b(?!\s+AS\b)", "c.nom AS classe"),
            (r"\bm\.nom\b(?!\s+AS\b)", "m.nom AS matiere"),
            (r"\bp\.nom_complet\b(?!\s+AS\b)", "p.nom_complet AS professeur"),
            (r"\bsa\.nom\b(?!\s+AS\b)", "sa.nom AS salle"),
        ]

        updated_clause = select_clause
        for pattern, replacement in replacements:
            updated_clause = re.sub(pattern, replacement, updated_clause, flags=re.IGNORECASE)

        return sql_query[:match.start(1)] + updated_clause + sql_query[match.end(1):]

    def _format_empty_calendar_response(self, question: str, context: dict) -> Optional[str]:
        if not self._is_calendar_question(question):
            return None

        scope = self._calendar_scope(question)
        type_filter = self._calendar_type_filter(question)
        date_label = context.get("date_actuelle", "aujourd'hui")

        if scope == "year":
            labels = {
                "vacances": "vacances",
                "jour_ferie": "jours fériés",
                "examen": "examens",
                "periode": "périodes",
            }
            target = labels.get(type_filter, "événements")
            return f"Aucun {target} trouvé pour l'année universitaire en cours."

        if type_filter == "vacances":
            return f"Non, il n'y a pas de vacances le {date_label}."
        if type_filter == "jour_ferie":
            return f"Non, il n'y a pas de jour férié le {date_label}."
        if type_filter == "examen":
            return f"Non, aucun examen n'est prévu le {date_label}."
        return f"Aucun événement calendrier trouvé le {date_label}."

    def _validate_select_only(self, sql_query: str) -> bool:
        if not sql_query:
            return False
        q = sql_query.replace("```sql", "").replace("```", "").strip()
        return bool(re.match(r"^\s*select\b", q, re.IGNORECASE))

    # ---------------------------------------------------------------------
    # Missing info
    # ---------------------------------------------------------------------
    def _needs_class(self, q_lower: str) -> bool:
        return any(
            [
                "emploi" in q_lower,
                "edt" in q_lower,
                "planning" in q_lower,
                "horaire" in q_lower,
                "cours" in q_lower,
                "séance" in q_lower,
                "seance" in q_lower,
                "j'ai cours" in q_lower,
                "demain" in q_lower,
                "aujourd" in q_lower,
                any(day in q_lower for day in ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]),
            ]
        )

    def _check_missing_info(self, question: str, context: dict) -> Optional[str]:
        if self._is_calendar_question(question):
            return None

        q_lower = (question or "").lower()

        if self._extract_prof_candidate(question):
            prof = self._extract_prof_candidate(question)
            if prof and not self._prof_exists_in_db(prof):
                return f"Je ne trouve pas le professeur '{prof}' dans la base de données."
            return None

        if not self._needs_class(q_lower):
            return None

        cls = self._extract_class_candidate(question)
        if not cls:
            return "Quelle est votre classe ? (ex: 2 ING GII 3, 1 TIC 2, 2 TIC-T, etc.)"

        cls = self._normalize_class_aliases(cls, context)
        if context.get("semestre_id") and not self._class_exists_in_db(cls, context):
            return (
                f"Je ne trouve pas la classe '{cls}' dans le semestre actuel ({context.get('semestre','?')}). "
                f"Vérifiez le nom (ex: '1 TIC 2') ou précisez le semestre (S1/S2)."
            )

        return None

    # ---------------------------------------------------------------------
    # ✅ Active version enforcement (critical)
    # ---------------------------------------------------------------------
    def _ensure_active_version_filter(self, sql_query: str) -> str:
        """
        Ensure timetable queries only read from ACTIVE emplois_versions.
        We enforce:
          JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id
        If user/Groq already joined versions, we only ensure v.actif = true.
        """
        if not sql_query:
            return sql_query

        q = sql_query
        lower = q.lower()

        # Only apply to queries using seances alias s
        if " from seances s" not in lower and " join seances s" not in lower:
            return q

        # If emplois_versions already present, ensure actif filter exists
        if "emplois_versions" in lower:
            if re.search(r"\bv\.actif\b", q, flags=re.IGNORECASE) or re.search(r"\bactif\b", q, flags=re.IGNORECASE):
                return q
            # add "AND v.actif = true" after ON clause if possible
            q = re.sub(
                r"(join\s+emplois_versions\s+v\s+on\s+[^;]+?)(\s+join|\s+where|\s+group|\s+order|;)",
                r"\1 AND v.actif = true\2",
                q,
                flags=re.IGNORECASE | re.DOTALL,
            )
            # if that didn't work, add to WHERE
            if not re.search(r"\bv\.actif\b", q, flags=re.IGNORECASE):
                if re.search(r"\bwhere\b", q, flags=re.IGNORECASE):
                    q = re.sub(r"\bwhere\b", "WHERE v.actif = true AND ", q, flags=re.IGNORECASE)
                else:
                    q = q.rstrip().rstrip(";") + " WHERE v.actif = true;"
            return q

        # Otherwise inject JOIN emplois_versions v after "FROM seances s"
        q = re.sub(
            r"\bfrom\s+seances\s+s\b",
            "FROM seances s JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id",
            q,
            flags=re.IGNORECASE,
        )
        return q

    # ---------------------------------------------------------------------
    # Safer day filter stripping
    # ---------------------------------------------------------------------
    def _strip_day_filter(self, sql_query: str) -> str:
        """
        Safer stripping: remove only direct predicates on s.jour in the main WHERE.
        """
        if not sql_query:
            return sql_query

        fixed = sql_query

        # Remove patterns "AND s.jour = 'X'" / "s.jour='X' AND"
        fixed = re.sub(r"\s+AND\s+s\.jour\s*=\s*'[^']*'\s*", " ", fixed, flags=re.IGNORECASE)
        fixed = re.sub(r"\bwhere\s+s\.jour\s*=\s*'[^']*'\s+and\s+", "WHERE ", fixed, flags=re.IGNORECASE)
        fixed = re.sub(r"\s+s\.jour\s*=\s*'[^']*'\s+and\s+", " ", fixed, flags=re.IGNORECASE)
        fixed = re.sub(
            r"\s+AND\s+LOWER\s*\(\s*s\.jour\s*\)\s*=\s*LOWER\s*\(\s*'[^']*'\s*\)\s*",
            " ",
            fixed,
            flags=re.IGNORECASE,
        )
        fixed = re.sub(
            r"\bwhere\s+LOWER\s*\(\s*s\.jour\s*\)\s*=\s*LOWER\s*\(\s*'[^']*'\s*\)\s+and\s+",
            "WHERE ",
            fixed,
            flags=re.IGNORECASE,
        )
        fixed = re.sub(
            r"\s+LOWER\s*\(\s*s\.jour\s*\)\s*=\s*LOWER\s*\(\s*'[^']*'\s*\)\s+and\s+",
            " ",
            fixed,
            flags=re.IGNORECASE,
        )
        fixed = re.sub(
            r"\s+AND\s+LOWER\s*\(\s*s\.jour\s*\)\s*=\s*'[^']*'\s*",
            " ",
            fixed,
            flags=re.IGNORECASE,
        )
        fixed = re.sub(
            r"\bwhere\s+LOWER\s*\(\s*s\.jour\s*\)\s*=\s*'[^']*'\s+and\s+",
            "WHERE ",
            fixed,
            flags=re.IGNORECASE,
        )
        fixed = re.sub(
            r"\s+LOWER\s*\(\s*s\.jour\s*\)\s*=\s*'[^']*'\s+and\s+",
            " ",
            fixed,
            flags=re.IGNORECASE,
        )
        fixed = re.sub(r"\bwhere\s*(group by|order by|limit|offset)\b", r"\1", fixed, flags=re.IGNORECASE)

        fixed = re.sub(r"\s+", " ", fixed).strip()
        if not fixed.endswith(";"):
            fixed += ";"
        return fixed

    def _inject_where_condition(self, sql_query: str, condition: str) -> str:
        fixed = sql_query.strip().rstrip(";")
        if re.search(r"\bwhere\b", fixed, flags=re.IGNORECASE):
            return re.sub(r"\bwhere\b", f"WHERE {condition} AND ", fixed, count=1, flags=re.IGNORECASE) + ";"

        clause = re.search(r"\b(group\s+by|order\s+by|limit|offset)\b", fixed, flags=re.IGNORECASE)
        if clause:
            return f"{fixed[:clause.start()].rstrip()} WHERE {condition} {fixed[clause.start():].lstrip()};"
        return f"{fixed} WHERE {condition};"

    def _enforce_requested_day_filter(self, question: str, sql_query: str, context: dict) -> str:
        requested_day = self._extract_requested_day(question, context)
        if not requested_day or self._is_full_schedule_request(question):
            return sql_query

        condition = f"LOWER(s.jour) = LOWER('{requested_day}')"
        fixed = sql_query

        fixed = re.sub(
            r"LOWER\s*\(\s*s\.jour\s*\)\s*=\s*LOWER\s*\(\s*'[^']*'\s*\)",
            condition,
            fixed,
            flags=re.IGNORECASE,
        )
        fixed = re.sub(
            r"\bs\.jour\s*=\s*'[^']*'",
            condition,
            fixed,
            flags=re.IGNORECASE,
        )

        has_day_filter = bool(
            re.search(r"\bs\.jour\s*=\s*'[^']*'", fixed, flags=re.IGNORECASE)
            or re.search(
                r"LOWER\s*\(\s*s\.jour\s*\)\s*=\s*LOWER\s*\(\s*'[^']*'\s*\)",
                fixed,
                flags=re.IGNORECASE,
            )
        )
        if not has_day_filter:
            fixed = self._inject_where_condition(fixed, condition)

        return fixed

    # ---------------------------------------------------------------------
    # Overrides for normalized matching / deterministic routing
    # ---------------------------------------------------------------------
    def _professor_match_condition(self, prof_name: str, field_sql: str = "p.nom_complet") -> Optional[str]:
        if not prof_name:
            return None

        def collapse_repeated_letters(token: str) -> str:
            return re.sub(r"([a-z0-9])\1+", r"\1", token)

        tokens = [
            re.sub(r"[^a-z0-9]", "", self._normalize_text(token))
            for token in re.split(r"[\s\-]+", prof_name)
            if token.strip()
        ]
        tokens = [token for token in tokens if token]
        if not tokens:
            return None

        raw_expr = f"LOWER({field_sql})"
        expr = f"REPLACE(REPLACE(REPLACE({raw_expr}, ' ', ''), '.', ''), '-', '')"
        compact_expr = (
            "REGEXP_REPLACE("
            f"REPLACE(REPLACE(REPLACE({raw_expr}, ' ', ''), '.', ''), '-', ''), "
            "'([a-z0-9])\\1+', '\\1', 'g')"
        )

        full_key = "".join(tokens)
        compact_full_key = collapse_repeated_letters(full_key)
        conditions = [f"{expr} LIKE '%{full_key}%'"]
        if compact_full_key != full_key:
            conditions.append(f"{compact_expr} LIKE '%{compact_full_key}%'")

        for idx, token in enumerate(tokens):
            if len(token) < 3:
                continue
            variants = [token]
            compact_variant = collapse_repeated_letters(token)
            if compact_variant != token:
                variants.append(compact_variant)
            other_initials = [other[0] for j, other in enumerate(tokens) if j != idx and other]
            initials_conditions = " AND ".join(
                f"{raw_expr} ~ '(^|[^a-z0-9]){initial}([.\\s/-]|$)'"
                for initial in dict.fromkeys(other_initials)
            )

            for variant in dict.fromkeys(variants):
                if other_initials:
                    conditions.append(f"({expr} LIKE '%{variant}%' AND {initials_conditions})")
                    conditions.append(f"({compact_expr} LIKE '%{variant}%' AND {initials_conditions})")
                else:
                    conditions.append(f"{expr} LIKE '%{variant}%'")
                    conditions.append(f"{compact_expr} LIKE '%{variant}%'")

        if len(tokens) >= 2:
            ordered_tokens = " AND ".join(f"{expr} LIKE '%{token}%'" for token in tokens if len(token) >= 3)
            if ordered_tokens:
                conditions.append(f"({ordered_tokens})")

            compact_tokens = [collapse_repeated_letters(token) for token in tokens if len(token) >= 3]
            compact_ordered_tokens = " AND ".join(f"{compact_expr} LIKE '%{token}%'" for token in compact_tokens if token)
            if compact_ordered_tokens:
                conditions.append(f"({compact_ordered_tokens})")

        return "(" + " OR ".join(dict.fromkeys(conditions)) + ")"

    def _teacher_prof_exists_in_db(self, prof_name: str) -> bool:
        if not self.db:
            return False
        condition = self._professor_match_condition(prof_name, "te.professeur_nom_complet")
        if not condition:
            return False
        row = self.db.execute(
            text(f"SELECT 1 FROM emplois_enseignants_seances te WHERE {condition} LIMIT 1")
        ).first()
        return bool(row)

    def _prof_exists_in_db(self, prof_name: str) -> bool:
        if self._teacher_prof_exists_in_db(prof_name):
            return True
        condition = self._professor_match_condition(prof_name)
        if not condition or not self.db:
            return False

        row = self.db.execute(
            text(f"SELECT 1 FROM professeurs p WHERE {condition} LIMIT 1")
        ).first()
        return bool(row)

    def _teacher_prof_schedule_sql(self, question: str, context: dict) -> Tuple[str, Dict[str, Any]]:
        prof_name = self._extract_schedule_prof_candidate(question) or self._extract_prof_candidate(question) or ""
        prof_condition = self._professor_match_condition(prof_name, "te.professeur_nom_complet") or "1=0"
        requested_day = self._extract_requested_day(question, context)
        sql = f"""
        SELECT
            te.classe_nom AS classe,
            te.matiere_nom AS matiere,
            te.professeur_nom_complet AS professeur,
            te.salle_nom AS salle,
            te.jour,
            te.heure_debut,
            te.heure_fin
        FROM emplois_enseignants_seances te
        WHERE {prof_condition}
        """
        params: Dict[str, Any] = {}
        if context.get("semestre_id"):
            sql += " AND te.semestre_id = :semester_id\n"
            params["semester_id"] = int(context["semestre_id"])
        if context.get("periode"):
            sql += " AND UPPER(te.periode_nom) = :periode_nom\n"
            params["periode_nom"] = str(context["periode"]).upper()
        if requested_day:
            sql += " AND LOWER(te.jour) = LOWER(:target_day)\n"
            params["target_day"] = requested_day
        sql += " ORDER BY CASE LOWER(te.jour) WHEN 'lundi' THEN 1 WHEN 'mardi' THEN 2 WHEN 'mercredi' THEN 3 WHEN 'jeudi' THEN 4 WHEN 'vendredi' THEN 5 WHEN 'samedi' THEN 6 WHEN 'dimanche' THEN 7 ELSE 8 END, te.heure_debut, te.heure_fin;"
        return sql, params

    def _extract_prof_candidate(self, question: str) -> Optional[str]:
        q = (question or "").strip()
        if self._is_schedule_intent(q) and self._extract_class_candidate(q):
            return None

        match = re.search(
            r"\b(mr|mme|m\.|monsieur|madame)\s+([A-Za-zÀ-ÿ'\-]+\s+[A-Za-zÀ-ÿ'\-]+(?:\s+[A-Za-zÀ-ÿ'\-]+)?)\b",
            q,
            re.IGNORECASE,
        )
        if match:
            return match.group(2).strip()

        match = re.search(r"\bde\s+([A-Za-zÀ-ÿ'\-]+\s+[A-Za-zÀ-ÿ'\-]+)\b", q, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
        else:
            fallback_match = re.search(
                r"(?:dans quelle classe se trouve|ou se trouve|pour quelle classe|quelle classe pour)\s+([A-Za-zÀ-ÿ'\-]+(?:\s+[A-Za-zÀ-ÿ'\-]+){0,2})$",
                q,
                re.IGNORECASE,
            )
            if fallback_match:
                candidate = fallback_match.group(1).strip()
            else:
                bare_match = re.fullmatch(r"\s*([A-Za-zÀ-ÿ'\-]+(?:\s+[A-Za-zÀ-ÿ'\-]+){1,2})\s*", q)
                if not bare_match or self._extract_class_candidate(q):
                    return None
                candidate = bare_match.group(1).strip()

        normalized_candidate = self._normalize_text(candidate)
        candidate_tokens = [token for token in re.split(r"[\s\-]+", normalized_candidate) if token]

        invalid_candidates = {
            "ma classe",
            "mon classe",
            "ma salle",
            "mon salle",
            "mon groupe",
            "ma groupe",
            "mon emploi",
            "mon edt",
            "mon planning",
            "cette annee",
        }
        invalid_tokens = {
            "lundi",
            "mardi",
            "mercredi",
            "jeudi",
            "vendredi",
            "samedi",
            "dimanche",
            "pour",
            "classe",
            "cours",
            "salle",
            "aujourd'hui",
            "aujourdhui",
            "demain",
            "hier",
            "cette",
            "annee",
            "ferie",
            "feries",
            "vacance",
            "vacances",
            "jour",
            "jours",
            "directeur",
            "direction",
            "enetcom",
            "universite",
            "ecole",
            "adresse",
            "contact",
            "actualite",
            "actualites",
            "dernier",
            "derniers",
            "derniere",
            "dernieres",
            "nouveaute",
            "nouveautes",
            "annonce",
            "annonces",
            "news",
            "emploi",
            "temps",
            "planning",
            "horaire",
            "edt",
        }
        if normalized_candidate in invalid_candidates or any(token in invalid_tokens for token in candidate_tokens):
            return None

        return candidate

    def _extract_room_candidate(self, question: str) -> Optional[str]:
        match = re.search(r"\bsalle\s+([A-Za-z0-9][A-Za-z0-9\- ]*)\b", question or "", flags=re.IGNORECASE)
        if not match:
            return None
        return self._normalize_room_name(match.group(1))

    def _normalize_room_name(self, room_name: str) -> str:
        if not room_name:
            return ""
        room = re.sub(r"\s+", " ", room_name).strip().upper()
        room = re.sub(r"\bC\s+(\d{2})\b", r"C\1", room)
        room = re.sub(r"\bTEL-TCOM1\b", "TEL-TCOM 1", room)
        room = re.sub(r"\bEL-CI\s+AUTO\b", "EL-CI AUTO", room)
        room = re.sub(r"\s*/\s*", " / ", room)
        return room

    def _room_key(self, room_name: str) -> str:
        return re.sub(r"[\s/-]+", "", self._normalize_room_name(room_name).lower())

    def _room_match_expression(self, alias: str = "sa") -> str:
        return f"REPLACE(REPLACE(LOWER({alias}.nom), ' ', ''), '-', '')"

    def _room_exists_in_db(self, room_name: str) -> bool:
        if not self.db or not room_name:
            return False
        row = self.db.execute(
            text(
                f"""
                SELECT 1
                FROM salles sa
                WHERE {self._room_match_expression('sa')} = :room_key
                LIMIT 1
                """
            ),
            {"room_key": self._room_key(room_name)},
        ).first()
        return bool(row)

    def _question_mentions_now(self, question: str) -> bool:
        q = self._normalize_text(question)
        return any(token in q for token in ["maintenant", "actuellement", "mtn", "en ce moment"])

    def _is_room_current_teacher_question(self, question: str) -> bool:
        q = self._normalize_text(question)
        return "qui enseigne" in q and "salle" in q and self._question_mentions_now(question)

    def _is_available_rooms_now_question(self, question: str) -> bool:
        q = self._normalize_text(question)
        has_room = "salle" in q
        has_availability = any(token in q for token in ["dispon", "diponn", "libre", "vide"])
        return has_room and has_availability and self._question_mentions_now(question)

    def _is_available_rooms_question(self, question: str) -> bool:
        q = self._normalize_text(question)
        has_room = "salle" in q
        has_availability = any(token in q for token in ["dispon", "diponn", "libre", "vide"])
        return has_room and has_availability

    def _is_available_rooms_day_question(self, question: str) -> bool:
        return self._is_available_rooms_question(question) and self._question_mentions_day(question) and not self._is_available_rooms_now_question(question)

    def _available_rooms_now_sql(self, context: dict) -> Tuple[str, Dict[str, Any]]:
        sql = """
        SELECT sa.nom AS salle
        FROM salles sa
        WHERE sa.nom NOT LIKE '%/%'
          AND EXISTS (
              SELECT 1
              FROM seances sx
              WHERE sx.salle_id = sa.id
          )
          AND NOT EXISTS (
            SELECT 1
            FROM seances s
            JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id
            WHERE s.salle_id = sa.id
              AND LOWER(s.jour) = LOWER(:current_day)
              AND :current_time >= s.heure_debut
              AND :current_time < s.heure_fin
              AND LOWER(COALESCE(s.type_seance, '')) IN ('cours', 'tp')
        """
        params: Dict[str, Any] = {
            "current_day": context.get("jour_actuel") or DAY_MAP_ISO[self._context_date(context).isoweekday()],
            "current_time": datetime.now().time().strftime("%H:%M:%S"),
        }
        if context.get("periode_id"):
            sql += " AND s.periode_id = :periode_id\n"
            params["periode_id"] = int(context["periode_id"])

        sql += " ) ORDER BY sa.nom;"
        return sql, params

    def _available_rooms_day_sql(self, question: str, context: dict) -> Tuple[str, Dict[str, Any]]:
        requested_day = self._extract_requested_day(question, context) or context.get("jour_actuel") or DAY_MAP_ISO[self._context_date(context).isoweekday()]
        sql = """
        SELECT sa.nom AS salle
        FROM salles sa
        WHERE sa.nom NOT LIKE '%/%'
          AND EXISTS (
              SELECT 1
              FROM seances sx
              WHERE sx.salle_id = sa.id
          )
          AND NOT EXISTS (
            SELECT 1
            FROM seances s
            JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id
            WHERE s.salle_id = sa.id
              AND LOWER(s.jour) = LOWER(:target_day)
              AND LOWER(COALESCE(s.type_seance, '')) IN ('cours', 'tp')
        """
        params: Dict[str, Any] = {
            "target_day": requested_day,
        }
        if context.get("periode_id"):
            sql += " AND s.periode_id = :periode_id\n"
            params["periode_id"] = int(context["periode_id"])

        sql += " ) ORDER BY sa.nom;"
        return sql, params

    def _is_prof_location_question(self, question: str) -> bool:
        q = self._normalize_text(question)
        if not self._extract_prof_candidate(question):
            return False
        markers = ["ou se trouve", "se trouve", "dans quelle salle", "est ou"]
        return any(marker in q for marker in markers)

    def _extract_schedule_prof_candidate(self, question: str) -> Optional[str]:
        prof = self._extract_prof_candidate(question)
        if prof:
            return prof
        if not self._is_schedule_intent(question) or self._extract_class_candidate(question):
            return None

        match = re.search(
            r"\bemploi(?:s)?\s+(?:du|de)\s+temps\s+de\s+([A-Za-zÀ-ÿ'\-]+(?:\s+[A-Za-zÀ-ÿ'\-]+){1,2})\s*$",
            question or "",
            re.IGNORECASE,
        )
        if not match:
            return None

        candidate = match.group(1).strip()
        if self._teacher_prof_exists_in_db(candidate) or self._prof_exists_in_db(candidate):
            return candidate
        return None

    def _is_prof_schedule_question(self, question: str) -> bool:
        return self._is_schedule_intent(question) and bool(self._extract_schedule_prof_candidate(question)) and not bool(
            self._extract_class_candidate(question)
        )

    def _is_prof_class_question(self, question: str) -> bool:
        q = self._normalize_text(question)
        if not self._extract_prof_candidate(question):
            return False
        markers = ["dans quelle classe", "quelle classe", "pour quelle classe", "classe se trouve"]
        return any(marker in q for marker in markers)

    def _is_prof_current_course_question(self, question: str) -> bool:
        q = self._normalize_text(question)
        if not self._extract_prof_candidate(question):
            return False
        course_markers = ["quel cours", "quelle matiere", "fait", "enseigne"]
        return any(marker in q for marker in course_markers) and self._question_mentions_now(question)

    def _is_prof_has_course_question(self, question: str) -> bool:
        q = self._normalize_text(question)
        if not self._extract_prof_candidate(question):
            return False
        availability_markers = ["a cours", "a un cours", "a t il cours", "a elle cours", "est ce qu il a cours", "est ce qu elle a cours"]
        return any(marker in q for marker in availability_markers)

    def _prof_location_sql(self, question: str, context: dict) -> Tuple[str, Dict[str, Any]]:
        prof_name = self._extract_prof_candidate(question) or ""
        if self._teacher_prof_exists_in_db(prof_name):
            prof_condition = self._professor_match_condition(prof_name, "te.professeur_nom_complet") or "1=0"
            requested_day = self._extract_requested_day(question, context)
            target_day = requested_day or context.get("jour_actuel") or DAY_MAP_ISO[self._context_date(context).isoweekday()]
            restrict_to_now = self._question_mentions_now(question) or not requested_day

            if restrict_to_now:
                sql = f"""
                SELECT DISTINCT te.salle_nom AS salle
                FROM emplois_enseignants_seances te
                WHERE {prof_condition}
                  AND LOWER(te.jour) = LOWER(:target_day)
                  AND :current_time >= te.heure_debut
                  AND :current_time < te.heure_fin
                """
                params: Dict[str, Any] = {
                    "target_day": target_day,
                    "current_time": datetime.now().time().strftime("%H:%M:%S"),
                }
            else:
                sql = f"""
                SELECT DISTINCT te.salle_nom AS salle, te.classe_nom AS classe, te.jour, te.heure_debut, te.heure_fin
                FROM emplois_enseignants_seances te
                WHERE {prof_condition}
                  AND LOWER(te.jour) = LOWER(:target_day)
                """
                params = {"target_day": target_day}

            if context.get("semestre_id"):
                sql += " AND te.semestre_id = :semester_id\n"
                params["semester_id"] = int(context["semestre_id"])
            if context.get("periode"):
                sql += " AND UPPER(te.periode_nom) = :periode_nom\n"
                params["periode_nom"] = str(context["periode"]).upper()

            sql += " ORDER BY te.heure_debut, te.salle_nom;"
            return sql, params

        prof_condition = self._professor_match_condition(prof_name) or "1=0"
        requested_day = self._extract_requested_day(question, context)
        target_day = requested_day or context.get("jour_actuel") or DAY_MAP_ISO[self._context_date(context).isoweekday()]
        restrict_to_now = self._question_mentions_now(question) or not requested_day

        if restrict_to_now:
            sql = f"""
            SELECT DISTINCT sa.nom AS salle
            FROM seances s
            JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id
            JOIN professeurs p ON p.id = s.professeur_id
            JOIN salles sa ON sa.id = s.salle_id
            WHERE {prof_condition}
              AND LOWER(s.jour) = LOWER(:target_day)
              AND :current_time >= s.heure_debut
              AND :current_time < s.heure_fin
            """
            params: Dict[str, Any] = {
                "target_day": target_day,
                "current_time": datetime.now().time().strftime("%H:%M:%S"),
            }
        else:
            sql = f"""
            SELECT DISTINCT sa.nom AS salle, c.nom AS classe, s.jour, s.heure_debut, s.heure_fin
            FROM seances s
            JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id
            JOIN professeurs p ON p.id = s.professeur_id
            JOIN salles sa ON sa.id = s.salle_id
            JOIN classes c ON c.id = s.classe_id
            WHERE {prof_condition}
              AND LOWER(s.jour) = LOWER(:target_day)
            """
            params = {
                "target_day": target_day,
            }
        if context.get("periode_id"):
            sql += " AND s.periode_id = :periode_id\n"
            params["periode_id"] = int(context["periode_id"])

        sql += " ORDER BY s.heure_debut, sa.nom;"
        return sql, params

    def _prof_class_sql(self, question: str, context: dict) -> Tuple[str, Dict[str, Any]]:
        prof_name = self._extract_prof_candidate(question) or ""
        if self._teacher_prof_exists_in_db(prof_name):
            prof_condition = self._professor_match_condition(prof_name, "te.professeur_nom_complet") or "1=0"
            requested_day = self._extract_requested_day(question, context)
            target_day = requested_day or context.get("jour_actuel") or DAY_MAP_ISO[self._context_date(context).isoweekday()]
            restrict_to_now = self._question_mentions_now(question) or not requested_day

            sql = f"""
            SELECT DISTINCT te.classe_nom AS classe, te.salle_nom AS salle, te.jour, te.heure_debut, te.heure_fin
            FROM emplois_enseignants_seances te
            WHERE {prof_condition}
              AND LOWER(te.jour) = LOWER(:target_day)
            """
            params: Dict[str, Any] = {"target_day": target_day}
            if restrict_to_now:
                sql += " AND :current_time >= te.heure_debut AND :current_time < te.heure_fin\n"
                params["current_time"] = datetime.now().time().strftime("%H:%M:%S")
            if context.get("semestre_id"):
                sql += " AND te.semestre_id = :semester_id\n"
                params["semester_id"] = int(context["semestre_id"])
            if context.get("periode"):
                sql += " AND UPPER(te.periode_nom) = :periode_nom\n"
                params["periode_nom"] = str(context["periode"]).upper()
            sql += " ORDER BY te.heure_debut, te.classe_nom;"
            return sql, params

        prof_condition = self._professor_match_condition(prof_name) or "1=0"
        requested_day = self._extract_requested_day(question, context)
        target_day = requested_day or context.get("jour_actuel") or DAY_MAP_ISO[self._context_date(context).isoweekday()]
        restrict_to_now = self._question_mentions_now(question) or not requested_day

        sql = f"""
        SELECT DISTINCT c.nom AS classe, sa.nom AS salle, s.jour, s.heure_debut, s.heure_fin
        FROM seances s
        JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id
        JOIN professeurs p ON p.id = s.professeur_id
        JOIN classes c ON c.id = s.classe_id
        JOIN salles sa ON sa.id = s.salle_id
        WHERE {prof_condition}
          AND LOWER(s.jour) = LOWER(:target_day)
        """
        params: Dict[str, Any] = {"target_day": target_day}
        if restrict_to_now:
            sql += " AND :current_time >= s.heure_debut AND :current_time < s.heure_fin\n"
            params["current_time"] = datetime.now().time().strftime("%H:%M:%S")
        if context.get("periode_id"):
            sql += " AND s.periode_id = :periode_id\n"
            params["periode_id"] = int(context["periode_id"])
        sql += " ORDER BY s.heure_debut, c.nom;"
        return sql, params

    def _prof_current_course_sql(self, question: str, context: dict) -> Tuple[str, Dict[str, Any]]:
        prof_name = self._extract_prof_candidate(question) or ""
        if self._teacher_prof_exists_in_db(prof_name):
            prof_condition = self._professor_match_condition(prof_name, "te.professeur_nom_complet") or "1=0"
            sql = f"""
            SELECT DISTINCT te.matiere_nom AS matiere, te.classe_nom AS classe, te.salle_nom AS salle, te.heure_debut, te.heure_fin
            FROM emplois_enseignants_seances te
            WHERE {prof_condition}
              AND LOWER(te.jour) = LOWER(:current_day)
              AND :current_time >= te.heure_debut
              AND :current_time < te.heure_fin
            """
            params: Dict[str, Any] = {
                "current_day": context.get("jour_actuel") or DAY_MAP_ISO[self._context_date(context).isoweekday()],
                "current_time": datetime.now().time().strftime("%H:%M:%S"),
            }
            if context.get("semestre_id"):
                sql += " AND te.semestre_id = :semester_id\n"
                params["semester_id"] = int(context["semestre_id"])
            if context.get("periode"):
                sql += " AND UPPER(te.periode_nom) = :periode_nom\n"
                params["periode_nom"] = str(context["periode"]).upper()

            sql += " ORDER BY te.heure_debut;"
            return sql, params

        prof_condition = self._professor_match_condition(prof_name) or "1=0"
        sql = f"""
        SELECT DISTINCT m.nom AS matiere, c.nom AS classe, sa.nom AS salle, s.heure_debut, s.heure_fin
        FROM seances s
        JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id
        JOIN professeurs p ON p.id = s.professeur_id
        JOIN matieres m ON m.id = s.matiere_id
        JOIN classes c ON c.id = s.classe_id
        JOIN salles sa ON sa.id = s.salle_id
        WHERE {prof_condition}
          AND LOWER(s.jour) = LOWER(:current_day)
          AND :current_time >= s.heure_debut
          AND :current_time < s.heure_fin
        """
        params: Dict[str, Any] = {
            "current_day": context.get("jour_actuel") or DAY_MAP_ISO[self._context_date(context).isoweekday()],
            "current_time": datetime.now().time().strftime("%H:%M:%S"),
        }
        if context.get("periode_id"):
            sql += " AND s.periode_id = :periode_id\n"
            params["periode_id"] = int(context["periode_id"])

        sql += " ORDER BY s.heure_debut;"
        return sql, params

    def _prof_has_course_sql(self, question: str, context: dict) -> Tuple[str, Dict[str, Any]]:
        prof_name = self._extract_prof_candidate(question) or ""
        if self._teacher_prof_exists_in_db(prof_name):
            prof_condition = self._professor_match_condition(prof_name, "te.professeur_nom_complet") or "1=0"
            requested_day = self._extract_requested_day(question, context)
            target_day = requested_day or context.get("jour_actuel") or DAY_MAP_ISO[self._context_date(context).isoweekday()]
            sql = f"""
            SELECT COUNT(*) AS total_cours
            FROM emplois_enseignants_seances te
            WHERE {prof_condition}
              AND LOWER(te.jour) = LOWER(:target_day)
              AND LOWER(COALESCE(te.type_seance, '')) IN ('cours', 'tp')
            """
            params: Dict[str, Any] = {"target_day": target_day}
            if context.get("semestre_id"):
                sql += " AND te.semestre_id = :semester_id\n"
                params["semester_id"] = int(context["semestre_id"])
            if context.get("periode"):
                sql += " AND UPPER(te.periode_nom) = :periode_nom\n"
                params["periode_nom"] = str(context["periode"]).upper()
            sql += ";"
            return sql, params

        prof_condition = self._professor_match_condition(prof_name) or "1=0"
        requested_day = self._extract_requested_day(question, context)
        target_day = requested_day or context.get("jour_actuel") or DAY_MAP_ISO[self._context_date(context).isoweekday()]
        sql = f"""
        SELECT COUNT(*) AS total_cours
        FROM seances s
        JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id
        JOIN professeurs p ON p.id = s.professeur_id
        WHERE {prof_condition}
          AND LOWER(s.jour) = LOWER(:target_day)
          AND LOWER(COALESCE(s.type_seance, '')) IN ('cours', 'tp')
        """
        params: Dict[str, Any] = {
            "target_day": target_day,
        }
        if context.get("periode_id"):
            sql += " AND s.periode_id = :periode_id\n"
            params["periode_id"] = int(context["periode_id"])

        sql += ";"
        return sql, params

    def _room_current_teacher_sql(self, question: str, context: dict) -> Tuple[str, Dict[str, Any]]:
        sql = """
        SELECT DISTINCT p.nom_complet
        FROM seances s
        JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id
        JOIN professeurs p ON p.id = s.professeur_id
        JOIN salles sa ON sa.id = s.salle_id
        WHERE REPLACE(REPLACE(LOWER(sa.nom), ' ', ''), '-', '') = :room_name
          AND LOWER(s.jour) = LOWER(:current_day)
          AND :current_time BETWEEN s.heure_debut AND s.heure_fin
        """
        params: Dict[str, Any] = {
            "room_name": self._room_key(self._extract_room_candidate(question) or ""),
            "current_day": context.get("jour_actuel") or DAY_MAP_ISO[self._context_date(context).isoweekday()],
            "current_time": datetime.now().time().strftime("%H:%M:%S"),
        }

        if context.get("periode_id"):
            sql += " AND s.periode_id = :periode_id\n"
            params["periode_id"] = int(context["periode_id"])

        sql += " ORDER BY p.nom_complet;"
        return sql, params

    def _user_requested_specific_periode(self, question: str) -> bool:
        q = self._normalize_text(question)
        return bool(re.search(r"\bp\s*1\b", q) or re.search(r"\bp\s*2\b", q))

    def _question_is_day_specific(self, question: str) -> bool:
        q = self._normalize_text(question)
        if self._question_mentions_day(question):
            return True
        if re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", q):
            return True
        if re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", q):
            return True
        return False

    def _is_calendar_question(self, question: str) -> bool:
        q = self._normalize_text(question)
        if any(marker in q for marker in ["cours", "seance", "emploi", "edt", "planning", "horaire"]):
            return False

        markers = [
            "vacance",
            "vacances",
            "jour ferie",
            "jours ferie",
            "fete",
            "aid",
            "ramadan",
            "examen",
            "examens",
            "ds",
            "rattrap",
            "ratt",
            "revision",
            "calendrier",
        ]
        return any(marker in q for marker in markers)

    def _parse_explicit_date(self, question: str) -> Optional[date]:
        match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", question or "")
        if match:
            try:
                return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
            except ValueError:
                return None

        match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", question or "")
        if match:
            try:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except ValueError:
                return None

        q = self._normalize_text(question)
        if "aujourd" in q:
            return date.today()
        if "demain" in q:
            return date.today() + timedelta(days=1)
        if "hier" in q:
            return date.today() - timedelta(days=1)
        return None

    def _calendar_type_filter(self, question: str) -> Optional[str]:
        q = self._normalize_text(question)
        if "vacance" in q:
            return "vacances"
        if any(marker in q for marker in ["jour ferie", "jours ferie", "fete", "aid"]):
            return "jour_ferie"
        if "revision" in q:
            return "revision"
        if any(marker in q for marker in ["examen", "ds", "ratt"]):
            return "examen"
        if "periode" in q:
            return "periode"
        return None

    def _calendar_scope(self, question: str) -> str:
        q = self._normalize_text(question)
        if any(token in q for token in ["prochain", "prochaine", "prochains", "prochaines", "a venir", "avenir"]):
            return "upcoming"
        if any(token in q for token in ["cette annee", "de cette annee", "toute l'annee", "toute l annee"]):
            return "year"
        if not self._parse_explicit_date(question) and not any(token in q for token in ["aujourd", "demain", "hier"]):
            type_filter = self._calendar_type_filter(question)
            if type_filter and any(
                token in q
                for token in [
                    "les ",
                    "liste",
                    "quels",
                    "quelles",
                    "prochains",
                    "prochaines",
                    "date",
                    "dates",
                    "quand",
                    "avenir",
                ]
            ):
                return "upcoming"
        return "day"

    def _repair_sql(self, sql_query: str) -> str:
        if not sql_query:
            return sql_query

        repairs = {
            r"\bs\.matie_re_id\b": "s.matiere_id",
            r"\bs\.matier(e)?_id\b": "s.matiere_id",
            r"\bs\.profeseur_id\b": "s.professeur_id",
            r"\bs\.professeurid\b": "s.professeur_id",
            r"\bs\.salleid\b": "s.salle_id",
            r"\bs\.classeid\b": "s.classe_id",
        }

        fixed = sql_query
        for pattern, replacement in repairs.items():
            fixed = re.sub(pattern, replacement, fixed, flags=re.IGNORECASE)

        fixed = re.sub(r"\bp\.nom\b", "p.nom_complet", fixed, flags=re.IGNORECASE)
        fixed = re.sub(r"\bp\.nomcomplet\b", "p.nom_complet", fixed, flags=re.IGNORECASE)
        fixed = re.sub(
            r"\s+AND\s+c\.departement_id\s+IN\s*\(\s*SELECT\s+d\.id\s+FROM\s+departements\s+d\s+WHERE\s+d\.id\s+IN\s*\(\s*SELECT\s+c\.departement_id\s+FROM\s+classes\s+c\s+WHERE\s+.*?\)\s*\)\s*",
            " ",
            fixed,
            flags=re.IGNORECASE | re.DOTALL,
        )
        fixed = re.sub(
            r"\bWHERE\s+c\.departement_id\s+IN\s*\(\s*SELECT\s+d\.id\s+FROM\s+departements\s+d\s+WHERE\s+d\.id\s+IN\s*\(\s*SELECT\s+c\.departement_id\s+FROM\s+classes\s+c\s+WHERE\s+.*?\)\s*\)\s*\)\s+AND\s+",
            "WHERE ",
            fixed,
            flags=re.IGNORECASE | re.DOTALL,
        )
        fixed = self._normalize_timetable_select_aliases(fixed)
        fixed = self._ensure_timetable_order(fixed)
        return fixed

    def _ensure_timetable_order(self, sql_query: str) -> str:
        lower = sql_query.lower()
        first_from = re.search(r"\bfrom\s+([a-z_][a-z0-9_]*)\s+([a-z_][a-z0-9_]*)", lower)
        if not first_from:
            return sql_query
        if first_from.group(1) != "seances" or first_from.group(2) != "s":
            return sql_query
        if re.search(r"\border\s+by\b", sql_query, flags=re.IGNORECASE):
            return sql_query

        order_clause = (
            " ORDER BY CASE LOWER(s.jour) "
            "WHEN 'lundi' THEN 1 WHEN 'mardi' THEN 2 WHEN 'mercredi' THEN 3 "
            "WHEN 'jeudi' THEN 4 WHEN 'vendredi' THEN 5 WHEN 'samedi' THEN 6 "
            "WHEN 'dimanche' THEN 7 ELSE 8 END, s.heure_debut, s.heure_fin"
        )
        return sql_query.rstrip().rstrip(";") + order_clause + ";"

    def _format_empty_calendar_response(self, question: str, context: dict) -> Optional[str]:
        if not self._is_calendar_question(question):
            return None

        scope = self._calendar_scope(question)
        type_filter = self._calendar_type_filter(question)
        date_label = context.get("date_actuelle", "aujourd'hui")

        if scope == "year":
            labels = {
                "vacances": "vacances",
                "jour_ferie": "jours feries",
                "examen": "examens",
                "periode": "periodes",
            }
            target = labels.get(type_filter, "evenements")
            return f"Aucun {target} trouve pour l'annee universitaire en cours."

        if scope == "upcoming":
            if type_filter == "vacances":
                return "Aucune vacances a venir n'a ete trouvee."
            if type_filter == "jour_ferie":
                return "Aucun jour ferie a venir n'a ete trouve."
            if type_filter == "examen":
                return "Aucun examen a venir n'a ete trouve."
            if type_filter == "revision":
                return "Aucune periode de revision a venir n'a ete trouvee."
            return "Aucun evenement a venir n'a ete trouve."

        if type_filter == "vacances":
            return f"Non, il n'y a pas de vacances le {date_label}."
        if type_filter == "jour_ferie":
            return f"Non, il n'y a pas de jour ferie le {date_label}."
        if type_filter == "examen":
            return f"Non, aucun examen n'est prevu le {date_label}."
        return f"Aucun evenement calendrier trouve le {date_label}."

    def _format_empty_response(self, question: str, context: dict) -> Optional[str]:
        calendar_message = self._format_empty_calendar_response(question, context)
        if calendar_message:
            return calendar_message

        if self._is_room_current_teacher_question(question):
            room_name = self._extract_room_candidate(question) or ""
            if room_name and not self._room_exists_in_db(room_name):
                return f"Je ne trouve pas la salle '{room_name}' dans la base de donnees."
            return f"La salle {room_name} est vide actuellement." if room_name else "Aucune salle correspondante n'a ete trouvee."

        if self._is_available_rooms_now_question(question):
            return "Aucune salle libre n'a ete trouvee actuellement."

        if self._is_available_rooms_day_question(question):
            requested_day = (self._extract_requested_day(question, context) or "").lower()
            if requested_day:
                return f"Aucune salle libre n'a ete trouvee {requested_day}."
            return "Aucune salle libre n'a ete trouvee pour ce jour."

        prof_name = self._extract_schedule_prof_candidate(question) or self._extract_prof_candidate(question)
        if self._is_prof_class_question(question):
            if prof_name and not self._prof_exists_in_db(prof_name):
                return f"Je ne trouve pas le professeur '{prof_name}' dans la base de donnees."
            requested_day = self._extract_requested_day(question, context)
            if requested_day:
                return f"Aucune classe n'a ete trouvee pour {prof_name} {requested_day.lower()}."
            return f"{prof_name} n'est pas en classe actuellement." if prof_name else "Ce professeur n'est pas en classe actuellement."

        if self._is_prof_location_question(question):
            if prof_name and not self._prof_exists_in_db(prof_name):
                return f"Je ne trouve pas le professeur '{prof_name}' dans la base de donnees."
            requested_day = self._extract_requested_day(question, context)
            if requested_day:
                return f"Aucune salle n'a ete trouvee pour {prof_name} {requested_day.lower()}."
            return f"{prof_name} n'est pas en cours actuellement." if prof_name else "Ce professeur n'est pas en cours actuellement."

        if self._is_prof_current_course_question(question):
            if prof_name and not self._prof_exists_in_db(prof_name):
                return f"Je ne trouve pas le professeur '{prof_name}' dans la base de donnees."
            return f"{prof_name} n'enseigne aucun cours en ce moment." if prof_name else "Aucun cours n'est en cours pour ce professeur."

        if self._is_prof_has_course_question(question):
            if prof_name and not self._prof_exists_in_db(prof_name):
                return f"Je ne trouve pas le professeur '{prof_name}' dans la base de donnees."
            requested_day = self._extract_requested_day(question, context)
            if requested_day:
                return f"Non, {prof_name} n'a pas de cours {requested_day.lower()}."
            return f"Non, {prof_name} n'a pas de cours aujourd'hui." if prof_name else "Non, ce professeur n'a pas de cours aujourd'hui."

        if self._is_schedule_intent(question) and prof_name and not self._extract_class_candidate(question):
            requested_day = self._extract_requested_day(question, context)
            if requested_day:
                return f"Aucun cours trouve pour {prof_name} {requested_day.lower()}."
            periode = context.get("periode")
            semestre = context.get("semestre")
            if semestre and periode:
                return f"Aucun cours trouve pour {prof_name} dans la periode active {semestre}/{periode}."
            return f"Aucun cours trouve pour {prof_name}."

        return None

    def _exec_and_format_v2(self, question: str, sql_query: str, params: Dict[str, Any], context: dict) -> str:
        try:
            print(f"SQL execute: {sql_query}")
            result = self.db.execute(text(sql_query), params or {})
            rows = result.fetchall()
            print(f"Resultats: {len(rows)} lignes")

            if not rows:
                return self._format_empty_response(question, context) or "Aucune donnee trouvee pour cette question."

            data = [dict(row._mapping) for row in rows]
            formatted = groq_service.format_response(question, data, context)
            return formatted or "Resultats trouves, mais impossible de formater la reponse."
        except Exception as e:
            print(f"Erreur SQL: {e}")
            return "Erreur lors de l'execution de la requete."

    def _needs_class(self, q_lower: str) -> bool:
        normalized_question = self._normalize_text(q_lower)
        return any(
            [
                "emploi" in normalized_question,
                "edt" in normalized_question,
                "planning" in normalized_question,
                "horaire" in normalized_question,
                "cours" in normalized_question,
                "seance" in normalized_question,
                "j'ai cours" in normalized_question,
                "demain" in normalized_question,
                "aujourd" in normalized_question,
                any(day in normalized_question for day in ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]),
            ]
        )

    def _check_missing_info(self, question: str, context: dict) -> Optional[str]:
        if (
            self._is_calendar_question(question)
            or self._is_room_current_teacher_question(question)
            or self._is_available_rooms_question(question)
            or self._is_available_rooms_now_question(question)
            or self._is_prof_schedule_question(question)
            or self._is_prof_class_question(question)
            or self._is_prof_location_question(question)
            or self._is_prof_current_course_question(question)
            or self._is_prof_has_course_question(question)
        ):
            return None

        prof = self._extract_prof_candidate(question)
        if prof:
            if not self._prof_exists_in_db(prof):
                return f"Je ne trouve pas le professeur '{prof}' dans la base de donnees."
            return None

        if not self._needs_class(question):
            return None

        cls = self._extract_class_candidate(question)
        if not cls:
            return "Quelle est votre classe ? (ex: 2 ING GII 3, 1 TIC 2, 2 TIC-T, etc.)"

        cls = self._normalize_class_aliases(cls, context)
        if context.get("semestre_id") and not self._class_exists_in_db(cls, context):
            return (
                f"Je ne trouve pas la classe '{cls}' dans le semestre actuel ({context.get('semestre','?')}). "
                "Verifiez le nom (ex: '1 TIC 2') ou precisez le semestre (S1/S2)."
            )

        return None

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def process_question(self, question: str) -> str:
        question = self._keep_last_user_message(question)
        print(f"\n=== Question reçue: {question} ===")

        context = get_current_academic_context(self.db)
        base = self._context_date(context)
        context["jour_actuel"] = DAY_MAP_ISO[base.isoweekday()]
        print(f"Contexte académique: {context}")

        # Calendar routing
        if self._is_calendar_question(question):
            sql_query, params = self._calendar_sql(question, context)
            return self._exec_and_format(question, sql_query, params, context)

        if self._is_all_classes_request(question):
            sql_query, params = self._all_classes_sql()
            return self._exec_and_format(question, sql_query, params, context)

        if self._is_room_current_teacher_question(question):
            sql_query, params = self._room_current_teacher_sql(question, context)
            return self._exec_and_format(question, sql_query, params, context)

        if self._is_available_rooms_now_question(question):
            sql_query, params = self._available_rooms_now_sql(context)
            return self._exec_and_format(question, sql_query, params, context)

        if self._is_available_rooms_day_question(question):
            sql_query, params = self._available_rooms_day_sql(question, context)
            return self._exec_and_format(question, sql_query, params, context)

        if self._is_prof_class_question(question):
            prof = self._extract_prof_candidate(question)
            if prof and not self._prof_exists_in_db(prof):
                return f"Je ne trouve pas le professeur '{prof}' dans la base de donnees."
            sql_query, params = self._prof_class_sql(question, context)
            return self._exec_and_format(question, sql_query, params, context)

        if self._is_prof_schedule_question(question):
            prof = self._extract_schedule_prof_candidate(question) or self._extract_prof_candidate(question)
            if prof and not self._prof_exists_in_db(prof):
                return f"Je ne trouve pas le professeur '{prof}' dans la base de donnees."
            sql_query, params = self._teacher_prof_schedule_sql(question, context) if self._teacher_prof_exists_in_db(prof or "") else ("", {})
            if sql_query:
                return self._exec_and_format(question, sql_query, params, context)

        if self._is_prof_location_question(question):
            prof = self._extract_prof_candidate(question)
            if prof and not self._prof_exists_in_db(prof):
                return f"Je ne trouve pas le professeur '{prof}' dans la base de donnees."
            sql_query, params = self._prof_location_sql(question, context)
            return self._exec_and_format(question, sql_query, params, context)

        if self._is_prof_current_course_question(question):
            prof = self._extract_prof_candidate(question)
            if prof and not self._prof_exists_in_db(prof):
                return f"Je ne trouve pas le professeur '{prof}' dans la base de donnees."
            sql_query, params = self._prof_current_course_sql(question, context)
            return self._exec_and_format(question, sql_query, params, context)

        if self._is_prof_has_course_question(question):
            prof = self._extract_prof_candidate(question)
            if prof and not self._prof_exists_in_db(prof):
                return f"Je ne trouve pas le professeur '{prof}' dans la base de donnees."
            sql_query, params = self._prof_has_course_sql(question, context)
            return self._exec_and_format(question, sql_query, params, context)

        if self._is_university_general_question(question):
            return university_info_service.answer_question(question)

        # Missing info
        missing = self._check_missing_info(question, context)
        if missing:
            return missing

        # Normalize class alias in question BEFORE Groq
        cls = self._extract_class_candidate(question)
        if cls:
            cls2 = self._normalize_class_aliases(cls, context)
            if cls2 != cls:
                question = re.sub(re.escape(cls), cls2, question, flags=re.IGNORECASE)

        if not (groq_service and getattr(groq_service, "enabled", False)):
            return "Groq API n'est pas activé (GROQ_API_KEY manquant). Impossible de générer la requête SQL."

        sql_query = groq_service.generate_sql(question, context, SCHEMA_INFO)
        if not sql_query:
            return "Groq n'a pas pu générer une requête SQL."

        if sql_query == "ASK_CLASS":
            return "Quelle est votre classe ?"
        if sql_query == "ASK_PROF":
            return "Quel professeur cherchez-vous ?"

        sql_query = (sql_query or "").replace("```sql", "").replace("```", "").strip()
        if not self._validate_select_only(sql_query):
            return "Requête SQL invalide (seulement SELECT autorisé)."

        # Repairs
        sql_query = self._repair_sql(sql_query)

        # ✅ ACTIVE VERSION FILTER (critical)
        sql_query = self._ensure_active_version_filter(sql_query)

        # ✅ Smarter default periode:
        sql_query = self._enforce_current_periode_default(question, sql_query, context)

        # ✅ If user asked P1/P2 explicitly, enforce it (overrides default)
        sql_query = self._enforce_periode_marker(question, sql_query, context)

        # ✅ Robust prof matching if it's a professor question
        sql_query = self._enforce_professor_matching(question, sql_query)

        # ✅ Make weekday filtering deterministic for explicit/relative day requests
        if self._question_mentions_day(question):
            sql_query = self._enforce_requested_day_filter(question, sql_query, context)

        # ✅ Full timetable requests should not keep a day filter, even if the model adds one.
        if self._is_schedule_intent(question) and (
            not self._question_mentions_day(question) or self._is_full_schedule_request(question)
        ):
            sql_query = self._strip_day_filter(sql_query)

        return self._exec_and_format(question, sql_query, {}, context)

    def _exec_and_format(self, question: str, sql_query: str, params: Dict[str, Any], context: dict) -> str:
        try:
            print(f"SQL exécuté: {sql_query}")
            result = self.db.execute(text(sql_query), params or {})
            rows = result.fetchall()
            print(f"Résultats: {len(rows)} lignes")

            if not rows:
                return self._format_empty_calendar_response(question, context) or "Aucune donnee trouvee pour cette question."
                return "Aucune donnée trouvée pour cette question."

            data = [dict(row._mapping) for row in rows]
            formatted = groq_service.format_response(question, data, context)

            return formatted or "Résultats trouvés, mais impossible de formater la réponse."
        except Exception as e:
            print(f"Erreur SQL: {e}")
            return "Erreur lors de l'exécution de la requête."
