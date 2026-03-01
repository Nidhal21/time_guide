"""
Script de test pour vérifier la configuration du backend
"""
import sys
import os

def test_imports():
    """Test que tous les modules nécessaires sont installés"""
    print("Test des imports...")
    try:
        import fastapi
        print("✓ FastAPI installé")
    except ImportError:
        print("✗ FastAPI manquant")
        return False
    
    try:
        import sqlalchemy
        print("✓ SQLAlchemy installé")
    except ImportError:
        print("✗ SQLAlchemy manquant")
        return False
    
    try:
        import pandas
        print("✓ Pandas installé")
    except ImportError:
        print("✗ Pandas manquant")
        return False
    
    try:
        import transformers
        print("✓ Transformers installé")
    except ImportError:
        print("✗ Transformers manquant")
        return False
    
    return True

def test_env():
    """Test que les variables d'environnement sont configurées"""
    print("\nTest des variables d'environnement...")
    from dotenv import load_dotenv
    load_dotenv()
    
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        print(f"✓ DATABASE_URL configuré")
    else:
        print("✗ DATABASE_URL manquant dans .env")
        return False
    
    model_name = os.getenv("MODEL_NAME")
    if model_name:
        print(f"✓ MODEL_NAME configuré: {model_name}")
    else:
        print("⚠ MODEL_NAME manquant, utilisation de la valeur par défaut")
    
    return True

def test_database():
    """Test la connexion à la base de données"""
    print("\nTest de connexion à la base de données...")
    try:
        from app.models.db_config import engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✓ Connexion PostgreSQL réussie")
            return True
    except Exception as e:
        print(f"✗ Erreur de connexion: {e}")
        return False

def main():
    print("=" * 50)
    print("Test de configuration du backend")
    print("=" * 50)
    
    tests = [
        ("Imports", test_imports),
        ("Variables d'environnement", test_env),
        ("Base de données", test_database)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"✗ Erreur lors du test {name}: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 50)
    print("Résumé des tests")
    print("=" * 50)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(r[1] for r in results)
    if all_passed:
        print("\n✓ Tous les tests sont passés!")
        print("Vous pouvez lancer le serveur avec: uvicorn main:app --reload")
    else:
        print("\n✗ Certains tests ont échoué. Veuillez corriger les erreurs.")
        sys.exit(1)

if __name__ == "__main__":
    main()
