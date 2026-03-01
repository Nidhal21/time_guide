# Backend - Chatbot Emploi du Temps

Backend FastAPI avec intégration du modèle Qwen2.5-7B-Instruct pour un chatbot d'emploi du temps universitaire.

## Architecture

```
User → Frontend → Backend API → LLM Agent (Qwen) → SQL Tool → PostgreSQL
```

## Prérequis

- Python 3.9+
- PostgreSQL 14+
- GPU recommandé (pour le modèle LLM)
- 16GB RAM minimum

## Installation

### 1. Installer PostgreSQL

```bash
# Windows: Télécharger depuis https://www.postgresql.org/download/windows/
# Créer la base de données
psql -U postgres
CREATE DATABASE emploi_temps_db;
\q
```

### 2. Initialiser la base de données

```bash
psql -U postgres -d emploi_temps_db -f init_db.sql
```

### 3. Installer les dépendances Python

```bash
cd backend
pip install -r requirements.txt
```

### 4. Configurer les variables d'environnement

Éditer le fichier `.env` :

```env
DATABASE_URL=postgresql://postgres:votre_password@localhost:5432/emploi_temps_db
HUGGINGFACE_TOKEN=votre_token_hf  # Optionnel
MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
```

### 5. Lancer le serveur

```bash
# Depuis le dossier backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Le serveur sera accessible sur `http://localhost:8000`

## API Endpoints

### Chat
- **POST** `/api/chat`
  - Body: `{ "message": "string", "user_role": "student|professor", "user_class": "string" }`
  - Response: `{ "response": "string" }`

### Admin
- **POST** `/api/admin/upload-emploi`
  - Form Data: 
    - `file`: Fichier Excel
    - `classe_nom`: Nom de la classe
    - `version_date`: Date au format YYYY-MM-DD
  - Response: `{ "success": boolean, "message": "string", "version_id": number }`

## Format Excel attendu

Le fichier Excel doit contenir les colonnes suivantes :

| Heure | Lundi | Mardi | Mercredi | Jeudi | Vendredi | Samedi |
|-------|-------|-------|----------|-------|----------|--------|
| 08:00-10:00 | MATIERE<br>Prof<br>Salle<br>Groupe | ... | ... | ... | ... | ... |

Chaque cellule contient :
1. Nom de la matière
2. Nom du professeur
3. Nom de la salle
4. Groupe (optionnel : P1, P2, etc.)

## Exemples de questions

- "Où est Mr BEN SLIMA maintenant ?"
- "Dans quelle salle j'ai cours maintenant ?"
- "Quel est mon emploi du temps de demain ?"
- "Quand est-ce que j'ai cours de TRAIT IMAGES ?"
- "Qui enseigne en salle C14 à 10h ?"

## Structure de la base de données

Voir `init_db.sql` pour la structure complète.

Tables principales :
- `annees_universitaires`
- `semestres`
- `departements`
- `classes`
- `professeurs`
- `matieres`
- `salles`
- `groupes`
- `emplois_versions`
- `seances`

## Modèle LLM

Le système utilise **Qwen2.5-7B-Instruct** de Hugging Face pour :
1. Générer des requêtes SQL à partir de questions en langage naturel
2. Formater les résultats en réponses naturelles

Le modèle est chargé automatiquement au démarrage (peut prendre quelques minutes).

## Optimisations

- Index sur les colonnes fréquemment recherchées
- Cache des requêtes SQL communes (à implémenter)
- Utilisation de GPU pour l'inférence LLM

## Troubleshooting

### Erreur de mémoire
Si le modèle ne charge pas, réduire la taille ou utiliser quantization :
```python
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    load_in_8bit=True  # Quantization 8-bit
)
```

### Connexion PostgreSQL échoue
Vérifier que PostgreSQL est démarré et que les credentials sont corrects dans `.env`

### Import Excel échoue
Vérifier le format du fichier Excel et que toutes les colonnes requises sont présentes
