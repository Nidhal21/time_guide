# Structure Complète du Projet

## 📁 Architecture des Fichiers

```
time-guide-ai-main/
│
├── 📂 backend/                          # Backend FastAPI
│   ├── 📂 app/
│   │   ├── 📂 models/
│   │   │   ├── __init__.py
│   │   │   ├── database.py              # Modèles SQLAlchemy
│   │   │   └── db_config.py             # Configuration DB
│   │   │
│   │   ├── 📂 routes/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py                  # Routes chat
│   │   │   └── admin.py                 # Routes admin
│   │   │
│   │   ├── 📂 services/
│   │   │   ├── __init__.py
│   │   │   ├── llm_service.py           # Service Qwen LLM
│   │   │   ├── sql_agent.py             # Agent SQL
│   │   │   └── excel_parser.py          # Parser Excel
│   │   │
│   │   └── 📂 utils/
│   │       └── __init__.py
│   │
│   ├── main.py                          # Point d'entrée FastAPI
│   ├── requirements.txt                 # Dépendances Python
│   ├── init_db.sql                      # Script SQL initialisation
│   ├── test_config.py                   # Script de test
│   ├── generate_example_excel.py        # Générateur Excel exemple
│   ├── .env                             # Variables d'environnement
│   ├── .env.example                     # Template .env
│   ├── .gitignore                       # Git ignore
│   ├── README.md                        # Doc backend
│   ├── API_DOCUMENTATION.md             # Doc API
│   └── EXCEL_FORMAT.md                  # Format Excel
│
├── 📂 src/                              # Frontend React
│   ├── 📂 components/
│   │   ├── 📂 auth/
│   │   ├── 📂 chat/
│   │   └── 📂 ui/
│   │
│   ├── 📂 pages/
│   │   ├── Chat.tsx                     # Page chat (modifiée)
│   │   ├── Admin.tsx                    # Page admin (modifiée)
│   │   ├── Index.tsx
│   │   └── Auth.tsx
│   │
│   └── ...
│
├── docker-compose.yml                   # Docker PostgreSQL
├── start_backend.bat                    # Script démarrage Windows
├── README.md                            # Documentation principale
├── QUICKSTART.md                        # Guide démarrage rapide
└── package.json                         # Dépendances Node.js
```

## 🔄 Flux de Données

```
┌─────────────────────────────────────────────────────────────┐
│                         UTILISATEUR                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                          │
│  • Chat.tsx : Interface de chat                             │
│  • Admin.tsx : Upload Excel                                 │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/REST
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   BACKEND API (FastAPI)                      │
│  • /api/chat : Traitement questions                         │
│  • /api/admin/upload-emploi : Import Excel                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    LLM AGENT (Qwen)                          │
│  • Comprend la question en langage naturel                  │
│  • Génère une requête SQL appropriée                        │
│  • Formate la réponse                                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      SQL TOOL                                │
│  • Exécute la requête SQL                                   │
│  • Récupère les données                                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                DATABASE (PostgreSQL)                         │
│  • 10 tables relationnelles                                 │
│  • Index optimisés                                          │
│  • Données emplois du temps                                 │
└─────────────────────────────────────────────────────────────┘
```

## 📊 Schéma de Base de Données

```
annees_universitaires
    ↓
semestres
    ↓
classes ← departements
    ↓
emplois_versions
    ↓
seances ← matieres
    ↑     professeurs
    ↑     salles
    ↑     groupes
```

## 🚀 Composants Clés

### Backend

1. **main.py**
   - Point d'entrée FastAPI
   - Configuration CORS
   - Enregistrement des routes

2. **llm_service.py**
   - Chargement du modèle Qwen2.5-7B-Instruct
   - Génération de requêtes SQL
   - Formatage des réponses

3. **sql_agent.py**
   - Orchestration LLM + SQL
   - Exécution sécurisée des requêtes
   - Gestion des erreurs

4. **excel_parser.py**
   - Lecture fichiers Excel
   - Extraction des données
   - Insertion en base de données

5. **database.py**
   - Modèles SQLAlchemy
   - Relations entre tables
   - Contraintes et index

### Frontend

1. **Chat.tsx**
   - Interface de chat
   - Appel API backend
   - Affichage des réponses

2. **Admin.tsx**
   - Upload de fichiers Excel
   - Gestion des emplois du temps
   - Feedback utilisateur

## 🔧 Technologies Utilisées

### Backend
- **FastAPI** : Framework web moderne et rapide
- **SQLAlchemy** : ORM Python
- **PostgreSQL** : Base de données relationnelle
- **Transformers** : Bibliothèque Hugging Face
- **Qwen2.5-7B-Instruct** : Modèle LLM
- **Pandas** : Traitement de données
- **OpenPyXL** : Lecture Excel

### Frontend
- **React** : Bibliothèque UI
- **TypeScript** : Typage statique
- **Vite** : Build tool
- **Tailwind CSS** : Framework CSS
- **shadcn-ui** : Composants UI

## 📝 Fichiers de Configuration

- **backend/.env** : Variables d'environnement
- **backend/requirements.txt** : Dépendances Python
- **package.json** : Dépendances Node.js
- **docker-compose.yml** : Configuration Docker
- **init_db.sql** : Initialisation base de données

## 📚 Documentation

- **README.md** : Documentation principale
- **QUICKSTART.md** : Guide de démarrage rapide
- **backend/README.md** : Documentation backend
- **backend/API_DOCUMENTATION.md** : Documentation API
- **backend/EXCEL_FORMAT.md** : Format Excel requis

## 🎯 Points d'Entrée

### Développement
- Frontend : `npm run dev` → http://localhost:5173
- Backend : `uvicorn main:app --reload` → http://localhost:8000
- API Docs : http://localhost:8000/docs

### Production
- Frontend : `npm run build` puis `npm run preview`
- Backend : `uvicorn main:app --host 0.0.0.0 --port 8000`

## 🔐 Sécurité

- Variables sensibles dans .env (non versionnées)
- Validation des entrées utilisateur
- Requêtes SQL paramétrées (protection injection SQL)
- CORS configuré pour origines autorisées

## 📈 Évolutions Futures

1. **Authentification**
   - JWT tokens
   - Rôles utilisateurs (admin, prof, étudiant)

2. **Notifications**
   - Rappels de cours
   - Changements d'emploi du temps

3. **Export**
   - PDF des emplois du temps
   - iCal pour calendriers

4. **Analytics**
   - Statistiques d'utilisation
   - Questions fréquentes

5. **Multi-langue**
   - Support français/anglais/arabe
