from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import ItemType


class ItemResponse(BaseModel):
    id: int
    name: str
    item_type: ItemType
    parent_id: int | None
    mime_type: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FolderCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: int | None = None


class RenameRequest(BaseModel):
    new_name: str = Field(min_length=1, max_length=255)


class FileRegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: int | None = None
    mime_type: str | None = None
    storage_path: str = Field(min_length=1, max_length=500)


class BreadcrumbNode(BaseModel):
    id: int | None
    name: str


class ListResponse(BaseModel):
    current_folder_id: int | None
    breadcrumb: list[BreadcrumbNode]
    items: list[ItemResponse]


class PreviewResponse(BaseModel):
    item_id: int
    name: str
    preview_type: str
    stream_url: str | None = None
    text_content: str | None = None
