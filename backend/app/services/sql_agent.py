# backend/app/services/sql_agent.py
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from threading import Lock
from time import monotonic
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

PROFESSOR_DIRECTORY_CACHE_TTL_SECONDS = 600
_PROFESSOR_DIRECTORY_CACHE_LOCK = Lock()
_PROFESSOR_DIRECTORY_CACHE: dict[str, Any] = {
    "loaded_at": 0.0,
    "reference_names": None,
    "all_names": None,
}
PROFESSOR_CONNECTOR_TOKENS = {
    "ben",
    "ibn",
    "ould",
    "bint",
    "el",
    "al",
}


class SQLAgent:
    def __init__(self, db: Session):
        self.db = db
        self._exec_and_format = self._exec_and_format_v2
        self._reference_professor_names_cache: Optional[list[str]] = None
        self._all_professor_names_cache: Optional[list[str]] = None
        self._candidate_professor_names_cache: dict[str, list[str]] = {}
        self._canonical_professor_name_cache: dict[str, str] = {}
        self._hydrate_professor_caches_from_global()

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

    def _hydrate_professor_caches_from_global(self) -> None:
        cached_all_names = _PROFESSOR_DIRECTORY_CACHE.get("all_names")
        cached_reference_names = _PROFESSOR_DIRECTORY_CACHE.get("reference_names")
        loaded_at = float(_PROFESSOR_DIRECTORY_CACHE.get("loaded_at") or 0.0)
        if not cached_all_names or not cached_reference_names:
            return
        if monotonic() - loaded_at > PROFESSOR_DIRECTORY_CACHE_TTL_SECONDS:
            return

        self._all_professor_names_cache = list(cached_all_names)
        self._reference_professor_names_cache = list(cached_reference_names)

    def _store_professor_caches_globally(self, all_names: list[str], reference_names: list[str]) -> None:
        if not all_names or not reference_names:
            return
        with _PROFESSOR_DIRECTORY_CACHE_LOCK:
            _PROFESSOR_DIRECTORY_CACHE["loaded_at"] = monotonic()
            _PROFESSOR_DIRECTORY_CACHE["all_names"] = list(all_names)
            _PROFESSOR_DIRECTORY_CACHE["reference_names"] = list(reference_names)

    def _split_professor_name_variants(self, value: str) -> list[str]:
        variants = []
        for part in re.split(r"\s*/\s*", value or ""):
            cleaned = self._clean_professor_display_name(part)
            if cleaned:
                variants.append(cleaned)
        return list(dict.fromkeys(variants))

    def _professor_name_signature(self, value: str) -> str:
        tokens = self._professor_tokens_for_match(value)
        return " ".join(sorted(tokens))

    def _professor_display_rank(self, value: str) -> tuple[int, int, int, int]:
        cleaned = self._clean_professor_display_name(value)
        tokens = self._professor_tokens_for_match(cleaned)
        full_tokens = sum(1 for token in tokens if len(token) > 1 and token not in PROFESSOR_CONNECTOR_TOKENS)
        return (
            1 if "." not in cleaned else 0,
            1 if "/" not in cleaned else 0,
            full_tokens,
            len(cleaned),
        )

    def _dedupe_professor_display_names(self, names: list[str]) -> list[str]:
        best_by_signature: dict[str, str] = {}
        for name in names:
            cleaned = self._clean_professor_display_name(name)
            if not cleaned:
                continue
            signature = self._professor_name_signature(cleaned) or self._norm(cleaned)
            current_best = best_by_signature.get(signature)
            if current_best is None or self._professor_display_rank(cleaned) > self._professor_display_rank(current_best):
                best_by_signature[signature] = cleaned
        return sorted(best_by_signature.values(), key=lambda item: self._normalize_text(item))

    def _load_reference_professor_names_from_db(self) -> list[str]:
        if not self.db:
            return []
        try:
            rows = self.db.execute(
                text(
                    """
                    SELECT DISTINCT te.professeur_nom_complet
                    FROM emplois_enseignants_seances te
                    WHERE te.professeur_nom_complet IS NOT NULL AND TRIM(te.professeur_nom_complet) <> ''
                    ORDER BY te.professeur_nom_complet
                    """
                )
            ).fetchall()
        except Exception:
            rows = []

        reference_names: list[str] = []
        for row in rows:
            reference_names.extend(self._split_professor_name_variants(str(row[0] or "").strip()))

        if not reference_names:
            try:
                rows = self.db.execute(
                    text(
                        """
                        SELECT DISTINCT p.nom_complet
                        FROM professeurs p
                        WHERE p.nom_complet IS NOT NULL AND TRIM(p.nom_complet) <> ''
                        ORDER BY p.nom_complet
                        """
                    )
                ).fetchall()
            except Exception:
                rows = []
            for row in rows:
                reference_names.extend(self._split_professor_name_variants(str(row[0] or "").strip()))

        return self._dedupe_professor_display_names(reference_names)

    def _load_all_professor_names_from_db(self) -> list[str]:
        if not self.db:
            return []
        try:
            rows = self.db.execute(
                text(
                    """
                    SELECT DISTINCT name
                    FROM (
                        SELECT nom_complet AS name FROM professeurs
                        UNION
                        SELECT professeur_nom_complet AS name FROM emplois_enseignants_seances
                    ) names
                    WHERE name IS NOT NULL AND TRIM(name) <> ''
                    ORDER BY name
                    """
                )
            ).fetchall()
        except Exception:
            return []

        names = []
        for row in rows:
            names.extend(self._candidate_professor_names(str(row[0] or "").strip()))
        return self._dedupe_professor_display_names([name for name in names if name])

    def _collapse_repeated_letters(self, token: str) -> str:
        return re.sub(r"([a-z0-9])\1+", r"\1", token or "")

    def _normalized_token_parts(self, value: str) -> list[str]:
        return [
            re.sub(r"[^a-z0-9]", "", self._normalize_text(part))
            for part in re.split(r"[\s/-]+", value or "")
            if part.strip()
        ]

    def _significant_professor_tokens(self, value: str) -> list[str]:
        return [
            token
            for token in self._professor_tokens_for_match(value)
            if token and token not in PROFESSOR_CONNECTOR_TOKENS
        ]

    def _has_professor_connector_token(self, value: str) -> bool:
        return any(token in PROFESSOR_CONNECTOR_TOKENS for token in self._professor_tokens_for_match(value))

    def _string_similarity(self, left: str, right: str) -> float:
        left_value = left or ""
        right_value = right or ""
        if not left_value or not right_value:
            return 0.0

        left_compact = self._collapse_repeated_letters(left_value)
        right_compact = self._collapse_repeated_letters(right_value)
        return max(
            SequenceMatcher(None, left_value, right_value).ratio(),
            SequenceMatcher(None, left_compact, right_compact).ratio(),
        )

    def _score_professor_candidate(self, requested_name: str, candidate_name: str) -> float:
        requested_tokens = self._normalized_token_parts(requested_name)
        candidate_tokens = self._normalized_token_parts(candidate_name)
        if not requested_tokens or not candidate_tokens:
            return 0.0

        requested_significant = self._significant_professor_tokens(requested_name)
        candidate_significant = self._significant_professor_tokens(candidate_name)
        if not requested_significant or not candidate_significant:
            return 0.0

        requested_joined = "".join(requested_tokens)
        candidate_joined = "".join(candidate_tokens)
        score = self._string_similarity(requested_joined, candidate_joined)

        requested_surname = requested_significant[-1]
        surname_score = max(self._string_similarity(requested_surname, candidate_token) for candidate_token in candidate_significant)
        same_surname_initial = any(candidate_token[:1] == requested_surname[:1] for candidate_token in candidate_significant if candidate_token)
        score = max(score, surname_score)

        token_pair_score = 0.0
        for requested_token in requested_significant:
            if len(requested_token) < 3:
                continue
            candidate_scores = [
                self._string_similarity(requested_token, candidate_token)
                for candidate_token in candidate_significant
                if len(candidate_token) >= 3
            ]
            if not candidate_scores:
                continue
            token_pair_score = max(
                token_pair_score,
                max(candidate_scores),
            )
        score = max(score, token_pair_score)

        common_tokens = set(requested_significant) & set(candidate_significant)
        if common_tokens:
            score += 0.08 * (len(common_tokens) / max(len(set(requested_tokens)), len(set(candidate_tokens))))
        first_score = max(self._string_similarity(requested_significant[0], candidate_token) for candidate_token in candidate_significant)
        if self._has_professor_connector_token(requested_name):
            if self._has_professor_connector_token(candidate_name):
                score += 0.08
            else:
                score -= 0.2
        if same_surname_initial:
            score += 0.06
        elif len(requested_surname) >= 3:
            score -= 0.14
        if requested_significant[0][0] == candidate_significant[0][0]:
            score += 0.04
        if surname_score >= 0.72:
            score += 0.12
        if first_score >= 0.88:
            score += 0.08
        elif first_score < 0.55:
            score -= 0.18
        if surname_score < 0.45:
            score -= 0.28
        if not common_tokens and surname_score < 0.55:
            score -= 0.18
        if " / " in candidate_name:
            score -= 0.12

        return min(max(score, 0.0), 0.99)

    def _surname_similarity(self, requested_name: str, candidate_name: str) -> float:
        requested_tokens = self._significant_professor_tokens(requested_name)
        candidate_tokens = self._significant_professor_tokens(candidate_name)
        if not requested_tokens or not candidate_tokens:
            return 0.0
        return max(self._string_similarity(requested_tokens[-1], candidate_token) for candidate_token in candidate_tokens)

    def _is_relevant_professor_candidate(self, requested_name: str, candidate_name: str) -> bool:
        requested_tokens = [token for token in self._significant_professor_tokens(requested_name) if len(token) >= 2]
        candidate_tokens = [token for token in self._significant_professor_tokens(candidate_name) if len(token) >= 2]
        if not requested_tokens or not candidate_tokens:
            return False

        if len(requested_tokens) == 1:
            return any(
                requested_tokens[0] == candidate_token
                or requested_tokens[0].startswith(candidate_token)
                or candidate_token.startswith(requested_tokens[0])
                for candidate_token in candidate_tokens
            )

        surname_score = self._surname_similarity(requested_name, candidate_name)
        first_score = max(self._string_similarity(requested_tokens[0], candidate_token) for candidate_token in candidate_tokens)
        same_surname_initial = any(candidate_token[:1] == requested_tokens[-1][:1] for candidate_token in candidate_tokens if candidate_token)
        if self._has_professor_connector_token(requested_name) and not self._has_professor_connector_token(candidate_name) and surname_score < 0.72:
            return False
        overlapping_tokens = {
            req
            for req in requested_tokens[1:]
            for cand in candidate_tokens
            if req == cand or req.startswith(cand) or cand.startswith(req)
        }
        return (
            surname_score >= 0.72
            or (surname_score >= 0.58 and first_score >= 0.82)
            or (first_score >= 0.9 and same_surname_initial and self._has_professor_connector_token(candidate_name))
            or (first_score >= 0.9 and bool(overlapping_tokens))
            or len(overlapping_tokens) >= 2
        )

    def _rank_professor_candidates(self, prof_name: str, min_score: float = 0.58, limit: int = 3) -> list[str]:
        requested_key = "".join(self._normalized_token_parts(prof_name))
        if not requested_key:
            return []

        scored_matches: list[tuple[float, int, str]] = []
        seen_keys = set()

        for candidate_name in self._all_professor_names():
            candidate_key = "".join(self._normalized_token_parts(candidate_name))
            if not candidate_key or candidate_key == requested_key or candidate_key in seen_keys:
                continue
            seen_keys.add(candidate_key)

            if not self._is_relevant_professor_candidate(prof_name, candidate_name):
                continue

            score = self._score_professor_candidate(prof_name, candidate_name)
            if score < min_score:
                continue

            scored_matches.append((score, abs(len(candidate_key) - len(requested_key)), candidate_name))

        scored_matches.sort(key=lambda item: (-item[0], item[1], item[2].lower()))
        if not scored_matches:
            return []

        best_score = scored_matches[0][0]
        filtered = [item for item in scored_matches if item[0] >= max(min_score, best_score - 0.08)]
        selected: list[tuple[str, str]] = []
        for _, _, name in filtered:
            suggestion_key = "".join(self._normalized_token_parts(self._clean_professor_display_name(name)))
            if not suggestion_key:
                continue

            replaced = False
            should_skip = False
            for index, (existing_key, _) in enumerate(selected):
                if suggestion_key == existing_key:
                    should_skip = True
                    break
                if suggestion_key.startswith(existing_key) or existing_key.startswith(suggestion_key):
                    if len(suggestion_key) > len(existing_key):
                        selected[index] = (suggestion_key, name)
                        replaced = True
                    else:
                        should_skip = True
                    break

            if should_skip:
                continue
            if not replaced:
                selected.append((suggestion_key, name))
            if len(selected) >= limit:
                break

        return [name for _, name in selected[:limit]]

    def _find_similar_professors(self, prof_name: str, limit: int = 3) -> list[str]:
        return self._rank_professor_candidates(prof_name, min_score=0.7, limit=limit)

    def _all_professor_names(self) -> list[str]:
        if self._all_professor_names_cache is not None:
            return self._all_professor_names_cache
        self._hydrate_professor_caches_from_global()
        if self._all_professor_names_cache is not None:
            return self._all_professor_names_cache

        if self._reference_professor_names_cache is None:
            self._reference_professor_names_cache = self._load_reference_professor_names_from_db()
        self._all_professor_names_cache = self._load_all_professor_names_from_db()
        self._store_professor_caches_globally(
            self._all_professor_names_cache,
            self._reference_professor_names_cache or [],
        )
        return self._all_professor_names_cache

    def _reference_professor_names(self) -> list[str]:
        if self._reference_professor_names_cache is not None:
            return self._reference_professor_names_cache
        self._hydrate_professor_caches_from_global()
        if self._reference_professor_names_cache is not None:
            return self._reference_professor_names_cache

        self._reference_professor_names_cache = self._load_reference_professor_names_from_db()
        return self._reference_professor_names_cache

    def _clean_professor_display_name(self, value: str) -> str:
        cleaned = re.sub(r"\s+", " ", (value or "")).strip()
        cleaned = re.sub(r"^(?:(?:mr|mme|m\.|monsieur|madame)\s+)+", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;/")
        return cleaned

    def _candidate_professor_names(self, value: str) -> list[str]:
        cache_key = value or ""
        if cache_key in self._candidate_professor_names_cache:
            return self._candidate_professor_names_cache[cache_key]
        if not value:
            return []
        parts = re.split(r"\s*/\s*", value)
        candidates = []
        for part in parts:
            cleaned = self._clean_professor_display_name(part)
            if not cleaned:
                continue
            candidates.append(self._canonical_professor_name(cleaned))
        result = list(dict.fromkeys(candidate for candidate in candidates if candidate))
        self._candidate_professor_names_cache[cache_key] = result
        return result

    def _canonical_professor_name(self, value: str) -> str:
        cleaned = self._clean_professor_display_name(value)
        if not cleaned:
            return ""
        if cleaned in self._canonical_professor_name_cache:
            return self._canonical_professor_name_cache[cleaned]

        input_tokens = self._professor_tokens_for_match(cleaned)
        if not input_tokens:
            return cleaned

        references = self._reference_professor_names()
        if not references:
            return cleaned

        exact_matches = []
        initial_matches = []
        input_signature = sorted(input_tokens)

        for reference in references:
            ref_tokens = self._professor_tokens_for_match(reference)
            if not ref_tokens:
                continue
            if sorted(ref_tokens) == input_signature:
                exact_matches.append(reference)
                continue
            if self._tokens_match_professor_reference(input_tokens, ref_tokens):
                initial_matches.append(reference)

        if len(exact_matches) == 1:
            self._canonical_professor_name_cache[cleaned] = exact_matches[0]
            return exact_matches[0]
        if len(initial_matches) == 1:
            self._canonical_professor_name_cache[cleaned] = initial_matches[0]
            return initial_matches[0]
        self._canonical_professor_name_cache[cleaned] = cleaned
        return cleaned

    def _tokens_match_professor_reference(self, input_tokens: list[str], ref_tokens: list[str]) -> bool:
        remaining = list(ref_tokens)
        for token in input_tokens:
            match_index = None
            for index, ref_token in enumerate(remaining):
                if token == ref_token:
                    match_index = index
                    break
                if len(token) == 1 and ref_token.startswith(token):
                    match_index = index
                    break
                if len(token) >= 3 and len(ref_token) >= 3 and (token.startswith(ref_token) or ref_token.startswith(token)):
                    match_index = index
                    break
            if match_index is None:
                return False
            remaining.pop(match_index)
        return True

    def _professor_tokens_for_match(self, value: str) -> list[str]:
        titles = {"mr", "mme", "m", "monsieur", "madame"}
        return [token for token in self._normalized_token_parts(value) if token and token not in titles]

    def _find_exact_professor_names(self, prof_name: str) -> list[str]:
        requested_tokens = self._professor_tokens_for_match(prof_name)
        if not requested_tokens:
            return []

        requested_joined = "".join(requested_tokens)
        requested_signature = sorted(requested_tokens)
        matches = []
        for candidate_name in self._all_professor_names():
            candidate_tokens = self._professor_tokens_for_match(candidate_name)
            if not candidate_tokens:
                continue
            if "".join(candidate_tokens) == requested_joined or sorted(candidate_tokens) == requested_signature:
                matches.append(candidate_name)
        return list(dict.fromkeys(matches))

    def _resolve_professor_name(self, prof_name: str) -> Optional[str]:
        if not prof_name:
            return None

        exact_matches = self._find_exact_professor_names(prof_name)
        if len(exact_matches) == 1:
            return exact_matches[0]

        requested_tokens = [token for token in self._professor_tokens_for_match(prof_name) if len(token) >= 3]
        matches = self._find_matching_professors(prof_name)
        if len(requested_tokens) >= 2 and len(matches) == 1:
            return matches[0]

        return None

    def _find_matching_professors(self, prof_name: str, limit: int = 3) -> list[str]:
        requested_tokens = [token for token in self._professor_tokens_for_match(prof_name) if len(token) >= 3]
        if not requested_tokens:
            return []

        min_score = 0.78 if len(requested_tokens) >= 2 else 0.88
        return self._rank_professor_candidates(prof_name, min_score=min_score, limit=limit)

    def _exact_professor_match_condition(self, prof_name: str, field_sql: str = "p.nom_complet") -> Optional[str]:
        cleaned_name = self._clean_professor_display_name(prof_name)
        target_key = "".join(self._normalized_token_parts(cleaned_name))
        if not target_key:
            return None
        expr = f"REPLACE(REPLACE(REPLACE(LOWER({field_sql}), ' ', ''), '.', ''), '-', '')"
        return f"{expr} = '{target_key}'"

    def _best_professor_match_condition(self, prof_name: str, field_sql: str = "p.nom_complet") -> Optional[str]:
        resolved_name = self._resolve_professor_name(prof_name) or prof_name
        return self._exact_professor_match_condition(resolved_name, field_sql) or self._professor_match_condition(resolved_name, field_sql)

    def _professor_confirmation_message(self, prof_name: str) -> Optional[str]:
        if not prof_name:
            return None

        exact_matches = self._find_exact_professor_names(prof_name)
        if exact_matches:
            return None

        requested_tokens = [token for token in self._professor_tokens_for_match(prof_name) if len(token) >= 3]
        matches = self._find_matching_professors(prof_name)

        if len(requested_tokens) <= 1:
            if len(matches) == 1:
                return f"Voulez-vous dire le professeur '{matches[0]}' ?"
            if matches:
                return f"Je ne suis pas sur du professeur '{prof_name}'. Voulez-vous dire : {', '.join(matches)} ?"

        if len(matches) == 1:
            return f"Le nom '{prof_name}' ressemble a '{matches[0]}'. Voulez-vous dire ce professeur ?"
        if len(matches) > 1:
            return f"Le nom '{prof_name}' est ambigu. Voulez-vous dire : {', '.join(matches)} ?"

        similar = self._find_similar_professors(prof_name)
        if len(similar) == 1:
            return f"Le nom '{prof_name}' ressemble a '{similar[0]}'. Voulez-vous dire ce professeur ?"
        if similar:
            return f"Le nom '{prof_name}' est proche de plusieurs professeurs. Voulez-vous dire : {', '.join(similar)} ?"

        return None

    def _score_room_candidate(self, requested_room: str, candidate_room: str) -> float:
        requested_key = self._room_key(requested_room)
        candidate_key = self._room_key(candidate_room)
        if not requested_key or not candidate_key:
            return 0.0

        score = self._string_similarity(requested_key, candidate_key)
        if requested_key[:1] and requested_key[:1] == candidate_key[:1]:
            score += 0.08
        if requested_key[-1:] and requested_key[-1:] == candidate_key[-1:]:
            score += 0.05
        return min(score, 0.99)

    def _find_similar_rooms(self, room_name: str, limit: int = 5) -> list[str]:
        if not self.db or not room_name:
            return []

        try:
            rows = self.db.execute(
                text(
                    """
                    SELECT DISTINCT sa.nom
                    FROM salles sa
                    WHERE sa.nom IS NOT NULL AND TRIM(sa.nom) <> ''
                    """
                )
            ).fetchall()
        except Exception:
            return []

        requested_key = self._room_key(room_name)
        scored_matches: list[tuple[float, int, str]] = []
        seen_keys = set()

        for row in rows:
            candidate_name = str(row[0] or "").strip()
            candidate_key = self._room_key(candidate_name)
            if not candidate_key or candidate_key == requested_key or candidate_key in seen_keys:
                continue
            seen_keys.add(candidate_key)

            score = self._score_room_candidate(room_name, candidate_name)
            if score < 0.55:
                continue

            scored_matches.append((score, abs(len(candidate_key) - len(requested_key)), self._normalize_room_name(candidate_name)))

        scored_matches.sort(key=lambda item: (-item[0], item[1], item[2].lower()))
        return [name for _, _, name in scored_matches[:limit]]

    def _prof_not_found_message(self, prof_name: str) -> str:
        suggestions = self._find_similar_professors(prof_name)
        if suggestions:
            return (
                f"Le professeur '{prof_name}' n'existe pas dans la base de donnees. "
                f"Voici des noms similaires : {', '.join(suggestions)}."
            )
        return f"Je ne trouve pas le professeur '{prof_name}' dans la base de donnees."

    def _room_not_found_message(self, room_name: str) -> str:
        suggestions = self._find_similar_rooms(room_name)
        if suggestions:
            return (
                f"La salle '{room_name}' n'existe pas dans la base de donnees. "
                f"Voici des salles similaires : {', '.join(suggestions)}."
            )
        return f"Je ne trouve pas la salle '{room_name}' dans la base de donnees."

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
            "j ai quoi",
            "jai quoi",
            "andi",
            "ghedwa",
            "tawa",
        ]
        if any(m in q for m in markers):
            return True
        if "emp" in q and ("temps" in q or "planning" in q or "horaire" in q):
            return True
        if self._extract_class_candidate(question) and any(day in q for day in ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche", "aujourd", "demain", "hier"]):
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
            "absence",
            "absences",
            "extranet",
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
        shorthand_codes = {"GII", "GEC", "GT", "IDSD", "INFO", "TELECOM"}

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

        m2 = re.search(r"\b(\d)\s*([A-Za-z\-]{2,10})\s*(\d)\b", q, flags=re.IGNORECASE)
        if m2:
            a, mid, b = m2.group(1), m2.group(2), m2.group(3)
            mid_u = mid.upper()
            if mid_u in shorthand_codes:
                return f"{a} ING {mid_u} {b}"
            return f"{a} {mid_u} {b}"

        m3 = re.search(r"\b(\d)(GII|GEC|GT|IDSD|INFO|TELECOM)(\d)\b", q, flags=re.IGNORECASE)
        if m3:
            year, specialty, group = m3.group(1), m3.group(2).upper(), m3.group(3)
            return f"{year} ING {specialty} {group}"

        return None

    def _class_key(self, class_name: str) -> str:
        return re.sub(r"[\s-]+", "", self._normalize_text(class_name or ""))

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
        key = self._class_key(class_name)
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

    def _is_class_schedule_question(self, question: str) -> bool:
        q = self._normalize_text(question)
        if not self._is_schedule_intent(question):
            if not (self._extract_class_candidate(question) and any(day in q for day in ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche", "aujourd", "demain", "hier"])):
                return False
        if not self._extract_class_candidate(question):
            return False
        if self._extract_room_candidate(question):
            return False
        if self._extract_schedule_prof_candidate(question) or self._extract_prof_candidate(question):
            return False
        return True

    def _is_class_location_question(self, question: str) -> bool:
        q = self._normalize_text(question)
        if not self._extract_class_candidate(question):
            return False
        location_markers = ["ou se trouve", "ou est", "dans quelle salle", "salle"]
        return "classe" in q and any(marker in q for marker in location_markers)

    def _class_schedule_period_id(self, question: str, context: dict) -> Optional[int]:
        q = (question or "").lower()
        want_p1 = bool(re.search(r"\bp\s*1\b", q))
        want_p2 = bool(re.search(r"\bp\s*2\b", q))
        if want_p1 and want_p2:
            return None

        if (want_p1 or want_p2) and context.get("semestre_id") and self.db:
            marker = "P1" if want_p1 else "P2"
            row = self.db.execute(
                text(
                    """
                    SELECT id
                    FROM periodes
                    WHERE semestre_id = :semester_id
                      AND UPPER(nom) = :periode_nom
                    LIMIT 1
                    """
                ),
                {
                    "semester_id": int(context["semestre_id"]),
                    "periode_nom": marker,
                },
            ).first()
            return int(row[0]) if row else None

        if self._is_full_schedule_request(question):
            return None

        current_period_id = context.get("periode_id")
        return int(current_period_id) if current_period_id else None

    def _class_schedule_sql(self, question: str, context: dict) -> Tuple[str, Dict[str, Any]]:
        cls = self._extract_class_candidate(question) or ""
        cls = self._normalize_class_aliases(cls, context)
        requested_day = self._extract_requested_day(question, context)

        sql = """
        SELECT
            c.nom AS classe,
            m.nom AS matiere,
            p.nom_complet AS professeur,
            sa.nom AS salle,
            s.jour,
            s.heure_debut,
            s.heure_fin,
            s.type_seance
        FROM seances s
        JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id
        JOIN classes c ON c.id = s.classe_id
        JOIN matieres m ON m.id = s.matiere_id
        JOIN professeurs p ON p.id = s.professeur_id
        JOIN salles sa ON sa.id = s.salle_id
        WHERE REPLACE(REPLACE(LOWER(c.nom), ' ', ''), '-', '') = :class_key
        """
        params: Dict[str, Any] = {
            "class_key": self._class_key(cls),
        }

        target_period_id = self._class_schedule_period_id(question, context)
        if target_period_id:
            sql += " AND s.periode_id = :periode_id\n"
            params["periode_id"] = target_period_id

        if requested_day:
            sql += " AND LOWER(s.jour) = LOWER(:target_day)\n"
            params["target_day"] = requested_day

        sql += (
            " ORDER BY CASE LOWER(s.jour) "
            "WHEN 'lundi' THEN 1 WHEN 'mardi' THEN 2 WHEN 'mercredi' THEN 3 "
            "WHEN 'jeudi' THEN 4 WHEN 'vendredi' THEN 5 WHEN 'samedi' THEN 6 "
            "WHEN 'dimanche' THEN 7 ELSE 8 END, s.heure_debut, s.heure_fin;"
        )
        return sql, params

    def _class_location_sql(self, question: str, context: dict) -> Tuple[str, Dict[str, Any]]:
        cls = self._extract_class_candidate(question) or ""
        cls = self._normalize_class_aliases(cls, context)
        requested_day = self._extract_requested_day(question, context)
        target_day = requested_day or context.get("jour_actuel") or DAY_MAP_ISO[self._context_date(context).isoweekday()]
        restrict_to_now = self._question_mentions_now(question) or not requested_day

        sql = """
        SELECT c.nom AS classe, sa.nom AS salle, s.jour, s.heure_debut, s.heure_fin
        FROM seances s
        JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id
        JOIN classes c ON c.id = s.classe_id
        JOIN salles sa ON sa.id = s.salle_id
        WHERE REPLACE(REPLACE(LOWER(c.nom), ' ', ''), '-', '') = :class_key
          AND LOWER(s.jour) = LOWER(:target_day)
        """
        params: Dict[str, Any] = {
            "class_key": self._class_key(cls),
            "target_day": target_day,
        }
        if restrict_to_now:
            sql += " AND :current_time >= s.heure_debut AND :current_time < s.heure_fin\n"
            params["current_time"] = datetime.now().time().strftime("%H:%M:%S")
        if context.get("periode_id"):
            sql += " AND s.periode_id = :periode_id\n"
            params["periode_id"] = int(context["periode_id"])

        sql += " ORDER BY s.heure_debut, sa.nom;"
        return sql, params

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
                ("classe" in q_lower and ("ou se trouve" in q_lower or "ou est" in q_lower or "dans quelle salle" in q_lower)),
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
        condition = self._best_professor_match_condition(prof_name, "te.professeur_nom_complet")
        if not condition:
            return False
        row = self.db.execute(
            text(f"SELECT 1 FROM emplois_enseignants_seances te WHERE {condition} LIMIT 1")
        ).first()
        return bool(row)

    def _prof_exists_in_db(self, prof_name: str) -> bool:
        if self._teacher_prof_exists_in_db(prof_name):
            return True
        condition = self._best_professor_match_condition(prof_name)
        if not condition or not self.db:
            return False

        row = self.db.execute(
            text(f"SELECT 1 FROM professeurs p WHERE {condition} LIMIT 1")
        ).first()
        return bool(row)

    def _teacher_prof_schedule_sql(self, question: str, context: dict) -> Tuple[str, Dict[str, Any]]:
        prof_name = self._extract_schedule_prof_candidate(question) or self._extract_prof_candidate(question) or ""
        prof_name = self._resolve_professor_name(prof_name) or prof_name
        prof_condition = self._best_professor_match_condition(prof_name, "te.professeur_nom_complet") or "1=0"
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
        requested_periode = self._schedule_periode_name(question, context)
        if requested_periode:
            sql += " AND UPPER(te.periode_nom) = :periode_nom\n"
            params["periode_nom"] = requested_periode
        if requested_day:
            sql += " AND LOWER(te.jour) = LOWER(:target_day)\n"
            params["target_day"] = requested_day
        sql += " ORDER BY CASE LOWER(te.jour) WHEN 'lundi' THEN 1 WHEN 'mardi' THEN 2 WHEN 'mercredi' THEN 3 WHEN 'jeudi' THEN 4 WHEN 'vendredi' THEN 5 WHEN 'samedi' THEN 6 WHEN 'dimanche' THEN 7 ELSE 8 END, te.heure_debut, te.heure_fin;"
        return sql, params

    def _schedule_periode_name(self, question: str, context: dict) -> Optional[str]:
        q = (question or "").lower()
        want_p1 = bool(re.search(r"\bp\s*1\b", q))
        want_p2 = bool(re.search(r"\bp\s*2\b", q))
        if want_p1 and not want_p2:
            return "P1"
        if want_p2 and not want_p1:
            return "P2"
        if self._question_is_day_specific(question) or self._question_mentions_now(question):
            periode = context.get("periode")
            return str(periode).upper() if periode else None
        return None

    def _is_valid_prof_candidate_text(self, candidate: str) -> bool:
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
            "donner lavis dabsence",
            "lavis dabsence",
            "avis dabsence",
            "avis d absence",
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
            "absence",
            "absences",
            "avis",
            "lavis",
            "dabsence",
            "donner",
            "extranet",
            "login",
            "connexion",
        }
        return not (
            normalized_candidate in invalid_candidates
            or any(token in invalid_tokens for token in candidate_tokens)
        )

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

        if not self._is_valid_prof_candidate_text(candidate):
            return None

        return candidate

    def _extract_room_candidate(self, question: str) -> Optional[str]:
        question_text = question or ""
        patterns = [
            r"\bsalle\s+([A-Za-z0-9][A-Za-z0-9\- ]*)\b",
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

    def _normalize_room_name(self, room_name: str) -> str:
        if not room_name:
            return ""
        room = re.sub(r"\s+", " ", room_name).strip().upper()
        room = re.sub(r"\b([A-Z])\s+(\d{2})\b", r"\1\2", room)
        room = re.sub(r"\b([A-Z])\s*0?(\d)\b", lambda match: f"{match.group(1)}{int(match.group(2)):02d}", room)
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

    def _is_room_schedule_question(self, question: str) -> bool:
        return self._is_schedule_intent(question) and bool(self._extract_room_candidate(question))

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

    def _room_schedule_sql(self, question: str, context: dict) -> Tuple[str, Dict[str, Any]]:
        room_name = self._extract_room_candidate(question) or ""
        requested_day = self._extract_requested_day(question, context)
        sql = """
        SELECT
            c.nom AS classe,
            m.nom AS matiere,
            p.nom_complet AS professeur,
            sa.nom AS salle,
            s.jour,
            s.heure_debut,
            s.heure_fin
        FROM seances s
        JOIN emplois_versions v ON v.id = s.version_id AND v.actif = true AND v.classe_id = s.classe_id
        JOIN salles sa ON sa.id = s.salle_id
        LEFT JOIN classes c ON c.id = s.classe_id
        LEFT JOIN matieres m ON m.id = s.matiere_id
        LEFT JOIN professeurs p ON p.id = s.professeur_id
        WHERE REPLACE(REPLACE(LOWER(sa.nom), ' ', ''), '-', '') = :room_name
        """
        params: Dict[str, Any] = {"room_name": self._room_key(room_name)}
        if requested_day:
            sql += " AND LOWER(s.jour) = LOWER(:target_day)\n"
            params["target_day"] = requested_day
        requested_periode = self._schedule_periode_name(question, context)
        if requested_periode and context.get("semestre_id"):
            sql += """
            AND s.periode_id = (
                SELECT p.id
                FROM periodes p
                WHERE p.semestre_id = :semester_id
                  AND UPPER(p.nom) = :periode_nom
                LIMIT 1
            )\n
            """
            params["semester_id"] = int(context["semestre_id"])
            params["periode_nom"] = requested_periode

        sql += (
            " ORDER BY CASE LOWER(s.jour) "
            "WHEN 'lundi' THEN 1 WHEN 'mardi' THEN 2 WHEN 'mercredi' THEN 3 "
            "WHEN 'jeudi' THEN 4 WHEN 'vendredi' THEN 5 WHEN 'samedi' THEN 6 "
            "WHEN 'dimanche' THEN 7 ELSE 8 END, s.heure_debut, s.heure_fin;"
        )
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
        if not self._is_schedule_intent(question) or self._extract_class_candidate(question) or self._extract_room_candidate(question):
            return None

        match = re.search(
            r"\bemploi(?:s)?\s+(?:du|de)\s+temps\s+de\s+([A-Za-zÀ-ÿ'\-]+(?:\s+[A-Za-zÀ-ÿ'\-]+){1,2})\s*$",
            question or "",
            re.IGNORECASE,
        )
        if not match:
            return None

        candidate = match.group(1).strip()
        return candidate if self._is_valid_prof_candidate_text(candidate) else None

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
        prof_name = self._resolve_professor_name(prof_name) or prof_name
        if self._teacher_prof_exists_in_db(prof_name):
            prof_condition = self._best_professor_match_condition(prof_name, "te.professeur_nom_complet") or "1=0"
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

            sql += " ORDER BY salle;"
            return sql, params

        prof_condition = self._best_professor_match_condition(prof_name) or "1=0"
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

        sql += " ORDER BY salle;"
        return sql, params

    def _prof_class_sql(self, question: str, context: dict) -> Tuple[str, Dict[str, Any]]:
        prof_name = self._extract_prof_candidate(question) or ""
        prof_name = self._resolve_professor_name(prof_name) or prof_name
        if self._teacher_prof_exists_in_db(prof_name):
            prof_condition = self._best_professor_match_condition(prof_name, "te.professeur_nom_complet") or "1=0"
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

        prof_condition = self._best_professor_match_condition(prof_name) or "1=0"
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
        prof_name = self._resolve_professor_name(prof_name) or prof_name
        if self._teacher_prof_exists_in_db(prof_name):
            prof_condition = self._best_professor_match_condition(prof_name, "te.professeur_nom_complet") or "1=0"
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

        prof_condition = self._best_professor_match_condition(prof_name) or "1=0"
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
        prof_name = self._resolve_professor_name(prof_name) or prof_name
        if self._teacher_prof_exists_in_db(prof_name):
            prof_condition = self._best_professor_match_condition(prof_name, "te.professeur_nom_complet") or "1=0"
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

        prof_condition = self._best_professor_match_condition(prof_name) or "1=0"
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
                return self._room_not_found_message(room_name)
            return f"La salle {room_name} est vide actuellement." if room_name else "Aucune salle correspondante n'a ete trouvee."

        if self._is_room_schedule_question(question):
            room_name = self._extract_room_candidate(question) or ""
            if room_name and not self._room_exists_in_db(room_name):
                return self._room_not_found_message(room_name)
            requested_day = self._extract_requested_day(question, context)
            if requested_day:
                return f"Aucun cours trouve pour la salle {room_name} {requested_day.lower()}."
            periode = context.get("periode")
            semestre = context.get("semestre")
            if semestre and periode:
                return f"Aucun cours trouve pour la salle {room_name} dans la periode active {semestre}/{periode}."
            return f"Aucun cours trouve pour la salle {room_name}."

        if self._is_available_rooms_now_question(question):
            return "Aucune salle libre n'a ete trouvee actuellement."

        if self._is_available_rooms_day_question(question):
            requested_day = (self._extract_requested_day(question, context) or "").lower()
            if requested_day:
                return f"Aucune salle libre n'a ete trouvee {requested_day}."
            return "Aucune salle libre n'a ete trouvee pour ce jour."

        if self._is_class_schedule_question(question):
            cls = self._extract_class_candidate(question) or ""
            cls = self._normalize_class_aliases(cls, context)
            requested_day = self._extract_requested_day(question, context)
            if requested_day:
                return f"Aucun cours trouve pour la classe {cls} {requested_day.lower()}."
            periode_id = self._class_schedule_period_id(question, context)
            semestre = context.get("semestre")
            periode = context.get("periode")
            if periode_id and semestre and periode:
                return f"Aucun cours trouve pour la classe {cls} dans la periode active {semestre}/{periode}."
            return f"Aucun cours trouve pour la classe {cls}."

        if self._is_class_location_question(question):
            cls = self._extract_class_candidate(question) or ""
            cls = self._normalize_class_aliases(cls, context)
            requested_day = self._extract_requested_day(question, context)
            if requested_day:
                return f"Aucune salle n'a ete trouvee pour la classe {cls} {requested_day.lower()}."
            return f"La classe {cls} n'a pas de cours en ce moment."

        prof_name = self._extract_schedule_prof_candidate(question) or self._extract_prof_candidate(question)
        if self._is_prof_class_question(question):
            if prof_name and not self._prof_exists_in_db(prof_name):
                return self._prof_not_found_message(prof_name)
            requested_day = self._extract_requested_day(question, context)
            if requested_day:
                return f"Aucune classe n'a ete trouvee pour {prof_name} {requested_day.lower()}."
            return f"{prof_name} n'est pas en classe actuellement." if prof_name else "Ce professeur n'est pas en classe actuellement."

        if self._is_prof_location_question(question):
            if prof_name and not self._prof_exists_in_db(prof_name):
                return self._prof_not_found_message(prof_name)
            requested_day = self._extract_requested_day(question, context)
            if requested_day:
                return f"Aucune salle n'a ete trouvee pour {prof_name} {requested_day.lower()}."
            return f"{prof_name} n'est pas en cours actuellement." if prof_name else "Ce professeur n'est pas en cours actuellement."

        if self._is_prof_current_course_question(question):
            if prof_name and not self._prof_exists_in_db(prof_name):
                return self._prof_not_found_message(prof_name)
            return f"{prof_name} n'enseigne aucun cours en ce moment." if prof_name else "Aucun cours n'est en cours pour ce professeur."

        if self._is_prof_has_course_question(question):
            if prof_name and not self._prof_exists_in_db(prof_name):
                return self._prof_not_found_message(prof_name)
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
                "j ai quoi" in normalized_question,
                "jai quoi" in normalized_question,
                "andi" in normalized_question,
                "ghedwa" in normalized_question,
                "tawa" in normalized_question,
                ("classe" in normalized_question and ("ou se trouve" in normalized_question or "ou est" in normalized_question or "dans quelle salle" in normalized_question)),
                "demain" in normalized_question,
                "aujourd" in normalized_question,
                any(day in normalized_question for day in ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]),
            ]
        )

    def _check_missing_info(self, question: str, context: dict) -> Optional[str]:
        if (
            self._is_calendar_question(question)
            or self._is_room_current_teacher_question(question)
            or self._is_room_schedule_question(question)
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
            confirmation = self._professor_confirmation_message(prof)
            if confirmation:
                return confirmation
            if not self._prof_exists_in_db(prof):
                return self._prof_not_found_message(prof)
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

        if self._is_room_schedule_question(question):
            room_name = self._extract_room_candidate(question) or ""
            if room_name and not self._room_exists_in_db(room_name):
                return self._room_not_found_message(room_name)
            sql_query, params = self._room_schedule_sql(question, context)
            return self._exec_and_format(question, sql_query, params, context)

        if self._is_available_rooms_now_question(question):
            sql_query, params = self._available_rooms_now_sql(context)
            return self._exec_and_format(question, sql_query, params, context)

        if self._is_available_rooms_day_question(question):
            sql_query, params = self._available_rooms_day_sql(question, context)
            return self._exec_and_format(question, sql_query, params, context)

        if self._is_class_location_question(question):
            cls = self._extract_class_candidate(question) or ""
            cls = self._normalize_class_aliases(cls, context)
            if context.get("semestre_id") and not self._class_exists_in_db(cls, context):
                return (
                    f"Je ne trouve pas la classe '{cls}' dans le semestre actuel ({context.get('semestre','?')}). "
                    "Verifiez le nom (ex: '1 TIC 2') ou precisez le semestre (S1/S2)."
                )
            sql_query, params = self._class_location_sql(question, context)
            return self._exec_and_format(question, sql_query, params, context)

        if self._is_prof_class_question(question):
            prof = self._extract_prof_candidate(question)
            confirmation = self._professor_confirmation_message(prof or "")
            if confirmation:
                return confirmation
            if prof and not self._prof_exists_in_db(prof):
                return self._prof_not_found_message(prof)
            sql_query, params = self._prof_class_sql(question, context)
            return self._exec_and_format(question, sql_query, params, context)

        if self._is_prof_schedule_question(question):
            prof = self._extract_schedule_prof_candidate(question) or self._extract_prof_candidate(question)
            confirmation = self._professor_confirmation_message(prof or "")
            if confirmation:
                return confirmation
            if prof and not self._prof_exists_in_db(prof):
                return self._prof_not_found_message(prof)
            sql_query, params = self._teacher_prof_schedule_sql(question, context) if self._teacher_prof_exists_in_db(prof or "") else ("", {})
            if sql_query:
                return self._exec_and_format(question, sql_query, params, context)

        if self._is_prof_location_question(question):
            prof = self._extract_prof_candidate(question)
            confirmation = self._professor_confirmation_message(prof or "")
            if confirmation:
                return confirmation
            if prof and not self._prof_exists_in_db(prof):
                return self._prof_not_found_message(prof)
            sql_query, params = self._prof_location_sql(question, context)
            return self._exec_and_format(question, sql_query, params, context)

        if self._is_prof_current_course_question(question):
            prof = self._extract_prof_candidate(question)
            confirmation = self._professor_confirmation_message(prof or "")
            if confirmation:
                return confirmation
            if prof and not self._prof_exists_in_db(prof):
                return self._prof_not_found_message(prof)
            sql_query, params = self._prof_current_course_sql(question, context)
            return self._exec_and_format(question, sql_query, params, context)

        if self._is_prof_has_course_question(question):
            prof = self._extract_prof_candidate(question)
            confirmation = self._professor_confirmation_message(prof or "")
            if confirmation:
                return confirmation
            if prof and not self._prof_exists_in_db(prof):
                return self._prof_not_found_message(prof)
            sql_query, params = self._prof_has_course_sql(question, context)
            return self._exec_and_format(question, sql_query, params, context)

        if self._is_class_schedule_question(question):
            cls = self._extract_class_candidate(question) or ""
            cls = self._normalize_class_aliases(cls, context)
            if context.get("semestre_id") and not self._class_exists_in_db(cls, context):
                return (
                    f"Je ne trouve pas la classe '{cls}' dans le semestre actuel ({context.get('semestre','?')}). "
                    "Verifiez le nom (ex: '1 TIC 2') ou precisez le semestre (S1/S2)."
                )
            sql_query, params = self._class_schedule_sql(question, context)
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
