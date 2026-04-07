import mimetypes
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.api.schemas import (
    FileRegisterRequest,
    FolderCreateRequest,
    ItemResponse,
    ListResponse,
    PreviewResponse,
    RenameRequest,
)
from app.core.config import STORAGE_DIR
from app.db.models import ItemType
from app.db.session import get_db
from app.services.file_service import FileService

router = APIRouter(prefix="/api/v1", tags=["file-manager"])


def get_file_service(db: Session = Depends(get_db)) -> FileService:
    return FileService(db)


@router.get("/items", response_model=ListResponse)
def list_items(
    parent_id: int | None = Query(default=None),
    service: FileService = Depends(get_file_service),
):
    items = service.list_items(parent_id=parent_id)
    breadcrumb = service.breadcrumb(parent_id)
    return {
        "current_folder_id": parent_id,
        "breadcrumb": breadcrumb,
        "items": items,
    }


@router.get("/items/search", response_model=list[ItemResponse])
def search_items(
    q: str = Query(min_length=1),
    parent_id: int | None = Query(default=None),
    service: FileService = Depends(get_file_service),
):
    return service.search_items(keyword=q, parent_id=parent_id)


@router.post("/folders", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_folder(payload: FolderCreateRequest, service: FileService = Depends(get_file_service)):
    return service.create_folder(name=payload.name.strip(), parent_id=payload.parent_id)


@router.post("/files/register", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def register_file(payload: FileRegisterRequest, service: FileService = Depends(get_file_service)):
    return service.register_file(
        name=payload.name.strip(),
        parent_id=payload.parent_id,
        storage_path=payload.storage_path,
        mime_type=payload.mime_type,
    )


@router.post("/files/upload", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    uploaded_file: UploadFile = File(...),
    parent_id: int | None = Query(default=None),
    service: FileService = Depends(get_file_service),
):
    if not uploaded_file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    extension = Path(uploaded_file.filename).suffix
    disk_name = f"{uuid4().hex}{extension}"
    destination = (STORAGE_DIR / disk_name).resolve()

    with destination.open("wb") as output:
        while True:
            chunk = await uploaded_file.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)

    mime_type = uploaded_file.content_type or mimetypes.guess_type(uploaded_file.filename)[0]

    return service.register_file(
        name=uploaded_file.filename,
        parent_id=parent_id,
        storage_path=disk_name,
        mime_type=mime_type,
    )


@router.patch("/items/{item_id}/rename", response_model=ItemResponse)
def rename_item(
    item_id: int,
    payload: RenameRequest,
    service: FileService = Depends(get_file_service),
):
    return service.rename_item(item_id=item_id, new_name=payload.new_name.strip())


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, service: FileService = Depends(get_file_service)):
    service.delete_item(item_id=item_id)
    return None


@router.get("/items/{item_id}/breadcrumb")
def breadcrumb(item_id: int, service: FileService = Depends(get_file_service)):
    item = service.get_item(item_id)
    folder_id = item.id if item.item_type == ItemType.FOLDER else item.parent_id
    return {"breadcrumb": service.breadcrumb(folder_id)}


@router.get("/items/{item_id}/preview", response_model=PreviewResponse)
def preview_item(item_id: int, service: FileService = Depends(get_file_service)):
    item = service.get_item(item_id)

    if item.item_type == ItemType.FOLDER:
        raise HTTPException(status_code=400, detail="Folder does not support preview")

    mime = item.mime_type or "application/octet-stream"

    if mime.startswith("image/"):
        preview_type = "image"
    elif mime == "application/pdf":
        preview_type = "pdf"
    elif mime.startswith("text/"):
        preview_type = "text"
    else:
        preview_type = "unsupported"

    response = {
        "item_id": item.id,
        "name": item.name,
        "preview_type": preview_type,
        "stream_url": None,
        "text_content": None,
    }

    if preview_type in {"image", "pdf"}:
        response["stream_url"] = f"/api/v1/items/{item.id}/stream"
    elif preview_type == "text":
        path = _resolve_storage_path(item.storage_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="File not found in storage")
        response["text_content"] = path.read_text(encoding="utf-8", errors="replace")[:4000]

    return response


@router.get("/items/{item_id}/stream")
def stream_item(item_id: int, service: FileService = Depends(get_file_service)):
    item = service.get_item(item_id)

    if item.item_type == ItemType.FOLDER:
        raise HTTPException(status_code=400, detail="Folder does not support stream")

    path = _resolve_storage_path(item.storage_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found in storage")

    mime = item.mime_type or "application/octet-stream"

    if mime.startswith("text/"):
        return PlainTextResponse(path.read_text(encoding="utf-8", errors="replace"))

    return FileResponse(path=path, media_type=mime, filename=item.name)


def _resolve_storage_path(storage_path: str | None) -> Path:
    if not storage_path:
        raise HTTPException(status_code=404, detail="File path is empty")

    full_path = (STORAGE_DIR / storage_path).resolve()
    storage_root = STORAGE_DIR.resolve()

    if not str(full_path).startswith(str(storage_root)):
        raise HTTPException(status_code=400, detail="Invalid storage path")

    return full_path
