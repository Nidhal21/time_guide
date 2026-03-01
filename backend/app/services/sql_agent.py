# backend/app/services/sql_agent.py
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text, select

from .groq_service import groq_service


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


class SQLAgent:
    def __init__(self, db: Session):
        self.db = db

    # ---------------------------------------------------------------------
    # ✅ Keep only last user message if history injected
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
    def _norm(self, s: str) -> str:
        return re.sub(r"\s+", "", (s or "").strip().lower())

    def _context_date(self, context: dict) -> date:
        da = context.get("date_actuelle")
        if da:
            try:
                return datetime.strptime(str(da), "%Y-%m-%d").date()
            except Exception:
                pass
        return date.today()

    def _is_day_token(self, token: str) -> bool:
        t = (token or "").strip().lower()
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
        q = (question or "").lower()
        if any(
            re.search(rf"\b{d}\b", q)
            for d in ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        ):
            return True
        if "aujourd" in q or "demain" in q or "hier" in q:
            return True
        return False

    # ✅ better intent detection (handles typos like "lempoi")
    def _is_schedule_intent(self, question: str) -> bool:
        q = (question or "").lower()
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
            return m2.group(1).strip()

        return None

    def _enforce_professor_matching(self, question: str, sql_query: str) -> str:
        prof = self._extract_prof_candidate(question)
        if not prof:
            return sql_query

        prof_key = re.sub(r"[^a-z0-9]", "", prof.lower())
        fixed = sql_query

        fixed = re.sub(
            r"p\.nom_complet\s*=\s*'[^']*'",
            "REPLACE(REPLACE(REPLACE(LOWER(p.nom_complet), ' ', ''), '.', ''), '-', '') "
            f"LIKE '%' || '{prof_key}' || '%'",
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
            "jour féri",
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
        if "jour féri" in q or "jour ferie" in q or "fête" in q or "fete" in q or "aid" in q:
            return "jour_ferie"
        if "révision" in q or "revision" in q:
            return "revision"
        if "examen" in q or "ds" in q or "ratt" in q:
            return "examen"
        if "periode" in q or "période" in q:
            return "periode"
        return None

    def _calendar_sql(self, question: str, context: dict) -> Tuple[str, Dict[str, Any]]:
        d = self._parse_explicit_date(question) or date.today()
        t = self._calendar_type_filter(question)

        sql = """
        SELECT nom, date_debut, date_fin, type
        FROM vacances_jours_feries
        WHERE :d BETWEEN date_debut AND date_fin
          AND annee_id = :annee_id
        """
        params: Dict[str, Any] = {"d": d, "annee_id": context.get("annee_id", 1)}

        if t:
            sql += " AND LOWER(type) = LOWER(:t)\n"
            params["t"] = t

        sql += " ORDER BY date_debut, nom;"
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
        return fixed

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

        fixed = re.sub(r"\s+", " ", fixed).strip()
        if not fixed.endswith(";"):
            fixed += ";"
        return fixed

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

        if not (groq_service and getattr(groq_service, "enabled", False)):
            return "Groq API n'est pas activé (GROQ_API_KEY manquant). Impossible de générer la requête SQL."

        # Calendar routing
        if self._is_calendar_question(question):
            sql_query, params = self._calendar_sql(question, context)
            return self._exec_and_format(question, sql_query, params, context)

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

        # ✅ If user didn't mention day and it's schedule intent -> remove any day filter
        if self._is_schedule_intent(question) and not self._question_mentions_day(question):
            sql_query = self._strip_day_filter(sql_query)

        return self._exec_and_format(question, sql_query, {}, context)

    def _exec_and_format(self, question: str, sql_query: str, params: Dict[str, Any], context: dict) -> str:
        try:
            print(f"SQL exécuté: {sql_query}")
            result = self.db.execute(text(sql_query), params or {})
            rows = result.fetchall()
            print(f"Résultats: {len(rows)} lignes")

            if not rows:
                return "Aucune donnée trouvée pour cette question."

            data = [dict(row._mapping) for row in rows]
            formatted = groq_service.format_response(question, data, context)

            return formatted or "Résultats trouvés, mais impossible de formater la réponse."
        except Exception as e:
            print(f"Erreur SQL: {e}")
            return "Erreur lors de l'exécution de la requête."