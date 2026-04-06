from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.db_config import get_db
from app.services.auth_service import get_current_user, login_user, logout_session, signup_user


router = APIRouter()


class SignInRequest(BaseModel):
    email: str
    password: str


class SignUpRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None


@router.post("/auth/login")
async def auth_login(payload: SignInRequest, db: Session = Depends(get_db)):
    return login_user(db, email=payload.email, password=payload.password)


@router.post("/auth/signup")
async def auth_signup(payload: SignUpRequest, db: Session = Depends(get_db)):
    return signup_user(db, email=payload.email, password=payload.password, full_name=payload.full_name)


@router.get("/auth/me")
async def auth_me(current_user=Depends(get_current_user)):
    return {"user": current_user}


@router.post("/auth/logout")
async def auth_logout(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    token = ""
    if authorization:
        _, _, token = authorization.partition(" ")
    logout_session(db, token.strip())
    return {"success": True}
