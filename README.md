# Time Guide AI

Plateforme web de consultation intelligente des emplois du temps universitaires pour l'ENET'Com.

Le projet combine:
- un frontend React/Vite,
- un backend FastAPI,
- une base PostgreSQL,
- un moteur d'import Excel,
- un agent conversationnel oriente SQL,
- un service d'assistance sur les informations ENET'Com.

## Vue d'ensemble

L'application permet:
- de poser des questions en langage naturel sur les emplois du temps,
- de consulter les cours, salles, enseignants et calendrier universitaire,
- d'importer les emplois du temps via un espace admin,
- de verifier automatiquement qu'un fichier Excel a ete depose dans la bonne categorie,
- d'afficher les resultats d'import dans la page admin et en popup notification.

Exemples de questions:
- `Quel est mon emploi du temps aujourd'hui ?`
- `Ou se trouve Mr BEN SLIMA maintenant ?`
- `Qui enseigne en salle C01 ?`
- `Quelles sont les salles disponibles lundi ?`
- `Y a-t-il des vacances aujourd'hui ?`

## Architecture

```text
Frontend React + Vite
        |
        v
API FastAPI
        |
        +--> Authentification
        +--> Import admin Excel
        +--> Agent SQL / logique IA
        +--> Service d'informations ENET'Com
        |
        v
PostgreSQL
```

## Fonctionnalites

### Utilisateur
- connexion et inscription,
- interface chat moderne,
- historique recent de conversation,
- consultation de l'emploi du temps,
- recherche de professeurs,
- recherche de salles disponibles,
- consultation du calendrier universitaire,
- questions generales sur ENET'Com.

### Administrateur
- acces protege a l'espace admin,
- import de:
  - `student_s1`
  - `student_s2`
  - `teachers_s1`
  - `teachers_s2`
  - `rooms_s1`
  - `rooms_s2`
  - `calendar`
- detection automatique du type de workbook,
- detection des incoherences de semestre,
- resultats d'import visibles dans la page,
- notifications popup de succes et d'erreur.

## Stack technique

### Frontend
- React 18
- TypeScript
- Vite
- React Router DOM
- Tailwind CSS
- shadcn/ui
- Radix UI
- Framer Motion
- Sonner
- Lucide React
- TanStack Query
- Vitest

### Backend
- FastAPI
- Uvicorn
- SQLAlchemy
- Psycopg
- Pandas
- OpenPyXL
- Requests
- Python Dotenv
- Pydantic

### IA et traitement intelligent
- Groq API
- modele configure dans le code: `llama-3.3-70b-versatile`
- logique metier specialisee dans `sql_agent.py`

### Base de donnees
- PostgreSQL

## Structure du projet

```text
time-guide-ai-main/
|-- backend/
|   |-- app/
|   |   |-- models/
|   |   |-- routes/
|   |   `-- services/
|   |-- tests/
|   |-- uploads/
|   |-- main.py
|   `-- requirements.txt
|-- src/
|   |-- components/
|   |-- contexts/
|   |-- hooks/
|   |-- lib/
|   `-- pages/
|-- load_data.py
|-- import_calendar.py
|-- docker-compose.yml
|-- package.json
`-- README.md
```

## Modules importants

### Frontend
- `src/pages/Chat.tsx`: interface de conversation
- `src/pages/Admin.tsx`: gestion des imports admin
- `src/pages/Auth.tsx`: connexion et inscription
- `src/contexts/AuthContext.tsx`: gestion de session cote client

### Backend
- `backend/main.py`: point d'entree FastAPI
- `backend/app/routes/chat.py`: endpoint `/api/chat`
- `backend/app/routes/auth.py`: endpoints d'authentification
- `backend/app/routes/admin.py`: endpoints admin
- `backend/app/services/sql_agent.py`: moteur principal des reponses
- `backend/app/services/groq_service.py`: communication avec Groq
- `backend/app/services/admin_import_service.py`: logique d'import admin
- `backend/app/services/excel_parser.py`: parsing des fichiers Excel
- `backend/app/services/university_info_service.py`: infos ENET'Com
- `load_data.py`: injection des seances en base
- `import_calendar.py`: import du calendrier universitaire

## Base de donnees

Tables principales:
- `annees_universitaires`
- `semestres`
- `periodes`
- `departements`
- `classes`
- `professeurs`
- `matieres`
- `salles`
- `groupes`
- `emplois_versions`
- `seances`
- `emplois_enseignants_seances`
- `vacances_jours_feries`

Tables de securite:
- `auth_users`
- `auth_sessions`

## Installation

## Prerequis
- Node.js 18+
- npm
- Python 3.10+ recommande
- PostgreSQL 14+
- Git

## 1. Clonage

```bash
git clone <votre-repo>
cd time-guide-ai-main
```

## 2. Base PostgreSQL

Option manuelle:

```bash
psql -U postgres
CREATE DATABASE emploi_temps;
CREATE USER emploi_user WITH PASSWORD 'emploi_temps';
GRANT ALL PRIVILEGES ON DATABASE emploi_temps TO emploi_user;
\q
```

Option Docker:

```bash
docker-compose up -d
```

## 3. Configuration backend

Creer `backend/.env` a partir de `backend/.env.example`.

Exemple:

```env
DATABASE_URL=postgresql://emploi_user:emploi_temps@127.0.0.1:5432/emploi_temps
GROQ_API_KEY=votre_cle_groq
MODEL_NAME=Qwen/Qwen2.5-3B-Instruct
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=admin123456
ADMIN_FULL_NAME=Administrateur ENETCOM
AUTH_SESSION_TTL_DAYS=14
```

Installation et lancement:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## 4. Configuration frontend

Depuis la racine:

```bash
npm install
npm run dev
```

Optionnel, creer `.env.local`:

```env
VITE_API_URL=http://127.0.0.1:8000/api
```

Le frontend tourne par defaut sur `http://localhost:8080`.

## Utilisation

### Chat
- route: `/chat`
- permet de discuter avec l'assistant universitaire

### Admin
- route: `/admin`
- permet de charger les fichiers Excel
- affiche les derniers imports
- affiche les resultats d'import et les notifications popup

## API

### Auth
- `POST /api/auth/login`
- `POST /api/auth/signup`
- `GET /api/auth/me`
- `POST /api/auth/logout`

### Chat
- `POST /api/chat`

Exemple:

```json
{
  "message": "Quel est l'emploi du temps de 1 ING GII 2 aujourd'hui ?",
  "user_role": "student",
  "user_class": "1 ING GII 2",
  "history": []
}
```

### Admin
- `GET /api/admin/imports/status`
- `POST /api/admin/imports/upload`

### Systeme
- `GET /health`

Documentation FastAPI:
- `http://127.0.0.1:8000/docs`

## Tests

### Frontend

```bash
npm run test
```

### Backend

```bash
cd backend
python -m pytest tests
```

Les tests couvrent notamment:
- l'API admin,
- les imports,
- l'authentification,
- l'API chat,
- l'agent SQL,
- le parseur Excel,
- le calendrier universitaire.

## Build

```bash
npm run build
```

## Securite et robustesse

- role admin obligatoire pour les imports,
- mots de passe utilisateurs haches avec PBKDF2,
- sessions stockees par hash de token,
- verification des categories et semestres a l'import,
- validation defensive des requetes SQL en lecture seule,
- normalisation de texte pour reduire les problemes d'encodage.

## Limitations

- la qualite des reponses depend de la qualite des fichiers Excel importes,
- certains formats atypiques d'Excel peuvent necessiter des adaptations,
- la partie IA depend de la disponibilite de Groq si elle est activee,
- PostgreSQL doit etre correctement configure pour exploiter tout le systeme.

## Documentation complementaire

- `ARCHITECTURE_DIAGRAM.md`
- `PROJECT_STRUCTURE.md`
- `SUMMARY.md`
- `LLM_ARCHITECTURE.md`
- `backend/API_DOCUMENTATION.md`
- `backend/README.md`
- `rapport.md`
