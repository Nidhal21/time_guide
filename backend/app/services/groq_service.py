# backend/app/services/groq_service.py
"""
Groq API Service for SQL generation + formatting

UPDATED / FIXED (aligned with your latest SQLAgent):
- Clean ONE-SELECT extraction + comment stripping
- Stronger "ONLY SELECT" enforcement
- Prompt updated to:
    * avoid CASE/EXTRACT(DOW)
    * avoid forcing periode_id always (SQLAgent now handles smart default + overrides)
    * include best-practice join for ACTIVE version (SQLAgent also enforces it, but we guide Groq)
- Safer timeouts + defensive JSON parsing
- Keeps your behavior: no local fallback formatting for timetable responses (except calendar rows formatting)
"""

from __future__ import annotations

import os
import re
import requests
from typing import Optional, Any, Dict


class GroqService:
    """Service for generating SQL using Groq API (Llama 3.3 70B)"""

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"

        # Reuse a session (faster + fewer connection issues)
        self._session = requests.Session()

        if not self.api_key:
            print("Warning: GROQ_API_KEY not found in environment")
            self.enabled = False
        else:
            self.enabled = True
            print(f"✓ Groq API initialized with {self.model}")

    # ----------------------------
    # Helpers
    # ----------------------------
    def _is_calendar_question(self, question: str) -> bool:
        q = (question or "").lower()
        keywords = [
            "vacance",
            "vacances",
            "jours féri",
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
            "calendrier universitaire",
        ]
        return any(k in q for k in keywords)

    def _validate_select_only(self, sql: str) -> bool:
        if not sql:
            return False
        s = sql.replace("```sql", "").replace("```", "").strip()
        return bool(re.match(r"^\s*select\b", s, re.IGNORECASE))

    def _strip_sql_comments(self, s: str) -> str:
        """Remove SQL comments: -- line comments and /* block comments */."""
        if not s:
            return s
        s = re.sub(r"/\*[\s\S]*?\*/", " ", s)
        s = re.sub(r"--[^\n]*", " ", s)
        return s

    def _extract_one_select(self, txt: str) -> str:
        """
        Extract from the first SELECT to the end, then truncate at the first semicolon.
        Ensure it ends with ';'.
        """
        if not txt:
            return txt

        # Keep from first SELECT
        up = txt.upper()
        idx = up.find("SELECT")
        if idx >= 0:
            txt = txt[idx:].strip()

        # Keep only first statement
        if ";" in txt:
            txt = txt.split(";", 1)[0].strip()

        txt = re.sub(r"\s+$", "", txt)
        if not txt.endswith(";"):
            txt += ";"
        return txt

    def _clean_sql(self, raw: str) -> str:
        """
        Extract a clean ONE-SELECT statement from model output.
        - removes markdown fences
        - supports ASK_CLASS / ASK_PROF
        - keeps from first SELECT
        - removes extra statements
        - strips SQL comments
        - ensures trailing semicolon
        """
        if not raw:
            return raw

        txt = raw.replace("```sql", "").replace("```", "").strip()
        txt = txt.replace("\u200b", "").strip()  # remove zero-width spaces

        if re.search(r"\bASK_CLASS\b", txt):
            return "ASK_CLASS"
        if re.search(r"\bASK_PROF\b", txt):
            return "ASK_PROF"

        txt = self._strip_sql_comments(txt)
        txt = re.sub(r"\s+", " ", txt).strip()
        txt = self._extract_one_select(txt)
        return txt

    def _safe_json(self, response: requests.Response) -> Optional[Dict[str, Any]]:
        try:
            return response.json()
        except Exception as e:
            print(f"Groq API JSON parse error: {e}")
            return None

    # ----------------------------
    # Missing info check (optional)
    # ----------------------------
    def _extract_class_candidate(self, question: str) -> Optional[str]:
        q = (question or "").strip()

        m = re.search(
            r"\b(\d)\s*(ING|TIC|LTIC|MP|MR)\b(?:\s+([A-Z0-9\-]+))?(?:\s+([A-Z0-9\-]+))?(?:\s+(\d))?\b",
            q,
            flags=re.IGNORECASE,
        )
        if m:
            parts = [p for p in m.groups() if p]
            cls = " ".join([parts[0]] + [p.upper() for p in parts[1:]])
            cls = re.sub(r"\s+", " ", cls).strip()
            return cls

        return None

    def check_missing_info(self, question: str) -> Optional[str]:
        """
        Kept for compatibility, but your SQLAgent already does missing-info checks.
        """
        if self._is_calendar_question(question):
            return None

        q_lower = (question or "").lower()

        needs_class = any(
            [
                "emploi du temps" in q_lower,
                "emplois du temps" in q_lower,
                "emploi de temps" in q_lower,
                "edt" in q_lower,
                "planning" in q_lower,
                "horaire" in q_lower,
                "quel cours" in q_lower,
                "quels cours" in q_lower,
                "cours" in q_lower,
                "séance" in q_lower,
                "seance" in q_lower,
                "mon cours" in q_lower,
                "mes cours" in q_lower,
                "j'ai cours" in q_lower,
                "demain" in q_lower,
                "aujourd" in q_lower,
                "hier" in q_lower,
                any(d in q_lower for d in ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]),
            ]
        )

        if not needs_class:
            return None

        cls = self._extract_class_candidate(question)
        if not cls:
            return "Quelle est votre classe ? (ex: 2 ING GII 3, 1 TIC 2, 2 TIC-T, etc.)"

        return None

    # ----------------------------
    # SQL generation (Groq)
    # ----------------------------
    def generate_sql(self, question: str, context: dict, schema_info: str) -> Optional[str]:
        """
        Returns SQL or ASK_* or None.
        NOTE:
        - We do NOT force periode_id logic here anymore (SQLAgent does it smarter).
        - We still allow user explicit P1/P2 in Groq output (SQLAgent enforces too).
        - We encourage joining active versions, but SQLAgent will enforce anyway.
        """
        if not self.enabled:
            return None

        periode_id = context.get("periode_id")
        semestre_id = context.get("semestre_id")
        annee_id = context.get("annee_id", 1)
        today_day_name = context.get("jour_actuel") or context.get("jour_nom") or ""

        prompt = f"""You are a PostgreSQL expert. Return ONLY ONE SQL SELECT query, or ASK_CLASS / ASK_PROF.

DATABASE SCHEMA:
{schema_info}

CONTEXT:
- Current Periode ID: {periode_id if periode_id is not None else "NULL"}
- Current Semestre ID: {semestre_id if semestre_id is not None else "NULL"}
- Current Annee ID: {annee_id}
- Today date: {context.get('date_actuelle', 'unknown')}
- Today weekday name (French): {today_day_name if today_day_name else "UNKNOWN"}

USER QUESTION (French):
{question}

STRICT RULES:
A) If the question is about timetable/seances AND the class is missing -> return exactly: ASK_CLASS
B) If the question is about timetable for a professor AND professor name is missing -> return exactly: ASK_PROF

C) Never output markdown. Never output explanations. ONLY the SQL (or ASK_*).
D) ALWAYS output ONE SELECT statement. No INSERT/UPDATE/DELETE/DDL. No multiple statements.

E) Class matching MUST normalize spaces:
   REPLACE(LOWER(c.nom), ' ', '') LIKE '%' || REPLACE(LOWER('<user_class>'), ' ', '') || '%'

F) ACTIVE VERSION RULE (IMPORTANT):
   For any timetable query on seances, you should use the ACTIVE timetable version:
   JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id

G) DAY RULE:
   - If the user mentions an explicit weekday (lundi/mardi/mercredi/jeudi/vendredi/samedi/dimanche),
     use that exact value: s.jour = 'Lundi' (etc).
   - Only if user says "aujourd'hui/demain/hier" and NO explicit weekday is mentioned:
       * DO NOT use CASE/EXTRACT(DOW).
       * Prefer using "Today weekday name (French)" when available and set s.jour to that literal.
       * If Today weekday name is UNKNOWN, then and only then you may use date-based mapping.

H) PERIOD RULE:
   - If user explicitly mentions P1 or P2 or "P1 et P2" or "complet", DO NOT force current periode_id.
     Instead JOIN periodes per and filter by:
        per.semestre_id = {semestre_id if semestre_id is not None else 0}
        AND per.nom IN ('P1') or ('P2') or ('P1','P2')
     and use s.periode_id = per.id.
   - If user does not mention P1/P2, you may omit periode filters entirely (agent will enforce when needed).

I) Rooms:
   Use alias 'sa' for salles, and use sa.nom for room name.

CALENDAR QUESTIONS:
- Use vacances_jours_feries (nom, date_debut, date_fin, type, annee_id).
- If asking for today events:
  SELECT nom, type, date_debut, date_fin
  FROM vacances_jours_feries
  WHERE CURRENT_DATE BETWEEN date_debut AND date_fin
    AND annee_id = {annee_id}
  ORDER BY date_debut;

SQL:"""

        try:
            response = self._session.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a PostgreSQL expert. "
                                "Return only ONE SELECT query or ASK_CLASS/ASK_PROF. "
                                "No explanations. No markdown."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 700,
                },
                timeout=25,
            )

            if response.status_code != 200:
                print(f"Groq API error: {response.status_code} - {response.text}")
                return None

            payload = self._safe_json(response)
            if not payload:
                return None

            raw = (
                payload.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            raw = (raw or "").strip()

            print(f"[DEBUG] Raw SQL from Groq: {raw}")

            sql = self._clean_sql(raw)

            if sql in {"ASK_CLASS", "ASK_PROF"}:
                return sql

            if not self._validate_select_only(sql):
                print("[DEBUG] Groq returned non-SELECT.")
                return None

            print(f"[DEBUG] Cleaned SQL: {sql}")
            return sql

        except Exception as e:
            print(f"Groq API exception: {e}")
            return None

    # ----------------------------
    # Response formatting (NO fallback)
    # ----------------------------
    def format_response(self, question: str, data: list, context: dict) -> Optional[str]:
        """
        No local formatting fallback (per request).
        Calendar rows -> deterministic local formatting OK.
        """
        if not self.enabled:
            return None

        if not data:
            return "Aucune donnée trouvée pour cette question."

        # Calendar rows -> local formatting
        if all(("date_debut" in r and "date_fin" in r and ("nom" in r or "Nom" in r)) for r in data):
            lines = []
            for r in data[:80]:
                nom = r.get("nom") or r.get("Nom") or ""
                typ = r.get("type") or r.get("Type") or ""
                dd = r.get("date_debut") or r.get("DateDebut")
                df = r.get("date_fin") or r.get("DateFin")
                lines.append(f"{dd} -> {df} | {typ} | {nom}")
            return "\n".join(lines).strip()

        data_str = "\n".join([str(dict(row)) for row in data[:25]])

        prompt = f"""You are a professional French university timetable assistant.

USER QUESTION: {question}

ACADEMIC CONTEXT:
- Semestre: {context.get("semestre")}
- Periode: {context.get("periode")}
- Date: {context.get("date_actuelle")}

SQL RESULTS ({len(data)} rows):
{data_str}

FORMAT (plain text, no markdown):
Voici votre emploi du temps pour 2 ING GII 3 :

Lundi :

8:15 - 9:45 | TRAIT IMAGES
Professeur : Mr BEN SLIMA M.
Salle : C14

RULES:
- Always in French
- Clear blank line between courses
- No markdown, no bullet points
- If multiple days, group by day title line (Lundi:, Mardi:, etc.)
- If multiple periods (P1/P2), group by "P1:" then days, then "P2:".

RESPONSE:"""

        try:
            response = self._session.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a professional French university assistant. "
                                "Format responses clearly with line breaks. No markdown."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 900,
                },
                timeout=30,
            )

            if response.status_code != 200:
                print(f"Groq format error: {response.status_code} - {response.text}")
                return None

            payload = self._safe_json(response)
            if not payload:
                return None

            raw = (
                payload.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            raw = (raw or "").strip()
            return self._postprocess_response(raw)

        except Exception as e:
            print(f"Groq format exception: {e}")
            return None

    def _postprocess_response(self, text: str) -> str:
        if not text:
            return text

        text = text.replace("**", "")

        # Ensure blank line before each time range (but not at start)
        text = re.sub(
            r"\s*(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})\s*",
            r"\n\n\1 ",
            text,
        ).strip()

        text = re.sub(r"\s+(Professeur\s*:)\s*", r"\n\1 ", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+(Salle\s*:)\s*", r"\n\1 ", text, flags=re.IGNORECASE)

        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


groq_service = GroqService()