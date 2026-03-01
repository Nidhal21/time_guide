# Guide de Dépannage

## 🔍 Problèmes Courants et Solutions

### 1. Problèmes d'Installation

#### ❌ "pip install échoue"
**Symptômes :** Erreurs lors de l'installation des dépendances Python

**Solutions :**
```bash
# Mettre à jour pip
python -m pip install --upgrade pip

# Installer avec verbose pour voir les erreurs
pip install -r requirements.txt -v

# Si problème avec torch, installer séparément
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

#### ❌ "npm install échoue"
**Symptômes :** Erreurs lors de l'installation des dépendances Node

**Solutions :**
```bash
# Nettoyer le cache
npm cache clean --force

# Supprimer node_modules et réinstaller
rmdir /s /q node_modules
del package-lock.json
npm install
```

---

### 2. Problèmes de Base de Données

#### ❌ "Connection refused" ou "could not connect to server"
**Symptômes :** Le backend ne peut pas se connecter à PostgreSQL

**Solutions :**
```bash
# Vérifier que PostgreSQL est démarré
# Windows : Services → PostgreSQL

# Avec Docker
docker ps  # Vérifier que le conteneur tourne
docker-compose up -d  # Redémarrer si nécessaire

# Tester la connexion
psql -U postgres -d emploi_temps_db
```

#### ❌ "database does not exist"
**Symptômes :** La base de données n'existe pas

**Solutions :**
```bash
# Créer la base de données
psql -U postgres
CREATE DATABASE emploi_temps_db;
\q

# Initialiser les tables
psql -U postgres -d emploi_temps_db -f backend/init_db.sql
```

#### ❌ "password authentication failed"
**Symptômes :** Mauvais mot de passe PostgreSQL

**Solutions :**
```bash
# Vérifier le .env
# DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/emploi_temps_db

# Réinitialiser le mot de passe PostgreSQL si nécessaire
# Windows : pg_ctl restart -D "C:\Program Files\PostgreSQL\14\data"
```

---

### 3. Problèmes avec le Modèle LLM

#### ❌ "Out of memory" ou "CUDA out of memory"
**Symptômes :** Le modèle ne charge pas, erreur de mémoire

**Solutions :**

**Option 1 : Utiliser quantization 8-bit**
```python
# Dans backend/app/services/llm_service.py
self.model = AutoModelForCausalLM.from_pretrained(
    self.model_name,
    load_in_8bit=True,  # Ajouter cette ligne
    device_map="auto"
)
```

**Option 2 : Utiliser un modèle plus petit**
```env
# Dans backend/.env
MODEL_NAME=Qwen/Qwen2.5-3B-Instruct  # Au lieu de 7B
```

**Option 3 : Utiliser CPU uniquement**
```python
# Dans backend/app/services/llm_service.py
self.device = "cpu"  # Forcer CPU
```

#### ❌ "Model download is slow"
**Symptômes :** Le téléchargement du modèle prend trop de temps

**Solutions :**
```bash
# Télécharger manuellement avec huggingface-cli
pip install huggingface-hub
huggingface-cli download Qwen/Qwen2.5-7B-Instruct

# Ou utiliser un miroir
export HF_ENDPOINT=https://hf-mirror.com
```

#### ❌ "Token limit exceeded"
**Symptômes :** Erreur lors de la génération de réponses longues

**Solutions :**
```python
# Dans llm_service.py, augmenter max_new_tokens
outputs = self.model.generate(
    **inputs,
    max_new_tokens=1024,  # Augmenter si nécessaire
    temperature=0.1
)
```

---

### 4. Problèmes d'Import Excel

#### ❌ "Invalid file format"
**Symptômes :** Le fichier Excel n'est pas reconnu

**Solutions :**
- Vérifier que le fichier est bien .xlsx ou .xls
- Ouvrir avec Excel et sauvegarder à nouveau
- Vérifier que les colonnes requises existent : Heure, Lundi, Mardi, etc.

#### ❌ "Parsing error"
**Symptômes :** Erreur lors de l'analyse du fichier

**Solutions :**
```python
# Vérifier le format des cellules
# Chaque cellule doit contenir :
# Ligne 1 : Matière
# Ligne 2 : Professeur
# Ligne 3 : Salle
# Ligne 4 : Groupe (optionnel)

# Exemple correct :
"""
TRAIT IMAGES
Mr BEN SLIMA
C14
"""
```

#### ❌ "Time format error"
**Symptômes :** Erreur de format d'heure

**Solutions :**
- Format requis : "HH:MM-HH:MM"
- Exemples valides : "08:00-10:00", "14:30-16:30"
- Exemples invalides : "8:00-10:00", "08h00-10h00"

---

### 5. Problèmes de Communication Frontend-Backend

#### ❌ "CORS error"
**Symptômes :** Erreur CORS dans la console du navigateur

**Solutions :**
```python
# Dans backend/main.py, vérifier la configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### ❌ "Network error" ou "Failed to fetch"
**Symptômes :** Le frontend ne peut pas contacter le backend

**Solutions :**
```bash
# Vérifier que le backend tourne
curl http://localhost:8000/health

# Vérifier l'URL dans le frontend
# src/pages/Chat.tsx et Admin.tsx
const API_URL = "http://localhost:8000/api";
```

#### ❌ "404 Not Found"
**Symptômes :** Endpoint non trouvé

**Solutions :**
- Vérifier que le backend est démarré
- Vérifier l'URL de l'endpoint
- Consulter la doc API : http://localhost:8000/docs

---

### 6. Problèmes de Performance

#### ❌ "Slow response time"
**Symptômes :** Le chatbot met trop de temps à répondre

**Solutions :**

**1. Optimiser les requêtes SQL**
```sql
-- Vérifier les index
SELECT * FROM pg_indexes WHERE tablename = 'seances';

-- Ajouter des index si nécessaire
CREATE INDEX idx_seance_heure ON seances(heure_debut, heure_fin);
```

**2. Réduire la température du modèle**
```python
# Dans llm_service.py
outputs = self.model.generate(
    **inputs,
    temperature=0.1,  # Plus bas = plus rapide mais moins créatif
    do_sample=False   # Désactiver le sampling
)
```

**3. Utiliser un cache**
```python
# Implémenter un cache simple
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_query(question: str):
    # ...
```

---

### 7. Problèmes de Déploiement

#### ❌ "Port already in use"
**Symptômes :** Le port 8000 ou 5173 est déjà utilisé

**Solutions :**
```bash
# Windows : Trouver et tuer le processus
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Ou utiliser un autre port
uvicorn main:app --port 8001
npm run dev -- --port 5174
```

#### ❌ "Module not found"
**Symptômes :** Import error lors du démarrage

**Solutions :**
```bash
# Vérifier que vous êtes dans le bon dossier
cd backend

# Vérifier l'environnement virtuel
python -c "import sys; print(sys.prefix)"

# Réinstaller les dépendances
pip install -r requirements.txt --force-reinstall
```

---

## 🧪 Tests de Diagnostic

### Test 1 : Vérifier l'installation complète
```bash
cd backend
python test_config.py
```

### Test 2 : Tester la connexion PostgreSQL
```bash
psql -U postgres -d emploi_temps_db -c "SELECT COUNT(*) FROM seances;"
```

### Test 3 : Tester l'API
```bash
# Health check
curl http://localhost:8000/health

# Test chat
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"test","user_role":"student","user_class":"test"}'
```

### Test 4 : Vérifier les logs
```bash
# Backend logs
# Regarder la console où uvicorn tourne

# PostgreSQL logs
# Windows : C:\Program Files\PostgreSQL\14\data\log\
```

---

## 📞 Obtenir de l'Aide

### Logs à fournir
1. Sortie de `python test_config.py`
2. Logs du backend (console uvicorn)
3. Logs PostgreSQL
4. Console du navigateur (F12)

### Informations système
```bash
# Python version
python --version

# Node version
node --version

# PostgreSQL version
psql --version

# RAM disponible
wmic OS get FreePhysicalMemory
```

### Checklist avant de demander de l'aide
- [ ] PostgreSQL est démarré
- [ ] La base de données existe et est initialisée
- [ ] Le fichier .env est correctement configuré
- [ ] Les dépendances sont installées (pip et npm)
- [ ] Les ports 8000 et 5173 sont disponibles
- [ ] Le test_config.py passe avec succès

---

## 🔧 Commandes Utiles

```bash
# Redémarrer tout
docker-compose restart
cd backend && uvicorn main:app --reload
cd .. && npm run dev

# Nettoyer et réinstaller
pip cache purge
npm cache clean --force
pip install -r requirements.txt
npm install

# Réinitialiser la base de données
psql -U postgres -d emploi_temps_db -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
psql -U postgres -d emploi_temps_db -f backend/init_db.sql

# Vérifier les processus
netstat -ano | findstr :8000
netstat -ano | findstr :5173
```
