from sqlalchemy import Column, Integer, String, Date, Time, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class AnneeUniversitaire(Base):
    __tablename__ = "annees_universitaires"
    id = Column(Integer, primary_key=True)
    libelle = Column(String(20), nullable=False)
    date_debut = Column(Date)
    date_fin = Column(Date)

class Semestre(Base):
    __tablename__ = "semestres"
    id = Column(Integer, primary_key=True)
    nom = Column(String(20), nullable=False)
    annee_id = Column(Integer, ForeignKey("annees_universitaires.id"))

class Periode(Base):
    __tablename__ = "periodes"
    id = Column(Integer, primary_key=True)
    nom = Column(String(10), nullable=False)  # P1 ou P2
    semestre_id = Column(Integer, ForeignKey("semestres.id"))
    date_debut = Column(Date, nullable=False)
    date_fin = Column(Date, nullable=False)

class Departement(Base):
    __tablename__ = "departements"
    id = Column(Integer, primary_key=True)
    nom = Column(String(100), nullable=False)

class Classe(Base):
    __tablename__ = "classes"
    id = Column(Integer, primary_key=True)
    nom = Column(String(50), nullable=False)
    departement_id = Column(Integer, ForeignKey("departements.id"))
    semestre_id = Column(Integer, ForeignKey("semestres.id"))

class Professeur(Base):
    __tablename__ = "professeurs"
    id = Column(Integer, primary_key=True)
    nom_complet = Column(String(150), nullable=False, index=True)
    grade = Column(String(50))
    specialite = Column(String(100))

class Matiere(Base):
    __tablename__ = "matieres"
    id = Column(Integer, primary_key=True)
    nom = Column(String(150), nullable=False)
    code = Column(String(20))

class Salle(Base):
    __tablename__ = "salles"
    id = Column(Integer, primary_key=True)
    nom = Column(String(100), nullable=False)
    type = Column(String(50))
    capacite = Column(Integer)

class Groupe(Base):
    __tablename__ = "groupes"
    id = Column(Integer, primary_key=True)
    nom = Column(String(20))
    classe_id = Column(Integer, ForeignKey("classes.id"))

class EmploiVersion(Base):
    __tablename__ = "emplois_versions"
    id = Column(Integer, primary_key=True)
    classe_id = Column(Integer, ForeignKey("classes.id"))
    version_date = Column(Date)
    actif = Column(Boolean, default=True)

class Seance(Base):
    __tablename__ = "seances"
    id = Column(Integer, primary_key=True)
    version_id = Column(Integer, ForeignKey("emplois_versions.id"))
    classe_id = Column(Integer, ForeignKey("classes.id"))
    matiere_id = Column(Integer, ForeignKey("matieres.id"))
    professeur_id = Column(Integer, ForeignKey("professeurs.id"))
    salle_id = Column(Integer, ForeignKey("salles.id"))
    groupe_id = Column(Integer, ForeignKey("groupes.id"), nullable=True)
    periode_id = Column(Integer, ForeignKey("periodes.id"), nullable=True)
    jour = Column(String(15), nullable=False, index=True)
    heure_debut = Column(Time, nullable=False)
    heure_fin = Column(Time, nullable=False)
    type_seance = Column(String(20))


class EmploiEnseignantSeance(Base):
    __tablename__ = "emplois_enseignants_seances"

    id = Column(Integer, primary_key=True)
    semestre_id = Column(Integer, ForeignKey("semestres.id"), nullable=False, index=True)
    professeur_nom_complet = Column(String(150), nullable=False, index=True)
    classe_nom = Column(String(50), nullable=False, index=True)
    matiere_nom = Column(String(150), nullable=False)
    salle_nom = Column(String(100))
    jour = Column(String(15), nullable=False, index=True)
    heure_debut = Column(Time, nullable=False)
    heure_fin = Column(Time, nullable=False)
    periode_nom = Column(String(10), nullable=False, index=True)
    type_seance = Column(String(20))
    source_file = Column(String(255))


class VacancesJoursFeries(Base):
    __tablename__ = "vacances_jours_feries"
    id = Column(Integer, primary_key=True)
    nom = Column(String(100), nullable=False)
    date_debut = Column(Date, nullable=False)
    date_fin = Column(Date, nullable=False)
    type = Column(String(20), nullable=False)  # "vacances", "jour_ferie", "examen", "revision"
    annee_id = Column(Integer, ForeignKey("annees_universitaires.id"))
