from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, ConfigDict


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

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# CÁC KHUÔN MỚI DÀNH CHO TÍNH NĂNG ĐĂNG NHẬP
# ==========================================

# 3. Khuôn hứng dữ liệu Đăng nhập
class UserLogin(BaseModel):
    username: str
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
    file_id: int
    expiration_days: Optional[int] = None
    expiration_value: Optional[int] = None
    expiration_unit: Optional[Literal["minute", "hour", "day", "month", "year"]] = None
    expiration_at: Optional[datetime] = None


class SharedLinkResponse(BaseModel):
    id: int
    file_id: int
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


class FolderItemResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    type: str = "folder"


class ItemListResponse(BaseModel):
    items: list[FileItemResponse | FolderItemResponse]


class FileListResponse(BaseModel):
    items: list[FileItemResponse]


class FileActionResponse(BaseModel):
    success: bool
    message: str


class FolderCreateRequest(BaseModel):
    name: str
    folder_id: Optional[int] = None


class RenameRequest(BaseModel):
    new_name: str


class SearchResultResponse(BaseModel):
    id: int
    name: str
    type: str
    size: Optional[int] = None
    created_at: datetime
    updated_at: datetime