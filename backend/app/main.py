from fastapi import FastAPI

from app.routes import auth
from .database import engine
from . import models
from fastapi.middleware.cors import CORSMiddleware
models.Base.metadata.create_all(bind=engine)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],
)
app.include_router(auth.router)
@app.get("/")
def read_root():
    return {"Hello": "World"}
