from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from azure.storage.blob import BlobServiceClient
import uuid
import os
from datetime import datetime

from app.routes import auth, shared, files, folder

from .database import engine
from . import models

# Khởi tạo Database
models.Base.metadata.create_all(bind=engine)


def ensure_schema_extensions() -> None:
    with engine.begin() as conn:
        # Check and add folders.is_deleted column
        column_exists = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = 'folders'
                  AND column_name = 'is_deleted'
                """
            )
        ).scalar()

        if not column_exists:
            conn.execute(text("ALTER TABLE folders ADD COLUMN is_deleted TINYINT(1) NOT NULL DEFAULT 0"))

        # Check and add shared_links.folder_id column
        column_exists = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = 'shared_links'
                  AND column_name = 'folder_id'
                """
            )
        ).scalar()

        if not column_exists:
            conn.execute(text("ALTER TABLE shared_links ADD COLUMN folder_id INT UNSIGNED NULL"))
            conn.execute(text("ALTER TABLE shared_links ADD CONSTRAINT fk_shared_links_folder_id FOREIGN KEY (folder_id) REFERENCES folders(id)"))

        # Make shared_links.file_id nullable - need to drop and recreate foreign key
        file_id_nullable = conn.execute(
            text(
                """
                SELECT IS_NULLABLE
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = 'shared_links'
                  AND column_name = 'file_id'
                """
            )
        ).scalar()

        if file_id_nullable == 'NO':
            # Drop the foreign key constraint first
            try:
                conn.execute(text("ALTER TABLE shared_links DROP FOREIGN KEY shared_links_ibfk_1"))
            except:
                pass  # Foreign key might not exist or have a different name
            
            # Modify the column to be nullable with correct type
            conn.execute(text("ALTER TABLE shared_links MODIFY COLUMN file_id INT UNSIGNED NULL"))
            
            # Re-add the foreign key constraint
            try:
                conn.execute(text("ALTER TABLE shared_links ADD CONSTRAINT fk_shared_links_file_id FOREIGN KEY (file_id) REFERENCES files(id)"))
            except:
                pass  # Constraint might already exist


ensure_schema_extensions()

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
app.include_router(folder.router)

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