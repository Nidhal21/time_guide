from __future__ import annotations

import html
import re
import time
import unicodedata
from typing import Dict, List, Tuple
from urllib.parse import urljoin

import requests

from .groq_service import groq_service


class UniversityInfoService:
    BASE_URL = "https://enetcom.rnu.tn/fr"
    ACTUALITES_URL = "https://enetcom.rnu.tn/fr/categories/1/actualites"
    ABSENCES_URL = "https://enetcom.rnu.tn/fr/app/my-studies-absences"
    CACHE_TTL_SECONDS = 1800
    MAX_CONTEXT_CHARS = 12000
    STUDY_PLAN_URLS: Dict[str, str] = {
        "idsd": "https://enetcom.rnu.tn/userfiles/files/Plan-Etudes/IDSD_V2_25_26.pdf",
        "gt": "https://enetcom.rnu.tn/userfiles/files/Plan-Etudes/GT_23-24.pdf",
        "gec": "https://enetcom.rnu.tn/userfiles/files/Plan-Etudes/GEC_23-24.pdf",
        "gii": "https://enetcom.rnu.tn/userfiles/files/Plan-Etudes/GII%202023-2024%20V2.pdf",
    }

    PAGE_CATALOG: Dict[str, str] = {
        "accueil": "https://enetcom.rnu.tn/fr",
        "presentation": "https://enetcom.rnu.tn/fr/enetcom/presentation",
        "contact": "https://enetcom.rnu.tn/fr/contact-footer",
        "mot_directeur": "https://enetcom.rnu.tn/fr/enetcom/mot-du-directeur",
        "ingenieur": "https://enetcom.rnu.tn/fr/formation-d-ingenieurs-formation",
        "licence": "https://enetcom.rnu.tn/fr/licence-unifiee-formation",
        "mastere_pro": "https://enetcom.rnu.tn/fr/mastere-professionnel-formation",
        "mastere_recherche": "https://enetcom.rnu.tn/fr/mastere-de-recherche-formation",
        "doctorat": "https://enetcom.rnu.tn/fr/formation-doctorale-formation",
        "telecom": "https://enetcom.rnu.tn/fr/enetcom/departement/telecommunication",
        "electronique": "https://enetcom.rnu.tn/fr/enetcom/departement/electronique",
        "informatique_industrielle": "https://enetcom.rnu.tn/fr/enetcom/departement/informatique-industrielle",
        "idsd": "https://enetcom.rnu.tn/fr/enetcom/departement/mathematique-et-informatique-decisionnelle",
        "international": "https://enetcom.rnu.tn/fr/international/partenariat-international",
        "recherche": "https://enetcom.rnu.tn/fr/recherche/structures-de-recherches/laboratoires-en-nouvelles-technologies-et-systemes-des-telecommunications",
        "stages": "https://enetcom.rnu.tn/fr/entreprises/stages-et-pfe/stages",
        "pfe": "https://enetcom.rnu.tn/fr/entreprises/stages-et-pfe/pfe",
        "bibliotheque": "https://enetcom.rnu.tn/fr/enetcom/bibliotheque1/inscription",
        "clubs": "https://enetcom.rnu.tn/fr/vie-estudiantine/clubs",
        "sports": "https://enetcom.rnu.tn/fr/vie-estudiantine/activites-sportives",
        "preinscriptions": "https://enetcom.rnu.tn/fr/etudiant-footer/pre-inscriptions-en-ligne",
        "actualites": "https://enetcom.rnu.tn/fr/categories/1/actualites",
    }

    KEYWORD_TO_PAGES: Dict[str, List[str]] = {
        "contact": ["contact"],
        "adresse": ["contact"],
        "telephone": ["contact"],
        "mail": ["contact"],
        "email": ["contact"],
        "presentation": ["presentation", "accueil"],
        "ecole": ["presentation", "accueil"],
        "universite": ["presentation", "accueil"],
        "directeur": ["mot_directeur", "presentation"],
        "formation": ["ingenieur", "licence", "mastere_pro", "mastere_recherche", "doctorat"],
        "ingenieur": ["ingenieur"],
        "licence": ["licence"],
        "master": ["mastere_pro", "mastere_recherche"],
        "mastere": ["mastere_pro", "mastere_recherche"],
        "doctorat": ["doctorat"],
        "departement": ["telecom", "electronique", "informatique_industrielle", "idsd"],
        "telecommunication": ["telecom"],
        "electronique": ["electronique"],
        "informatique": ["informatique_industrielle", "idsd"],
        "donnees": ["idsd"],
        "recherche": ["recherche"],
        "laboratoire": ["recherche"],
        "international": ["international"],
        "bourse": ["accueil", "international"],
        "stage": ["stages"],
        "pfe": ["pfe"],
        "bibliotheque": ["bibliotheque"],
        "club": ["clubs"],
        "sport": ["sports"],
        "preinscription": ["preinscriptions"],
        "inscription": ["preinscriptions", "doctorat"],
        "actualite": ["actualites"],
        "actualites": ["actualites"],
        "nouveaute": ["actualites", "accueil"],
        "nouveautes": ["actualites", "accueil"],
        "annonce": ["actualites"],
        "annonces": ["actualites"],
        "news": ["actualites"],
    }

    def __init__(self):
        self._session = requests.Session()
        self._cache: Dict[str, Tuple[float, str]] = {}

    def _normalize_text(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = normalized.replace("'", " ")
        normalized = re.sub(r"[^a-zA-Z0-9\s/-]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized.lower()

    def _html_to_text(self, html_content: str) -> str:
        text = re.sub(r"<script[\s\S]*?</script>", " ", html_content, flags=re.IGNORECASE)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _fetch_page_html(self, url: str, force_refresh: bool = False) -> str:
        now = time.time()
        cached = self._cache.get(url)
        if not force_refresh and cached and now - cached[0] < self.CACHE_TTL_SECONDS:
            return cached[1]

        response = self._session.get(url, timeout=20)
        response.raise_for_status()
        html_content = response.text
        self._cache[url] = (now, html_content)
        return html_content

    def _fetch_page_text(self, url: str, force_refresh: bool = False) -> str:
        html_content = self._fetch_page_html(url, force_refresh=force_refresh)
        return self._html_to_text(html_content)

    def _is_news_question(self, question: str) -> bool:
        normalized_question = self._normalize_text(question)
        markers = [
            "actualite",
            "actualites",
            "nouveaute",
            "nouveautes",
            "dernieres actualites",
            "dernieres nouvelles",
            "dernieres annonces",
            "news",
            "quoi de neuf",
        ]
        return any(marker in normalized_question for marker in markers)

    def _is_absence_question(self, question: str) -> bool:
        normalized_question = self._normalize_text(question)
        markers = [
            "absence",
            "absences",
            "dabsence",
            "avis d absence",
            "avis de absence",
            "avis absence",
            "lavis",
            "avis",
            "justificatif d absence",
            "justificatif absence",
            "extranet",
        ]
        return any(marker in normalized_question for marker in markers)

    def _study_plan_keys_for_question(self, question: str) -> List[str]:
        normalized_question = self._normalize_text(question)
        if not any(marker in normalized_question for marker in ["plan", "etude", "etudes", "programme", "curriculum"]):
            return []

        keys: List[str] = []
        if "idsd" in normalized_question:
            keys.append("idsd")
        if "informatique industrielle" in normalized_question or "gii" in normalized_question:
            keys.append("gii")
        if "gec" in normalized_question:
            keys.append("gec")
        if re.search(r"\bgt\b", normalized_question) or "genie telecommunication" in normalized_question:
            keys.append("gt")
        if not keys:
            keys = ["gii", "gec", "idsd", "gt"]
        return list(dict.fromkeys(keys))

    def _study_plan_response(self, keys: List[str]) -> str:
        labels = {
            "idsd": "IDSD : Mathématiques et Informatique Décisionnelle",
            "gii": "GII : Génie Informatique Industrielle",
            "gec": "GEC : Génie Electronique de Communication",
            "gt": "GT : Génie Télécommunication",
        }
        lines = ["Voici les URLs des plans d'etudes ENET'Com :", ""]
        for key in keys:
            lines.append(f"- {labels[key]} : {self.STUDY_PLAN_URLS[key]}")
        lines.extend(["", f"Source : {self.BASE_URL}"])
        return "\n".join(lines)

    def _absence_response(self) -> str:
        try:
            response = self._session.get(self.ABSENCES_URL, timeout=20, allow_redirects=True)
            final_url = str(response.url)
            page_text = self._html_to_text(response.text or "")
        except Exception as e:
            print(f"University absences fetch error for {self.ABSENCES_URL}: {e}")
            return (
                "Je n'ai pas pu verifier la page des absences pour le moment. "
                f"Vous pouvez essayer ici : {self.ABSENCES_URL}"
            )

        normalized_text = self._normalize_text(page_text)
        login_markers = [
            "/login" in final_url.lower(),
            "se connecter" in normalized_text,
            "connexion" in normalized_text,
            "login" in normalized_text,
            "espace extranet" in normalized_text and "connect" in normalized_text,
        ]
        if any(login_markers):
            return (
                "Pour consulter les absences des enseignants, l'etudiant doit d'abord se connecter a l'Espace Extranet. "
                f"Ensuite, il peut ouvrir cette page : {self.ABSENCES_URL}"
            )

        if "pas d absence des enseignants" in normalized_text:
            return (
                "Il n'y a pas d'absence des enseignants pour le moment.\n\n"
                f"Source : {self.ABSENCES_URL}"
            )

        snippet = re.sub(r"\s+", " ", page_text).strip()[:700]
        if snippet:
            return (
                "Voici ce que j'ai pu recuperer depuis la page des absences :\n"
                f"{snippet}\n\nSource : {self.ABSENCES_URL}"
            )

        return f"La page des absences est disponible ici : {self.ABSENCES_URL}"

    def _extract_latest_news(self, limit: int = 6) -> List[Tuple[str, str]]:
        try:
            html_content = self._fetch_page_html(self.ACTUALITES_URL, force_refresh=True)
        except Exception as e:
            print(f"University news fetch error for {self.ACTUALITES_URL}: {e}")
            return []
        matches = re.findall(r'<a[^>]+href="([^"]*/article/[^"]+)"[^>]*>(.*?)</a>', html_content, flags=re.IGNORECASE | re.DOTALL)

        items: List[Tuple[str, str]] = []
        seen_urls = set()
        for href, raw_title in matches:
            url = urljoin(self.BASE_URL, html.unescape(href))
            if url in seen_urls:
                continue

            title = re.sub(r"<[^>]+>", " ", raw_title)
            title = html.unescape(title)
            title = re.sub(r"\s+", " ", title).strip()
            if self._normalize_text(title) in {"lire la suite", "plus de details", "plus"}:
                slug = url.rstrip("/").split("/")[-1]
                slug = re.sub(r"^\d+-", "", slug)
                slug = slug.replace("-", " ")
                slug = re.sub(r"\s+", " ", slug).strip()
                title = slug.capitalize()

            if not title or len(title) < 8:
                continue

            seen_urls.add(url)
            items.append((title, url))
            if len(items) >= limit:
                break

        return items

    def _select_urls(self, question: str) -> List[str]:
        normalized_question = self._normalize_text(question)
        selected = [self.PAGE_CATALOG["accueil"], self.PAGE_CATALOG["presentation"], self.PAGE_CATALOG["contact"]]

        for keyword, page_keys in self.KEYWORD_TO_PAGES.items():
            if keyword in normalized_question:
                for page_key in page_keys:
                    url = self.PAGE_CATALOG[page_key]
                    if url not in selected:
                        selected.append(url)

        return selected[:6]

    def _build_context(self, question: str) -> Tuple[str, List[str]]:
        urls = self._select_urls(question)
        blocks: List[str] = []
        used_urls: List[str] = []
        current_length = 0

        for index, url in enumerate(urls, start=1):
            try:
                text_content = self._fetch_page_text(url)
            except Exception as e:
                print(f"University site fetch error for {url}: {e}")
                continue

            snippet = text_content[:2500]
            block = f"[Source {index}] URL: {url}\nContenu: {snippet}"
            if current_length + len(block) > self.MAX_CONTEXT_CHARS:
                break
            blocks.append(block)
            used_urls.append(url)
            current_length += len(block)

        return "\n\n".join(blocks), used_urls

    def answer_question(self, question: str) -> str:
        study_plan_keys = self._study_plan_keys_for_question(question)
        if study_plan_keys:
            return self._study_plan_response(study_plan_keys)

        if self._is_absence_question(question):
            return self._absence_response()

        if self._is_news_question(question):
            news_items = self._extract_latest_news()
            if not news_items:
                return (
                    "Je n'ai pas pu recuperer les dernieres actualites pour le moment. "
                    f"Vous pouvez consulter {self.ACTUALITES_URL}."
                )

            lines = ["Voici les dernieres actualites ENET'Com :", ""]
            for index, (title, url) in enumerate(news_items, start=1):
                lines.append(f"{index}. {title}")
                lines.append(url)
                if index != len(news_items):
                    lines.append("")
            lines.extend(["", f"Source officielle actualisee : {self.ACTUALITES_URL}"])
            return "\n".join(lines).strip()

        context, urls = self._build_context(question)
        if not context:
            return (
                "Je n'ai pas pu recuperer les informations depuis le site officiel pour le moment. "
                f"Vous pouvez consulter {self.BASE_URL}."
            )

        if not (groq_service and getattr(groq_service, "enabled", False)):
            return (
                "Je peux repondre aux questions generales a partir du site officiel ENET'Com, "
                f"mais le modele n'est pas active. Consultez {self.BASE_URL}."
            )

        prompt = f"""Tu es l'assistant officiel ENET'Com.

Reponds uniquement a partir du contexte ci-dessous extrait du site officiel {self.BASE_URL}.
Si l'information n'est pas clairement presente, dis-le franchement et renvoie vers le site officiel.
Reponse en francais, concise, utile, sans markdown complexe.
Termine par une ligne 'Sources :' suivie de 1 a 3 URLs utiles.

Question utilisateur :
{question}

Contexte site officiel :
{context}
"""

        response = groq_service._post_with_retry(
            {
                "model": groq_service.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Tu reponds a des questions generales sur ENET'Com uniquement a partir du site officiel fourni. Ne fabrique rien.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 1024,
            },
            timeout=30,
        )

        if response is None or response.status_code != 200:
            if response is not None:
                print(f"University info Groq error: {response.status_code} - {response.text}")
            fallback_sources = "\n".join(urls[:3]) if urls else self.BASE_URL
            return (
                "Je n'ai pas pu formuler la reponse automatiquement, mais vous pouvez verifier ici :\n"
                f"{fallback_sources}"
            )

        payload = groq_service._safe_json(response)
        if not payload:
            fallback_sources = "\n".join(urls[:3]) if urls else self.BASE_URL
            return (
                "Je n'ai pas pu lire la reponse du modele, mais vous pouvez verifier ici :\n"
                f"{fallback_sources}"
            )

        raw = (payload.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
        if raw:
            return raw

        fallback_sources = "\n".join(urls[:3]) if urls else self.BASE_URL
        return (
            "Je n'ai pas trouve de reponse exploitable pour le moment. "
            "Consultez le site officiel :\n"
            f"{fallback_sources}"
        )


university_info_service = UniversityInfoService()
