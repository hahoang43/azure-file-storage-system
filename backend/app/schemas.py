from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime
from typing import Literal, Optional

class UpdateUsernameRequest(BaseModel):
    username: str
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    is_active: bool
    created_at: datetime
    updated_at: datetime
    used_storage: int
    max_storage: int

# ==========================================
# CÁC KHUÔN MỚI DÀNH CHO TÍNH NĂNG ĐĂNG NHẬP
# ==========================================

# 3. Khuôn hứng dữ liệu Đăng nhập
class UserLogin(BaseModel):
    email: str
    password: str

# 4. Khuôn trả về Thẻ thông hành (JWT)
class Token(BaseModel):
    access_token: str
    token_type: str
# 5. Khuôn đổi mật khẩu
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class SharedLinkCreateRequest(BaseModel):
    file_id: Optional[int] = None
    folder_id: Optional[int] = None
    expiration_days: Optional[int] = None
    expiration_value: Optional[int] = None
    expiration_unit: Optional[Literal["minute", "hour", "day", "month", "year"]] = None
    expiration_at: Optional[datetime] = None


class SharedLinkResponse(BaseModel):
    id: int
    file_id: Optional[int] = None
    folder_id: Optional[int] = None
    file_name: str
    file_size: int
    expires_at: Optional[datetime] = None
    created_at: datetime
    is_expired: bool
    public_url: str


class SharedLinkListResponse(BaseModel):
    items: list[SharedLinkResponse]


class PublicDownloadInfoResponse(BaseModel):
    file_name: str
    file_size: int
    content_type: str
    expires_at: Optional[datetime] = None
    preview_url: str
    download_url: str


class FileItemResponse(BaseModel):
    id: int
    name: str
    size: int
    content_type: str
    blob_url: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    type: str = "file"


class FileListResponse(BaseModel):
    items: list[FileItemResponse]


class TrashItemResponse(BaseModel):
    id: int
    name: str
    size: int
    content_type: str
    blob_url: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    type: Literal["file", "folder"]
    parent_id: Optional[int] = None


class TrashListResponse(BaseModel):
    items: list[TrashItemResponse]


class FileActionResponse(BaseModel):
    success: bool
    message: str


class FolderCreateRequest(BaseModel):
    name: str
    parent_id: int | None = None


class FolderResponse(BaseModel):
    id: int
    name: str
    owner_id: int
    parent_id: int | None = None
    size: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FolderListResponse(BaseModel):
    items: list[FolderResponse]

class FolderAndFileListResponse(BaseModel):
    folders: list[FolderResponse]
    files: list[FileItemResponse]
class RenameRequest(BaseModel):
    id: int
    new_name: str
