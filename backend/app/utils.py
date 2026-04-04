import os
import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext

# 1. CÔNG CỤ BĂM MẬT KHẨU
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

# 2. CÔNG CỤ TẠO THẺ THÔNG HÀNH (JWT)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "mot_chuoi_bi_mat_du_phong_cho_local")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 # Thẻ chỉ có tác dụng trong 60 phút (Bảo mật)

def create_access_token(data: dict):
    to_encode = data.copy()
    # Tính toán thời gian hết hạn của thẻ
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    # Ký và đóng dấu Thẻ bằng chữ ký bí mật
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt