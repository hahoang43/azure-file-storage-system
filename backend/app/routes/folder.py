import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pathlib import Path
from app import models, schemas
from app.database import get_db
from app.routes.auth import get_current_user
from app.utils import delete_blob_by_url

router = APIRouter(prefix="/folders", tags=["Thư mục"])

_DEFAULT_STORAGE_ROOT = Path.home() / ".mycloud_storage"
_STORAGE_ROOT = Path(os.getenv("MYCLOUD_STORAGE_DIR", str(_DEFAULT_STORAGE_ROOT))).resolve()
FOLDER_NOT_FOUND_MESSAGE = "Không tìm thấy thư mục"
FOLDER_NOT_FOUND_IN_TRASH_MESSAGE = "Không tìm thấy thư mục trong thùng rác"


def _owner_storage_dir(owner_id: int) -> Path:
    owner_dir = _STORAGE_ROOT / str(owner_id)
    owner_dir.mkdir(parents=True, exist_ok=True)
    return owner_dir


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
            return current_folder_id != folder_id
        current_folder_id = folder_obj.parent_id
    return False


def _calculate_folder_size(db: Session, owner_id: int, folder_id: int, include_deleted: bool = False) -> int:
    """Calculate total size of a folder recursively, with optional deleted-content inclusion."""
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


def _delete_folder_tree_permanently(
    db: Session,
    owner_id: int,
    target_folder_id: int,
    owner_dir: Path,
) -> int:
    reclaimed_storage = 0

    child_ids = (
        db.query(models.Folder.id)
        .filter(models.Folder.owner_id == owner_id, models.Folder.parent_id == target_folder_id)
        .all()
    )
    for (child_id,) in child_ids:
        reclaimed_storage += _delete_folder_tree_permanently(db, owner_id, child_id, owner_dir)

    file_items = (
        db.query(models.File)
        .filter(models.File.owner_id == owner_id, models.File.folder_id == target_folder_id)
        .all()
    )

    for file_obj in file_items:
        for saved_path in owner_dir.glob(f"{file_obj.id}__*"):
            if saved_path.exists():
                saved_path.unlink(missing_ok=True)

        if file_obj.blob_url:
            delete_blob_by_url(file_obj.blob_url)

        db.query(models.SharedLink).filter(models.SharedLink.file_id == file_obj.id).delete()
        reclaimed_storage += int(file_obj.size or 0)
        db.delete(file_obj)

    folder_obj = (
        db.query(models.Folder)
        .filter(models.Folder.id == target_folder_id, models.Folder.owner_id == owner_id)
        .first()
    )
    if folder_obj:
        db.delete(folder_obj)

    return reclaimed_storage


@router.post(
    "/create",
    response_model=schemas.FolderResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"description": "Dữ liệu thư mục không hợp lệ"}},
)
def create_folder(
    req: schemas.FolderCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    folder_name = req.name.strip()
    if not folder_name:
        raise HTTPException(status_code=400, detail="Tên thư mục không được để trống")
    existing = db.query(models.Folder).filter_by(owner_id=current_user.id, name=folder_name, parent_id=req.parent_id, is_deleted=False).first()
    if existing:
        raise HTTPException(status_code=400, detail="Đã có thư mục trùng tên")
    folder = models.Folder(name=folder_name, owner_id=current_user.id, parent_id=req.parent_id)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder

@router.get("/list", response_model=schemas.FolderListResponse)
def list_folders(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
    parent_id: int | None = None,
):
    q = db.query(models.Folder).filter(models.Folder.owner_id == current_user.id, models.Folder.is_deleted.is_(False))
    if parent_id is None:
        q = q.filter(models.Folder.parent_id.is_(None))
    else:
        q = q.filter(models.Folder.parent_id == parent_id)
    items = q.order_by(models.Folder.updated_at.desc()).all()
    
    # Calculate size for each folder
    items_with_size = []
    for folder in items:
        folder_dict = {
            "id": folder.id,
            "name": folder.name,
            "owner_id": folder.owner_id,
            "parent_id": folder.parent_id,
            "size": _calculate_folder_size(db, current_user.id, folder.id),
            "created_at": folder.created_at,
            "updated_at": folder.updated_at,
        }
        items_with_size.append(schemas.FolderResponse(**folder_dict))
    
    return {"items": items_with_size}

@router.get("/contents", response_model=schemas.FolderAndFileListResponse)
def list_folders_and_files(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
    parent_id: int | None = None,
):
    folder_q = db.query(models.Folder).filter(models.Folder.owner_id == current_user.id, models.Folder.is_deleted.is_(False))
    if parent_id is None:
        folder_q = folder_q.filter(models.Folder.parent_id.is_(None))
    else:
        folder_q = folder_q.filter(models.Folder.parent_id == parent_id)
    folders = folder_q.order_by(models.Folder.updated_at.desc()).all()

    file_q = db.query(models.File).filter(models.File.owner_id == current_user.id, models.File.is_deleted.is_(False))
    if parent_id is None:
        file_q = file_q.filter(models.File.folder_id.is_(None))
    else:
        file_q = file_q.filter(models.File.folder_id == parent_id)
    files = file_q.order_by(models.File.updated_at.desc()).all()

    # Calculate size for each folder
    folders_with_size = []
    for folder in folders:
        folder_dict = {
            "id": folder.id,
            "name": folder.name,
            "owner_id": folder.owner_id,
            "parent_id": folder.parent_id,
            "size": _calculate_folder_size(db, current_user.id, folder.id),
            "created_at": folder.created_at,
            "updated_at": folder.updated_at,
        }
        folders_with_size.append(schemas.FolderResponse(**folder_dict))
    
    return {"folders": folders_with_size, "files": files}
@router.put(
    "/rename",
    response_model=schemas.FileActionResponse,
    responses={404: {"description": "Không tìm thấy thư mục"}},
)
def rename_folder(
    req: schemas.RenameRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    folder_obj = db.query(models.Folder).filter(models.Folder.id == req.id, models.Folder.owner_id == current_user.id, models.Folder.is_deleted.is_(False)).first()
    if not folder_obj:
        raise HTTPException(status_code=404, detail=FOLDER_NOT_FOUND_MESSAGE)
    folder_obj.name = req.new_name.strip()
    db.commit()
    return {"success": True, "message": "Đã đổi tên thư mục"}
@router.delete(
    "/{folder_id}",
    response_model=schemas.FileActionResponse,
    responses={404: {"description": "Không tìm thấy thư mục"}, 500: {"description": "Khong the xoa file tren Azure"}},
)
def delete_folder(
    folder_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    folder = db.query(models.Folder).filter(models.Folder.id == folder_id, models.Folder.owner_id == current_user.id, models.Folder.is_deleted.is_(False)).first()
    if not folder:
        raise HTTPException(status_code=404, detail=FOLDER_NOT_FOUND_MESSAGE)

    def move_folder_tree_to_trash(target_folder_id: int):
        child_ids = (
            db.query(models.Folder.id)
            .filter(
                models.Folder.owner_id == current_user.id,
                models.Folder.parent_id == target_folder_id,
                models.Folder.is_deleted.is_(False),
            )
            .all()
        )
        for (child_id,) in child_ids:
            move_folder_tree_to_trash(child_id)

        file_items = (
            db.query(models.File)
            .filter(
                models.File.owner_id == current_user.id,
                models.File.folder_id == target_folder_id,
                models.File.is_deleted.is_(False),
            )
            .all()
        )
        for file_obj in file_items:
            file_obj.is_deleted = True

        folder_obj = (
            db.query(models.Folder)
            .filter(models.Folder.id == target_folder_id, models.Folder.owner_id == current_user.id)
            .first()
        )
        if folder_obj:
            folder_obj.is_deleted = True

    try:
        move_folder_tree_to_trash(folder.id)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"success": True, "message": "Đã chuyển thư mục và toàn bộ nội dung vào thùng rác"}


@router.get("/trash", response_model=schemas.FolderListResponse)
def list_deleted_folders(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    folders = [
        folder for folder in (
            db.query(models.Folder)
            .filter(models.Folder.owner_id == current_user.id, models.Folder.is_deleted.is_(True))
            .order_by(models.Folder.updated_at.desc())
            .all()
        )
        if not _folder_has_deleted_ancestor(db, current_user.id, folder.id)
    ]

    items_with_size = []
    for folder in folders:
        folder_dict = {
            "id": folder.id,
            "name": folder.name,
            "owner_id": folder.owner_id,
            "parent_id": folder.parent_id,
            "size": _calculate_folder_size(db, current_user.id, folder.id, include_deleted=True),
            "created_at": folder.created_at,
            "updated_at": folder.updated_at,
        }
        items_with_size.append(schemas.FolderResponse(**folder_dict))

    return {"items": items_with_size}


@router.post(
    "/{folder_id}/restore",
    response_model=schemas.FileActionResponse,
    responses={404: {"description": "Không tìm thấy thư mục trong thùng rác"}},
)
def restore_folder(
    folder_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    folder = (
        db.query(models.Folder)
        .filter(models.Folder.id == folder_id, models.Folder.owner_id == current_user.id, models.Folder.is_deleted.is_(True))
        .first()
    )
    if not folder:
        raise HTTPException(status_code=404, detail=FOLDER_NOT_FOUND_IN_TRASH_MESSAGE)

    def restore_folder_tree(target_folder_id: int):
        folder_obj = (
            db.query(models.Folder)
            .filter(models.Folder.id == target_folder_id, models.Folder.owner_id == current_user.id)
            .first()
        )
        if not folder_obj:
            return

        folder_obj.is_deleted = False

        file_items = (
            db.query(models.File)
            .filter(
                models.File.owner_id == current_user.id,
                models.File.folder_id == target_folder_id,
                models.File.is_deleted.is_(True),
            )
            .all()
        )
        for file_obj in file_items:
            file_obj.is_deleted = False

        child_ids = (
            db.query(models.Folder.id)
            .filter(models.Folder.owner_id == current_user.id, models.Folder.parent_id == target_folder_id)
            .all()
        )
        for (child_id,) in child_ids:
            restore_folder_tree(child_id)

    restore_folder_tree(folder.id)
    db.commit()
    return {"success": True, "message": "Đã khôi phục thư mục"}


@router.delete(
    "/{folder_id}/permanent",
    response_model=schemas.FileActionResponse,
    responses={404: {"description": "Không tìm thấy thư mục"}, 500: {"description": "Khong the xoa file tren Azure"}},
)
def permanent_delete_folder(
    folder_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    folder = (
        db.query(models.Folder)
        .filter(models.Folder.id == folder_id, models.Folder.owner_id == current_user.id)
        .first()
    )
    if not folder:
        raise HTTPException(status_code=404, detail=FOLDER_NOT_FOUND_MESSAGE)

    owner_dir = _owner_storage_dir(current_user.id)
    try:
        reclaimed_storage = _delete_folder_tree_permanently(db, current_user.id, folder.id, owner_dir)
        current_user.used_storage = max(0, int(current_user.used_storage - reclaimed_storage))
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"success": True, "message": "Đã xóa vĩnh viễn thư mục"}