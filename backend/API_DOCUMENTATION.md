# Documentation API

## Base URL
```
http://localhost:8000
```

## Endpoints

### 1. Health Check

**GET** `/health`

Vérifie que le serveur est opérationnel.

**Response:**
```json
{
  "status": "healthy"
}
```

---

### 2. Chat avec le Bot

**POST** `/api/chat`

Envoie un message au chatbot et reçoit une réponse.

**Request Body:**
```json
{
  "message": "Où est Mr BEN SLIMA maintenant ?",
  "user_role": "student",
  "user_class": "2 ING GII 3"
}
```

**Parameters:**
- `message` (string, required): La question de l'utilisateur
- `user_role` (string, required): "student" ou "professor"
- `user_class` (string, optional): Nom de la classe (pour les étudiants)

**Response:**
```json
{
  "response": "Mr BEN SLIMA est actuellement en salle C14 pour le cours de TRAIT IMAGES de 08:00 à 10:00."
}
```

**Exemples de questions:**
- "Où est Mr BEN SLIMA maintenant ?"
- "Dans quelle salle j'ai cours maintenant ?"
- "Quel est mon emploi du temps de demain ?"
- "Quand est-ce que j'ai cours de TRAIT IMAGES ?"
- "Qui enseigne en salle C14 à 10h ?"
- "Quels cours j'ai le lundi ?"

---

### 3. Upload Emploi du Temps

**POST** `/api/admin/upload-emploi`

Upload un fichier Excel contenant un emploi du temps.

**Request (multipart/form-data):**
- `file` (file, required): Fichier Excel (.xlsx ou .xls)
- `classe_nom` (string, required): Nom de la classe (ex: "2 ING GII 3")
- `version_date` (string, required): Date de version au format YYYY-MM-DD

**Response (Success):**
```json
{
  "success": true,
  "message": "Emploi du temps importé avec succès",
  "version_id": 1
}
```

**Response (Error):**
```json
{
  "success": false,
  "message": "Erreur lors de l'import: [détails de l'erreur]"
}
```

**Format Excel requis:**

Le fichier doit contenir les colonnes suivantes :
- `Heure` : Format "HH:MM-HH:MM"
- `Lundi`, `Mardi`, `Mercredi`, `Jeudi`, `Vendredi`, `Samedi`

Chaque cellule de cours doit contenir (séparé par des retours à la ligne) :
1. Nom de la matière
2. Nom du professeur
3. Nom de la salle
4. Groupe (optionnel)

**Exemple de cellule:**
```
TRAIT IMAGES
Mr BEN SLIMA
C14
```

---

## Codes d'erreur

- `200` : Succès
- `400` : Requête invalide
- `404` : Ressource non trouvée
- `500` : Erreur serveur

---

## Exemples avec cURL

### Chat
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Où est Mr BEN SLIMA maintenant ?",
    "user_role": "student",
    "user_class": "2 ING GII 3"
  }'
```

### Upload
```bash
curl -X POST http://localhost:8000/api/admin/upload-emploi \
  -F "file=@emploi_temps.xlsx" \
  -F "classe_nom=2 ING GII 3" \
  -F "version_date=2026-02-15"
```

---

## Exemples avec JavaScript (Fetch)

### Chat
```javascript
const response = await fetch('http://localhost:8000/api/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    message: "Où est Mr BEN SLIMA maintenant ?",
    user_role: "student",
    user_class: "2 ING GII 3"
  })
});

const data = await response.json();
console.log(data.response);
```

### Upload
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('classe_nom', '2 ING GII 3');
formData.append('version_date', '2026-02-15');

const response = await fetch('http://localhost:8000/api/admin/upload-emploi', {
  method: 'POST',
  body: formData
});

const data = await response.json();
console.log(data);
```

---

## Documentation Interactive

Une documentation interactive Swagger est disponible à :
```
http://localhost:8000/docs
```

Une documentation ReDoc alternative est disponible à :
```
http://localhost:8000/redoc
```
