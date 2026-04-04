from pydantic import BaseModel
from datetime import datetime

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