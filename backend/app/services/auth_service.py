from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.db_config import get_db


SESSION_TTL_DAYS = int(os.getenv("AUTH_SESSION_TTL_DAYS", "14"))
PASSWORD_ITERATIONS = 200_000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _token_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _configured_admin_email() -> str:
    return _normalize_email(os.getenv("ADMIN_EMAIL", ""))


def _configured_admin_password() -> str:
    return os.getenv("ADMIN_PASSWORD", "")


def _configured_admin_name() -> str:
    return (os.getenv("ADMIN_FULL_NAME", "Administrateur ENETCOM") or "Administrateur ENETCOM").strip()


def _hash_password(password: str, salt: Optional[str] = None) -> str:
    use_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        (password or "").encode("utf-8"),
        use_salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    return f"{use_salt}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash or "$" not in stored_hash:
        return False
    salt, expected = stored_hash.split("$", 1)
    actual = _hash_password(password, salt).split("$", 1)[1]
    return secrets.compare_digest(actual, expected)


def ensure_auth_tables(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS auth_users (
                id TEXT PRIMARY KEY,
                email VARCHAR(255) NOT NULL UNIQUE,
                full_name VARCHAR(255),
                password_hash TEXT NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                email VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                role VARCHAR(20) NOT NULL DEFAULT 'user',
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
    )
    db.commit()


def _auth_not_configured_error() -> HTTPException:
    return HTTPException(
        status_code=500,
        detail="ADMIN_EMAIL et ADMIN_PASSWORD doivent etre definis dans le fichier .env.",
    )


def _admin_identity() -> Dict[str, Any]:
    email = _configured_admin_email()
    password = _configured_admin_password()
    if not email or not password:
        raise _auth_not_configured_error()
    return {
        "id": "admin",
        "email": email,
        "full_name": _configured_admin_name(),
        "role": "admin",
        "created_at": None,
    }


def _session_payload(token: str, expires_at: datetime) -> Dict[str, Any]:
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires_at.isoformat(),
    }


def _create_session(db: Session, user: Dict[str, Any]) -> Dict[str, Any]:
    token = secrets.token_urlsafe(48)
    session_id = secrets.token_urlsafe(16)
    expires_at = _utcnow() + timedelta(days=SESSION_TTL_DAYS)

    db.execute(
        text("DELETE FROM auth_sessions WHERE email = :email OR expires_at < :now"),
        {"email": user["email"], "now": _utcnow().replace(tzinfo=None)},
    )
    db.execute(
        text(
            """
            INSERT INTO auth_sessions (id, user_id, email, full_name, role, token_hash, expires_at)
            VALUES (:id, :user_id, :email, :full_name, :role, :token_hash, :expires_at)
            """
        ),
        {
            "id": session_id,
            "user_id": user["id"],
            "email": user["email"],
            "full_name": user.get("full_name"),
            "role": user["role"],
            "token_hash": _token_hash(token),
            "expires_at": expires_at.replace(tzinfo=None),
        },
    )
    db.commit()
    return _session_payload(token, expires_at)


def _user_row_to_payload(row) -> Dict[str, Any]:
    created_at = row.get("created_at")
    if hasattr(created_at, "isoformat"):
        created_at_value = created_at.isoformat()
    elif created_at:
        created_at_value = str(created_at)
    else:
        created_at_value = None

    return {
        "id": row["id"],
        "email": row["email"],
        "full_name": row["full_name"],
        "role": row["role"],
        "created_at": created_at_value,
    }


def signup_user(db: Session, email: str, password: str, full_name: Optional[str] = None) -> Dict[str, Any]:
    ensure_auth_tables(db)
    normalized_email = _normalize_email(email)
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Email obligatoire.")
    if len((password or "").strip()) < 6:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 6 caracteres.")
    if normalized_email == _configured_admin_email():
        raise HTTPException(status_code=403, detail="Cet email est reserve au compte admin.")

    existing = db.execute(
        text("SELECT id FROM auth_users WHERE email = :email LIMIT 1"),
        {"email": normalized_email},
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Un compte existe deja avec cet email.")

    user_id = secrets.token_urlsafe(12)
    display_name = (full_name or normalized_email.split("@")[0]).strip()
    password_hash = _hash_password(password)

    db.execute(
        text(
            """
            INSERT INTO auth_users (id, email, full_name, password_hash, role)
            VALUES (:id, :email, :full_name, :password_hash, 'user')
            """
        ),
        {
            "id": user_id,
            "email": normalized_email,
            "full_name": display_name,
            "password_hash": password_hash,
        },
    )
    db.commit()

    user = {
        "id": user_id,
        "email": normalized_email,
        "full_name": display_name,
        "role": "user",
        "created_at": None,
    }
    session = _create_session(db, user)
    return {"user": user, "session": session}


def login_user(db: Session, email: str, password: str) -> Dict[str, Any]:
    ensure_auth_tables(db)
    normalized_email = _normalize_email(email)
    admin_identity = _admin_identity()

    if normalized_email == admin_identity["email"]:
        if password != _configured_admin_password():
            raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect.")
        return {
            "user": admin_identity,
            "session": _create_session(db, admin_identity),
        }

    row = db.execute(
        text(
            """
            SELECT id, email, full_name, password_hash, role, created_at
            FROM auth_users
            WHERE email = :email
            LIMIT 1
            """
        ),
        {"email": normalized_email},
    ).mappings().first()

    if not row or not _verify_password(password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect.")

    user = _user_row_to_payload(row)
    session = _create_session(db, user)
    return {"user": user, "session": session}


def logout_session(db: Session, token: str) -> None:
    if not token:
        return
    ensure_auth_tables(db)
    db.execute(
        text("DELETE FROM auth_sessions WHERE token_hash = :token_hash"),
        {"token_hash": _token_hash(token)},
    )
    db.commit()


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentification requise.")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token Bearer invalide.")
    return token.strip()


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    ensure_auth_tables(db)
    token = _extract_bearer_token(authorization)

    row = db.execute(
        text(
            """
            SELECT user_id, email, full_name, role, expires_at
            FROM auth_sessions
            WHERE token_hash = :token_hash
            LIMIT 1
            """
        ),
        {"token_hash": _token_hash(token)},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalide.")

    expires_at = row["expires_at"]
    if expires_at and expires_at < _utcnow().replace(tzinfo=None):
        db.execute(text("DELETE FROM auth_sessions WHERE token_hash = :token_hash"), {"token_hash": _token_hash(token)})
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expiree.")

    return {
        "id": row["user_id"],
        "email": row["email"],
        "full_name": row["full_name"],
        "role": row["role"],
        "created_at": None,
        "token": token,
    }


def get_admin_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acces admin requis.")
    return current_user
