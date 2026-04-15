from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Annotated
from app import models, schemas
from app.database import get_db
from app.routes.auth import get_current_user

router = APIRouter(prefix="/folders", tags=["Thư mục"])


@router.post("/create", response_model=schemas.FolderResponse, status_code=status.HTTP_201_CREATED)
def create_folder(
    req: schemas.FolderCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    folder_name = req.name.strip()
    if not folder_name:
        raise HTTPException(status_code=400, detail="Tên thư mục không được để trống")
    existing = db.query(models.Folder).filter_by(owner_id=current_user.id, name=folder_name, parent_id=req.parent_id).first()
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
    q = db.query(models.Folder).filter(models.Folder.owner_id == current_user.id)
    if parent_id is None:
        q = q.filter(models.Folder.parent_id.is_(None))
    else:
        q = q.filter(models.Folder.parent_id == parent_id)
    items = q.order_by(models.Folder.updated_at.desc()).all()
    return {"items": items}

@router.get("/contents", response_model=schemas.FolderAndFileListResponse)
def list_folders_and_files(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
    parent_id: int | None = None,
):
    folder_q = db.query(models.Folder).filter(models.Folder.owner_id == current_user.id)
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

    return {"folders": folders, "files": files}
@router.put("/rename", response_model=schemas.FileActionResponse)
def rename_folder(
    req: schemas.RenameRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    folder_obj = db.query(models.Folder).filter(models.Folder.id == req.id, models.Folder.owner_id == current_user.id).first()
    if not folder_obj:
        raise HTTPException(status_code=404, detail="Không tìm thấy thư mục")
    folder_obj.name = req.new_name.strip()
    db.commit()
    return {"success": True, "message": "Đã đổi tên thư mục"}
@router.delete("/{folder_id}", response_model=schemas.FileActionResponse)
def delete_folder(
    folder_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    # Tìm thư mục
    folder = db.query(models.Folder).filter(models.Folder.id == folder_id, models.Folder.owner_id == current_user.id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Không tìm thấy thư mục")

    # Đệ quy xóa mềm file trong thư mục con
    def soft_delete_files_in_folder(f):
        # Xóa file trong thư mục này
        files = db.query(models.File).filter(models.File.folder_id == f.id, models.File.owner_id == current_user.id, models.File.is_deleted.is_(False)).all()
        for file in files:
            file.is_deleted = True
        # Xử lý thư mục con (nếu có)
        for child in (getattr(f, 'children', []) or []):
            soft_delete_files_in_folder(child)

    soft_delete_files_in_folder(folder)

    # Xóa thư mục (cứng)
    def delete_folder_and_children(f):
        for child in (getattr(f, 'children', []) or []):
            delete_folder_and_children(child)
        db.delete(f)

    delete_folder_and_children(folder)
    db.commit()
    return {"success": True, "message": "Đã xóa thư mục và toàn bộ file bên trong"}