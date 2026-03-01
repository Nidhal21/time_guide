-- Script d'initialisation de la base de données

-- 1. Table annees_universitaires
CREATE TABLE IF NOT EXISTS annees_universitaires (
    id SERIAL PRIMARY KEY,
    libelle VARCHAR(20) NOT NULL,
    date_debut DATE,
    date_fin DATE
);

-- 2. Table semestres
CREATE TABLE IF NOT EXISTS semestres (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(20) NOT NULL,
    annee_id INTEGER REFERENCES annees_universitaires(id)
);

-- 3. Table departements
CREATE TABLE IF NOT EXISTS departements (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL
);

-- 4. Table classes
CREATE TABLE IF NOT EXISTS classes (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(50) NOT NULL,
    departement_id INTEGER REFERENCES departements(id),
    semestre_id INTEGER REFERENCES semestres(id)
);

-- 5. Table professeurs
CREATE TABLE IF NOT EXISTS professeurs (
    id SERIAL PRIMARY KEY,
    nom_complet VARCHAR(150) NOT NULL,
    grade VARCHAR(50),
    specialite VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_prof_nom ON professeurs(nom_complet);

-- 6. Table matieres
CREATE TABLE IF NOT EXISTS matieres (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(150) NOT NULL,
    code VARCHAR(20)
);

-- 7. Table salles
CREATE TABLE IF NOT EXISTS salles (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    type VARCHAR(50),
    capacite INTEGER
);

-- 8. Table groupes
CREATE TABLE IF NOT EXISTS groupes (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(20),
    classe_id INTEGER REFERENCES classes(id)
);

-- 9. Table emplois_versions
CREATE TABLE IF NOT EXISTS emplois_versions (
    id SERIAL PRIMARY KEY,
    classe_id INTEGER REFERENCES classes(id),
    version_date DATE,
    actif BOOLEAN DEFAULT TRUE
);

-- 10. Table seances
CREATE TABLE IF NOT EXISTS seances (
    id SERIAL PRIMARY KEY,
    version_id INTEGER REFERENCES emplois_versions(id),
    classe_id INTEGER REFERENCES classes(id),
    matiere_id INTEGER REFERENCES matieres(id),
    professeur_id INTEGER REFERENCES professeurs(id),
    salle_id INTEGER REFERENCES salles(id),
    groupe_id INTEGER REFERENCES groupes(id),
    jour VARCHAR(15) NOT NULL,
    heure_debut TIME NOT NULL,
    heure_fin TIME NOT NULL,
    type_seance VARCHAR(20)
);

-- Index pour optimisation
CREATE INDEX IF NOT EXISTS idx_seance_jour ON seances(jour);
CREATE INDEX IF NOT EXISTS idx_seance_prof ON seances(professeur_id);
CREATE INDEX IF NOT EXISTS idx_seance_classe ON seances(classe_id);
CREATE INDEX IF NOT EXISTS idx_seance_salle ON seances(salle_id);

-- Données de test
INSERT INTO annees_universitaires (libelle, date_debut, date_fin) 
VALUES ('2025/2026', '2025-09-01', '2026-06-30')
ON CONFLICT DO NOTHING;

INSERT INTO departements (nom) 
VALUES ('GII'), ('INFO'), ('TELECOM')
ON CONFLICT DO NOTHING;
