# Architecture Visuelle du Système

## Vue d'Ensemble

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                          CHATBOT EMPLOI DU TEMPS                          ║
║                                                                           ║
║  Frontend (React) ←→ Backend (FastAPI) ←→ LLM (Qwen) ←→ PostgreSQL      ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

## Architecture Détaillée

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              UTILISATEURS                                │
│                                                                          │
│  👨‍🎓 Étudiants        👨‍🏫 Professeurs        👨‍💼 Administrateurs        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 │ HTTP/HTTPS
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React + Vite)                          │
│                        http://localhost:5173                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐     │
│  │   Chat.tsx       │  │   Admin.tsx      │  │   Index.tsx      │     │
│  │                  │  │                  │  │                  │     │
│  │ • Interface chat │  │ • Upload Excel   │  │ • Page accueil   │     │
│  │ • Historique     │  │ • Gestion files  │  │ • Navigation     │     │
│  │ • Questions      │  │ • Statut upload  │  │                  │     │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘     │
│                                                                          │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 │ REST API (JSON)
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      BACKEND API (FastAPI)                               │
│                     http://localhost:8000                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                         main.py                                 │    │
│  │  • Configuration CORS                                           │    │
│  │  • Enregistrement routes                                        │    │
│  │  • Création tables DB                                           │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────┐  ┌──────────────────────┐                    │
│  │   routes/chat.py     │  │   routes/admin.py    │                    │
│  │                      │  │                      │                    │
│  │ POST /api/chat       │  │ POST /api/admin/     │                    │
│  │ • Reçoit question    │  │      upload-emploi   │                    │
│  │ • Appelle SQL Agent  │  │ • Reçoit Excel       │                    │
│  │ • Retourne réponse   │  │ • Parse et stocke    │                    │
│  └──────────┬───────────┘  └──────────┬───────────┘                    │
│             │                          │                                 │
│             ▼                          ▼                                 │
│  ┌──────────────────────┐  ┌──────────────────────┐                    │
│  │ services/            │  │ services/            │                    │
│  │ sql_agent.py         │  │ excel_parser.py      │                    │
│  │                      │  │                      │                    │
│  │ • Orchestration      │  │ • Lecture Excel      │                    │
│  │ • Appelle LLM        │  │ • Extraction données │                    │
│  │ • Exécute SQL        │  │ • Insertion DB       │                    │
│  └──────────┬───────────┘  └──────────┬───────────┘                    │
│             │                          │                                 │
│             ▼                          │                                 │
│  ┌──────────────────────┐             │                                 │
│  │ services/            │             │                                 │
│  │ llm_service.py       │             │                                 │
│  │                      │             │                                 │
│  │ • Qwen2.5-7B-Instruct│             │                                 │
│  │ • Génère SQL         │             │                                 │
│  │ • Formate réponses   │             │                                 │
│  └──────────┬───────────┘             │                                 │
│             │                          │                                 │
│             ▼                          ▼                                 │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │                    models/database.py                         │      │
│  │                                                               │      │
│  │  • Modèles SQLAlchemy                                         │      │
│  │  • Relations entre tables                                     │      │
│  │  • Contraintes et index                                       │      │
│  └───────────────────────────┬───────────────────────────────────┘      │
│                              │                                           │
└──────────────────────────────┼───────────────────────────────────────────┘
                               │
                               │ SQL Queries
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      DATABASE (PostgreSQL)                               │
│                     postgresql://localhost:5432                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────┐   │
│  │ annees_            │  │ semestres          │  │ departements   │   │
│  │ universitaires     │  │                    │  │                │   │
│  └─────────┬──────────┘  └──────────┬─────────┘  └────────┬───────┘   │
│            │                        │                      │            │
│            └────────────────────────┴──────────────────────┘            │
│                                     │                                    │
│                                     ▼                                    │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                          classes                                │    │
│  └──────────────────────────────┬─────────────────────────────────┘    │
│                                 │                                        │
│                                 ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                      emplois_versions                           │    │
│  └──────────────────────────────┬─────────────────────────────────┘    │
│                                 │                                        │
│                                 ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                         seances                                 │    │
│  │  (Table centrale avec toutes les séances de cours)             │    │
│  └──────────────────────────────┬─────────────────────────────────┘    │
│                                 │                                        │
│            ┌────────────────────┼────────────────────┐                  │
│            │                    │                    │                  │
│            ▼                    ▼                    ▼                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐           │
│  │ professeurs    │  │ matieres       │  │ salles         │           │
│  └────────────────┘  └────────────────┘  └────────────────┘           │
│                                                                          │
│  ┌────────────────┐                                                     │
│  │ groupes        │                                                     │
│  │ (P1, P2, etc.) │                                                     │
│  └────────────────┘                                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Flux de Données : Question Chat

```
1. Utilisateur tape : "Où est Mr BEN SLIMA maintenant ?"
   │
   ▼
2. Frontend (Chat.tsx)
   │ POST /api/chat
   │ { message: "Où est Mr BEN SLIMA maintenant ?",
   │   user_role: "student",
   │   user_class: "2 ING GII 3" }
   ▼
3. Backend (routes/chat.py)
   │ Reçoit la requête
   │ Crée un SQL Agent
   ▼
4. SQL Agent (services/sql_agent.py)
   │ Appelle le LLM Service
   ▼
5. LLM Service (services/llm_service.py)
   │ Prompt : "Génère une requête SQL pour : Où est Mr BEN SLIMA maintenant ?"
   │ Qwen2.5-7B-Instruct traite
   ▼
6. LLM génère :
   │ SELECT c.nom, s.jour, s.heure_debut, s.heure_fin, sa.nom
   │ FROM seances s
   │ JOIN classes c ON s.classe_id = c.id
   │ JOIN professeurs p ON s.professeur_id = p.id
   │ JOIN salles sa ON s.salle_id = sa.id
   │ WHERE p.nom_complet = 'Mr BEN SLIMA'
   │ AND s.jour = 'Lundi'
   │ AND s.heure_debut <= CURRENT_TIME
   │ AND s.heure_fin >= CURRENT_TIME
   ▼
7. SQL Agent exécute la requête sur PostgreSQL
   │ Résultat : [{ nom: "2 ING GII 3", jour: "Lundi", 
   │              heure_debut: "08:00", heure_fin: "10:00",
   │              salle: "C14" }]
   ▼
8. LLM Service formate la réponse
   │ "Mr BEN SLIMA est actuellement en salle C14 avec la classe 
   │  2 ING GII 3 de 08:00 à 10:00."
   ▼
9. Backend retourne au Frontend
   │ { response: "Mr BEN SLIMA est actuellement..." }
   ▼
10. Frontend affiche la réponse à l'utilisateur
```

## Flux de Données : Upload Excel

```
1. Admin sélectionne un fichier Excel
   │
   ▼
2. Frontend (Admin.tsx)
   │ POST /api/admin/upload-emploi
   │ FormData {
   │   file: emploi_temps.xlsx,
   │   classe_nom: "2 ING GII 3",
   │   version_date: "2026-02-15"
   │ }
   ▼
3. Backend (routes/admin.py)
   │ Reçoit le fichier
   │ Sauvegarde temporairement
   ▼
4. Excel Parser (services/excel_parser.py)
   │ Lit le fichier Excel avec pandas
   │ Parse chaque cellule :
   │   - Matière
   │   - Professeur
   │   - Salle
   │   - Groupe (optionnel)
   ▼
5. Pour chaque séance :
   │ • Crée/récupère la matière
   │ • Crée/récupère le professeur
   │ • Crée/récupère la salle
   │ • Crée/récupère le groupe
   │ • Crée la séance
   ▼
6. Insertion dans PostgreSQL
   │ INSERT INTO matieres ...
   │ INSERT INTO professeurs ...
   │ INSERT INTO salles ...
   │ INSERT INTO seances ...
   ▼
7. Backend retourne le résultat
   │ { success: true,
   │   message: "Emploi du temps importé avec succès",
   │   version_id: 1 }
   ▼
8. Frontend affiche le succès
```

## Composants Clés

```
┌─────────────────────────────────────────────────────────────┐
│                    LLM SERVICE                               │
│                                                              │
│  Input:  Question en langage naturel                        │
│  Output: Requête SQL PostgreSQL                             │
│                                                              │
│  Modèle: Qwen2.5-7B-Instruct                                │
│  • 7 milliards de paramètres                                │
│  • Spécialisé pour les instructions                         │
│  • Support multilingue (français)                           │
│  • Génération de code SQL                                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    SQL AGENT                                 │
│                                                              │
│  Rôle: Orchestrateur entre LLM et Database                  │
│                                                              │
│  1. Reçoit la question                                      │
│  2. Appelle le LLM pour générer SQL                         │
│  3. Valide et nettoie la requête                            │
│  4. Exécute sur PostgreSQL                                  │
│  5. Retourne les résultats au LLM                           │
│  6. Formate la réponse finale                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  EXCEL PARSER                                │
│                                                              │
│  Rôle: Transformer Excel en données structurées             │
│                                                              │
│  1. Lit le fichier Excel (pandas)                           │
│  2. Parse chaque cellule (matière, prof, salle)            │
│  3. Crée les entités si elles n'existent pas               │
│  4. Insère les séances dans la DB                           │
│  5. Gère les groupes (P1, P2)                               │
└─────────────────────────────────────────────────────────────┘
```

## Technologies

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   React      │  │   FastAPI    │  │    Qwen      │  │  PostgreSQL  │
│              │  │              │  │              │  │              │
│ • TypeScript │  │ • Python 3.9+│  │ • 7B params  │  │ • Version 14+│
│ • Vite       │  │ • Async      │  │ • Instruct   │  │ • Relations  │
│ • Tailwind   │  │ • REST API   │  │ • Hugging    │  │ • Index      │
│ • shadcn-ui  │  │ • CORS       │  │   Face       │  │ • ACID       │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

## Ports et URLs

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend:  http://localhost:5173                           │
│  Backend:   http://localhost:8000                           │
│  API Docs:  http://localhost:8000/docs                      │
│  Database:  postgresql://localhost:5432/emploi_temps_db     │
└─────────────────────────────────────────────────────────────┘
```
