# End-of-Studies Project Report
## Time Guide AI: Intelligent University Timetable Assistant for ENET'Com

**Author:** Student Project Team  
**Project Type:** End-of-Studies Project (PFE)  
**Institution Context:** ENET'Com  
**Project Language:** English  
**Repository Reviewed:** `time-guide-ai-main`

---

## Acknowledgements

This work was developed within an academic context that encouraged both technical rigor and practical problem solving. Sincere appreciation is extended to the supervisors, instructors, and institutional stakeholders who contributed through guidance, feedback, and academic support throughout the realization of this project.

Gratitude is also addressed to the open-source communities and technical ecosystems behind the tools used in this project, including React, FastAPI, PostgreSQL, SQLAlchemy, Tailwind CSS, Pandas, and many other libraries that made the implementation possible. Finally, thanks are due to all users, colleagues, and reviewers whose questions and feedback help transform a technical solution into a more relevant academic platform.

## List of Figures

At the current stage of the report, no embedded numbered figures are inserted as final graphical elements. However, the report already contains several architecture-oriented sections that can be converted into official figures in a formatted university version. The most relevant figures would be:

- Figure 1. Global architecture of Time Guide AI
- Figure 2. Chat request processing workflow
- Figure 3. Administration import workflow
- Figure 4. UML-style use case representation
- Figure 5. UML-style sequence flow of chatbot interaction
- Figure 6. UML-style module and relation view

## List of Tables

The report currently relies mainly on paragraph-based explanation. In a final formatted version, the following tables would be the most useful:

- Table 1. Functional objectives of the project
- Table 2. Main technologies and tools used
- Table 3. Core academic database entities
- Table 4. Main API endpoints
- Table 5. Model and architecture comparison
- Table 6. Improvement and upgrade perspectives

---

## Abstract

This project presents the design and implementation of **Time Guide AI**, an intelligent academic assistant developed for ENET'Com in order to simplify timetable consultation and access to institutional information. The system addresses a practical academic problem: timetable data is often available in static formats such as Excel sheets, while students, teachers, and administrators need fast, flexible, and natural access to schedule-related information. To solve this problem, the project combines a React-based frontend, a FastAPI backend, a PostgreSQL database, an Excel data-import pipeline, and a hybrid intelligent-processing layer.

The implemented solution allows authenticated users to ask natural-language questions related to class schedules, professor locations, room availability, academic calendar events, and general ENET'Com information. It also provides a protected administration interface for importing student, teacher, room, and calendar workbooks. A major contribution of the project is its hybrid architecture: instead of relying entirely on a large language model, the system combines deterministic routing, controlled SQL generation, database constraints, and selective use of a hosted model through the Groq API. This improves reliability for academic queries while preserving conversational flexibility.

The report explains the project context, objectives, architecture, technologies, data model, intelligent-processing workflow, and testing approach. It also includes UML-style analysis through use case explanation, sequence flow description, and module-relation interpretation. Finally, it discusses the current strengths of the project, its limitations, and possible upgrade paths that could transform it into a broader academic digital assistant.

## Keywords

End-of-Studies Project, PFE, timetable assistant, ENET'Com, FastAPI, React, PostgreSQL, Groq API, natural language interface, Excel parsing, SQL agent, intent routing, academic information system

---

## Table of Contents

1. Acknowledgements  
2. List of Figures  
3. List of Tables  
4. Abstract  
5. Keywords  
6. General Introduction  
7. Chapter 1. Project Context and Functional Analysis  
8. Chapter 2. System Architecture and UML-Oriented Analysis  
9. Chapter 3. Implementation and Technologies Used  
10. Chapter 4. Validation, Results, and Discussion  
11. Chapter 5. Improvement and Upgrade Perspectives  
12. General Conclusion  
13. Bibliography / References

---

## General Introduction

Digital transformation in higher education is no longer limited to online course content or administrative portals. Modern universities increasingly need smart systems capable of organizing academic information, simplifying access to data, and reducing the time spent by students, teachers, and administrators searching for operational details. In this context, timetable consultation remains one of the most frequent and most critical daily tasks in academic life. Students need to know their courses, rooms, and time slots quickly. Teachers need to identify their teaching sessions and assigned classes. Administrative staff need a reliable way to upload and update schedules while preserving data consistency.

This project, entitled **Time Guide AI**, was designed as an intelligent academic assistant dedicated to timetable consultation and university information access for **ENET'Com**. The system combines a modern web interface, a Python backend, a PostgreSQL relational database, an Excel import pipeline, and an artificial-intelligence-driven query layer. The objective is not only to display timetable data, but also to allow users to ask questions in natural language such as: *What is my timetable today?*, *Where is Professor X now?*, *Which rooms are available on Monday?*, or *Are there holidays today?*

The originality of the project lies in its **hybrid intelligent architecture**. Instead of relying only on a large language model, the application mixes deterministic logic, database-aware routing, guarded SQL generation, and contextual formatting. This design improves reliability for timetable-related queries while still preserving the flexibility of conversational interaction. In addition, the project includes a dedicated administration interface for importing student, teacher, room, and university-calendar Excel workbooks. This makes the platform maintainable in a real institutional environment where schedule files are frequently updated.

This report presents a detailed study of the project as implemented in the repository. It explains the business problem, the architecture, the technologies used, the role of each major tool, the intelligent-processing pipeline, the database design, the testing strategy, and the main strengths and limitations of the current system. It also clarifies an important architectural point discovered during repository analysis: whereas the active runtime code now uses **Groq API with the model `llama-3.3-70b-versatile`**, supported by strong local deterministic logic. For this reason, this report distinguishes clearly between **historical/experimental components** and the **current implementation actually used by the application**.

In summary, the general introduction defines the academic motivation, the practical value, and the technical orientation of the project. It establishes that Time Guide AI is not only a software prototype, but also a response to a real institutional need. The following chapters progressively move from functional analysis to architecture, implementation, validation, and future improvement perspectives.

---

## Chapter 1. Project Context and Functional Analysis

### 1.1 Project Context and Problem Statement

University timetable information is usually distributed through Excel files, PDF documents, or static administrative pages. Although these formats are convenient for publication, they are often inefficient for interactive consultation. A student who only wants to know the next class may need to open a complete schedule sheet and manually identify the correct row, time slot, and group. A professor may need to browse several documents to find the class or room assigned at a given moment. Administrators may face repetitive and error-prone tasks when updating timetable versions across different categories of data.

At ENET'Com, this creates several practical difficulties:

- Timetable files are rich in information but not optimized for conversational access.
- Users formulate needs in natural language, not in SQL or rigid filters.
- The same information may be needed from different perspectives: class view, teacher view, room view, or calendar view.
- Schedule data changes over time and therefore requires a controlled import workflow.
- Some university information is not stored in the database and must be fetched from the official ENET'Com website.

The project addresses this problem by building a centralized intelligent web platform that transforms heterogeneous academic data into a searchable and conversational assistant.

---

### 1.2 Project Objectives

The main objective of the project is to build an intelligent academic assistant capable of answering timetable and university-information questions in a simple and natural way.

The specific objectives are:

- To provide a user-friendly web interface for conversational timetable consultation.
- To allow natural-language queries related to classes, professors, rooms, schedules, and calendar events.
- To store timetable data in a structured relational database.
- To offer an administration dashboard for importing and refreshing schedule data from Excel workbooks.
- To secure administration features using authentication and role-based access.
- To integrate an AI layer able to classify user intent, generate or refine SQL queries when needed, and produce natural responses.
- To maintain robustness through deterministic routing, SQL validation, and import consistency checks.

---

### 1.3 Functional Scope of the Application

The repository shows that the application supports two major user spaces: a **user chat space** and an **administration space**.

### 1.3.1 User Features

The chat interface allows authenticated users to:

- ask for a class timetable;
- ask where a professor is located;
- ask which teacher is using a room;
- ask for available rooms;
- ask about holidays, exams, revisions, and other academic-calendar events;
- ask for general ENET'Com information such as contact details, study plans, news, clubs, internships, and PFE information.

### 1.3.2 Administrator Features

The admin interface allows administrators to:

- log in using a protected admin account;
- upload multiple Excel files in one operation;
- separate uploads by category and semester;
- validate that the uploaded workbook matches the selected category;
- reimport timetable or calendar data into the database;
- consult import summaries and latest uploaded files;
- receive success or error notifications after import.

### 1.3.3 Supported Upload Categories

The current implementation supports the following upload slots:

- `student_s1`
- `student_s2`
- `teachers_s1`
- `teachers_s2`
- `rooms_s1`
- `rooms_s2`
- `calendar`

This classification is important because the backend validates both **audience type** and **semester consistency** before accepting a workbook.

### Chapter 1 Conclusion

This first chapter clarified the institutional context of the project, the practical timetable-access problem, and the main functional objectives of the proposed solution. It also identified the major user and administrator interactions that define the operational scope of the platform. These elements form the functional basis for the architectural and technical choices presented in the following chapter.

---

## Chapter 2. System Architecture and UML-Oriented Analysis

### 2.1 Global System Overview

The project follows a classic web architecture enriched by an intelligent-processing layer:

1. The user interacts with a React-based frontend.
2. The frontend sends requests to a FastAPI backend.
3. The backend authenticates the user when needed.
4. For chat requests, the backend routes the message toward:
   - the SQL-based academic agent,
   - the university web information service,
   - the conversational fallback,
   - or a clarification response.
5. The SQL agent accesses PostgreSQL to retrieve structured timetable data.
6. The university information service fetches ENET'Com official pages when the question concerns general institutional information.
7. The result is formatted and returned to the frontend.

This overview reveals that the system is not a single chatbot call. It is a **multi-stage decision system** combining routing, validation, database logic, web extraction, and selective AI usage.

In practice, the user sees a simple chat interface, but the internal workflow is much richer. When a message is submitted, the backend does not immediately send it to a model. It first determines what type of request it is handling. If the question is related to timetable data, the system tries to answer through structured logic and database access. If the question concerns institutional information about ENET'Com, another service is activated. If the question is casual conversation or outside the project scope, the system responds differently. This makes the application more precise, more stable, and more efficient.

The project also combines two kinds of knowledge sources. The first source is structured internal data imported from Excel files and stored in PostgreSQL. The second source is official ENET'Com web content accessed when the user asks for broader institutional information. This means the platform does not depend on a single source of truth. It integrates relational academic data and official web information into one assistant.

---

### 2.2 Software Architecture

The software architecture is organized around four major layers:

- Presentation layer
- Application/API layer
- Data layer
- Intelligent-processing layer

### 2.2.1 Presentation Layer

The presentation layer is implemented with **React**, **TypeScript**, **Vite**, **Tailwind CSS**, and UI libraries such as **shadcn/ui**, **Radix UI**, and **Lucide React**. It is responsible for rendering the chat page, authentication page, and administration dashboard.

### 2.2.2 Application/API Layer

The application layer is implemented with **FastAPI**. It exposes REST endpoints for authentication, chat, and admin import operations. It also initializes the database schema and auth tables at startup.

### 2.2.3 Data Layer

The data layer uses **PostgreSQL** as the persistent relational database and **SQLAlchemy** for ORM mapping and session management. It stores timetable sessions, timetable versions, classes, teachers, rooms, groups, academic periods, semesters, and holidays.

### 2.2.4 Intelligent-Processing Layer

The intelligent layer is composed of:

- `IntentRouter`, which classifies the user request and reconstructs conversational context;
- `SQLAgent`, which builds, repairs, validates, and executes academic queries;
- `GroqService`, which provides selective large-language-model capabilities;
- `UniversityInfoService`, which fetches and summarizes official ENET'Com web information;
- deterministic formatting rules that reduce dependence on model output.

This architecture is one of the strongest aspects of the project because it avoids blind dependence on AI while still exploiting AI where it adds value.

From an engineering point of view, this structure improves maintainability. The route layer coordinates requests, the service layer contains business logic, the data layer stores structured information, and the intelligent layer adds conversational flexibility. Because responsibilities are clearly separated, each part can be improved, tested, or replaced without forcing a complete redesign of the application.

Another important architectural advantage is the balance between deterministic logic and model assistance. Repetitive and high-precision academic operations are handled through rules and controlled SQL, while the model is used where natural language flexibility is truly useful. This makes the project more robust than a fully model-driven design.

### 2.3 UML-Style Use Case Diagram Explanation

From a UML use case perspective, the system revolves around two principal human actors: the **authenticated user** and the **administrator**. A third supporting external actor can also be identified: the **official ENET'Com website**, which provides institutional information for some queries.

The authenticated user interacts mainly with the chatbot. The associated use cases are: sign in, access chat, ask timetable question, ask professor question, ask room question, ask academic calendar question, and ask institutional information question. These use cases all converge toward the conversation interface, but they do not follow the same internal processing logic. Some requests are resolved through structured database access, while others use institutional web retrieval.

The administrator actor is associated with platform maintenance use cases. These include: authenticate as admin, access dashboard, upload workbook, validate workbook category, import data into the database, consult import status, and review latest uploaded files. In a UML interpretation, the validation of workbook type and semester can be seen as an included sub-use case inside the upload-and-import workflow because it is systematically executed before import success is confirmed.

The ENET'Com website can be treated as an external actor connected to the use case “provide university information.” When the user asks about study plans, contact information, news, departments, internships, or PFE information, the system may rely on official pages as the information source. This creates a clean conceptual separation between timetable-oriented use cases and institutional-information use cases.

### 2.4 UML-Style Sequence Flow Explanation

The main chat sequence starts when the user types a message on the frontend. The frontend sends the request to the FastAPI backend with the message, optional class information, and short conversation history. The backend route initializes the routing and processing services, then passes the request to the intent router. The intent router classifies the question and determines the correct execution path.

If the request is a structured academic query, the route delegates processing to the SQL agent. The SQL agent builds or refines the SQL logic, validates constraints, executes the query on PostgreSQL, formats the result, and returns it through the route to the frontend. The frontend then renders the final answer in the chat interface.

If the request concerns institutional information, the route delegates it to the university information service. That service may fetch ENET'Com web pages, extract relevant content, optionally ask the model to summarize grounded context, and finally return the answer to the route before it is sent back to the frontend.

The administration sequence follows another flow. The administrator selects one or more Excel files and submits them through the dashboard. The frontend sends a multipart request to the backend. The backend verifies admin privileges, saves the files, validates workbook signatures and semester coherence, triggers the corresponding import functions, updates the database, and returns an import summary. The frontend then displays upload results and notifications.

### 2.5 UML-Style Class and Module Relations

The repository is not presented as a formal UML class diagram, but its structure can be interpreted in UML-like terms. The `main.py` module aggregates the application and composes the route modules. The route modules depend on service modules because they delegate business actions instead of implementing them directly. The service modules depend on the data layer because they use the database schema and sessions to execute project logic.

Inside the academic domain model, `Classe`, `EmploiVersion`, `Seance`, `Professeur`, `Salle`, `Matiere`, `Groupe`, and `Periode` form the core relational structure. A class is associated with timetable versions, a version is associated with sessions, and a session can reference a professor, room, subject, group, and academic period. This corresponds to a dense network of associations in UML terms.

At the service level, `IntentRouter` collaborates with `GroqService` and depends on conversational context. `SQLAgent` depends on the database and may also call `GroqService` in fallback situations. `UniversityInfoService` depends on web retrieval and may use the model to summarize official content. `AdminImportService` depends on parser and import modules. These relations are best understood as dependency and collaboration links between modules.

### Chapter 2 Conclusion

This chapter presented the architecture of the project from both a technical and UML-oriented point of view. It explained the system layers, the main execution flows, the use case perspective, the sequence perspective, and the relations between modules and data entities. It shows that the project architecture is modular, realistic, and well suited to gradual future evolution.

---

## Chapter 3. Implementation and Technologies Used

### 3.1 Frontend Layer

The frontend code is located in the `src/` directory and is built as a single-page application.

### 3.1.1 Main Pages

The most important pages are:

- `src/pages/Chat.tsx`
- `src/pages/Admin.tsx`
- `src/pages/Auth.tsx`
- `src/pages/Index.tsx`
- `src/pages/NotFound.tsx`

### 3.1.2 Chat Interface

The chat page is the central user-facing interface. It displays the conversation history, allows users to send messages, shows a typing indicator, and maintains recent history in order to support contextual follow-up questions. The frontend sends the last messages as `history` to the backend, which helps the intent router rebuild context.

This means the frontend does more than simply render responses. It actively supports the conversational quality of the system. If the user sends a short follow-up such as “tomorrow” or “for GII 2”, the backend can use recent history to interpret the new message correctly. This reduces repetition and makes the assistant easier to use in everyday academic situations.

### 3.1.3 Authentication Interface

The authentication page supports both sign-in and sign-up. It includes a two-mode form, client-side loading states, and route redirection according to user role. After a successful login, standard users are redirected to `/chat`, while administrators are redirected to `/admin`.

### 3.1.4 Administration Interface

The administration page provides upload cards for each data category, a summary of latest uploaded files, import results, and visual feedback using notifications. The design is practical and adapted to an administrative workflow rather than a generic chatbot page.

This page is operationally very important because the whole chatbot depends on up-to-date and well-structured timetable data. Through this interface, administrators can refresh the platform knowledge base without manually manipulating SQL or internal scripts. In a real university context, this reduces technical complexity and makes the system easier to maintain over time.

### 3.1.5 Route Protection

Route protection is implemented through:

- `ProtectedRoute.tsx`
- `AdminRoute.tsx`

These components use the authentication context and ensure that unauthenticated users cannot access protected pages, while non-admin users are redirected away from the administration dashboard.

### 3.1.6 Authentication State Management

Authentication state is managed in `src/contexts/AuthContext.tsx`. The context:

- stores the current user and session,
- persists the access token in local storage,
- restores the session through `/api/auth/me`,
- exposes `signIn`, `signUp`, and `signOut` methods.

This is a clean and understandable frontend architecture for a PFE-sized project.

---

### 3.2 Backend Layer

The backend is structured around FastAPI routes and service modules.

### 3.2.1 Main Entry Point

The file `backend/main.py` initializes the FastAPI application, configures CORS, creates database tables, ensures authentication tables exist, and registers the routers.

### 3.2.2 Main Routes

The backend contains three main route modules:

- `backend/app/routes/chat.py`
- `backend/app/routes/auth.py`
- `backend/app/routes/admin.py`

### 3.2.3 Chat Route

The `/api/chat` endpoint accepts a message, user role, optional class, and optional history. It then:

- creates an `SQLAgent`,
- creates an `IntentRouter`,
- normalizes the user class,
- routes the request,
- delegates execution to the appropriate service.

This route is an orchestration layer, not a simple model call.

Its role is to transform a raw user message into a controlled backend workflow. Instead of treating all questions in the same way, the route prepares the execution context, creates the required services, and delegates the request to the most appropriate component. This makes the backend modular and prevents the architecture from collapsing into a single monolithic chatbot function.

### 3.2.4 Authentication Route

The authentication router exposes:

- `POST /api/auth/login`
- `POST /api/auth/signup`
- `GET /api/auth/me`
- `POST /api/auth/logout`

It supports both normal users and a special configured admin user from environment variables.

### 3.2.5 Administration Route

The administration router exposes:

- `GET /api/admin/imports/status`
- `POST /api/admin/imports/upload`

It only allows access to authenticated administrators and forwards upload processing to `admin_import_service.py`.

---

### 3.3 Database Design

The relational data model is defined in `backend/app/models/database.py`. The schema is centered around the academic timetable domain.

### 3.3.1 Core Academic Entities

The main entities are:

- `AnneeUniversitaire`
- `Semestre`
- `Periode`
- `Departement`
- `Classe`
- `Professeur`
- `Matiere`
- `Salle`
- `Groupe`
- `EmploiVersion`
- `Seance`
- `EmploiEnseignantSeance`
- `VacancesJoursFeries`

### 3.3.2 Role of the Most Important Tables

**`classes`** stores the academic classes associated with departments and semesters.  
**`professeurs`** stores teachers.  
**`salles`** stores rooms.  
**`matieres`** stores subjects.  
**`seances`** stores the actual scheduled teaching sessions with day, time, room, professor, class, group, and period.  
**`emplois_versions`** stores timetable versions and identifies which one is active.  
**`emplois_enseignants_seances`** stores a teacher-centric reference representation used to answer teacher-oriented questions more directly.  
**`vacances_jours_feries`** stores holidays, revision periods, exams, and other academic events.

### 3.3.3 Design Choice: Active Timetable Version

One notable design choice is the use of an **active version flag** in `emplois_versions`. The SQL agent explicitly enforces this constraint when timetable queries are generated. This prevents the chatbot from returning stale timetable data.

This is a realistic and very useful design decision because university timetables often change during the semester. If the system queried all imported sessions without distinguishing active and inactive versions, users could receive contradictory answers. By preserving versions while enforcing active selection at query time, the project keeps historical data without sacrificing answer consistency.

### 3.3.4 Authentication Tables

Authentication uses SQL tables created dynamically by `auth_service.py`:

- `auth_users`
- `auth_sessions`

This means the project does not depend on an external authentication platform.

---

### 3.4 Artificial Intelligence and Intelligent Processing Layer

This section is the core of the project because the repository is not just a CRUD application. It is an intelligent academic assistant.

### 3.4.1 Intent Router

The file `backend/app/services/intent_router.py` is responsible for understanding the *type* of question before any database query is executed.

Its role includes:

- intent classification;
- entity extraction;
- contextual follow-up resolution;
- pending clarification management;
- class and professor reconstruction from short replies;
- distinction between academic requests, university-information requests, small talk, and out-of-scope messages.

This component is especially important because it reduces unnecessary model calls and improves accuracy on follow-up conversations such as:

- “And tomorrow?”
- “For GII 2”
- “Yes”
- “No”

The intent router is one of the most advanced parts of the application because it treats conversation as a sequence rather than as isolated prompts. It can reuse earlier context, recover missing information, and continue a pending clarification flow. In practical use, this means the user does not always need to repeat the full question. This greatly improves the realism of the assistant.

### 3.4.2 SQL Agent

The file `backend/app/services/sql_agent.py` is the main academic reasoning engine.

Its responsibilities include:

- retrieving the current academic context;
- recognizing timetable-related patterns;
- extracting class, room, and professor names;
- generating deterministic SQL for known intents;
- validating that SQL remains read-only;
- repairing malformed model-generated SQL;
- enforcing active timetable-version filtering;
- enforcing day and period constraints;
- executing SQL queries;
- formatting the final answer.

The SQL agent is very important from a software-engineering perspective because it shows that the project does not trust the model blindly. It adds control rules before query execution.

This module contains much of the practical intelligence of the project. It understands recurring academic operations such as class timetable retrieval, professor location, room availability, and calendar checks. It also contains normalization and typo-tolerance mechanisms, which are essential because real users often write names, classes, and rooms in inconsistent ways.

Another major strength is its defensive design. The agent validates that only read-only queries are allowed, repairs malformed SQL when necessary, enforces active timetable versions, and applies precise filters for day and period interpretation. This transforms the project from a risky text-to-SQL prototype into a more controlled academic information system.

### 3.4.3 Groq Service

The current active model integration is implemented in `backend/app/services/groq_service.py`.

This service:

- connects to the Groq Chat Completions API;
- uses the model `llama-3.3-70b-versatile`;
- classifies some messages as academic or non-academic;
- generates SQL in fallback situations where deterministic routing is insufficient;
- formats database results when appropriate;
- produces out-of-scope or conversational responses.

The model is therefore used selectively, not everywhere.

This selective usage is one of the most mature technical choices in the project. The model is not asked to solve every problem. Instead, it is used where its linguistic flexibility is valuable, such as difficult classification, fallback SQL generation, and some response-writing tasks. This reduces instability and improves confidence in routine timetable answers.

### 3.4.4 University Information Service

The file `backend/app/services/university_info_service.py` handles questions that are not pure timetable questions but still belong to the ENET'Com domain.

It can:

- fetch official ENET'Com pages;
- fetch current news;
- provide study-plan URLs;
- detect and summarize absence information;
- build context from official pages;
- ask the model to answer based only on official sources.

This is a strong design decision because general university information should not be guessed from timetable tables.

It also improves trustworthiness. Questions about contacts, study plans, departments, clubs, or ENET'Com news require different sources from timetable data. By giving these requests to a dedicated institutional-information service, the project keeps a cleaner separation between structured academic data and general university content.

### 3.4.5 Historical Local LLM Service

The repository also contains `backend/app/services/llm_service.py`, which documents an older or experimental approach based on local **Qwen** models loaded through Hugging Face and PyTorch.

However, after reading the active runtime code, this service is **not part of the main execution path** of the current application. It should therefore be described as:

- a historical prototype,
- an experimental local alternative,
- or a previous architecture idea preserved in the repository.

This distinction is essential for an accurate PFE report.

---

### 3.5 Excel Parsing and Data Import Pipeline

The project includes a significant data-engineering aspect: timetable data is imported from Excel workbooks.

### 3.5.1 Vertical Excel Parser

The parser logic is implemented in `backend/app/services/excel_parser.py`.

Its purpose is to transform timetable workbooks into normalized session objects. It supports three workbook perspectives:

- student view,
- teacher view,
- room view.

The parser detects:

- French day names,
- time ranges,
- period markers such as `P1` and `P2`,
- room names,
- class names,
- professor names,
- course blocks distributed vertically inside the sheet.

This parser is a key technical contribution because timetable spreadsheets are usually created for human reading, not for direct machine querying. The parser transforms visual worksheet organization into normalized session objects that can be inserted into database tables. Without this transformation layer, the chatbot would not have a reliable timetable knowledge base to query.

### 3.5.2 Timetable Import Script

The script `load_data.py` is responsible for converting parsed sessions into database records. It:

- prepares sessions by semester;
- expands sessions with missing period markers;
- creates missing classes, groups, professors, rooms, and subjects;
- creates timetable versions;
- inserts sessions into `seances`;
- populates `emplois_enseignants_seances` for teacher-centric lookup.

This script transforms unstructured Excel data into a normalized academic database.

### 3.5.3 Calendar Import Script

The file `import_calendar.py` imports academic calendar information such as:

- semester period markers,
- vacations,
- exams,
- revision periods,
- holidays.

It reads workbook structures, date patterns, text labels, and footer events, then stores them in `vacances_jours_feries`.

### 3.5.4 Admin Import Service

The central import orchestration is implemented in `backend/app/services/admin_import_service.py`.

This service:

- saves uploaded files;
- extracts workbook metadata;
- detects the workbook signature;
- validates audience type and semester;
- triggers the correct import function;
- builds an admin dashboard summary.

This module is operationally very important because it protects the system against incorrect uploads, such as a teacher workbook accidentally uploaded in the student category.

This protection is highly relevant in real administrative workflows. In many cases, system inconsistency comes not from code failure but from human upload mistakes. By detecting workbook signatures and validating semester alignment, the service reduces the risk of introducing incorrect data into the database.

---

### 3.6 Authentication, Authorization, and Security

Security in this project is pragmatic and adapted to the needs of a university timetable platform.

### 3.6.1 User Accounts

Users can sign up and sign in using email and password. Their credentials are stored in the database.

### 3.6.2 Password Security

Passwords are hashed using **PBKDF2-HMAC-SHA256** with **200,000 iterations**. This is a solid security choice for a custom authentication implementation.

### 3.6.3 Session Security

Sessions are token-based. The raw token is generated securely, but only its SHA-256 hash is stored in the database. This reduces the impact of database leakage.

### 3.6.4 Admin Access

The admin account is configured through environment variables:

- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `ADMIN_FULL_NAME`

The admin role is enforced server-side before import endpoints can be used.

### 3.6.5 Query Safety

The SQL agent enforces several protections:

- SELECT-only validation;
- SQL cleanup and repair;
- active-version enforcement;
- controlled professor and room matching;
- defensive conditions before execution.

This makes the intelligent layer safer than a raw “text-to-SQL” architecture.

---

### 3.7 API Design and Main Endpoints

The application exposes a clean REST API.

### 3.7.1 System Endpoints

- `GET /`
- `GET /health`

### 3.7.2 Authentication Endpoints

- `POST /api/auth/login`
- `POST /api/auth/signup`
- `GET /api/auth/me`
- `POST /api/auth/logout`

### 3.7.3 Chat Endpoint

- `POST /api/chat`

The request includes:

- `message`
- `user_role`
- `user_class`
- `history`

### 3.7.4 Administration Endpoints

- `GET /api/admin/imports/status`
- `POST /api/admin/imports/upload`

This endpoint design is simple, readable, and appropriate for a project of this scale.

---

### 3.8 Technologies and Tools Used

This section explains the major technologies and tools used in the project and the role of each one.

### 3.8.1 Frontend Technologies

**React 18**  
React is a JavaScript library used to build interactive user interfaces. In this project, React is used to create the chat page, authentication page, and administration page as reusable components.

**TypeScript**  
TypeScript is a typed superset of JavaScript. It improves reliability by adding static typing, better editor support, and safer component contracts.

**Vite**  
Vite is a modern frontend build tool. It provides very fast development startup and efficient production bundling.

**React Router DOM**  
This library is used for client-side routing. It manages page navigation between `/chat`, `/auth`, `/admin`, and fallback routes.

**Tailwind CSS**  
Tailwind CSS is a utility-first CSS framework. It helps build responsive and modern interfaces quickly by composing utility classes directly inside components.

**shadcn/ui**  
shadcn/ui is a component architecture based on reusable UI primitives. It provides a structured way to create polished interface elements while keeping the code customizable.

**Radix UI**  
Radix UI provides accessible low-level components such as dialogs, tooltips, dropdowns, and form-related primitives.

**Framer Motion**  
Framer Motion is an animation library used in the admin page and other UI transitions to improve visual feedback.

**Lucide React**  
Lucide React provides icon components used throughout the interface.

**Sonner**  
Sonner is used for toast notifications, especially in the admin upload workflow.

**TanStack Query**  
TanStack Query is included in the frontend setup and provides a scalable foundation for server-state management, even though the current code uses direct `fetch` in several places.

The frontend stack was chosen in a coherent way. React and TypeScript provide a modern component architecture, Vite speeds up development and build workflows, and Tailwind CSS with shadcn/ui helps the team build a professional interface quickly. These tools are well suited to a PFE context because they allow the project to focus on business value instead of spending too much time on low-level UI setup.

### 3.8.2 Backend Technologies

**FastAPI**  
FastAPI is a modern Python web framework used to build the REST API. It is known for speed, type-based validation, and automatic documentation.

**Uvicorn**  
Uvicorn is the ASGI server used to run the FastAPI application.

**SQLAlchemy**  
SQLAlchemy is used for ORM definitions and database interaction. It maps Python classes to SQL tables and manages sessions.

**psycopg / psycopg2**  
These PostgreSQL drivers enable communication between Python and PostgreSQL. The application uses `psycopg` in SQLAlchemy configuration and `psycopg2` in the calendar import script.

**Pydantic**  
Pydantic validates request and response models in FastAPI, ensuring cleaner API contracts.

**python-dotenv**  
This library loads environment variables from `.env`, allowing secure and flexible configuration.

The backend stack is equally appropriate for this type of system. FastAPI is efficient for service-based APIs, SQLAlchemy is suitable for relational academic data, and PostgreSQL is an excellent database choice for structured entities such as classes, sessions, semesters, rooms, and teachers. Pandas and OpenPyXL are also very relevant because timetable ingestion depends on Excel workbooks provided by the institution.

### 3.8.3 Data Processing Technologies

**Pandas**  
Pandas is used to read Excel files and manipulate worksheet data efficiently.

**OpenPyXL**  
OpenPyXL is used for workbook-level Excel parsing, especially in the calendar import pipeline.

### 3.8.4 Artificial Intelligence and Integration Tools

**Groq API**  
Groq API provides hosted inference for large language models. In the current implementation, it is the active external AI provider.

**Model: `llama-3.3-70b-versatile`**  
This is the model configured in `groq_service.py`. It is used for selective message classification, SQL generation fallback, and some response generation tasks.

**Transformers**  
The Hugging Face `transformers` library appears in the repository for the historical `llm_service.py`, which experimented with local Qwen models.

**PyTorch**  
PyTorch is also part of the historical local-model path. It would be used to load and run Qwen locally if that path were activated.

### 3.8.5 Testing Tools

**Pytest**  
Pytest is used for backend tests.

**Vitest**  
Vitest is used for frontend testing.

**Testing Library**  
`@testing-library/react` and `@testing-library/jest-dom` are included for frontend component testing.

### 3.8.6 Deployment and Environment Tools

**Docker Compose**  
Docker Compose is used to launch PostgreSQL locally for development.

**Node.js and npm**  
These are required to install and run the frontend stack.

**Python virtual environment**  
A Python virtual environment isolates backend dependencies from the system environment.

The AI-related tool selection reflects the evolution of the project. The active code uses Groq-hosted inference to reduce local hardware constraints, while the repository still contains traces of an earlier local-model path using Transformers and PyTorch. This shows that the project explored multiple strategies before converging toward the current hybrid implementation.

---

### 3.9 Development Workflow and Project Structure

The repository is clearly divided into frontend and backend concerns.

### 3.9.1 Main Folders

- `src/` for frontend source code
- `backend/` for backend source code
- `public/` for static assets
- root-level Python scripts for imports
- root-level markdown documentation

### 3.9.2 Backend Internal Organization

Inside `backend/app/`, the code is separated into:

- `models/`
- `routes/`
- `services/`

This is a strong architectural choice because it separates:

- persistent data representation,
- HTTP endpoint definitions,
- business logic and intelligent services.

### 3.9.3 Documentation State

The repository contains several markdown documents such as:

- `README.md`
- `SUMMARY.md`
- `PROJECT_STRUCTURE.md`
- `ARCHITECTURE_DIAGRAM.md`
- `LLM_ARCHITECTURE.md`
- `rapport.md`

During repository review, it became clear that some of these documents describe an older Qwen-based architecture and are not fully aligned with the current runtime code. This report therefore serves as a more accurate and up-to-date synthesis of the implementation.

### Chapter 3 Conclusion

This chapter detailed the concrete implementation of the system, including the frontend, backend, database, AI-related services, import workflow, security layer, API design, and technologies used. It demonstrated that the project is built on a coherent full-stack foundation where each technical component has a clear functional role.

---

## Chapter 4. Validation, Results, and Discussion

### 4.1 Testing and Validation

Testing exists in both frontend and backend parts of the project.

### 4.1.1 Backend Test Suite

The repository includes ten backend test modules:

- `test_admin_api.py`
- `test_admin_import_service.py`
- `test_auth_service.py`
- `test_calendar_import.py`
- `test_chat_api.py`
- `test_excel_parser_views.py`
- `test_groq_service.py`
- `test_intent_router.py`
- `test_sql_agent.py`
- `test_university_info_service.py`

These tests cover important areas such as:

- admin API behavior,
- upload/import validation,
- authentication logic,
- SQL agent rules,
- intent routing,
- Groq response formatting,
- chat endpoint behavior,
- university-information logic,
- calendar extraction,
- Excel parser behavior.

### 4.1.2 Frontend Test Suite

The frontend uses **Vitest** with a `jsdom` environment. At the moment, the repository contains one basic smoke test in `src/test/example.test.ts`.

### 4.1.3 Validation Results Observed During Review

The following commands were executed during this repository review:

- `npm run test`
- `python -m pytest backend\tests`

Observed results:

- Frontend tests passed: **1 test passed out of 1**.
- Backend tests did **not** execute successfully in the current environment. Test collection failed because:
  - the test suite expects `app` imports that require a specific Python path setup;
  - one environment issue appears with Python 3.13 and SQLAlchemy during test collection;
  - one calendar test expects Excel fixture files that are not present in the current workspace.

### 4.1.4 Interpretation

This means the project contains a meaningful backend test suite, but it is not currently portable enough to run successfully in any environment without adjustment. For a PFE report, this should be presented honestly: **the project has strong testing intent and substantial test coverage areas, but environment reproducibility still needs improvement**.

This is still a positive quality signal. The main issue is not the absence of tests, but the reproducibility of the test environment. A future iteration can strengthen the project significantly by standardizing fixtures, test database configuration, and execution instructions.

---

### 4.2 Model Comparison and Results Discussion

This section is especially important because the user requested a model comparison.

### 4.2.1 Important Clarification

The repository contains evidence of **two AI architecture directions**:

1. **Historical / experimental local-model path**
   - based on Qwen models through Hugging Face and PyTorch;
   - represented by `llm_service.py` and older documentation files.

2. **Current runtime path**
   - based on **Groq API**;
   - model configured as **`llama-3.3-70b-versatile`**;
   - represented by `groq_service.py`, `chat.py`, `sql_agent.py`, and `intent_router.py`.

Therefore, the most accurate comparison is between:

- the older local-Qwen idea,
- the currently active Groq-hosted Llama model,
- and the deterministic non-LLM logic that is heavily used in the present system.

### 4.2.2 Architectural Comparison

| Aspect | Historical Local Qwen Path | Current Groq Llama Path | Deterministic Local Logic |
|---|---|---|---|
| Status in repository | Present but not active in current main flow | Active in current code | Active and central |
| Main files | `llm_service.py`, older docs | `groq_service.py` | `intent_router.py`, `sql_agent.py` |
| Infrastructure | Requires local model loading and more hardware | Requires Groq API key and internet access | Runs locally with backend and DB |
| Typical role | Natural language to SQL generation | SQL fallback, classification, conversational handling, ENET'Com summarization | Intent routing, entity extraction, SQL rules, filtering, formatting |
| Resource cost | High local RAM/GPU requirements | External inference cost, lower local hardware need | Low AI cost, high reliability |
| Reliability for strict timetable logic | Medium without safeguards | Good when guarded | Very high for known patterns |
| Deployment complexity | Higher | Moderate | Low |

### 4.2.3 Why the Current Hybrid Strategy Is Better

From the actual code, the current system does not rely entirely on the LLM. This is a good engineering decision for several reasons:

- timetable questions are repetitive and structured;
- deterministic SQL is often more reliable than fully generative SQL;
- class names, professor names, and room names require exact or fuzzy-controlled matching;
- active semester and timetable-version constraints must be enforced precisely;
- clarification messages are often better handled by rules than by free generation.

As a result, the system uses the model where it helps most, but preserves deterministic control where correctness matters most.

### 4.2.4 Results Observed in the Repository

The repository does **not** contain a formal benchmark dataset, accuracy matrix, latency dashboard, or quantitative evaluation comparing models on the same test set. Therefore, no scientifically measured accuracy percentage can be claimed from the code alone.

However, several qualitative results can be inferred from the implementation:

- the project evolved from a pure LLM-oriented concept toward a more robust hybrid architecture;
- the current code includes extensive safeguards around SQL execution;
- the intent router supports contextual follow-up and clarification management;
- the teacher, room, class, and calendar use cases are explicitly modeled;
- the backend test suite strongly focuses on correctness for routing, formatting, typo handling, and day filtering.

### 4.2.5 Practical Comparison of Expected Behavior

**Local Qwen approach**  
This approach is useful when offline or self-hosted inference is required, but it introduces more operational complexity, more hardware constraints, and higher maintenance burden.

**Groq + Llama approach**  
This approach simplifies deployment because model hosting is externalized. It provides strong language capabilities without requiring a local GPU. However, it introduces network dependency and external-service dependence.

**Deterministic rule-based core**  
This is the most reliable part of the system for structured timetable retrieval. It offers predictable behavior, better safety, and easier debugging.

### 4.2.6 Final Evaluation of the AI Strategy

The most successful result of this project is not the use of one model over another. The real success is the **hybrid design**:

- rules for reliability,
- database logic for precision,
- model assistance for flexibility,
- web-source grounding for general university information.

That is a strong and defendable engineering choice for a PFE project.

---

### 4.3 Strengths of the Project

The main strengths observed in the repository are:

- clear separation between frontend, backend, and services;
- practical use case with real academic value;
- hybrid AI architecture instead of naive chatbot integration;
- protected admin import workflow;
- support for class, teacher, room, and calendar perspectives;
- dynamic extraction of ENET'Com official information;
- security-conscious session handling;
- meaningful backend test coverage areas;
- import-validation logic that reduces operational mistakes.

---

### 4.4 Limitations and Risks

Despite its strengths, the project still has several limitations.

### 4.4.1 Documentation Inconsistency

Some existing repository documents describe a local Qwen architecture that does not match the active runtime code. This can confuse future developers unless documentation is consolidated.

### 4.4.2 Backend Test Portability

The backend tests do not run cleanly in the current environment without additional setup. This weakens reproducibility.

### 4.4.3 Dependency on Data Quality

The chatbot quality depends strongly on the correctness and consistency of imported Excel files. Poorly formatted source files can lead to inaccurate results.

### 4.4.4 External AI Dependency

The current production model path depends on Groq availability and API configuration.

### 4.4.5 Limited Frontend Testing

Frontend testing is still minimal and currently includes only a basic smoke test.

### 4.4.6 Mixed Import Stack

The project uses both ORM and direct database-driver access in different scripts. This is not necessarily wrong, but it increases maintenance complexity.

### Chapter 4 Conclusion

This chapter examined validation practices, observed test results, model and architecture comparison, as well as the main strengths and limitations of the current implementation. It highlighted both the maturity of the hybrid design and the areas where the project can become more rigorous, especially in documentation alignment, reproducible testing, and measurable evaluation.

---

## Chapter 5. Improvement and Upgrade Perspectives

### 5.1 Possible Improvements and Future Work

The following improvements would be valuable in a next project phase:

- align all markdown documentation with the actual current implementation;
- make backend tests runnable through a reproducible test setup;
- add real frontend component and integration tests;
- add observability and structured logging;
- measure latency and answer accuracy on a representative academic question set;
- add export features such as PDF or iCalendar;
- support multilingual responses;
- provide role-specific personalization for students and professors;
- cache university-site content and selected chatbot responses;
- improve analytics for admin imports and chatbot usage.

### 5.1.1 How the Project Can Be Upgraded Technically

The first important upgrade would be to unify the repository documentation. At the moment, some files still describe an older Qwen-based architecture while the current runtime path is Groq-based. A future version should clearly separate archived experiments from active implementation. This would improve maintainability, reduce confusion for future developers, and strengthen the overall professional quality of the repository.

Another major technical improvement would be to make backend testing fully reproducible. The current repository already contains many backend tests, which is a strength, but they depend on environment conditions that are not yet stable enough. This can be improved by adding a dedicated test database configuration, clearer fixture management, and a standardized execution process. Once this is done, the test suite can become a reliable validation layer for future development.

The frontend can also be upgraded by using TanStack Query more systematically for API state management. This would improve request caching, retry behavior, mutation synchronization, and loading-state consistency. Additional frontend tests should also be introduced for route protection, authentication flow, admin upload behavior, and chat rendering.

### 5.1.2 How the AI Layer Can Be Improved

One of the best future upgrades would be to build a real evaluation dataset of academic questions. This dataset should include timetable queries, typo-heavy requests, room questions, professor questions, calendar questions, follow-up prompts, and out-of-scope messages. With such a dataset, the team could measure routing quality, SQL-generation quality, and response quality more scientifically.

Another AI-related upgrade would be personalization. Since the system already has authentication, future versions could associate each student with a default class and each professor with a default identity. In that case, the chatbot could answer many questions without repeatedly asking for the same context. This would improve usability and make the assistant more natural in daily use.

The model strategy itself can also evolve. The project may continue with hosted inference and improve prompts, caching, and fallback rules, or revisit the local-model path if offline deployment becomes an institutional requirement. Because the current architecture is modular, this kind of upgrade remains realistic.

### 5.1.3 Functional Improvements

From a functional point of view, the project can be upgraded by adding export and synchronization features such as PDF generation, iCalendar export, and integration with personal calendar tools. This would transform the system from a consultation assistant into a more complete daily planning tool for students and teachers.

Another valuable improvement would be a notification subsystem. The platform could inform users about timetable changes, upcoming exams, holidays, or professor absences. Since the project already stores academic periods and imports institutional data, this would be a natural extension of the existing design.

The administration space can also evolve into a richer monitoring dashboard. It could display statistics on imports, anomalies, upload history, session counts by semester, and chatbot usage analytics. This would increase the institutional usefulness of the platform beyond question answering alone.

### 5.1.4 Long-Term Upgrade Vision

The long-term evolution of the project is to move from a timetable assistant toward a broader academic digital assistant. The current foundations are already strong: authentication, import workflow, structured relational data, institutional information retrieval, and hybrid intelligent processing. With progressive improvements, the same platform could support timetable consultation, personalized academic help, alerts, exports, and broader university information services in one unified environment.

### Chapter 5 Conclusion

This chapter showed that the project has strong upgrade potential at technical, functional, and AI-related levels. The current implementation already provides a robust base for future development, and the proposed improvements demonstrate that the platform can evolve gradually into a richer academic digital service without losing the strengths of its present architecture.

---

## General Conclusion

Time Guide AI is a serious and well-structured academic software project that addresses a real institutional problem: efficient access to timetable and university information. The application combines a modern web frontend, a clean API backend, a relational academic database, an Excel import pipeline, and a hybrid intelligent layer adapted to the operational reality of ENET'Com.

What makes the project particularly interesting from an engineering standpoint is that it goes beyond a simple chatbot demonstration. It integrates real data workflows, role-based administration, deterministic reasoning, guarded SQL execution, official-web information retrieval, and selective large-language-model usage. This makes the project much more credible and practical than a purely generative prototype.

The repository also shows an evolution in architectural thinking: from an earlier local-Qwen concept to a more maintainable Groq-based hybrid approach. This evolution is positive because it reflects a move toward better reliability, clearer separation of responsibilities, and more realistic deployment constraints.

In conclusion, this project is a strong PFE case study in applied AI engineering, full-stack development, and academic-information systems. With a few improvements in documentation consistency, test reproducibility, and evaluation metrics, it can become an even more robust and professional platform.

---

## Bibliography / References

The bibliography below is formatted in **IEEE style**, which is widely used in engineering and computer science reports:

[1] FastAPI, "FastAPI Documentation." [Online]. Available: https://fastapi.tiangolo.com/

[2] React, "React Documentation." [Online]. Available: https://react.dev/

[3] Vite, "Vite Documentation." [Online]. Available: https://vitejs.dev/

[4] PostgreSQL Global Development Group, "PostgreSQL Documentation." [Online]. Available: https://www.postgresql.org/docs/

[5] SQLAlchemy, "SQLAlchemy Documentation." [Online]. Available: https://docs.sqlalchemy.org/

[6] Tailwind Labs, "Tailwind CSS Documentation." [Online]. Available: https://tailwindcss.com/docs/

[7] Radix UI, "Radix UI Documentation." [Online]. Available: https://www.radix-ui.com/

[8] Pandas Development Team, "Pandas Documentation." [Online]. Available: https://pandas.pydata.org/docs/

[9] OpenPyXL, "OpenPyXL Documentation." [Online]. Available: https://openpyxl.readthedocs.io/

[10] Vitest, "Vitest Documentation." [Online]. Available: https://vitest.dev/

[11] pytest, "pytest Documentation." [Online]. Available: https://docs.pytest.org/

[12] Groq, "Groq API Documentation." [Online]. Available: https://console.groq.com/docs/

[13] ENET'Com, "Official ENET'Com Website." [Online]. Available: https://enetcom.rnu.tn/fr

If required by the university, this bibliography can also be converted later into APA or another institutional citation format.


