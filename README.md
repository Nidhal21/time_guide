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
- 🔐 **Authentification** : Système de login sécurisé
- 📱 **Interface responsive** : Utilisable sur desktop et mobile

## Technologies

### Frontend
- React + TypeScript
- Vite
- Tailwind CSS
- shadcn-ui
- React Router

### Backend
- FastAPI
- SQLAlchemy
- PostgreSQL
- Transformers (Hugging Face)
- Qwen2.5-7B-Instruct
- JWT pour l'authentification

## Installation

### Prérequis
- Node.js 18+
- Python 3.9+
- PostgreSQL 14+
- 16GB RAM minimum (pour le modèle LLM)
- Git

### 1. Cloner le projet

```bash
git clone https://github.com/Nidhal21/time_guide.git
cd time-guide-ai-main
```

### 2. Configuration de l'environnement

#### Variables d'environnement
Créer un fichier `.env` à la racine avec :

```env
# Base de données
DATABASE_URL=postgresql://username:password@localhost:5432/emploi_temps_db

# JWT
JWT_SECRET_KEY=votre_cle_secrete_jwt
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# LLM
MODEL_PATH=models/Qwen2.5-7B-Instruct
GROQ_API_KEY=votre_cle_groq

# Autres
ADMIN_PASSWORD=admin123
```

### 3. Configuration Backend

```bash
# Installer PostgreSQL et créer la base de données
psql -U postgres
CREATE DATABASE emploi_temps_db;
\q

# Initialiser la base de données
psql -U postgres -d emploi_temps_db -f backend/init_db.sql

# Créer un environnement virtuel Python
python -m venv .venv
.venv\Scripts\activate  # Sur Windows

# Installer les dépendances Python
cd backend
pip install -r requirements.txt

# Lancer le backend
uvicorn main:app --reload --port 8000
```

Ou utiliser le script de démarrage Windows :
```bash
start_backend.bat
```

### 4. Configuration Frontend

```bash
# Installer les dépendances
npm install

# Lancer le frontend
npm run dev
```

### 5. Utilisation avec Docker (Optionnel)

```bash
# Construire et lancer les services
docker-compose up --build
```

## Utilisation

### Pour les Administrateurs

1. Accéder à la page Admin (`/admin`)
2. Se connecter avec les credentials admin
3. Uploader un fichier Excel avec l'emploi du temps
4. Spécifier la classe et la date de version
5. Le système parse automatiquement et stocke dans la base de données

Format Excel requis : Voir [EXCEL_FORMAT.md](backend/EXCEL_FORMAT.md)

### Pour les Étudiants/Professeurs

1. Accéder au chat (`/chat`)
2. Se connecter avec vos credentials
3. Poser des questions en langage naturel :
   - "Où est Mr BEN SLIMA maintenant ?"
   - "Dans quelle salle j'ai cours maintenant ?"
   - "Quel est mon emploi du temps de demain ?"
   - "Quand est-ce que j'ai cours de TRAIT IMAGES ?"

## Tests

### Backend
```bash
cd backend
pytest tests/
```

### Frontend
```bash
npm test
```

## Structure du Projet

```
time-guide-ai-main/
├── backend/
│   ├── app/
│   │   ├── models/          # Modèles SQLAlchemy
│   │   ├── routes/          # Routes API (chat, admin, auth)
│   │   ├── services/        # Services (LLM, Excel, SQL, Auth)
│   │   └── utils/
│   ├── tests/               # Tests unitaires
│   ├── main.py              # Point d'entrée FastAPI
│   ├── requirements.txt     # Dépendances Python
│   ├── init_db.sql          # Script SQL d'initialisation
│   └── README.md            # Documentation backend
├── src/
│   ├── components/          # Composants React réutilisables
│   ├── pages/               # Pages principales (Chat, Admin, Auth)
│   ├── contexts/            # Contextes React (Auth)
│   ├── hooks/               # Hooks personnalisés
│   └── lib/                 # Utilitaires
├── public/                  # Assets statiques
├── docker-compose.yml       # Configuration Docker
├── package.json             # Dépendances Node.js
├── tsconfig.json            # Configuration TypeScript
├── tailwind.config.ts       # Configuration Tailwind
├── vite.config.ts           # Configuration Vite
├── start_backend.bat        # Script de démarrage Windows
└── README.md
```

## API Endpoints

### Authentification
- `POST /api/auth/login` - Connexion utilisateur
- `POST /api/auth/register` - Inscription (si activé)

### Chat
- `POST /api/chat` - Envoyer un message au chatbot

### Admin
- `POST /api/admin/upload-emploi` - Uploader un emploi du temps Excel
- `GET /api/admin/emplois` - Lister les emplois du temps

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

## Contribution

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/nouvelle-fonction`)
3. Commit vos changements (`git commit -am 'Ajout nouvelle fonction'`)
4. Push vers la branche (`git push origin feature/nouvelle-fonction`)
5. Créer une Pull Request

## Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## Support

Pour toute question ou problème :
- Ouvrir une issue sur GitHub
- Contacter l'équipe de développement
