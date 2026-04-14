import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File as FastAPIFile, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.routes.auth import get_current_user
from app.routes.folders import get_owned_folder_or_404

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


def _to_folder_item(folder_obj: models.Folder) -> schemas.FolderItemResponse:
    return schemas.FolderItemResponse(
        id=folder_obj.id,
        name=folder_obj.name,
        created_at=folder_obj.created_at,
        updated_at=folder_obj.updated_at,
        type="folder",
    )


def _ensure_unique_file_name(
    db: Session,
    current_user: models.User,
    folder_id: int | None,
    file_name: str,
    exclude_file_id: int | None = None,
) -> None:
    query = (
        db.query(models.File)
        .filter(
            models.File.owner_id == current_user.id,
            models.File.is_deleted.is_(False),
            models.File.folder_id.is_(folder_id) if folder_id is None else models.File.folder_id == folder_id,
            func.lower(models.File.name) == file_name.lower(),
        )
    )
    if exclude_file_id is not None:
        query = query.filter(models.File.id != exclude_file_id)
    if query.first():
        raise HTTPException(status_code=400, detail="Ten file da ton tai trong thu muc nay")


@router.get("/list", response_model=schemas.FileListResponse)
def list_files(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
    folder_id: Annotated[int | None, Query(description="Id thu muc")] = None,
):
    file_query = db.query(models.File).filter(models.File.owner_id == current_user.id, models.File.is_deleted.is_(False))
    if folder_id is None:
        file_query = file_query.filter(models.File.folder_id.is_(None))
    else:
        get_owned_folder_or_404(db, current_user, folder_id)
        file_query = file_query.filter(models.File.folder_id == folder_id)

    items = file_query.order_by(models.File.updated_at.desc()).all()
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


@router.post("/folders", response_model=schemas.FolderItemResponse, status_code=status.HTTP_201_CREATED)
def create_folder(
    folder_create: schemas.FolderCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    # Kiểm tra parent folder tồn tại
    if folder_create.folder_id:
        parent_folder = (
            db.query(models.Folder)
            .filter(
                models.Folder.id == folder_create.folder_id,
                models.Folder.owner_id == current_user.id
            )
            .first()
        )
        if not parent_folder:
            raise HTTPException(status_code=404, detail="Thư mục cha không tồn tại")
    
    new_folder = models.Folder(
        name=folder_create.name,
        owner_id=current_user.id,
        folder_id=folder_create.folder_id,
    )
    db.add(new_folder)
    db.commit()
    db.refresh(new_folder)
    return _to_folder_item(new_folder)


@router.post("/upload", response_model=schemas.FileItemResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: Annotated[UploadFile, FastAPIFile(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
    folder_id: Annotated[int | None, Form()] = None,
):
    # Kiểm tra folder tồn tại
    if folder_id:
        folder_obj = (
            db.query(models.Folder)
            .filter(models.Folder.id == folder_id, models.Folder.owner_id == current_user.id)
            .first()
        )
        if not folder_obj:
            raise HTTPException(status_code=404, detail="Thu muc khong ton tai")
    
    safe_name = Path(file.filename or "uploaded_file").name
    contents = await file.read()
    size_bytes = len(contents)

    if size_bytes == 0:
        raise HTTPException(status_code=400, detail="File rong khong hop le")

    if current_user.used_storage + size_bytes > current_user.max_storage:
        raise HTTPException(status_code=400, detail="Khong du dung luong de tai len file")

    if folder_id is not None:
        get_owned_folder_or_404(db, current_user, folder_id)

    _ensure_unique_file_name(db, current_user, folder_id, safe_name)

    new_file = models.File(
        name=safe_name,
        size=size_bytes,
        content_type=file.content_type or "application/octet-stream",
        blob_url="",
        owner_id=current_user.id,
        folder_id=folder_id,
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


@router.patch("/{file_id}", response_model=schemas.FileItemResponse)
def rename_file(
    file_id: int,
    payload: schemas.FileRenameRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    file_obj = (
        db.query(models.File)
        .filter(models.File.id == file_id, models.File.owner_id == current_user.id, models.File.is_deleted.is_(False))
        .first()
    )
    if not file_obj:
        raise HTTPException(status_code=404, detail="Khong tim thay file")

    new_name = Path(payload.name or "").name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Ten file khong duoc de trong")

    _ensure_unique_file_name(db, current_user, file_obj.folder_id, new_name, exclude_file_id=file_obj.id)

    file_obj.name = new_name
    db.commit()
    db.refresh(file_obj)
    return _to_file_item(file_obj)


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


@router.patch("/{file_id}/rename", response_model=schemas.FileActionResponse)
def rename_file(
    file_id: int,
    request: schemas.RenameRequest,
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

    # Đổi tên file trên hệ thống
    old_path = _find_saved_file_path(current_user.id, file_obj.id)
    if old_path and old_path.exists():
        new_path = old_path.parent / f"{file_obj.id}__{request.new_name}"
        old_path.rename(new_path)

    file_obj.name = request.new_name
    db.commit()
    return {"success": True, "message": "Da doi ten file"}


@router.patch("/folders/{folder_id}/rename", response_model=schemas.FileActionResponse)
def rename_folder(
    folder_id: int,
    request: schemas.RenameRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    folder_obj = (
        db.query(models.Folder)
        .filter(models.Folder.id == folder_id, models.Folder.owner_id == current_user.id)
        .first()
    )
    if not folder_obj:
        raise HTTPException(status_code=404, detail="Khong tim thay thu muc")

    folder_obj.name = request.new_name
    db.commit()
    return {"success": True, "message": "Da doi ten thu muc"}


def _delete_folder_recursive(folder_id: int, owner_id: int, db: Session, current_user: models.User):
    """Xóa folder và toàn bộ files/folders bên trong"""
    # Lấy tất cả files trong folder
    files = db.query(models.File).filter(models.File.folder_id == folder_id).all()
    for file in files:
        # Xóa file từ storage
        saved_path = _find_saved_file_path(owner_id, file.id)
        if saved_path and saved_path.exists():
            saved_path.unlink(missing_ok=True)
        
        # Xóa shared links
        db.query(models.SharedLink).filter(models.SharedLink.file_id == file.id).delete()
        
        # Cập nhật storage
        if file.size:
            current_user.used_storage = max(0, int(current_user.used_storage - file.size))
        
        db.query(models.File).filter(models.File.id == file.id).delete(synchronize_session=False)
    
    # Xóa tất cả subfolders
    subfolders = db.query(models.Folder).filter(models.Folder.folder_id == folder_id).all()
    for subfolder in subfolders:
        _delete_folder_recursive(subfolder.id, owner_id, db, current_user)
    
    # Xóa folder hiện tại. Dùng query.delete để kiểm soát thứ tự xóa với self-FK.
    db.query(models.Folder).filter(models.Folder.id == folder_id).delete(synchronize_session=False)


@router.delete("/folders/{folder_id}", response_model=schemas.FileActionResponse)
def delete_folder(
    folder_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    folder_obj = (
        db.query(models.Folder)
        .filter(models.Folder.id == folder_id, models.Folder.owner_id == current_user.id)
        .first()
    )
    if not folder_obj:
        raise HTTPException(status_code=404, detail="Khong tim thay thu muc")

    _delete_folder_recursive(folder_id, current_user.id, db, current_user)
    db.commit()
    return {"success": True, "message": "Da xoa thu muc va tat ca noi dung ben trong"}


@router.get("/search", response_model=list[schemas.SearchResultResponse])
def search_files(
    q: Annotated[str, Query(min_length=1)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    # Tìm files
    files = (
        db.query(models.File)
        .filter(
            models.File.owner_id == current_user.id,
            models.File.name.ilike(f"%{q}%"),
            models.File.is_deleted.is_(False)
        )
        .all()
    )
    
    # Tìm folders
    folders = (
        db.query(models.Folder)
        .filter(
            models.Folder.owner_id == current_user.id,
            models.Folder.name.ilike(f"%{q}%")
        )
        .all()
    )
    
    results = []
    for file in files:
        results.append(schemas.SearchResultResponse(
            id=file.id,
            name=file.name,
            type="file",
            size=file.size,
            created_at=file.created_at,
            updated_at=file.updated_at,
        ))
    
    for folder in folders:
        results.append(schemas.SearchResultResponse(
            id=folder.id,
            name=folder.name,
            type="folder",
            created_at=folder.created_at,
            updated_at=folder.updated_at,
        ))
    
    return results


@router.get("/{file_id}/preview")
def preview_file(
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    file_obj = (
        db.query(models.File)
        .filter(
            models.File.id == file_id,
            models.File.owner_id == current_user.id,
            models.File.is_deleted.is_(False)
        )
        .first()
    )
    if not file_obj:
        raise HTTPException(status_code=404, detail="Khong tim thay file")

    # Cho phép preview theo MIME hoặc theo phần mở rộng khi client upload thiếu content-type.
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp", "text/plain", "application/pdf"}
    previewable_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".txt", ".pdf"}
    ext = Path(file_obj.name).suffix.lower()
    if file_obj.content_type not in allowed_types and ext not in previewable_exts:
        raise HTTPException(status_code=400, detail="Khong the xem truoc file nay")

    saved_path = _find_saved_file_path(current_user.id, file_obj.id)
    if not saved_path or not saved_path.exists():
        raise HTTPException(status_code=404, detail="Noi dung file khong ton tai")

    return FileResponse(
        path=saved_path,
        media_type=file_obj.content_type,
        filename=file_obj.name,
    )
