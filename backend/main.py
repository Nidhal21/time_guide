from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import admin, auth, chat
from app.models.db_config import SessionLocal, engine
from app.models.database import Base
from app.services.auth_service import ensure_auth_tables

app = FastAPI(title="Emploi du Temps Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8080", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup() -> None:
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
    return {"message": "Emploi du Temps Chatbot API"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
