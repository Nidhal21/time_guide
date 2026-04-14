import sys
import locale
import os
from pathlib import Path
from dotenv import load_dotenv

# Charger le .env
env_file = Path(__file__).parent.parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Set locale to handle encoding issues
if sys.platform == 'win32':
    try:
        locale.setlocale(locale.LC_ALL, 'C')
    except:
        pass

os.environ['PGCLIENTENCODING'] = 'UTF8'
os.environ['LANG'] = 'en_US.UTF-8'

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Charger DATABASE_URL depuis l'environnement
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://emploi_user:emploi_temps@127.0.0.1:5432/emploi_temps")

# Normalize URL scheme for SQLAlchemy + psycopg3
if DATABASE_URL:
    # Render sometimes provides postgres:// instead of postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    # SQLAlchemy requires postgresql+psycopg:// to use psycopg v3
    if DATABASE_URL.startswith("postgresql://") and "+" not in DATABASE_URL.split("://")[0]:
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
