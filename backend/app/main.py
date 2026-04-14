from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from azure.storage.blob import BlobServiceClient
import uuid
import os
from datetime import datetime

from app.routes import auth, shared, files, folders

from .database import engine, ensure_folder_parent_column
from . import models

# Khởi tạo Database
models.Base.metadata.create_all(bind=engine)
ensure_folder_parent_column()

app = FastAPI()

# --- CẤU HÌNH CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(shared.router)
app.include_router(files.router)
app.include_router(folders.router)

# --- CẤU HÌNH AZURE BLOB STORAGE ---
AZURE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=YOUR_ACCOUNT;AccountKey=YOUR_KEY;EndpointSuffix=core.windows.net"
CONTAINER_NAME = "uploads" 

@app.get("/")
def read_root():
    return {"message": "Hệ thống Azure File Storage đang chạy mượt mà!"}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)

        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        blob_client = container_client.get_blob_client(unique_filename)

        contents = await file.read()
        blob_client.upload_blob(contents, overwrite=True)
        
        file_metadata = {
            "file_name": file.filename,
            "azure_name": unique_filename,
            "size_bytes": len(contents),
            "file_url": blob_client.url,
            "created_at": datetime.now().isoformat()
        }
        
        return {"status": "success", "message": "Upload thành công", "data": file_metadata}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))