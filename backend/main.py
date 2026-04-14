import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from app.models.database import Base
from app.models.db_config import SessionLocal, engine
from app.routes import admin, auth, chat
from app.services.auth_service import ensure_auth_tables


load_dotenv()


def _parse_cors_origins() -> list[str]:
    raw_value = os.getenv("CORS_ALLOWED_ORIGINS", "")
    origins = [origin.strip() for origin in raw_value.split(",") if origin.strip()]
    if origins:
        return origins
    return [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
    ]


def _cors_allow_origin_regex() -> str | None:
    explicit_regex = os.getenv("CORS_ALLOW_ORIGIN_REGEX", "").strip()
    if explicit_regex:
        return explicit_regex
    if os.getenv("RENDER", "").lower() == "true":
        return r"https://.*\.vercel\.app"
    return None


def _ensure_runtime_directories() -> None:
    base_uploads_dir = Path(__file__).resolve().parent / "uploads"
    for relative_path in (
        "",
        "calendar",
        "students",
        "students/s1",
        "students/s2",
        "teachers",
        "teachers/s1",
        "teachers/s2",
    ):
        (base_uploads_dir / relative_path).mkdir(parents=True, exist_ok=True)


app = FastAPI(title="Emploi du Temps Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(),
    allow_origin_regex=_cors_allow_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    _ensure_runtime_directories()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_auth_tables(db)
    finally:
        db.close()


app.include_router(auth.router, prefix="/api", tags=["Auth"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(admin.router, prefix="/api", tags=["Admin"])


@app.get("/")
async def root():
    return {
        "message": "Emploi du Temps Chatbot API",
        "status": "ok",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
