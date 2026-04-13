import os
from pathlib import Path
from typing import Annotated, List

from fastapi import APIRouter, Depends, File as FastAPIFile, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.routes.auth import get_current_user

router = APIRouter(prefix="/files", tags=["Quan ly file"])

_STORAGE_ROOT = Path(__file__).resolve().parents[2] / "storage"


def _owner_storage_dir(owner_id: int) -> Path:
    owner_dir = _STORAGE_ROOT / str(owner_id)
    owner_dir.mkdir(parents=True, exist_ok=True)
    return owner_dir


def _find_saved_file_path(owner_id: int, file_id: int) -> Path | None:
    owner_dir = _owner_storage_dir(owner_id)
    matches = list(owner_dir.glob(f"{file_id}__*"))
    if not matches:
        return None
    return matches[0]


def _to_file_item(file_obj: models.File) -> schemas.FileItemResponse:
    return schemas.FileItemResponse(
        id=file_obj.id,
        name=file_obj.name,
        size=file_obj.size,
        content_type=file_obj.content_type,
        blob_url=file_obj.blob_url,
        is_deleted=file_obj.is_deleted,
        created_at=file_obj.created_at,
        updated_at=file_obj.updated_at,
        type="file",
    )


@router.get("/list", response_model=schemas.FileListResponse)
def list_files(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    items = (
        db.query(models.File)
        .filter(models.File.owner_id == current_user.id, models.File.is_deleted.is_(False))
        .order_by(models.File.updated_at.desc())
        .all()
    )
    return {"items": [_to_file_item(item) for item in items]}


@router.get("/trash", response_model=schemas.FileListResponse)
def list_trash(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    items = (
        db.query(models.File)
        .filter(models.File.owner_id == current_user.id, models.File.is_deleted.is_(True))
        .order_by(models.File.updated_at.desc())
        .all()
    )
    return {"items": [_to_file_item(item) for item in items]}


@router.post("/upload", response_model=schemas.FileItemResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: Annotated[UploadFile, FastAPIFile(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    safe_name = Path(file.filename or "uploaded_file").name
    contents = await file.read()
    size_bytes = len(contents)

    if size_bytes == 0:
        raise HTTPException(status_code=400, detail="File rong khong hop le")

    if current_user.used_storage + size_bytes > current_user.max_storage:
        raise HTTPException(status_code=400, detail="Khong du dung luong de tai len file")

    new_file = models.File(
        name=safe_name,
        size=size_bytes,
        content_type=file.content_type or "application/octet-stream",
        blob_url="",
        owner_id=current_user.id,
        folder_id=None,
        is_deleted=False,
    )

    db.add(new_file)
    db.flush()

    saved_path = _owner_storage_dir(current_user.id) / f"{new_file.id}__{safe_name}"
    try:
        saved_path.write_bytes(contents)
        public_base = os.getenv("PUBLIC_API_BASE_URL", "http://127.0.0.1:8000")
        new_file.blob_url = f"{public_base}/files/public-content/{new_file.id}"
        current_user.used_storage = int(current_user.used_storage + size_bytes)
        db.commit()
        db.refresh(new_file)
        return _to_file_item(new_file)
    except Exception as exc:
        db.rollback()
        if saved_path.exists():
            saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Khong the tai file len: {exc}")


@router.delete("/{file_id}", response_model=schemas.FileActionResponse)
def move_to_trash(
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    file_obj = (
        db.query(models.File)
        .filter(models.File.id == file_id, models.File.owner_id == current_user.id)
        .first()
    )
    if not file_obj:
        raise HTTPException(status_code=404, detail="Khong tim thay file")

    if not file_obj.is_deleted:
        file_obj.is_deleted = True
        db.commit()

    return {"success": True, "message": "Da chuyen file vao thung rac"}


@router.post("/{file_id}/restore", response_model=schemas.FileActionResponse)
def restore_from_trash(
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    file_obj = (
        db.query(models.File)
        .filter(
            models.File.id == file_id,
            models.File.owner_id == current_user.id,
            models.File.is_deleted.is_(True),
        )
        .first()
    )
    if not file_obj:
        raise HTTPException(status_code=404, detail="Khong tim thay file trong thung rac")

    file_obj.is_deleted = False
    db.commit()
    return {"success": True, "message": "Da khoi phuc file"}


@router.delete("/{file_id}/permanent", response_model=schemas.FileActionResponse)
def permanent_delete(
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    file_obj = (
        db.query(models.File)
        .filter(models.File.id == file_id, models.File.owner_id == current_user.id)
        .first()
    )
    if not file_obj:
        raise HTTPException(status_code=404, detail="Khong tim thay file")

    saved_path = _find_saved_file_path(current_user.id, file_obj.id)
    if saved_path and saved_path.exists():
        saved_path.unlink(missing_ok=True)

    db.query(models.SharedLink).filter(models.SharedLink.file_id == file_obj.id).delete()

    if file_obj.size:
        current_user.used_storage = max(0, int(current_user.used_storage - file_obj.size))

    db.delete(file_obj)
    db.commit()
    return {"success": True, "message": "Da xoa vinh vien file"}


@router.get("/public-content/{file_id}")
def public_content(
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
    download: Annotated[bool, Query(description="True: tai xuong, False: xem truc tiep")] = False,
):
    file_obj = db.query(models.File).filter(models.File.id == file_id, models.File.is_deleted.is_(False)).first()
    if not file_obj:
        raise HTTPException(status_code=404, detail="Khong tim thay file")

    saved_path = _find_saved_file_path(file_obj.owner_id, file_obj.id)
    if not saved_path or not saved_path.exists():
        raise HTTPException(status_code=404, detail="Noi dung file khong ton tai")

    disposition_type = "attachment" if download else "inline"
    return FileResponse(
        path=saved_path,
        media_type=file_obj.content_type,
        filename=file_obj.name,
        content_disposition_type=disposition_type,
    )
