# Chatbot Emploi du Temps Universitaire

Chatbot intelligent pour la gestion et consultation des emplois du temps universitaires, utilisant le modèle Qwen2.5-7B-Instruct.

## Architecture

```
User
 ↓
Frontend (React + Vite)
 ↓
Backend API (FastAPI)
 ↓
LLM Agent (Qwen2.5-7B-Instruct)
 ↓
SQL Tool
 ↓
Database (PostgreSQL)
```

## Fonctionnalités

- 💬 **Chat intelligent** : Posez des questions en langage naturel
- 📊 **Import Excel** : Upload des emplois du temps depuis des fichiers Excel
- 🔍 **Recherche avancée** : Trouvez rapidement les cours, salles, professeurs
- 👥 **Multi-utilisateurs** : Support étudiants et professeurs
- 🤖 **IA intégrée** : Génération automatique de requêtes SQL

## Technologies

### Frontend
- React + TypeScript
- Vite
- Tailwind CSS
- shadcn-ui

### Backend
- FastAPI
- SQLAlchemy
- PostgreSQL
- Transformers (Hugging Face)
- Qwen2.5-7B-Instruct

## Installation

### Prérequis
- Node.js 18+
- Python 3.9+
- PostgreSQL 14+
- 16GB RAM minimum (pour le modèle LLM)

### 1. Cloner le projet

```bash
git clone <YOUR_GIT_URL>
cd time-guide-ai-main
```

### 2. Configuration Backend

```bash
# Installer PostgreSQL et créer la base de données
psql -U postgres
CREATE DATABASE emploi_temps_db;
\q

# Initialiser la base de données
psql -U postgres -d emploi_temps_db -f backend/init_db.sql

# Installer les dépendances Python
cd backend
pip install -r requirements.txt

# Configurer les variables d'environnement
# Éditer backend/.env avec vos credentials

# Lancer le backend
uvicorn main:app --reload --port 8000
```

Ou utiliser le script de démarrage Windows :
```bash
start_backend.bat
```

### 3. Configuration Frontend

```bash
# Installer les dépendances
npm install

# Lancer le frontend
npm run dev
```

## Utilisation

### Pour les Administrateurs

1. Accéder à la page Admin
2. Uploader un fichier Excel avec l'emploi du temps
3. Spécifier la classe et la date de version
4. Le système parse automatiquement et stocke dans la base de données

Format Excel requis : Voir [EXCEL_FORMAT.md](backend/EXCEL_FORMAT.md)

### Pour les Étudiants/Professeurs

1. Accéder au chat
2. Poser des questions en langage naturel :
   - "Où est Mr BEN SLIMA maintenant ?"
   - "Dans quelle salle j'ai cours maintenant ?"
   - "Quel est mon emploi du temps de demain ?"
   - "Quand est-ce que j'ai cours de TRAIT IMAGES ?"

## Structure du Projet

```
time-guide-ai-main/
├── backend/
│   ├── app/
│   │   ├── models/          # Modèles SQLAlchemy
│   │   ├── routes/          # Routes API
│   │   ├── services/        # Services (LLM, Excel, SQL)
│   │   └── utils/
│   ├── main.py              # Point d'entrée FastAPI
│   ├── requirements.txt     # Dépendances Python
│   ├── init_db.sql          # Script SQL d'initialisation
│   └── README.md            # Documentation backend
├── src/
│   ├── components/          # Composants React
│   ├── pages/               # Pages (Chat, Admin)
│   └── ...
├── start_backend.bat        # Script de démarrage Windows
└── README.md
```

## API Endpoints

### Chat
- `POST /api/chat` - Envoyer un message au chatbot

### Admin
- `POST /api/admin/upload-emploi` - Uploader un emploi du temps Excel

### Health
- `GET /health` - Vérifier l'état du serveur

Documentation complète : `http://localhost:8000/docs`

## Base de Données

### Tables principales
- `annees_universitaires` - Années académiques
- `semestres` - Semestres
- `departements` - Départements (GII, INFO, TELECOM)
- `classes` - Classes
- `professeurs` - Professeurs
- `matieres` - Matières
- `salles` - Salles de cours
- `groupes` - Groupes (P1, P2, etc.)
- `emplois_versions` - Versions des emplois du temps
- `seances` - Séances de cours

## Modèle LLM

Le système utilise **Qwen2.5-7B-Instruct** pour :
1. Comprendre les questions en langage naturel
2. Générer des requêtes SQL appropriées
3. Formater les réponses de manière naturelle

Le modèle est téléchargé automatiquement depuis Hugging Face au premier démarrage.

## Développement

### Frontend
```bash
npm run dev      # Mode développement
npm run build    # Build production
npm run preview  # Prévisualiser le build
```

### Backend
```bash
uvicorn main:app --reload  # Mode développement avec hot-reload
```

## Troubleshooting

### Le modèle LLM ne charge pas
- Vérifier que vous avez assez de RAM (16GB minimum)
- Utiliser la quantization 8-bit si nécessaire
- Vérifier votre connexion internet pour le téléchargement

### Erreur de connexion PostgreSQL
- Vérifier que PostgreSQL est démarré
- Vérifier les credentials dans `backend/.env`
- Vérifier que la base de données existe

### Import Excel échoue
- Vérifier le format du fichier (voir EXCEL_FORMAT.md)
- Vérifier que toutes les colonnes requises sont présentes

## Licence

MIT

## Support

Pour toute question ou problème, ouvrir une issue sur GitHub.
