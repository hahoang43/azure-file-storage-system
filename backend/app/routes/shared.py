import os
from datetime import datetime, timedelta
from secrets import token_urlsafe
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas, utils
from app.database import get_db
from app.routes.auth import get_current_user

router = APIRouter(
    prefix="/shared-links",
    tags=["Chia se file"],
)


def _build_public_link(token: str) -> str:
    public_base = os.getenv("PUBLIC_DOWNLOAD_BASE_URL", "http://127.0.0.1:5500/frontend/download.html")
    separator = "&" if "?" in public_base else "?"
    return f"{public_base}{separator}token={token}"


def _to_shared_link_response(shared_link: models.SharedLink) -> schemas.SharedLinkResponse:
    now = datetime.now()
    is_expired = bool(shared_link.expires_at and shared_link.expires_at < now)
    return schemas.SharedLinkResponse(
        id=shared_link.id,
        file_id=shared_link.file_id,
        file_name=shared_link.file.name,
        file_size=shared_link.file.size,
        expires_at=shared_link.expires_at,
        created_at=shared_link.created_at,
        is_expired=is_expired,
        public_url=_build_public_link(shared_link.token),
    )


@router.post(
    "",
    response_model=schemas.SharedLinkResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"description": "Du lieu khong hop le"}, 404: {"description": "Khong tim thay file"}},
)
def create_shared_link(
    payload: schemas.SharedLinkCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    file_obj = (
        db.query(models.File)
        .filter(models.File.id == payload.file_id, models.File.owner_id == current_user.id)
        .first()
    )
    if not file_obj:
        raise HTTPException(status_code=404, detail="Khong tim thay file")

    if file_obj.is_deleted:
        raise HTTPException(status_code=400, detail="File da bi xoa vao thung rac")

    if payload.expiration_days is not None and payload.expiration_days <= 0:
        raise HTTPException(status_code=400, detail="expiration_days phai lon hon 0")

    expires_at = None
    if payload.expiration_days:
        expires_at = datetime.now() + timedelta(days=payload.expiration_days)

    token = token_urlsafe(24)
    public_url = _build_public_link(token)

    new_link = models.SharedLink(
        file_id=file_obj.id,
        link=public_url,
        token=token,
        expires_at=expires_at,
    )
    db.add(new_link)
    db.commit()
    db.refresh(new_link)

    return _to_shared_link_response(new_link)


@router.get("", response_model=schemas.SharedLinkListResponse)
def list_my_shared_links(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    links = (
        db.query(models.SharedLink)
        .join(models.File, models.SharedLink.file_id == models.File.id)
        .filter(models.File.owner_id == current_user.id)
        .order_by(models.SharedLink.created_at.desc())
        .all()
    )
    return {"items": [_to_shared_link_response(link) for link in links]}


@router.delete(
    "/{shared_link_id}",
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "Khong tim thay link chia se"}},
)
def revoke_shared_link(
    shared_link_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    shared_link = (
        db.query(models.SharedLink)
        .join(models.File, models.SharedLink.file_id == models.File.id)
        .filter(models.SharedLink.id == shared_link_id, models.File.owner_id == current_user.id)
        .first()
    )
    if not shared_link:
        raise HTTPException(status_code=404, detail="Khong tim thay link chia se")

    db.delete(shared_link)
    db.commit()
    return {"success": True, "message": "Da thu hoi link chia se"}


@router.get(
    "/public/{token}",
    response_model=schemas.PublicDownloadInfoResponse,
    responses={404: {"description": "Link/File khong ton tai"}, 410: {"description": "Link da het han"}},
)
def get_public_download_info(token: str, db: Annotated[Session, Depends(get_db)]):
    shared_link = db.query(models.SharedLink).filter(models.SharedLink.token == token).first()
    if not shared_link:
        raise HTTPException(status_code=404, detail="Link chia se khong ton tai")

    if shared_link.expires_at and shared_link.expires_at < datetime.now():
        raise HTTPException(status_code=410, detail="Link chia se da het han")

    file_obj = db.query(models.File).filter(models.File.id == shared_link.file_id).first()
    if not file_obj or file_obj.is_deleted:
        raise HTTPException(status_code=404, detail="File khong con kha dung")

    # Keep public URL short-lived to reduce exposure risk.
    download_url = utils.build_readonly_blob_sas_url(file_obj.blob_url)

    return schemas.PublicDownloadInfoResponse(
        file_name=file_obj.name,
        file_size=file_obj.size,
        content_type=file_obj.content_type,
        expires_at=shared_link.expires_at,
        download_url=download_url,
    )
