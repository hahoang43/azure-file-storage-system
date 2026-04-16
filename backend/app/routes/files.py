import os
from pathlib import Path
from threading import Lock
from typing import Annotated, List

from fastapi import APIRouter, Depends, File as FastAPIFile, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.routes.auth import get_current_user

router = APIRouter(prefix="/files", tags=["Quan ly file"])

_DEFAULT_STORAGE_ROOT = Path.home() / ".mycloud_storage"
_STORAGE_ROOT = Path(os.getenv("MYCLOUD_STORAGE_DIR", str(_DEFAULT_STORAGE_ROOT))).resolve()
FILE_NOT_FOUND_MESSAGE = "Khong tim thay file"
FILE_NOT_FOUND_IN_TRASH_MESSAGE = "Khong tim thay file trong thung rac"
FOLDER_NOT_FOUND_MESSAGE = "Khong tim thay thu muc"
FILE_CONTENT_NOT_FOUND_MESSAGE = "Noi dung file khong ton tai"
_FOLDER_CREATE_LOCK = Lock()


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


def _to_trash_folder_item(folder_obj: models.Folder, folder_size: int) -> schemas.TrashItemResponse:
    return schemas.TrashItemResponse(
        id=folder_obj.id,
        name=folder_obj.name,
        size=folder_size,
        content_type="folder",
        blob_url="",
        is_deleted=True,
        created_at=folder_obj.created_at,
        updated_at=folder_obj.updated_at,
        type="folder",
        parent_id=folder_obj.parent_id,
    )


def _to_trash_file_item(file_obj: models.File) -> schemas.TrashItemResponse:
    return schemas.TrashItemResponse(
        id=file_obj.id,
        name=file_obj.name,
        size=file_obj.size,
        content_type=file_obj.content_type,
        blob_url=file_obj.blob_url,
        is_deleted=file_obj.is_deleted,
        created_at=file_obj.created_at,
        updated_at=file_obj.updated_at,
        type="file",
        parent_id=file_obj.folder_id,
    )


def _folder_has_deleted_ancestor(db: Session, owner_id: int, folder_id: int | None) -> bool:
    current_folder_id = folder_id
    while current_folder_id is not None:
        folder_obj = (
            db.query(models.Folder)
            .filter(models.Folder.id == current_folder_id, models.Folder.owner_id == owner_id)
            .first()
        )
        if not folder_obj:
            return False
        if folder_obj.is_deleted:
            return True
        current_folder_id = folder_obj.parent_id
    return False


def _calculate_folder_size(db: Session, owner_id: int, folder_id: int, include_deleted: bool = False) -> int:
    file_query = db.query(models.File.size).filter(
        models.File.owner_id == owner_id,
        models.File.folder_id == folder_id,
    )
    if include_deleted:
        file_query = file_query.filter(models.File.is_deleted.is_(True))
    else:
        file_query = file_query.filter(models.File.is_deleted.is_(False))

    files_size = file_query.all()
    total_size = sum(f[0] for f in files_size if f and f[0])

    folder_query = db.query(models.Folder.id).filter(
        models.Folder.owner_id == owner_id,
        models.Folder.parent_id == folder_id,
    )
    if include_deleted:
        folder_query = folder_query.filter(models.Folder.is_deleted.is_(True))
    else:
        folder_query = folder_query.filter(models.Folder.is_deleted.is_(False))

    subfolders = folder_query.all()
    for subfolder in subfolders:
        total_size += _calculate_folder_size(db, owner_id, subfolder[0], include_deleted=include_deleted)

    return total_size


def _find_folder_by_name(
    db: Session,
    owner_id: int,
    parent_id: int | None,
    folder_name: str,
) -> models.Folder | None:
    return (
        db.query(models.Folder)
        .filter(
            models.Folder.owner_id == owner_id,
            models.Folder.parent_id == parent_id,
            models.Folder.name == folder_name,
            models.Folder.is_deleted.is_(False),
        )
        .order_by(models.Folder.id.asc())
        .first()
    )


def _coalesce_duplicate_folders(
    db: Session,
    owner_id: int,
    parent_id: int | None,
    folder_name: str,
) -> models.Folder | None:
    matches = (
        db.query(models.Folder)
        .filter(
            models.Folder.owner_id == owner_id,
            models.Folder.parent_id == parent_id,
            models.Folder.name == folder_name,
            models.Folder.is_deleted.is_(False),
        )
        .order_by(models.Folder.id.asc())
        .all()
    )

    if not matches:
        return None

    primary = matches[0]
    for dup in matches[1:]:
        db.query(models.File).filter(models.File.folder_id == dup.id).update({models.File.folder_id: primary.id})
        db.query(models.Folder).filter(models.Folder.parent_id == dup.id).update({models.Folder.parent_id: primary.id})
        dup.is_deleted = True

    return primary


def _get_or_create_folder(
    db: Session,
    owner_id: int,
    parent_id: int | None,
    folder_name: str,
) -> models.Folder:
    # Folder uploads can fire many concurrent requests with the same relative path.
    # Serialize get-or-create to avoid duplicate folders under the same parent.
    with _FOLDER_CREATE_LOCK:
        existing = _coalesce_duplicate_folders(db, owner_id, parent_id, folder_name)
        if existing:
            return existing

        new_folder = models.Folder(name=folder_name, owner_id=owner_id, parent_id=parent_id)
        db.add(new_folder)
        db.flush()
        return new_folder


def _resolve_target_folder_id(
    db: Session,
    owner_id: int,
    base_folder_id: int | None,
    relative_path: str | None,
) -> int | None:
    if not relative_path:
        return base_folder_id

    normalized = relative_path.replace("\\", "/").strip("/")
    if not normalized:
        return base_folder_id

    parts = [part for part in normalized.split("/") if part]
    # Last segment is file name; remaining are folder levels.
    folder_parts = parts[:-1]
    if not folder_parts:
        return base_folder_id

    parent_id = base_folder_id
    for folder_name in folder_parts:
        folder = _get_or_create_folder(db, owner_id, parent_id, folder_name)
        parent_id = folder.id

    return parent_id


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
    visible_items = [item for item in items if not _folder_has_deleted_ancestor(db, current_user.id, item.folder_id)]
    return {"items": [_to_file_item(item) for item in visible_items]}


@router.get("/trash", response_model=schemas.TrashListResponse)
def list_trash(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    file_items = (
        db.query(models.File)
        .filter(models.File.owner_id == current_user.id, models.File.is_deleted.is_(True))
        .order_by(models.File.updated_at.desc())
        .all()
    )

    folder_items = [
        folder
        for folder in (
            db.query(models.Folder)
            .filter(models.Folder.owner_id == current_user.id, models.Folder.is_deleted.is_(True))
            .order_by(models.Folder.updated_at.desc())
            .all()
        )
        if folder.parent_id is None or not _folder_has_deleted_ancestor(db, current_user.id, folder.parent_id)
    ]

    items: list[schemas.TrashItemResponse] = [
        *[_to_trash_file_item(item) for item in file_items],
        *[
            _to_trash_folder_item(
                item,
                _calculate_folder_size(db, current_user.id, item.id, include_deleted=True),
            )
            for item in folder_items
        ],
    ]
    items.sort(key=lambda item: item.updated_at, reverse=True)
    return {"items": items}


@router.post(
    "/upload",
    response_model=schemas.FileItemResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"description": "Du lieu khong hop le"}, 404: {"description": "Khong tim thay thu muc"}, 500: {"description": "Tai file len that bai"}},
)
async def upload_file(
    file: Annotated[UploadFile, FastAPIFile(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
    folder_id: Annotated[int | None, Form()] = None,
    relative_path: Annotated[str | None, Form()] = None,
):
    safe_name = Path(file.filename or "uploaded_file").name
    contents = await file.read()
    size_bytes = len(contents)

    if size_bytes == 0:
        raise HTTPException(status_code=400, detail="File rong khong hop le")

    if folder_id is not None:
        folder_obj = (
            db.query(models.Folder)
            .filter(models.Folder.id == folder_id, models.Folder.owner_id == current_user.id, models.Folder.is_deleted.is_(False))
            .first()
        )
        if not folder_obj:
            raise HTTPException(status_code=404, detail=FOLDER_NOT_FOUND_MESSAGE)

    target_folder_id = _resolve_target_folder_id(
        db=db,
        owner_id=current_user.id,
        base_folder_id=folder_id,
        relative_path=relative_path,
    )

    existing_file = (
        db.query(models.File)
        .filter(
            models.File.owner_id == current_user.id,
            models.File.folder_id == target_folder_id,
            models.File.name == safe_name,
            models.File.is_deleted.is_(False),
        )
        .first()
    )

    old_size = int(existing_file.size) if existing_file else 0
    storage_delta = size_bytes - old_size
    if current_user.used_storage + storage_delta > current_user.max_storage:
        raise HTTPException(status_code=400, detail="Khong du dung luong de tai len file")

    if existing_file:
        file_obj = existing_file
    else:
        file_obj = models.File(
            name=safe_name,
            size=size_bytes,
            content_type=file.content_type or "application/octet-stream",
            blob_url="",
            owner_id=current_user.id,
            folder_id=target_folder_id,
            is_deleted=False,
        )
        db.add(file_obj)
        db.flush()

    old_saved_path = _find_saved_file_path(current_user.id, file_obj.id)
    saved_path = _owner_storage_dir(current_user.id) / f"{file_obj.id}__{safe_name}"
    try:
        saved_path.write_bytes(contents)
        if old_saved_path and old_saved_path != saved_path and old_saved_path.exists():
            old_saved_path.unlink(missing_ok=True)

        public_base = os.getenv("PUBLIC_API_BASE_URL", "http://127.0.0.1:8000")
        file_obj.name = safe_name
        file_obj.size = size_bytes
        file_obj.content_type = file.content_type or "application/octet-stream"
        file_obj.folder_id = target_folder_id
        file_obj.blob_url = f"{public_base}/files/public-content/{file_obj.id}"
        current_user.used_storage = int(current_user.used_storage + storage_delta)
        db.commit()
        db.refresh(file_obj)
        return _to_file_item(file_obj)
    except Exception as exc:
        db.rollback()
        if saved_path.exists():
            saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Khong the tai file len: {exc}")


@router.delete(
    "/{file_id}",
    response_model=schemas.FileActionResponse,
    responses={404: {"description": "Khong tim thay file"}},
)
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
        raise HTTPException(status_code=404, detail=FILE_NOT_FOUND_MESSAGE)

    if not file_obj.is_deleted:
        file_obj.is_deleted = True
        db.commit()

    return {"success": True, "message": "Da chuyen file vao thung rac"}


@router.post(
    "/{file_id}/restore",
    response_model=schemas.FileActionResponse,
    responses={404: {"description": "Khong tim thay file trong thung rac"}},
)
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
        raise HTTPException(status_code=404, detail=FILE_NOT_FOUND_IN_TRASH_MESSAGE)

    file_obj.is_deleted = False
    db.commit()
    return {"success": True, "message": "Da khoi phuc file"}


@router.delete(
    "/{file_id}/permanent",
    response_model=schemas.FileActionResponse,
    responses={404: {"description": "Khong tim thay file"}},
)
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
        raise HTTPException(status_code=404, detail=FILE_NOT_FOUND_MESSAGE)

    saved_path = _find_saved_file_path(current_user.id, file_obj.id)
    if saved_path and saved_path.exists():
        saved_path.unlink(missing_ok=True)

    db.query(models.SharedLink).filter(models.SharedLink.file_id == file_obj.id).delete()

    if file_obj.size:
        current_user.used_storage = max(0, int(current_user.used_storage - file_obj.size))

    db.delete(file_obj)
    db.commit()
    return {"success": True, "message": "Da xoa vinh vien file"}


@router.get(
    "/public-content/{file_id}",
    responses={404: {"description": "Khong tim thay file hoac noi dung"}},
)
def public_content(
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
    download: Annotated[bool, Query(description="True: tai xuong, False: xem truc tiep")] = False,
):
    file_obj = db.query(models.File).filter(models.File.id == file_id, models.File.is_deleted.is_(False)).first()
    if not file_obj:
        raise HTTPException(status_code=404, detail=FILE_NOT_FOUND_MESSAGE)

    if _folder_has_deleted_ancestor(db, file_obj.owner_id, file_obj.folder_id):
        raise HTTPException(status_code=404, detail=FILE_NOT_FOUND_MESSAGE)

    saved_path = _find_saved_file_path(file_obj.owner_id, file_obj.id)
    if not saved_path or not saved_path.exists():
        raise HTTPException(status_code=404, detail=FILE_CONTENT_NOT_FOUND_MESSAGE)

    disposition_type = "attachment" if download else "inline"
    return FileResponse(
        path=saved_path,
        media_type=file_obj.content_type,
        filename=file_obj.name,
        content_disposition_type=disposition_type,
    )
@router.put(
    "/rename",
    response_model=schemas.FileActionResponse,
    responses={404: {"description": "Khong tim thay file"}},
)
def rename_file(
    req: schemas.RenameRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    file_obj = db.query(models.File).filter(models.File.id == req.id, models.File.owner_id == current_user.id).first()
    if not file_obj:
        raise HTTPException(status_code=404, detail=FILE_NOT_FOUND_MESSAGE)
    file_obj.name = req.new_name.strip()
    db.commit()
    return {"success": True, "message": "Đã đổi tên file"}
