from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.routes.auth import get_current_user

router = APIRouter(prefix="/folders", tags=["Thu muc"])


def get_owned_folder_or_404(db: Session, current_user: models.User, folder_id: int) -> models.Folder:
    folder = (
        db.query(models.Folder)
        .filter(models.Folder.id == folder_id, models.Folder.owner_id == current_user.id)
        .first()
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Khong tim thay thu muc")
    return folder


def _to_folder_response(db: Session, folder: models.Folder) -> schemas.FolderResponse:
    file_count = (
        db.query(func.count(models.File.id))
        .filter(models.File.folder_id == folder.id)
        .scalar()
    )
    return schemas.FolderResponse(
        id=folder.id,
        name=folder.name,
        owner_id=folder.owner_id,
        parent_id=folder.parent_id,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
        file_count=int(file_count or 0),
    )


@router.get("", response_model=schemas.FolderListResponse)
def list_folders(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
    parent_id: Annotated[int | None, Query(description="Id thu muc cha")] = None,
    all: Annotated[bool, Query(description="Lay toan bo cay thu muc")] = False,
):
    folder_query = db.query(models.Folder).filter(models.Folder.owner_id == current_user.id)
    if not all:
        if parent_id is None:
            folder_query = folder_query.filter(models.Folder.parent_id.is_(None))
        else:
            folder_query = folder_query.filter(models.Folder.parent_id == parent_id)
    folders = folder_query.order_by(models.Folder.updated_at.desc()).all()
    return {"items": [_to_folder_response(db, folder) for folder in folders]}


@router.post("", response_model=schemas.FolderResponse, status_code=status.HTTP_201_CREATED)
def create_folder(
    payload: schemas.FolderCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    folder_name = payload.name.strip()
    if not folder_name:
        raise HTTPException(status_code=400, detail="Ten thu muc khong duoc de trong")

    if payload.parent_id is not None:
        get_owned_folder_or_404(db, current_user, payload.parent_id)

    existing_folder = (
        db.query(models.Folder)
        .filter(
            models.Folder.owner_id == current_user.id,
            func.lower(models.Folder.name) == folder_name.lower(),
            models.Folder.parent_id.is_(payload.parent_id) if payload.parent_id is None else models.Folder.parent_id == payload.parent_id,
        )
        .first()
    )
    if existing_folder:
        raise HTTPException(status_code=400, detail="Thu muc da ton tai")

    new_folder = models.Folder(name=folder_name, owner_id=current_user.id, parent_id=payload.parent_id)
    db.add(new_folder)
    db.commit()
    db.refresh(new_folder)
    return _to_folder_response(db, new_folder)


@router.patch("/{folder_id}", response_model=schemas.FolderResponse)
def rename_folder(
    folder_id: int,
    payload: schemas.FolderRenameRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    folder = get_owned_folder_or_404(db, current_user, folder_id)
    folder_name = payload.name.strip()
    if not folder_name:
        raise HTTPException(status_code=400, detail="Ten thu muc khong duoc de trong")

    duplicate_folder = (
        db.query(models.Folder)
        .filter(
            models.Folder.owner_id == current_user.id,
            models.Folder.id != folder.id,
            func.lower(models.Folder.name) == folder_name.lower(),
        )
        .first()
    )
    if duplicate_folder:
        raise HTTPException(status_code=400, detail="Thu muc da ton tai")

    folder.name = folder_name
    db.commit()
    db.refresh(folder)
    return _to_folder_response(db, folder)


@router.delete("/{folder_id}", response_model=schemas.FolderActionResponse)
def delete_folder(
    folder_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    folder = get_owned_folder_or_404(db, current_user, folder_id)

    def _delete_folder_tree(folder_obj: models.Folder) -> None:
        child_folders = db.query(models.Folder).filter(models.Folder.parent_id == folder_obj.id).all()
        for child_folder in child_folders:
            _delete_folder_tree(child_folder)

        folder_files = db.query(models.File).filter(models.File.folder_id == folder_obj.id).all()
        for file_obj in folder_files:
            try:
                from app.routes.files import _find_saved_file_path

                saved_path = _find_saved_file_path(current_user.id, file_obj.id)
                if saved_path and saved_path.exists():
                    saved_path.unlink(missing_ok=True)
            except Exception:
                pass

            db.query(models.SharedLink).filter(models.SharedLink.file_id == file_obj.id).delete()

            if file_obj.size:
                current_user.used_storage = max(0, int(current_user.used_storage - file_obj.size))

            db.delete(file_obj)

        db.delete(folder_obj)

    _delete_folder_tree(folder)
    db.commit()
    return {"success": True, "message": "Da xoa thu muc"}