-- Script de création de la base de données
-- Exécuter avec: psql -U postgres -f init_db.sql

-- Créer la base de données
CREATE DATABASE emploi_temps;

-- Se connecter à la nouvelle BD
\c emploi_temps

-- Créer l'utilisateur
CREATE USER emploi_user WITH PASSWORD 'emploi_temps';

-- Donner les permissions
GRANT ALL PRIVILEGES ON DATABASE emploi_temps TO emploi_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO emploi_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO emploi_user;

-- Vérifier
SELECT 'Base de données créée avec succès!' as status;
