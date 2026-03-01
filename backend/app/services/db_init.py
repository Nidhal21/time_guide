"""
Script pour créer les tables et initialiser les données de base
À exécuter une seule fois pour mettre en place la base de données
"""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date

# Charger les variables d'environnement
env_file = Path(__file__).parent.parent.parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                if key not in os.environ:
                    os.environ[key] = value

from app.models.database import Base, AnneeUniversitaire, Semestre, Periode

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@127.0.0.1:5432/emploi_temps")

def init_database():
    """Crée toutes les tables"""
    engine = create_engine(DATABASE_URL, echo=True)
    
    # Créer les tables
    print("\n📊 Création des tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables créées avec succès")

def seed_academic_calendar():
    """Initialise le calendrier académique 2025-2026"""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    print("\n📚 Initialisation du calendrier académique...")
    
    try:
        # Vérifier si l'année existe déjà
        annee = db.query(AnneeUniversitaire).filter_by(libelle="2025-2026").first()
        if annee:
            print("✓ Année 2025-2026 existe déjà")
        else:
            annee = AnneeUniversitaire(
                libelle="2025-2026",
                date_debut=date(2025, 9, 1),
                date_fin=date(2026, 8, 31)
            )
            db.add(annee)
            db.commit()
            print("✓ Année 2025-2026 créée")
        
        # Créer Semestre 1
        sem1 = db.query(Semestre).filter_by(nom="S1", annee_id=annee.id).first()
        if not sem1:
            sem1 = Semestre(nom="S1", annee_id=annee.id)
            db.add(sem1)
            db.commit()
            print("✓ Semestre S1 créé")
        
        # Créer Semestre 2
        sem2 = db.query(Semestre).filter_by(nom="S2", annee_id=annee.id).first()
        if not sem2:
            sem2 = Semestre(nom="S2", annee_id=annee.id)
            db.add(sem2)
            db.commit()
            print("✓ Semestre S2 créé")
        
        # Créer Périodes S1
        p1_s1 = db.query(Periode).filter_by(nom="P1", semestre_id=sem1.id).first()
        if not p1_s1:
            p1_s1 = Periode(
                nom="P1",
                semestre_id=sem1.id,
                date_debut=date(2025, 9, 1),
                date_fin=date(2025, 11, 30)
            )
            db.add(p1_s1)
            print("✓ Période S1-P1 créée")
        
        p2_s1 = db.query(Periode).filter_by(nom="P2", semestre_id=sem1.id).first()
        if not p2_s1:
            p2_s1 = Periode(
                nom="P2",
                semestre_id=sem1.id,
                date_debut=date(2025, 12, 1),
                date_fin=date(2026, 2, 28)
            )
            db.add(p2_s1)
            print("✓ Période S1-P2 créée")
        
        # Créer Périodes S2
        p1_s2 = db.query(Periode).filter_by(nom="P1", semestre_id=sem2.id).first()
        if not p1_s2:
            p1_s2 = Periode(
                nom="P1",
                semestre_id=sem2.id,
                date_debut=date(2026, 3, 1),
                date_fin=date(2026, 5, 31)
            )
            db.add(p1_s2)
            print("✓ Période S2-P1 créée")
        
        p2_s2 = db.query(Periode).filter_by(nom="P2", semestre_id=sem2.id).first()
        if not p2_s2:
            p2_s2 = Periode(
                nom="P2",
                semestre_id=sem2.id,
                date_debut=date(2026, 6, 1),
                date_fin=date(2026, 8, 31)
            )
            db.add(p2_s2)
            print("✓ Période S2-P2 créée")
        
        db.commit()
        print("\n✅ Calendrier académique initialisé")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        db.rollback()
    finally:
        db.close()

def load_calendar_from_excel(calendar_file: str):
    """
    Charge le calendrier depuis le fichier Excel dédié
    Pour personnaliser les dates exactes des périodes
    """
    import pandas as pd
    from pathlib import Path
    
    calendar_path = Path(__file__).parent.parent.parent / "public" / "excel_files" / calendar_file
    
    if not calendar_path.exists():
        print(f"⚠️  Fichier calendrier non trouvé: {calendar_path}")
        return
    
    print(f"\n📅 Chargement du calendrier depuis: {calendar_file}")
    
    try:
        df = pd.read_excel(calendar_path)
        print(df.head(20))
        # À adapter selon la structure réelle du fichier Excel
    except Exception as e:
        print(f"⚠️  Erreur lors de la lecture: {e}")

if __name__ == "__main__":
    print("🚀 Initialisation de la base de données...")
    
    # Créer les tables
    init_database()
    
    # Initialiser le calendrier académique
    seed_academic_calendar()
    
    # Optionnel: charger le calendrier détaillé depuis Excel
    # load_calendar_from_excel("Calendrier universitaire 2024-2025 Modifié.xlsx")
    
    print("\n✅ Initialisation terminée!")
    print("\nProchaines étapes:")
    print("1. Vérifiez votre .env pour DATABASE_URL")
    print("2. Exécutez: python -m app.services.excel_importer")
