# Time Guide AI - Project Resume

## 1. Project Overview

**Time Guide AI** is an intelligent web platform for querying university timetables at ENET'Com. It combines natural language processing with SQL generation to provide conversational access to timetable data.

### Core Capabilities
- Answer natural language questions about **class schedules** (emploi de temps de classe)
- Query **professor locations, availability, and schedules**
- Check **room availability** and current room usage
- Import Excel timetables with automatic validation and database updates
- Support multilingual input (French, Arabic, Tunisian dialect) with typo tolerance
- Extract and serve **institutional information directly from ENET'Com website** (no hardcoded data)
- Track academic calendar (holidays, exam periods)

### Key Problem Solved
Students, professors, and staff can ask questions like:
- "Quel est mon emploi du temps demain ?" (What's my class timetable tomorrow?)
- "Quel est mon emploi de temps de 2 GII 3 ?" (What's the timetable for class 2 GII 3?)
- "Où est Mr BEN SLIMA maintenant ?" (Where is Mr BEN SLIMA now?)
- "Quelles salles sont libres lundi ?" (Which rooms are free Monday?)
- "Quelles sont les coordonnées du département informatique ?" (What's the contact info for IT department?)
- Instead of manually checking spreadsheets, websites, or office phone numbers

---

## 2. Technology Stack & Tools

### Frontend
|

### Backend
| Technology | Purpose |
|-----------|---------|
| **FastAPI** | Modern async Python web framework |
| **Uvicorn** | ASGI server runner |
| **SQLAlchemy** | ORM for database interaction |
| **Psycopg** | PostgreSQL Python adapter |
| **Pandas** | Data manipulation & Excel parsing |
| **OpenPyXL** | Read/write Excel files |
| **Pydantic** | Data validation |
| **Python Dotenv** | Environment variable management |

### AI & Intelligent Processing
| Technology | Purpose |
|-----------|---------|
| **Groq API** | LLM service for intent classification & entity extraction |
| **llama-3.3-70b-versatile** | Specific Groq model used |

### Database
| Technology | Purpose |
|-----------|---------|
| **PostgreSQL 14+** | Relational database |

### Deployment & Orchestration
| Technology | Purpose |
|-----------|---------|
| **Local Development** | Direct Python/Node.js execution (no Docker) |

---

---

## 3. Architecture Overview

```
┌─────────────────────────────────────┐
│    Frontend (React/Vite/TypeScript) │
│  - Chat Interface                   │
│  - Admin Dashboard                  │
│  - Authentication UI                │
└────────────────────┬────────────────┘
                     │ HTTPS
                     ▼
┌─────────────────────────────────────┐
│  FastAPI Backend                    │
│                                     │
│  ┌───────────────────────────────┐ │
│  │ Routes Layer                  │ │
│  │ - /api/chat                   │ │
│  │ - /api/admin/upload-emploi    │ │
│  │ - /api/auth                   │ │
│  └────────────┬────────────────┬─┘ │
│               │                │    │
│         ┌─────▼────┐    ┌──────▼──┐│
│         │ Intent   │    │ Admin   ││
│         │ Router   │    │ Import  ││
│         │ Service  │    │ Service ││
│         └─────┬────┘    └──────┬──┘│
│               │                │    │
│      ┌────────▼────────────────▼──┐ │
│      │ SQLAgent + GroqService    │ │
│      │ - Intent classification   │ │
│      │ - Entity extraction       │ │
│      │ - SQL generation         │ │
│      │ - Response formatting    │ │
│      └────────┬────────────────┬─┘ │
│              │                 │    │
│      ┌───────▼──┐    ┌────────▼──┐ │
│      │ Groq     │    │ Excel     │ │
│      │ API      │    │ Parser    │ │
│      └──────┬───┘    └────────┬──┘ │
└─────────────┼─────────────────┼────┘
              │                 │
              │ REST            │ File Processing
              ▼                 ▼
┌─────────────────────────────────────┐
│  PostgreSQL Database                │
│  - Classes, Professors              │
│  - Rooms, Schedules                 │
│  - Academic Calendar                │
│  - Users & Sessions                 │
└─────────────────────────────────────┘
```

---

## 4. Query Processing Pipeline

### Step-by-Step Flow: User Question → AI Response

#### **Step 1: Frontend Submission**
```
User types: "Où est Mr BEN SLIMA maintenant ?"
```
- React Chat component captures the message
- Sends POST request to `/api/chat` endpoint
- Includes: message content, user role (student/professor), user class

#### **Step 2: Backend Receives Request**
```python
# In: backend/app/routes/chat.py
ChatRequest(
    message="Où est Mr BEN SLIMA maintenant ?",
    user_role="student",
    user_class="2 ING GII 3",
    history=[...]  # Optional conversation history
)
```

#### **Step 3: Message Mode Classification**
**Service:** `groq_service._classify_message_mode()`

Determines if the message is academic or conversational:
- Checks for obvious academic markers: "prof", "cours", "salle", day names
- Uses LLM with temperature=0.0 (deterministic) for classification
- Returns: `"ACADEMIC"` or `"NON_ACADEMIC"`

If `NON_ACADEMIC`: Skip to conversational response (Step 8)

#### **Step 4: Intent Classification**
**Service:** `groq_service._classify_assistant_intent()`

Classifies the intent from 4 categories:
- **GREETING**: Casual conversation, thanks, help requests
- **TIMETABLE**: Schedule/room/professor queries
- **ENETCOM_INFO**: Institutional information
- **OUT_OF_SCOPE**: Unrelated requests

**LLM Prompt Understanding:**
- Supports multilingual input (French, Arabic, English, mixed)
- Tolerates typos, abbreviations, slang
- Uses conversation history for context
- Returns: One category label

**Example Query Types:**
```
1. CLASS TIMETABLE: "Quel est l'emploi de temps de 2 GII 3 ?"
   → Shows all sessions for that class
   → Requires class name to be identified

2. PROFESSOR LOCATION: "Où est Mr BEN SLIMA maintenant ?"
   → Shows current or upcoming sessions for professor
   → No class required

3. ROOM AVAILABILITY: "Quelles salles sont libres lundi ?"
   → Lists available rooms
   → No class or professor required

4. INSTITUTIONAL: "Quelles sont les coordonnées du département ?"
   → Fetches from ENET'Com website
   → No database query needed
```

#### **Step 5: Detailed Query Analysis**
**Service:** `groq_service._analyze_user_message()`

Extracts structured information from the raw message:

```json
{
  "intent": "PROF_LOCATION",
  "answer_source": "DATABASE",
  "confidence": 0.95,
  "standalone_query": "Où se trouve le professeur BEN SLIMA maintenant ?",
  "class_name": null,
  "professor_name": "BEN SLIMA",
  "room_name": null,
  "day_hint": "aujourd'hui",
  "time_hint": "maintenant",
  "university_topic": null
}
```

**Entity Extraction Rules:**
- `professor_name`: Extracted from titles (Mr, Mme, Dr) + name patterns
- `day_hint`: Recognized in French, Arabic, or casual variations (demain, ghoudwa, ajrd)
- `class_name`: Only extracted if asking about "their own" class (not for professor queries)
- `room_name`: Extracted when asking about specific rooms
- `confidence`: 0.95-1.0 = very clear, 0.5-0.7 = requires inference, 0.3-0.5 = significant guessing

#### **Step 6: Intent Routing Decision**
**Service:** `intent_router.route()`

After Step 4-5, router decides execution path:

**Decision Tree:**
```
If answer_source == "UNIVERSITY_SITE"
    → Call UniversityInfoService
    → Fetch institutional knowledge from ENET'Com website
    → Return relevant information (departments, contacts, programs, etc.)

If answer_source == "SMALLTALK"
    → Call groq_service.build_smalltalk_response()
    → Return conversational reply

If answer_source == "OUT_OF_SCOPE"
    → Return polite refusal + capabilities list

If answer_source == "DATABASE"
    → Continue to SQL generation
    → Query the database
```

For our example: remains "DATABASE" → proceed to Step 7

#### **Step 7: SQL Generation & Database Query**
**Service:** `SQLAgent.process_routed_question()` → `groq_service.generate_sql()`

**Missing Info Check:**
```python
# First: Verify we have required information
check_missing_info(question)

# For PROF_LOCATION: don't need class
# For CLASS_SCHEDULE: requires class
# For ROOM_SCHEDULE: don't need class
```

**SQL Generation Process:**
1. Extract schema information from database metadata
2. Send to Groq with prompt:
```python
prompt = f"""You are a PostgreSQL expert. Return ONLY ONE SQL SELECT query.

DATABASE SCHEMA:
{schema_info}

CONTEXT:
- Current Periode ID: {periode_id}
- Resolved professor: BEN SLIMA
- User class: 2 ING GII 3 (may not be needed)

USER QUESTION:
Où est Mr BEN SLIMA maintenant ?

Return only the SQL or ASK_CLASS/ASK_PROF if info is missing.
"""
```

3. Groq generates SQL (example):
```sql
SELECT DISTINCT s.jour, s.heure_debut, s.heure_fin, 
       sa.nom AS salle, m.nom AS matiere,
       c.nom AS classe
FROM seances s
JOIN salles sa ON s.salle_id = sa.id
JOIN professeurs p ON s.professeur_id = p.id
JOIN matieres m ON s.matiere_id = m.id
JOIN classes c ON s.classe_id = c.id
JOIN emplois_versions v ON v.id = s.version_id
WHERE LOWER(p.nom) LIKE '%ben slima%'
  AND v.actif = true
  AND s.jour = 'Lundi'
  AND CURRENT_TIME BETWEEN s.heure_debut AND s.heure_fin
LIMIT 20;
```

4. Validate SQL:
   - Check it's SELECT-only (no INSERT/UPDATE/DELETE)
   - Execute against PostgreSQL
   - Collect results

#### **Step 8: Response Formatting**
**Service:** `groq_service.format_response()`

Transform raw database results into natural language:

**Query Results:**
```
| jour   | heure_debut | heure_fin | salle | matiere      | classe      |
|--------|---------|----------|-------|---------|---------|
| Lundi  | 08:00   | 10:00    | C14   | TRAIT IMAGES | 2 ING GII 3 |
```

**Formatting Strategies:**

1. **Single Value:** Return directly
   - If only one room found: "Salle C14"

2. **Timetable Format:** Group by day and time
   ```
   Lundi :
   
   08:00 - 10:00 | TRAIT IMAGES
   Professeur : Mr BEN SLIMA
   Salle : C14
   ```

3. **List Format:** For available rooms
   ```
   Il y a 3 salles disponibles actuellement :
   - Salle A02
   - Salle B05
   - Salle D11
   ```

4. **LLM Polish (if needed):** For complex results
   - Sends structured data + question to Groq
   - Gets natural language response
   - Post-processes markdown removal

#### **Step 9: Response Return to Frontend**
```json
{
  "response": "Mr BEN SLIMA est actuellement en salle C14 pour le cours de TRAIT IMAGES de 08:00 à 10:00."
}
```

Frontend displays message in chat interface, updates conversation history

---

## 5. Excel Import Process

### Workflow: File Upload → Database Update

#### **Phase 1: File Reception**
```
User (Admin) uploads: "emploi_times_s1.xlsx"
Endpoint: POST /api/admin/upload-emploi
Fields:
  - file: Binary Excel file
  - classe_nom: "2 ING GII 3"
  - version_date: "2026-02-15"
```

#### **Phase 2: File Type Detection**
**Service:** `admin_import_service.detect_workbook_type()`

Examines file structure to auto-detect type:

```python
# Workbook types:
# - "student_s1" → Classes for Semester 1
# - "student_s2" → Classes for Semester 2
# - "teachers_s1" → Professors for Semester 1
# - "teachers_s2" → Professors for Semester 2
# - "rooms_s1" → Rooms for Semester 1
# - "rooms_s2" → Rooms for Semester 2
# - "calendar" → Academic calendar dates

Detection logic:
1. Count number of sheets in workbook
2. Examine column headers (Lundi, Mardi, etc.)
3. Look for specific sheet names
4. Check for periodo markers (P1), (P2)
5. Return best-matching type
```

#### **Phase 3: Excel Parsing**
**Service:** `excel_parser.VerticalExcelParser`

Converts Excel sheet into structured sessions:

**Input Format (Excel Cell Structure):**
```
Time Column | Monday    | Tuesday | Wednesday
08:00-10:00 | Matter    | ---     | Matter
            | Professor | ---     | Professor  
            | Room      | ---     | Room
            | Group 1   | ---     | Group
```

**Example Cell Content:**
```
TRAIT IMAGES
(P1)
Mr BEN SLIMA
C14
Master students
```

**Parsing Algorithm:**

1. **Time Extraction:**
   - Regex: `(\d{1,2})[h:]\s*(\d{2})\s*-\s*(\d{1,2})[h:]\s*(\d{2})`
   - Result: `08:00 - 10:00` → `start=08:00, end=10:00`

2. **Cell Block Parsing:**
   - Split each cell by newlines
   - Detect period marker: `(P1)` or `(P2)`
   - Separate lines into:
     - Matter line (subject name)
     - Professor line (contains "Mr"/"Mme"/"Dr")
     - Room line (starts with "Salle" or format like "C14")
     - Group line (optional)

3. **Type Inference:**
   - If subject contains "TP" → type = "TP"
   - If subject contains "TD" → type = "TD"
   - Else → type = "cours"

4. **Session Creation:**
   ```python
   Session(
       jour="Lundi",
       heure_debut=time(8, 0),
       heure_fin=time(10, 0),
       classe_id=2,  # Resolved from class name
       professeur_id=15,  # Resolved from professor name
       matiere_id=42,  # Resolved from subject name
       salle_id=8,  # Resolved from room name
       type_seance="cours",
       groupe="Master students",
       periode="P1",  # From marker
       version_id=1,  # Associated with uploaded version
   )
   ```

#### **Phase 4: Validation**
**Service:** `admin_import_service.validate_and_import()`

Checks for inconsistencies:

```python
# Validations:
1. Semester consistency check
   - If uploading "student_s1", can't reference Semester 2 classes
   
2. Entity existence validation
   - Does the professor exist in DB?
   - Does the room exist in DB?
   - Does the subject exist in DB?
   
3. Date range validation
   - Is version date within current academic year?
   - No future dates
   
4. Duplicate detection
   - Same session already exists?
   - Same time slot conflict?

# Actions on validation failure:
- Return detailed error message
- Don't insert anything into database
- Suggest corrections to admin
```

#### **Phase 5: Database Insertion**
**Service:** `SQLAlchemy ORM`

Transactional insertion:

```python
# Transaction process:
1. Begin transaction
2. For each parsed session:
   a. Check for existing exact match
   b. If exists: skip (no duplicate)
   c. If new: insert into seances table
   d. Update emplois_versions.actif = true for this version
   e. Mark old versions as actif = false (only 1 active version per class)
   
3. If all sessions inserted successfully:
   - COMMIT transaction
   - Return success with import count
   
4. If any error:
   - ROLLBACK all changes
   - Return error response
```

#### **Phase 6: User Feedback**
**Response to Admin:**

```json
{
  "success": true,
  "message": "Emploi du temps importé avec succès",
  "details": {
    "type": "student_s1",
    "classe": "2 ING GII 3",
    "sessions_imported": 48,
    "sessions_updated": 2,
    "sessions_skipped": 0,
    "version_id": 15,
    "import_date": "2026-02-15"
  }
}
```

**Database Tracking:**
- `emplois_versions` table records each version
- `seances` table links to specific version
- Old versions kept for audit trail
- Only latest active version used for queries

---

## 6. External Data Sources

### University Information Service
The system extracts institutional information dynamically from the **ENET'Com website**:

| Information Type | Source | Purpose |
|-----------------|--------|---------|
| **Departments** | University website | Answer "departments" queries |
| **Contact Info** | University website | Phone, email, office locations |
| **Study Programs** | University website | Programs, degrees offered |
| **Campus Services** | University website | Library, facilities, support services |
| **Internship/PFE Info** | University website | Internship opportunities, rules |
| **Official Announcements** | University website | Recent news, events |

**Key Principle:** All institutional information is fetched live from ENET'Com's online resources - no hardcoded data. This ensures information is always current.

**Example Query Flow:**
```
User: "Quelles sont les coordonnées du département informatique ?"
      ↓
Intent classified as ENETCOM_INFO
      ↓
UniversityInfoService queries ENET'Com website
      ↓
Returns: "Département Informatique: Tel +216 71 941 xxx, Email info@enetcom.tn"
```

---

## 7. Database Schema (Key Tables)

### Core Academic Data

**Classes (Classes)**
```sql
id | nom           | semestre_id | code_class
1  | 2 ING GII 3   | 3           | 2ING3
2  | 1 TIC 1       | 1           | 1TIC1
```

**Professors (Professeurs)**
```sql
id | nom           | email               | specialite
15 | BEN SLIMA     | benslima@enetcom.tn | Images
```

**Rooms (Salles)**
```sql
id | nom  | capacite | bâtiment
8  | C14  | 45       | C
```

**Subjects (Matieres)**
```sql
id | nom          | code | credits
42 | TRAIT IMAGES | TI   | 3
```

**Schedules (Seances)**
```sql
id | jour   | heure_debut | heure_fin | classe_id | prof_id | salle_id | matiere_id | type_seance | periode | version_id
100| Lundi  | 08:00:00    | 10:00:00  | 1         | 15      | 8        | 42         | cours       | P1      | 15
```

**Timetable Versions (Emplois_Versions)**
```sql
id | classe_id | version_date | actif | upload_date | created_by
15 | 1         | 2026-02-15   | true  | 2026-02-15  | admin_user
```

**Academic Calendar (Vacances_Jours_Feries)**
```sql
id | nom           | date_debut | date_fin   | type      | annee_id
1  | Ramadan       | 2026-03-01 | 2026-03-30 | religieux | 1
```

### Security & Users

**Users (Auth_Users)**
```sql
id | email            | username | password_hash | role      | class_id
1  | student@enet.tn  | etudiant | hashed_pwd    | student   | 1
2  | admin@enet.tn    | admin    | hashed_pwd    | admin     | NULL
```

**Sessions (Auth_Sessions)**
```sql
token  | user_id | expires_at | created_at
abc... | 1       | 2026-02-20 | 2026-02-15
```

---

## 8. Tools & Techniques Summary

### Backend Architecture Patterns

1. **Layered Architecture:**
   - Routes Layer (FastAPI routing)
   - Service Layer (Business logic: Groq, SQL, Intent Router)
   - Data Layer (SQLAlchemy ORM)
   - Integration Layer (External APIs, File parsing)

2. **Dependency Injection:**
   ```python
   # FastAPI provides DB session automatically
   async def chat(request: ChatRequest, db: Session = Depends(get_db)):
       agent = SQLAgent(db)  # Injected DB dependency
   ```

3. **Error Handling:**
   - Validation at entry (Pydantic models)
   - Try-catch for LLM API calls (Groq)
   - Transaction rollback on DB errors

### ML/AI Techniques

1. **Temperature Control:**
   - Intent classification: `temperature=0.0` → deterministic
   - Response generation: `temperature=0.1-0.3` → consistent but natural

2. **Prompt Engineering:**
   - System message sets role & capabilities
   - User prompt contains context (schema, question, rules)
   - Structured output format (JSON) enforced

3. **Multilingual Support:**
   - LLM trained on multilingual data
   - No explicit language detection → natural mixed-language handling
   - Phonetic understanding of Tunisian Arabic

### Data Processing

1. **Excel Parsing:**
   - Regex for time extraction and pattern matching
   - Line-by-line parsing for multi-line cells
   - Type inference from content

2. **Text Normalization:**
   - Unicode normalization (NFKD)
   - Accent removal
   - Case normalization for case-insensitive search
   - Typo correction (mapping common misspellings)

3. **Deduplication:**
   - MD5 hash of session components
   - Skip exact duplicates during import
   - Keep version history for audit trail

---

## 9. Performance Considerations

| Operation | Expected Duration | Optimization |
|-----------|-----------------|--------------|
| Intent classification | 50-150ms | Cached markers, deterministic LLM |
| SQL generation | 200-500ms | Temperature=0.0, limited tokens |
| Database query | 10-100ms | Indexed columns (jour, classe_id) |
| Excel import 50 sessions | 2-5s | Batch insertion, transaction |
| Response formatting | 1-50ms | Heuristic rules first, LLM fallback |
| **Total chat response** | **300-800ms** | Parallel where possible |

---

## 10. Key Features & Differentiators

| Feature | How It Works | Benefit |
|---------|----------|---------|
| **Multilingual** | LLM trained on French, Arabic, English | Works for diverse student population |
| **Typo Tolerant** | Text normalization + LLM understanding | Handles "y9ari" (phonetic Tunisian) |
| **Admin Import** | Auto-detects file type + validates | No manual configuration needed |
| **Smart Routing** | Intent-based execution path | Faster response for non-DB queries |
| **Entity Extraction** | Structured JSON output | Enables precise SQL generation |
| **Version Control** | Tracks all imported versions | Audit trail + rollback capability |
| **Context Aware** | Uses conversation history | Understands pronouns & follow-ups |

---

## 11. Example End-to-End Flow

**Scenario:** Student asks "Win y9ari mr ali ghoudwa ?" (Tunisian: "Where does Mr. Ali teach tomorrow?")

```
1. Frontend sends to /api/chat
   → message: "Win y9ari mr ali ghoudwa ?"
   → user_class: "2 ING GII 3"

2. Message Mode Check
   → Obvious academic markers detected
   → Classified as ACADEMIC (skip conversational logic)

3. Intent Classification
   → Multilingual understanding recognizes Tunisian
   → Classified as TIMETABLE

4. Query Analysis
   → professor_name: "ALI"
   → day_hint: "ghoudwa" (tomorrow)
   → Confidence: 0.92

5. Routing Decision
   → answer_source: DATABASE
   → Proceed to SQL generation

6. Missing Info Check
   → Has professor name → don't need class
   → Proceed

7. SQL Generation
   → Groq generates to find Ali's schedule tomorrow
   
8. Database Query
   → Returns 2 sessions for Professor Ali tomorrow

9. Response Formatting
   → "Mr ALI enseigne demain de 09:00 à 11:00 en salle A05 (TRAIT IMAGES) 
      et de 14:00 à 16:00 en salle B12 (MATH)."

10. Return to Frontend
    → Display in chat interface
    → Add to conversation history
```

**Alternative Scenario:** Student asks "Quel est mon emploi de temps de 2 GII 3 ?" (Class timetable)

```
1. Frontend sends class timetable query
2. Message Mode Check → ACADEMIC
3. Intent Classification → TIMETABLE
4. Query Analysis
   → Identified: "class_name": "2 GII 3"
   → No professor specified
   → Confidence: 0.98
5. Routing Decision → DATABASE
6. Missing Info Check
   → Has class name → proceed ✓
7. SQL Generation
   → SELECT all seances WHERE classe_id = 2 AND version_id = (latest active)
8. Database Query
   → Returns 24+ sessions for the week
9. Response Formatting
   → Groups by day, shows times, professors, rooms, subjects
   → Natural French timetable output with proper formatting
10. Return structured timetable to Frontend
```

---

## 12. Conclusion

Time Guide AI represents a modern approach to university information access by combining:
- **RESTful API** architecture with FastAPI
- **Intelligent NLP** via Groq's LLaMA model
- **Structured data extraction** using entity recognition
- **Dynamic SQL generation** without hardcoded queries
- **Multilingual & fault-tolerant** design
- **Admin-friendly** Excel import system
- **Live institutional data** fetched directly from ENET'Com website (no hardcoded data)

The system handles concurrent requests and maintains data consistency through transactional database operations on PostgreSQL. The modular architecture allows easy addition of new intents, services, or database queries without code duplication.

**Key Differentiators:**
- Supports both **class timetables** (emploi de temps) and **professor schedules**
- No container overhead (direct Python/Node.js deployment)
- Real-time institutional data from university website ensures accuracy
- Multilingual support including Tunisian Arabic phonetic input
