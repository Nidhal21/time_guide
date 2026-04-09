from __future__ import annotations

import os
import re
import unicodedata
from typing import Any, Dict, Optional

import requests

SUSPICIOUS_MOJIBAKE_CHARS = ("Ã", "Â", "â", "€", "™", "œ", "�")
DAY_DISPLAY_ORDER = {
    "lundi": 1,
    "mardi": 2,
    "mercredi": 3,
    "jeudi": 4,
    "vendredi": 5,
    "samedi": 6,
    "dimanche": 7,
}
FRENCH_DAY_NAMES = tuple(DAY_DISPLAY_ORDER.keys())

class GroqService:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"
        self._session = requests.Session()

        if not self.api_key:
            print("Warning: GROQ_API_KEY not found in environment")
            self.enabled = False
        else:
            self.enabled = True
            print(f"Groq API initialized with {self.model}")

    # --- Helpers ---

    def _repair_text_encoding(self, value: str) -> str:
        if not value:
            return ""

        repaired = value.replace("\xa0", " ").replace("�", "'").replace("`", "'")
        if any(ch in repaired for ch in SUSPICIOUS_MOJIBAKE_CHARS):
            for source_encoding in ("latin1", "cp1252"):
                try:
                    candidate = repaired.encode(source_encoding).decode("utf-8")
                except Exception:
                    continue
                if candidate and candidate != repaired:
                    repaired = candidate
                    break
        return repaired

    def _normalize_text(self, text: str) -> str:
        repaired = self._repair_text_encoding(text or "")
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

    def _normalize_room_name(self, value: Any) -> str:
        text = self._repair_text_encoding(str(value or ""))
        text = re.sub(r"\s+", " ", text).strip().upper()
        text = re.sub(r"\b([A-Z])\s+(\d{2})\b", r"\1\2", text)
        text = re.sub(r"\b([A-Z])\s*0?(\d)\b", lambda match: f"{match.group(1)}{int(match.group(2)):02d}", text)
        text = re.sub(r"\bTEL-TCOM1\b", "TEL-TCOM 1", text)
        text = re.sub(r"\bEL-CI\s+AUTO\b", "EL-CI AUTO", text)
        text = re.sub(r"\s*/\s*", " / ", text)
        return text

    def _room_key(self, value: Any) -> str:
        normalized = self._normalize_room_name(value).lower()
        return re.sub(r"[\s/-]+", "", normalized)

    def _extract_requested_day_label(self, question: str) -> Optional[str]:
        q = self._normalize_text(question)
        for day_name in FRENCH_DAY_NAMES:
            if re.search(rf"\b{re.escape(day_name)}\b", q):
                return day_name
        if "aujourd" in q:
            return "aujourd'hui"
        if "demain" in q:
            return "demain"
        if "hier" in q:
            return "hier"
        return None

    def _is_calendar_question(self, question: str) -> bool:
        q = self._normalize_text(question)
        keywords = [
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
        return any(keyword in q for keyword in keywords)

    def _validate_select_only(self, sql: str) -> bool:
        if not sql:
            return False
        cleaned = sql.replace("```sql", "").replace("```", "").strip()
        return bool(re.match(r"^\s*select\b", cleaned, re.IGNORECASE))

    def _strip_sql_comments(self, sql: str) -> str:
        if not sql:
            return sql
        sql = re.sub(r"/\*[\s\S]*?\*/", " ", sql)
        sql = re.sub(r"--[^\n]*", " ", sql)
        return sql

    def _extract_one_select(self, raw: str) -> str:
        if not raw:
            return raw
        idx = raw.upper().find("SELECT")
        if idx >= 0:
            raw = raw[idx:].strip()
        if ";" in raw:
            raw = raw.split(";", 1)[0].strip()
        if not raw.endswith(";"):
            raw += ";"
        return raw

    def _clean_sql(self, raw: str) -> str:
        if not raw:
            return raw
        text = raw.replace("```sql", "").replace("```", "").strip()
        text = text.replace("\u200b", "").strip()
        if re.search(r"\bASK_CLASS\b", text):
            return "ASK_CLASS"
        if re.search(r"\bASK_PROF\b", text):
            return "ASK_PROF"
        text = self._strip_sql_comments(text)
        text = re.sub(r"\s+", " ", text).strip()
        return self._extract_one_select(text)

    def _safe_json(self, response: requests.Response) -> Optional[Dict[str, Any]]:
        try:
            return response.json()
        except Exception as e:
            print(f"Groq API JSON parse error: {e}")
            return None

    def _extract_room_name(self, question: str) -> Optional[str]:
        question_text = question or ""
        patterns = [
            r"\bsalle\s+([A-Za-z0-9][A-Za-z0-9 ]*)\b",
            r"\bemploi(?:s)?\s+(?:du|de)\s+temps\s+de\s+([A-Za-z]{1,6}\s*0?\d{1,2})\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, question_text, flags=re.IGNORECASE)
            if not match:
                continue
            candidate = re.sub(
                r"\b(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|aujourd'hui|aujourdhui|demain|hier|maintenant|actuellement|mtn)\b.*$",
                "",
                match.group(1),
                flags=re.IGNORECASE,
            ).strip()
            normalized = self._normalize_room_name(candidate)
            if re.fullmatch(r"[A-Z][0-9]{2}", normalized) or re.fullmatch(r"[A-Z]{2,}[0-9]{1,2}", normalized):
                return normalized
            if pattern == patterns[0]:
                return normalized
        return None

    def _format_lookup_response(self, question: str, data: list) -> Optional[str]:
        if not data:
            return None

        keys = list(data[0].keys())
        normalized_keys = {key.lower(): key for key in keys}
        q = self._normalize_text(question)

        if len(keys) == 1:
            key = keys[0]
            values = []
            for row in data:
                value = row.get(key)
                if value is None:
                    continue
                value_str = str(value).strip()
                if value_str and value_str not in values:
                    values.append(value_str)

            if not values:
                return None

            if key.lower() in {"nom_complet", "prof", "professeur"}:
                room_name = self._extract_room_name(question)
                if "qui enseigne" in q and room_name:
                    if len(values) == 1:
                        return f"En salle {room_name}, c'est {values[0]} qui enseigne actuellement."
                    return f"En salle {room_name}, les enseignants trouves sont : {', '.join(values)}."
                return values[0] if len(values) == 1 else ", ".join(values)

            if key.lower() in {"total_cours", "count"}:
                try:
                    total = int(values[0])
                except Exception:
                    return None
                if total <= 0:
                    return None
                if "aujourd" in q:
                    return f"Oui, ce professeur a {total} cours aujourd'hui."
                day_label = self._extract_requested_day_label(question)
                if day_label and day_label not in {"aujourd'hui", "demain", "hier"}:
                    return f"Oui, ce professeur a {total} cours {day_label}."
                return f"Oui, ce professeur a {total} cours prevus."

            if key.lower() in {"nom", "room", "salle"}:
                if any(token in q for token in ["dispon", "libre", "vide"]):
                    unique_values = []
                    seen = set()
                    for value in values:
                        display_value = self._normalize_room_name(value)
                        norm = self._room_key(display_value)
                        if norm in seen:
                            continue
                        seen.add(norm)
                        unique_values.append(display_value)
                    if not unique_values:
                        return None
                    room_label = "salle" if len(unique_values) == 1 else "salles"
                    if any(token in q for token in ["maintenant", "actuellement", "mtn", "en ce moment"]):
                        intro = f"Il y a {len(unique_values)} {room_label} disponible{'s' if len(unique_values) > 1 else ''} actuellement :"
                    else:
                        day_label = self._extract_requested_day_label(question)
                        if day_label == "aujourd'hui":
                            intro = f"Les {room_label} disponible{'s' if len(unique_values) > 1 else ''} aujourd'hui {'sont' if len(unique_values) > 1 else 'est'} :"
                        elif day_label == "demain":
                            intro = f"Les {room_label} disponible{'s' if len(unique_values) > 1 else ''} demain {'sont' if len(unique_values) > 1 else 'est'} :"
                        elif day_label and day_label != "hier":
                            intro = f"Les {room_label} disponible{'s' if len(unique_values) > 1 else ''} {day_label} {'sont' if len(unique_values) > 1 else 'est'} :"
                        else:
                            intro = f"Voici {len(unique_values)} {room_label} disponible{'s' if len(unique_values) > 1 else ''} :"
                    lines = [intro]
                    lines.extend(f"- {value}" for value in unique_values[:80])
                    if len(unique_values) > 80:
                        lines.append(f"... et {len(unique_values) - 80} autres salles.")
                    return "\n".join(lines)
                if "ou se trouve" in q:
                    if len(values) == 1:
                        return f"Ce professeur se trouve en salle {self._normalize_room_name(values[0])}."
                    normalized_values = [self._normalize_room_name(value) for value in values]
                    return f"Ce professeur se trouve dans plusieurs salles : {', '.join(normalized_values)}."
                if len(values) == 1:
                    return f"Salle {self._normalize_room_name(values[0])}."
                normalized_values = [self._normalize_room_name(value) for value in values]
                return ", ".join(f"Salle {value}" for value in normalized_values)

            if key.lower() == "classe":
                if "quelle classe" in q or "dans quelle classe" in q or "pour quelle classe" in q:
                    if len(values) == 1:
                        return f"Ce professeur est dans la classe {values[0]}."
                    return "Ce professeur intervient dans les classes suivantes : " + ", ".join(values) + "."
                return values[0] if len(values) == 1 else ", ".join(values)

        if {"matiere", "heure_debut", "heure_fin"}.issubset(normalized_keys):
            first = data[0]
            matiere = str(first.get(normalized_keys["matiere"]) or "").strip()
            start = self._format_time(first.get(normalized_keys["heure_debut"]))
            end = self._format_time(first.get(normalized_keys["heure_fin"]))
            room_value = first.get(normalized_keys["salle"]) if "salle" in normalized_keys else first.get(normalized_keys["room"], "")
            room = self._normalize_room_name(room_value) if room_value else ""
            classe = str(first.get(normalized_keys["classe"]) or "").strip() if "classe" in normalized_keys else ""

            if any(marker in q for marker in ["quel cours", "quelle matiere", "fait il", "enseigne t il", "enseigne maintenant"]):
                details = [f"{matiere} ({start} - {end})"]
                if classe:
                    details.append(f"pour {classe}")
                if room:
                    details.append(f"en salle {room}")
                return "Le cours actuel est " + " ".join(details) + "."

        if {"jour", "heure_debut", "heure_fin"}.issubset(normalized_keys):
            if (
                "ou se trouve" in q
                and "salle" in normalized_keys
                and "classe" in normalized_keys
            ):
                lines = []
                for row in data:
                    day = str(row.get(normalized_keys["jour"]) or "").strip()
                    start = self._format_time(row.get(normalized_keys["heure_debut"]))
                    end = self._format_time(row.get(normalized_keys["heure_fin"]))
                    classe = str(row.get(normalized_keys["classe"]) or "").strip()
                    salle = self._normalize_room_name(row.get(normalized_keys["salle"]))
                    lines.append(f"- {day} {start}-{end} : {classe} en salle {salle}")
                if lines:
                    return "Voici ou se trouve ce professeur :\n" + "\n".join(lines[:12])
            return None

        if len(data) == 1:
            row = data[0]
            parts = [f"{key}: {value}" for key, value in row.items() if value is not None]
            if parts:
                return "\n".join(parts)

        return None

    def _format_time(self, value: Any) -> str:
        if value is None:
            return "?"
        if hasattr(value, "strftime"):
            try:
                return value.strftime("%H:%M")
            except Exception:
                pass

        text = str(value).strip()
        if not text:
            return "?"
        match = re.match(r"^(\d{1,2}):(\d{2})", text)
        if match:
            return f"{int(match.group(1)):02d}:{match.group(2)}"
        return text

    def _format_timetable_response(self, data: list) -> Optional[str]:
        if not data:
            return None
        if not {"jour", "heure_debut", "heure_fin"}.issubset(data[0].keys()):
            return None

        class_names = []
        grouped: Dict[str, list] = {}
        seen_entries = set()
        for row in data:
            day = str(row.get("jour") or "").strip() or "Jour inconnu"
            class_name = str(row.get("classe") or "").strip()
            if class_name and class_name not in class_names:
                class_names.append(class_name)

            entry = {
                "time": f"{self._format_time(row.get('heure_debut'))} - {self._format_time(row.get('heure_fin'))}",
                "matiere": str(row.get("matiere") or "Cours").strip(),
                "professeur": str(row.get("professeur") or row.get("nom_complet") or "Non precise").strip(),
                "salle": self._normalize_room_name(row.get("salle") or row.get("room") or "Non precisee"),
            }
            dedupe_key = (day, entry["time"], entry["matiere"], entry["professeur"], entry["salle"])
            if dedupe_key in seen_entries:
                continue
            seen_entries.add(dedupe_key)

            grouped.setdefault(day, []).append(
                entry
            )

        title = f"Voici votre emploi du temps pour {class_names[0]} :" if len(class_names) == 1 else "Voici votre emploi du temps :"
        lines = [title]
        sorted_days = sorted(grouped.keys(), key=lambda day: (DAY_DISPLAY_ORDER.get(day.lower(), 99), day.lower()))
        for day in sorted_days:
            entries = sorted(grouped[day], key=lambda entry: entry["time"])
            lines.extend(["", f"{day} :", ""])
            for index, entry in enumerate(entries):
                lines.append(f"{entry['time']} | {entry['matiere']}")
                lines.append(f"Professeur : {entry['professeur']}")
                lines.append(f"Salle : {entry['salle']}")
                if index != len(entries) - 1:
                    lines.append("")
        return "\n".join(lines).strip()

    def _post_with_retry(self, payload: dict, timeout: int = 25) -> Optional[requests.Response]:
        for attempt in range(2):
            try:
                return self._session.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=timeout,
                )
            except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
                if attempt == 0:
                    print(f"Groq connection error (retrying): {e}")
                    self._session = requests.Session()
                    continue
                print(f"Groq API exception: {e}")
                return None
            except Exception as e:
                print(f"Groq API exception: {e}")
                return None
        return None

    # --- Missing info check ---

    def _extract_class_candidate(self, question: str) -> Optional[str]:
        match = re.search(
            r"\b(\d)\s*(ING|TIC|LTIC|MP|MR)\b(?:\s+([A-Z0-9\-]+))?(?:\s+([A-Z0-9\-]+))?(?:\s+(\d))?\b",
            (question or "").strip(),
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        parts = [part for part in match.groups() if part]
        return re.sub(r"\s+", " ", " ".join([parts[0]] + [part.upper() for part in parts[1:]])).strip()

    def check_missing_info(self, question: str) -> Optional[str]:
        if self._is_calendar_question(question):
            return None

        q = self._normalize_text(question)
        no_class_needed = any(
            [
                "professeur" in q,
                "prof " in q,
                re.search(r"\b(mr|mme|dr)\b", q),
                "quelles classes" in q,
                "liste" in q and "classe" in q,
                "classes existent" in q,
                "tous les prof" in q,
                "liste des prof" in q,
                "salle" in q and not any(token in q for token in ["cours", "emploi", "seance"]),
            ]
        )
        if no_class_needed:
            return None

        needs_class = any(
            [
                "emploi du temps" in q,
                "emplois du temps" in q,
                "edt" in q,
                "planning" in q,
                "horaire" in q,
                "quel cours" in q,
                "quels cours" in q,
                "cours" in q,
                "seance" in q,
                "tp" in q.split(),
                "mon cours" in q,
                "mes cours" in q,
                "j ai cours" in q,
                "demain" in q,
                "aujourd" in q,
                "hier" in q,
                any(day in q for day in ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]),
            ]
        )
        if not needs_class:
            return None
        if not self._extract_class_candidate(question):
            return "Quelle est votre classe ? (ex: 2 ING GII 3, 1 TIC 2, 2 TIC-T, etc.)"
        return None

    # --- SQL generation ---

    def generate_sql(self, question: str, context: dict, schema_info: str) -> Optional[str]:
        if not self.enabled:
            return None

        periode_id = context.get("periode_id")
        semestre_id = context.get("semestre_id")
        annee_id = context.get("annee_id", 1)
        today_day_name = context.get("jour_actuel") or context.get("jour_nom") or ""
        resolved_class = self._extract_class_candidate(question) or "MISSING"

        prompt = f"""You are a PostgreSQL expert. Return ONLY ONE SQL SELECT query, or ASK_CLASS / ASK_PROF.

DATABASE SCHEMA:
{schema_info}

CONTEXT:
- Current Periode ID: {periode_id if periode_id is not None else 'NULL'}
- Current Semestre ID: {semestre_id if semestre_id is not None else 'NULL'}
- Current Annee ID: {annee_id}
- Today date: {context.get('date_actuelle', 'unknown')}
- Today weekday name (French): {today_day_name if today_day_name else 'UNKNOWN'}
- Resolved class from the question: {resolved_class}

USER QUESTION (French):
{question}

STRICT RULES:
A) If the question is about timetable/seances AND the class is missing -> return exactly: ASK_CLASS
B) If the question is about timetable for a professor AND professor name is missing -> return exactly: ASK_PROF
C) Never output markdown. Never output explanations. ONLY the SQL (or ASK_*).
D) ALWAYS output ONE SELECT statement. No INSERT/UPDATE/DELETE/DDL.
E) NEVER use c.id directly to match the class.
F) If class is available, use:
   REPLACE(LOWER(c.nom), ' ', '') LIKE '%' || REPLACE(LOWER('{resolved_class}'), ' ', '') || '%'
G) Active timetable version:
   JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id
H) If you filter by day, use LOWER(s.jour) = LOWER('Lundi') style matching.
I) For rooms, use alias sa and sa.nom.
J) For calendar questions, use vacances_jours_feries (nom, date_debut, date_fin, type, annee_id).

SQL:"""

        response = self._post_with_retry(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a PostgreSQL expert. Return only ONE SELECT query or ASK_CLASS/ASK_PROF. No explanations. No markdown."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.0,
                "max_tokens": 2000,
            }
        )
        if response is None or response.status_code != 200:
            if response is not None:
                print(f"Groq API error: {response.status_code} - {response.text}")
            return None

        payload = self._safe_json(response)
        if not payload:
            return None

        raw = (payload.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
        print(f"[DEBUG] Raw SQL from Groq: {raw}")

        sql = self._clean_sql(raw)
        if sql in {"ASK_CLASS", "ASK_PROF"}:
            return sql
        if not self._validate_select_only(sql):
            print("[DEBUG] Groq returned non-SELECT.")
            return None

        print(f"[DEBUG] Cleaned SQL: {sql}")
        return sql

    # --- Response formatting ---

    def format_response(self, question: str, data: list, context: dict) -> Optional[str]:
        if not data:
            return "Aucune donnee trouvee pour cette question."

        if all(("date_debut" in row and "date_fin" in row and ("nom" in row or "Nom" in row)) for row in data):
            lines = []
            for row in data[:80]:
                nom = row.get("nom") or row.get("Nom") or ""
                event_type = row.get("type") or row.get("Type") or ""
                date_start = row.get("date_debut") or row.get("DateDebut")
                date_end = row.get("date_fin") or row.get("DateFin")
                lines.append(f"{date_start} -> {date_end} | {event_type} | {nom}")
            return "\n".join(lines).strip()

        lookup_response = self._format_lookup_response(question, data)
        if lookup_response:
            return lookup_response

        timetable_response = self._format_timetable_response(data)
        if timetable_response:
            return timetable_response

        if not self.enabled:
            return None

        data_str = "\n".join([str(dict(row)) for row in data[:80]])
        prompt = f"""You are a professional French university assistant.

USER QUESTION: {question}
ACADEMIC CONTEXT:
- Semestre: {context.get('semestre')}
- Periode: {context.get('periode')}
- Date: {context.get('date_actuelle')}

SQL RESULTS ({len(data)} rows):
{data_str}

Return plain French text with line breaks and no markdown."""

        response = self._post_with_retry(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a professional French university assistant. Format responses clearly with line breaks. No markdown."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 1000,
            },
            timeout=30,
        )
        if response is None or response.status_code != 200:
            if response is not None:
                print(f"Groq format error: {response.status_code} - {response.text}")
            return None

        payload = self._safe_json(response)
        if not payload:
            return None

        raw = (payload.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
        return self._postprocess_response(raw)

    def _postprocess_response(self, text: str) -> str:
        if not text:
            return text
        text = text.replace("**", "")
        text = re.sub(r"\s*(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})\s*", r"\n\n\1 ", text).strip()
        text = re.sub(r"\s+(Professeur\s*:)\s*", r"\n\1 ", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+(Salle\s*:)\s*", r"\n\1 ", text, flags=re.IGNORECASE)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


groq_service = GroqService()
