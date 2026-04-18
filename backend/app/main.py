from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from azure.storage.blob import BlobServiceClient
import uuid
import os
from sqlalchemy import text
from datetime import datetime
from app.routes import auth, shared, files, folder
from . import models
from dotenv import load_dotenv
from app.routes import auth, shared, files, folder
from .database import engine, get_db
from sqlalchemy.orm import Session
from fastapi import Depends

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

# --- ĐỒNG BỘ BIẾN MÔI TRƯỜNG VỚI .env ---
load_dotenv()
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "user-files")

@app.get("/")
def read_root():
    return {"message": "Hệ thống Azure File Storage đang chạy mượt mà!"}

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)

        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        blob_client = container_client.get_blob_client(unique_filename)

        contents = await file.read()
        blob_client.upload_blob(contents, overwrite=True)
        file_url = blob_client.url


        # Lưu thông tin file vào MySQL (đúng trường model File)
        new_file = models.File(
            name=file.filename,
            size=len(contents),
            content_type=file.content_type,
            blob_url=file_url,
            owner_id=1  # Thay bằng user_id thực tế nếu có xác thực đăng nhập
        )
        db.add(new_file)
        db.commit()
        db.refresh(new_file)

        file_metadata = {
            "file_id": new_file.id,
            "file_name": new_file.name,
            "azure_name": unique_filename,
            "size_bytes": new_file.size,
            "file_url": new_file.blob_url,
            "created_at": new_file.created_at.isoformat()
        }
        return {"status": "success", "message": "Upload thành công", "data": file_metadata}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))