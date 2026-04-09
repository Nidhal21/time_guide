# Rapport PFE - Time Guide AI

## Page de garde

**Titre du projet:** Conception et developpement d'une plateforme intelligente de consultation des emplois du temps universitaires

**Nom de l'application:** Time Guide AI

**Etablissement cible:** ENET'Com

**Type de projet:** Projet de Fin d'Etudes

**Etudiant / Binome:** A completer

**Encadrant academique:** A completer

**Encadrant professionnel:** A completer

**Annee universitaire:** A completer

Remarque:
- cette base est prete pour rediger le rapport final,
- les informations administratives restent a personnaliser avant depot.

## Remerciements

Cette section peut etre adaptee pour remercier:
- l'etablissement,
- l'encadrant academique,
- l'encadrant professionnel,
- les enseignants,
- la famille,
- les collegues ou camarades.

## Resume

Ce projet consiste a concevoir et developper une plateforme web intelligente permettant de consulter les emplois du temps universitaires a l'aide du langage naturel. La solution s'appuie sur un frontend React, un backend FastAPI, une base PostgreSQL, un moteur d'import Excel et une logique d'intelligence artificielle orientee exploitation de donnees.

L'objectif principal est de centraliser les informations pedagogiques et d'offrir une consultation simple, rapide et fiable pour les etudiants, enseignants et administrateurs. L'application propose egalement un espace d'administration permettant d'importer les emplois du temps et le calendrier universitaire tout en verifiant la coherence des fichiers deposes.

**Mots-cles:** chatbot, emploi du temps, FastAPI, React, PostgreSQL, Excel, SQL, intelligence artificielle.

## Abstract

This project focuses on the design and development of an intelligent web platform for consulting university timetables through natural language. The system relies on a React frontend, a FastAPI backend, a PostgreSQL database, an Excel import engine, and AI-assisted SQL processing logic.

The main objective is to centralize academic scheduling data and provide fast, simple, and reliable access for students, teachers, and administrators. The application also includes an administrative interface for importing timetable and academic calendar files with built-in consistency checking.

**Keywords:** chatbot, timetable, FastAPI, React, PostgreSQL, Excel, SQL, artificial intelligence.

## Table des matieres

1. Introduction generale
2. Contexte et problematique
3. Etude de l'existant
4. Analyse des besoins
5. Specification des besoins
6. Methodologie de travail
7. Conception generale
8. Conception detaillee
9. Realisation technique
10. Intelligence artificielle et traitement intelligent
11. Gestion des imports Excel
12. Securite
13. Tests et validation
14. Resultats
15. Limites et perspectives
16. Conclusion generale
17. Bibliographie / Webographie
18. Annexes

## Chapitre 1 - Introduction generale

La digitalisation des services universitaires est devenue un enjeu majeur afin d'ameliorer l'acces a l'information, la communication et l'efficacite organisationnelle. Parmi les informations les plus consultees dans un etablissement universitaire figurent les emplois du temps, les affectations de salles, les disponibilites des enseignants et le calendrier academique.

Dans de nombreux contextes, ces informations sont encore diffusees sous forme de fichiers Excel, de PDF ou d'affichages statiques. Bien que ces supports soient largement utilises, ils ne permettent pas une consultation intuitive, rapide et personnalisee. L'utilisateur est souvent oblige de parcourir manuellement plusieurs documents pour obtenir une information simple telle que:
- `Quel cours ai-je maintenant ?`
- `Ou se trouve un enseignant ?`
- `Quelles salles sont disponibles ?`

Le projet `Time Guide AI` a ete concu pour repondre a cette problematique. Il s'agit d'une plateforme web intelligente capable de centraliser les donnees issues des emplois du temps et de permettre leur consultation via une interface conversationnelle.

L'originalite du projet reside dans la combinaison de plusieurs approches:
- import structure de fichiers Excel,
- modelisation relationnelle des donnees,
- interrogation intelligente via un agent conversationnel,
- espace d'administration dedie au controle des imports.

## Chapitre 2 - Contexte et problematique

### 2.1 Contexte

L'ENET'Com manipule plusieurs types d'informations pedagogiques:
- emplois des etudiants,
- emplois des enseignants,
- emplois des salles,
- calendrier universitaire,
- informations institutionnelles et actualites.

Ces donnees sont utiles quotidiennement pour plusieurs profils d'utilisateurs:
- les etudiants,
- les enseignants,
- les responsables administratifs.

### 2.2 Problematique

La gestion classique des emplois du temps presente plusieurs difficultes:
- les fichiers sont parfois nombreux et differents selon le public cible,
- l'utilisateur doit connaitre a l'avance le bon document a consulter,
- les mises a jour ne sont pas toujours faciles a suivre,
- les donnees Excel ne sont pas directement exploitables pour une recherche intelligente,
- le depot d'un mauvais fichier dans une mauvaise categorie peut fausser l'exploitation.

### 2.3 Objectif

L'objectif du projet est de concevoir une solution permettant:
- d'integrer les donnees d'emploi du temps dans une base exploitable,
- de proposer une consultation en langage naturel,
- d'offrir un espace admin pour l'import et le controle de coherence,
- de reduire le temps de recherche d'information,
- de fiabiliser l'exploitation des donnees importees.

## Chapitre 3 - Etude de l'existant

### 3.1 Solutions traditionnelles

Les solutions couramment utilisees sont:
- les fichiers Excel partages,
- les PDF,
- les tableaux d'affichage,
- les communications par email ou messagerie.

### 3.2 Inconvenients

Ces approches presentent plusieurs limites:
- faible interactivite,
- consultation lente,
- recherche manuelle,
- risque d'erreurs d'interpretation,
- absence d'une base centralisee interrogeable,
- absence d'automatisation intelligente.

### 3.3 Positionnement de la solution

La solution proposee apporte:
- une centralisation des donnees,
- une interface conversationnelle,
- une logique de verification lors des imports,
- une meilleure experience utilisateur,
- un gain de temps pour les etudiants et l'administration.

## Chapitre 4 - Analyse des besoins

### 4.1 Besoins fonctionnels

Le systeme doit permettre:
- l'inscription et la connexion des utilisateurs,
- la connexion de l'administrateur,
- la consultation de l'emploi du temps via un chatbot,
- la recherche de salles, d'enseignants et de matieres,
- la consultation du calendrier universitaire,
- la consultation de certaines informations generales ENET'Com,
- l'import des fichiers Excel par categorie,
- la verification automatique du type de fichier,
- la verification du semestre detecte,
- l'affichage des resultats d'import,
- l'affichage de notifications de succes et d'erreur.

### 4.2 Besoins non fonctionnels

Le systeme doit egalement garantir:
- une interface ergonomique,
- de bonnes performances de consultation,
- une securite minimale des acces,
- une architecture modulaire,
- une maintainabilite correcte,
- une compatibilite desktop et mobile,
- une fiabilite des imports.

### 4.3 Acteurs

#### Utilisateur simple
- s'inscrit,
- se connecte,
- interroge le chatbot.

#### Administrateur
- accede a l'espace admin,
- importe les fichiers Excel,
- controle les erreurs,
- maintient la base de donnees a jour.

## Chapitre 5 - Specification des besoins

### 5.1 Cas d'utilisation

#### Cas 1: Consultation de l'emploi du temps
1. l'utilisateur saisit une question,
2. le frontend l'envoie au backend,
3. l'agent traite la requete,
4. la base de donnees est interrogee,
5. la reponse est retournee.

#### Cas 2: Import d'un fichier Excel
1. l'admin choisit une categorie,
2. il selectionne un fichier,
3. le backend sauvegarde et analyse le fichier,
4. le fichier est accepte ou rejete,
5. le resultat est affiche.

#### Cas 3: Detection d'une erreur d'import
1. un fichier est depose dans une mauvaise categorie,
2. le backend detecte l'incoherence,
3. un message d'erreur est genere,
4. l'admin voit l'erreur dans la page et en popup.

### 5.2 Contraintes

- les donnees sources proviennent de fichiers Excel,
- la base cible est PostgreSQL,
- les requetes doivent rester securisees,
- la solution doit rester simple a deployer localement.

## Chapitre 6 - Methodologie de travail

### 6.1 Approche adoptee

Une approche iterative a ete retenue:
- analyse du besoin,
- modelisation,
- implementation backend,
- implementation frontend,
- integration IA,
- ajout des imports admin,
- tests et ameliorations.

### 6.2 Outils de travail

- Visual Studio Code
- Git
- GitHub
- Node.js
- npm
- Python
- PostgreSQL
- Docker Compose

### 6.3 Justification

Cette methodologie est adaptee car:
- les besoins ont evolue par affinage,
- les formats de fichiers Excel necessitent plusieurs ajustements,
- les cas conversationnels sont progressifs,
- la phase de validation est importante.

## Chapitre 7 - Conception generale

### 7.1 Architecture globale

Le systeme suit une architecture client-serveur moderne:
- un frontend React pour l'interface utilisateur,
- un backend FastAPI pour l'API et la logique metier,
- une base PostgreSQL pour le stockage relationnel,
- un service IA pour assister l'interpretation et le formatage.

### 7.2 Vue logique

#### Couche presentation
Cette couche est representee par le frontend web. Elle gere:
- l'authentification,
- la saisie des questions,
- l'affichage des reponses,
- la gestion de l'espace admin.

#### Couche metier
Cette couche est representee par le backend. Elle gere:
- l'authentification,
- le traitement des imports,
- la logique conversationnelle,
- l'interrogation de la base,
- la communication avec les services externes.

#### Couche donnees
Cette couche est representee par PostgreSQL. Elle stocke:
- les entites academiques,
- les seances,
- les versions des emplois,
- les calendriers,
- les sessions utilisateur.

### 7.3 Justification des choix techniques

#### React
Choisi pour:
- sa modularite,
- la richesse de son ecosysteme,
- sa reactivite.

#### FastAPI
Choisi pour:
- sa rapidite,
- sa simplicite,
- sa documentation automatique,
- son integration naturelle avec Python.

#### PostgreSQL
Choisi pour:
- sa robustesse,
- sa fiabilite,
- ses performances sur les donnees relationnelles.

## Chapitre 8 - Conception detaillee

### 8.1 Conception de la base de donnees

Le modele de donnees s'articule autour de plusieurs entites principales.

#### Entites academiques
- `annees_universitaires`
- `semestres`
- `periodes`
- `departements`
- `classes`
- `groupes`

#### Entites metier de planification
- `professeurs`
- `matieres`
- `salles`
- `emplois_versions`
- `seances`
- `emplois_enseignants_seances`
- `vacances_jours_feries`

#### Entites de securite
- `auth_users`
- `auth_sessions`

### 8.2 Description des tables principales

#### `classes`
Contient les classes pedagogiques et leur rattachement semestriel.

#### `professeurs`
Contient les noms complets des enseignants.

#### `salles`
Contient les salles et laboratoires.

#### `emplois_versions`
Permet de gerer l'activation de la version d'emploi du temps utilisee par le chatbot.

#### `seances`
Table centrale contenant:
- le jour,
- l'heure de debut,
- l'heure de fin,
- la matiere,
- le professeur,
- la salle,
- le groupe,
- la periode.

### 8.3 Conception des APIs

#### API d'authentification
- `POST /api/auth/login`
- `POST /api/auth/signup`
- `GET /api/auth/me`
- `POST /api/auth/logout`

#### API de chat
- `POST /api/chat`

#### API admin
- `GET /api/admin/imports/status`
- `POST /api/admin/imports/upload`

#### API systeme
- `GET /health`

### 8.4 Conception de l'interface utilisateur

Le frontend est organise autour de pages claires:
- `Index.tsx`: redirection vers le chat,
- `Auth.tsx`: connexion et inscription,
- `Chat.tsx`: assistant conversationnel,
- `Admin.tsx`: interface d'administration.

### 8.5 Composants principaux

- composant de saisie des messages,
- composant d'affichage de message,
- sidebar de conversations,
- composants UI reutilisables shadcn,
- toaster pour les notifications,
- routes protegees pour le role admin.

## Chapitre 9 - Realisation technique

### 9.1 Frontend

Le frontend a ete developpe avec React et TypeScript.

#### Outils et bibliotheques utilises
- `react`
- `react-dom`
- `react-router-dom`
- `@tanstack/react-query`
- `framer-motion`
- `sonner`
- `lucide-react`
- `tailwindcss`
- `@radix-ui/*`
- `vitest`

#### Role du frontend
- proposer une experience utilisateur moderne,
- envoyer les requetes API,
- gerer les etats de chargement,
- afficher les messages de succes et d'erreur,
- afficher l'espace admin.

#### Gestion d'authentification cote client

Le fichier `src/contexts/AuthContext.tsx` assure:
- la connexion,
- l'inscription,
- la sauvegarde du token,
- le chargement de la session courante,
- la deconnexion.

### 9.2 Backend

Le backend a ete developpe avec FastAPI et SQLAlchemy.

#### Librairies backend
- `fastapi`
- `uvicorn`
- `sqlalchemy`
- `psycopg`
- `pandas`
- `openpyxl`
- `requests`
- `python-dotenv`
- `pydantic`

#### Point d'entree

Le fichier `backend/main.py`:
- initialise l'application,
- configure CORS,
- cree les tables necessaires,
- charge les routes.

### 9.3 Organisation du backend

#### Dossier `routes`
Contient les endpoints:
- `auth.py`
- `chat.py`
- `admin.py`

#### Dossier `services`
Contient les services metier:
- `auth_service.py`
- `sql_agent.py`
- `groq_service.py`
- `admin_import_service.py`
- `excel_parser.py`
- `university_info_service.py`

#### Dossier `models`
Contient:
- `database.py`
- `db_config.py`

### 9.4 Scripts metier importants

#### `load_data.py`
Ce script permet:
- la preparation des seances,
- la creation des entites manquantes,
- l'import des seances en base,
- la gestion des versions actives.

#### `import_calendar.py`
Ce script traite le calendrier universitaire et insere les vacances, examens et jours feries.

## Chapitre 10 - Intelligence artificielle et traitement intelligent

### 10.1 Role de l'intelligence artificielle

L'IA dans ce projet n'est pas utilisee comme un chatbot generaliste libre. Elle est specialisee dans le domaine universitaire et orientee vers la consultation de donnees structurees.

Son role principal est de:
- comprendre la question de l'utilisateur,
- aider a produire une requete exploitable,
- reformuler les resultats en francais clair,
- gerer certains cas ambigus.

### 10.2 Techniques appliquees

#### Normalisation textuelle
Le systeme applique plusieurs traitements:
- suppression des espaces superflus,
- reduction des problemes d'encodage,
- suppression des accents dans certains traitements,
- correction de quelques fautes frequentes.

#### Gestion du contexte de conversation
Le routeur de chat et l'agent peuvent:
- reutiliser la derniere classe mentionnee,
- reutiliser le dernier professeur mentionne,
- detecter une demande de clarification,
- distinguer une nouvelle question d'une reponse courte.

#### Resolution des noms proches
Le systeme utilise:
- des comparaisons de similarite,
- des heuristiques sur les noms de famille,
- une mise en cache de repertoires de professeurs,
- une proposition de noms proches si un professeur n'est pas reconnu.

### 10.3 Service Groq

Le fichier `groq_service.py` montre que le systeme utilise l'API Groq avec:
- un modele configure par defaut,
- un controle de la structure SQL,
- un nettoyage des reponses,
- des fonctions de reformulation metier.

### 10.4 Agent SQL

Le fichier `sql_agent.py` joue un role central:
- identification de l'intention,
- exploitation du contexte academique actif,
- construction ou reinterpretation des questions,
- execution SQL,
- formatage des resultats.

### 10.5 Informations ENET'Com

Le service `university_info_service.py` permet:
- de consulter le site officiel ENET'Com,
- d'extraire certaines actualites,
- de recuperer des liens utiles,
- de fournir des reponses sur les informations institutionnelles.

## Chapitre 11 - Gestion des imports Excel

### 11.1 Importance des imports

Le coeur du projet repose sur la transformation des fichiers Excel en donnees structurables. Sans cette etape, aucune consultation intelligente ne serait fiable.

### 11.2 Types de fichiers supportes

Le systeme accepte:
- les emplois des etudiants,
- les emplois des enseignants,
- les emplois des salles,
- le calendrier universitaire.

Chaque categorie peut etre associee a un semestre selon le cas.

### 11.3 Validation metier

Le service d'import admin verifie:
- l'audience detectee du workbook,
- le semestre detecte,
- la compatibilite avec la categorie choisie.

Exemple:
- un fichier enseignants depose dans `Emplois des etudiants S1` est rejete avec un message explicite.

### 11.4 Parsing Excel

Le parseur `excel_parser.py` est concu pour traiter plusieurs vues:
- vue etudiant,
- vue enseignant,
- vue salle.

Il gere notamment:
- les lignes de jours,
- les plages horaires,
- les blocs fusionnes ou composes,
- les marqueurs `P1` / `P2`,
- l'extraction de matiere, professeur, salle et classe.

### 11.5 Injection en base

Lors de l'import, le systeme peut:
- creer automatiquement des classes,
- creer des groupes,
- ajouter des professeurs,
- ajouter des salles,
- ajouter des matieres,
- recreer les versions actives.

### 11.6 Espace admin

L'espace admin:
- affiche les derniers fichiers importes,
- permet d'uploader plusieurs categories,
- affiche les resultats d'import,
- remonte les erreurs via popup notification,
- permet de suivre l'etat de la base.

## Chapitre 12 - Securite

### 12.1 Authentification

Le systeme distingue:
- les utilisateurs normaux stockes en base,
- l'administrateur configure par variables d'environnement.

### 12.2 Protection des mots de passe

Les mots de passe utilisateurs sont proteges avec:
- PBKDF2-HMAC SHA256,
- un sel aleatoire,
- un nombre d'iterations important.

### 12.3 Sessions

Les sessions sont:
- generees de maniere aleatoire,
- stockees sous forme de hash de token,
- associees a une date d'expiration.

### 12.4 Controle d'acces

Le backend impose:
- un Bearer token valide pour les routes protegees,
- un role `admin` pour l'espace d'administration.

### 12.5 Securite metier

Le systeme ajoute aussi:
- une verification des categories d'import,
- un controle du semestre,
- une limitation defensive des requetes SQL a la lecture.

## Chapitre 13 - Tests et validation

### 13.1 Tests backend

Le projet contient des tests pour:
- l'API admin,
- le service d'import admin,
- l'authentification,
- l'API de chat,
- l'agent SQL,
- le parseur Excel,
- le calendrier universitaire,
- le service d'information universitaire.

Exemples de fichiers de test:
- `backend/tests/test_admin_api.py`
- `backend/tests/test_admin_import_service.py`
- `backend/tests/test_auth_service.py`
- `backend/tests/test_chat_api.py`
- `backend/tests/test_sql_agent.py`

### 13.2 Tests frontend

Le frontend utilise:
- `vitest`,
- `@testing-library/react`,
- `@testing-library/jest-dom`.

### 13.3 Scenarios de validation

Les scenarios de validation comprennent:
- connexion utilisateur,
- connexion admin,
- import valide d'un fichier,
- rejet d'un fichier mal classe,
- consultation d'un emploi du temps,
- recherche d'un enseignant,
- recherche d'une salle disponible,
- consultation du calendrier.

## Chapitre 14 - Resultats

Le projet aboutit a une solution fonctionnelle permettant:
- une consultation conversationnelle des emplois du temps,
- un espace d'administration exploitable,
- une centralisation des donnees dans PostgreSQL,
- une gestion coherente des imports,
- une meilleure accessibilite a l'information.

### Valeur ajoutee

La valeur ajoutee de la solution est:
- le gain de temps,
- la reduction des erreurs de consultation,
- la centralisation des donnees,
- l'amelioration de l'experience utilisateur,
- la valorisation des donnees Excel existantes.

## Chapitre 15 - Limites et perspectives

### 15.1 Limites

- dependance a la qualite des fichiers Excel,
- besoin de maintenir la logique de parsing,
- variabilite possible des formulations utilisateur,
- besoin d'un environnement PostgreSQL correctement configure.

### 15.2 Perspectives

- tableau de bord analytique admin,
- export PDF ou ICS,
- gestion avancee des droits,
- monitoring,
- deploiement cloud,
- historique complet des imports,
- interface mobile dediee.

## Chapitre 16 - Conclusion generale

Ce projet de fin d'etudes a permis de concevoir et realiser une plateforme complete de consultation intelligente des emplois du temps universitaires. Il a mobilise plusieurs competences complementaires:
- developpement frontend,
- developpement backend,
- modelisation de base de donnees,
- parsing de fichiers Excel,
- integration d'intelligence artificielle,
- securisation des acces,
- tests et validation.

La solution obtenue repond a un besoin concret et constitue une base serieuse pour un enrichissement futur dans un contexte universitaire reel.

## Chapitre 17 - Bibliographie / Webographie

References recommandees a completer dans la version finale:
- Documentation React
- Documentation FastAPI
- Documentation SQLAlchemy
- Documentation PostgreSQL
- Documentation Pandas
- Documentation OpenPyXL
- Documentation Tailwind CSS
- Documentation Vite
- Documentation Groq API
- Site officiel ENET'Com

## Chapitre 18 - Annexes

### Annexe A - Technologies utilisees

#### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- Radix UI
- Framer Motion
- Sonner
- Lucide React
- TanStack Query
- Vitest

#### Backend
- FastAPI
- Uvicorn
- SQLAlchemy
- Psycopg
- Pandas
- OpenPyXL
- Requests
- Pydantic
- Python Dotenv

#### Base de donnees
- PostgreSQL

#### Outils
- Git
- GitHub
- Visual Studio Code
- Docker Compose

### Annexe B - Structure resumee du projet

```text
backend/
  app/
    models/
    routes/
    services/
  tests/
src/
  components/
  contexts/
  hooks/
  pages/
```

### Annexe C - Commandes utiles

#### Frontend

```bash
npm install
npm run dev
npm run build
npm run test
```

#### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
python -m pytest tests
```

### Annexe D - Endpoints API

- `POST /api/auth/login`
- `POST /api/auth/signup`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `POST /api/chat`
- `GET /api/admin/imports/status`
- `POST /api/admin/imports/upload`
- `GET /health`

### Annexe E - Elements a personnaliser avant depot

- page de garde,
- noms des encadrants,
- contexte reel de stage ou d'accueil,
- planning reel du projet,
- captures d'ecran,
- diagrammes UML ou Merise si demandes,
- bibliographie finale selon la norme exigee.
