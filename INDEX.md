# 📚 Index de la Documentation

Bienvenue dans le projet **Chatbot Emploi du Temps** ! Ce fichier vous guide vers toute la documentation disponible.

---

## 🚀 Pour Commencer

### Nouveau sur le projet ?
1. **[README.md](README.md)** - Vue d'ensemble du projet
2. **[QUICKSTART.md](QUICKSTART.md)** - Guide de démarrage rapide (15-30 min)
3. **[SUMMARY.md](SUMMARY.md)** - Synthèse complète du projet

### Installation
1. **[QUICKSTART.md](QUICKSTART.md)** - Instructions d'installation pas à pas
2. **[docker-compose.yml](docker-compose.yml)** - Configuration PostgreSQL
3. **[start_backend.bat](start_backend.bat)** - Script de démarrage Windows

---

## 📖 Documentation Principale

### Vue d'Ensemble
- **[README.md](README.md)** - Documentation principale du projet
- **[SUMMARY.md](SUMMARY.md)** - Synthèse finale avec checklist
- **[CHANGELOG.md](CHANGELOG.md)** - Récapitulatif des modifications

### Architecture
- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - Structure détaillée du projet
- **[ARCHITECTURE_DIAGRAM.md](ARCHITECTURE_DIAGRAM.md)** - Diagrammes visuels ASCII

### Guides
- **[QUICKSTART.md](QUICKSTART.md)** - Démarrage rapide
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Guide de dépannage complet

---

## 🔧 Documentation Backend

### Général
- **[backend/README.md](backend/README.md)** - Documentation backend complète
- **[backend/requirements.txt](backend/requirements.txt)** - Dépendances Python
- **[backend/.env.example](backend/.env.example)** - Template variables d'environnement

### API
- **[backend/API_DOCUMENTATION.md](backend/API_DOCUMENTATION.md)** - Documentation API REST
  - Endpoints
  - Exemples cURL
  - Exemples JavaScript
  - Codes d'erreur

### Base de Données
- **[backend/init_db.sql](backend/init_db.sql)** - Script SQL d'initialisation
  - 10 tables
  - Index optimisés
  - Données de test

### Format de Données
- **[backend/EXCEL_FORMAT.md](backend/EXCEL_FORMAT.md)** - Format Excel requis
  - Structure du fichier
  - Format des cellules
  - Exemples

### Utilitaires
- **[backend/test_config.py](backend/test_config.py)** - Script de test configuration
- **[backend/generate_example_excel.py](backend/generate_example_excel.py)** - Générateur Excel

---

## 💻 Code Source

### Backend Structure
```
backend/
├── main.py                    # Point d'entrée FastAPI
├── app/
│   ├── models/
│   │   ├── database.py        # Modèles SQLAlchemy
│   │   └── db_config.py       # Configuration DB
│   ├── routes/
│   │   ├── chat.py            # Routes chat
│   │   └── admin.py           # Routes admin
│   └── services/
│       ├── llm_service.py     # Service Qwen LLM
│       ├── sql_agent.py       # Agent SQL
│       └── excel_parser.py    # Parser Excel
```

### Frontend Structure
```
src/
├── pages/
│   ├── Chat.tsx               # Page chat (modifiée)
│   ├── Admin.tsx              # Page admin (modifiée)
│   └── Index.tsx              # Page accueil
└── components/
    ├── chat/                  # Composants chat
    └── ui/                    # Composants UI
```

---

## 🎯 Par Cas d'Usage

### Je veux installer le projet
1. [QUICKSTART.md](QUICKSTART.md) - Installation complète
2. [backend/README.md](backend/README.md) - Configuration backend
3. [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Si problèmes

### Je veux comprendre l'architecture
1. [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Structure détaillée
2. [ARCHITECTURE_DIAGRAM.md](ARCHITECTURE_DIAGRAM.md) - Diagrammes visuels
3. [SUMMARY.md](SUMMARY.md) - Flux de données

### Je veux utiliser l'API
1. [backend/API_DOCUMENTATION.md](backend/API_DOCUMENTATION.md) - Documentation API
2. http://localhost:8000/docs - Swagger UI (après démarrage)
3. [backend/README.md](backend/README.md) - Exemples

### Je veux uploader un emploi du temps
1. [backend/EXCEL_FORMAT.md](backend/EXCEL_FORMAT.md) - Format requis
2. [backend/generate_example_excel.py](backend/generate_example_excel.py) - Générer exemple
3. http://localhost:5173/admin - Interface upload

### J'ai un problème
1. [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Guide de dépannage
2. [backend/test_config.py](backend/test_config.py) - Tester configuration
3. [CHANGELOG.md](CHANGELOG.md) - Vérifier les modifications

### Je veux contribuer
1. [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Comprendre la structure
2. [backend/README.md](backend/README.md) - Backend
3. [README.md](README.md) - Vue d'ensemble

---

## 📊 Documentation par Composant

### LLM (Qwen2.5-7B-Instruct)
- **Fichier** : [backend/app/services/llm_service.py](backend/app/services/llm_service.py)
- **Doc** : [backend/README.md](backend/README.md) - Section "Modèle LLM"
- **Config** : [backend/.env](backend/.env) - Variable MODEL_NAME

### SQL Agent
- **Fichier** : [backend/app/services/sql_agent.py](backend/app/services/sql_agent.py)
- **Doc** : [ARCHITECTURE_DIAGRAM.md](ARCHITECTURE_DIAGRAM.md) - Section "SQL Agent"
- **Schéma** : [backend/init_db.sql](backend/init_db.sql)

### Excel Parser
- **Fichier** : [backend/app/services/excel_parser.py](backend/app/services/excel_parser.py)
- **Format** : [backend/EXCEL_FORMAT.md](backend/EXCEL_FORMAT.md)
- **Exemple** : [backend/generate_example_excel.py](backend/generate_example_excel.py)

### Base de Données
- **Script** : [backend/init_db.sql](backend/init_db.sql)
- **Modèles** : [backend/app/models/database.py](backend/app/models/database.py)
- **Config** : [backend/app/models/db_config.py](backend/app/models/db_config.py)

### API REST
- **Routes Chat** : [backend/app/routes/chat.py](backend/app/routes/chat.py)
- **Routes Admin** : [backend/app/routes/admin.py](backend/app/routes/admin.py)
- **Doc API** : [backend/API_DOCUMENTATION.md](backend/API_DOCUMENTATION.md)

### Frontend
- **Chat** : [src/pages/Chat.tsx](src/pages/Chat.tsx)
- **Admin** : [src/pages/Admin.tsx](src/pages/Admin.tsx)
- **Config** : [package.json](package.json)

---

## 🔍 Recherche Rapide

### Commandes
- **Démarrer backend** : `uvicorn main:app --reload` ou `start_backend.bat`
- **Démarrer frontend** : `npm run dev`
- **Tester config** : `python backend/test_config.py`
- **Générer Excel** : `python backend/generate_example_excel.py`

### URLs
- **Frontend** : http://localhost:5173
- **Backend** : http://localhost:8000
- **API Docs** : http://localhost:8000/docs
- **Health** : http://localhost:8000/health

### Fichiers de Configuration
- **Backend env** : [backend/.env](backend/.env)
- **Frontend env** : [.env](.env)
- **Docker** : [docker-compose.yml](docker-compose.yml)
- **Python deps** : [backend/requirements.txt](backend/requirements.txt)
- **Node deps** : [package.json](package.json)

---

## 📝 Checklist Complète

### Installation
- [ ] Lire [README.md](README.md)
- [ ] Suivre [QUICKSTART.md](QUICKSTART.md)
- [ ] Configurer [backend/.env](backend/.env)
- [ ] Exécuter [backend/test_config.py](backend/test_config.py)

### Configuration
- [ ] PostgreSQL installé et démarré
- [ ] Base de données créée ([backend/init_db.sql](backend/init_db.sql))
- [ ] Dépendances Python installées ([backend/requirements.txt](backend/requirements.txt))
- [ ] Dépendances Node installées ([package.json](package.json))

### Test
- [ ] Backend accessible (http://localhost:8000)
- [ ] Frontend accessible (http://localhost:5173)
- [ ] Générer Excel exemple ([backend/generate_example_excel.py](backend/generate_example_excel.py))
- [ ] Uploader via admin (http://localhost:5173/admin)
- [ ] Tester chat (http://localhost:5173/chat)

### En cas de problème
- [ ] Consulter [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- [ ] Vérifier les logs
- [ ] Tester la configuration ([backend/test_config.py](backend/test_config.py))

---

## 🎓 Ressources d'Apprentissage

### Technologies Utilisées
- **FastAPI** : https://fastapi.tiangolo.com/
- **React** : https://react.dev/
- **PostgreSQL** : https://www.postgresql.org/docs/
- **Qwen** : https://huggingface.co/Qwen
- **SQLAlchemy** : https://www.sqlalchemy.org/
- **Transformers** : https://huggingface.co/docs/transformers/

### Concepts
- **LLM Agent** : [ARCHITECTURE_DIAGRAM.md](ARCHITECTURE_DIAGRAM.md)
- **SQL Tool** : [backend/app/services/sql_agent.py](backend/app/services/sql_agent.py)
- **REST API** : [backend/API_DOCUMENTATION.md](backend/API_DOCUMENTATION.md)

---

## 📞 Support

### Documentation
Tous les fichiers .md de ce projet sont votre première ressource.

### Tests
- [backend/test_config.py](backend/test_config.py) - Vérifier la configuration
- http://localhost:8000/health - Tester l'API

### Logs
- Console backend (uvicorn)
- Console frontend (npm)
- Console navigateur (F12)
- PostgreSQL logs

---

## 🎉 Prêt à Commencer ?

1. **Nouveau ?** → [QUICKSTART.md](QUICKSTART.md)
2. **Problème ?** → [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
3. **Comprendre ?** → [ARCHITECTURE_DIAGRAM.md](ARCHITECTURE_DIAGRAM.md)
4. **Développer ?** → [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

**Bon développement ! 🚀**
