import os
import jwt
from datetime import datetime, timedelta
from urllib.parse import urlparse

from passlib.context import CryptContext
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()
try:
    from azure.storage.blob import BlobSasPermissions, generate_blob_sas
except ImportError:
    BlobSasPermissions = None
    generate_blob_sas = None

# 1. CÔNG CỤ BĂM MẬT KHẨU
# Dùng pbkdf2_sha256 để tránh lỗi tương thích passlib+bcrypt trên một số môi trường.
# Giữ bcrypt_sha256 để vẫn verify được hash cũ (nếu có).
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt_sha256"], deprecated="auto")

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
    expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    # Ký và đóng dấu Thẻ bằng chữ ký bí mật
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 3. HÀM XÁC THỰC VÀ GIẢI MÃ JWT
from jose import JWTError, jwt as jose_jwt

def verify_access_token(token: str, credentials_exception):
    try:
        payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        return email
    except JWTError:
        raise credentials_exception


def parse_blob_url(blob_url: str):
    """Parse an Azure Blob URL into account/container/blob components."""
    parsed = urlparse(blob_url)
    netloc_parts = parsed.netloc.split(".")
    if len(netloc_parts) < 1 or not netloc_parts[0]:
        raise ValueError("Blob URL khong hop le")

    path_parts = parsed.path.lstrip("/").split("/", 1)
    if len(path_parts) != 2:
        raise ValueError("Blob URL khong co du thong tin container/blob")

    account_name = netloc_parts[0]
    container_name, blob_name = path_parts
    return account_name, container_name, blob_name


def build_readonly_blob_sas_url(blob_url: str, expires_at: datetime | None = None) -> str:
    """
    Build a short-lived read-only SAS URL for a blob.
    Falls back to original URL when Azure credentials are not configured.
    """
    account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
    if not account_key or not BlobSasPermissions or not generate_blob_sas:
        return blob_url

    account_name, container_name, blob_name = parse_blob_url(blob_url)
    sas_expiry = expires_at or (datetime.now() + timedelta(minutes=30))

    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=container_name,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=sas_expiry,
    )
    return f"{blob_url}?{sas_token}"