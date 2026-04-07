from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as file_router
from app.core.config import DATA_DIR, STORAGE_DIR
from app.db.base import Base
from app.db.seed import seed_initial_data
from app.db.session import engine
from app.db.session import SessionLocal

app = FastAPI(title="Azure File Storage System API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(file_router)
