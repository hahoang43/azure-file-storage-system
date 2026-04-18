import os
import jwt
from datetime import datetime, timedelta
from urllib.parse import urlparse

from passlib.context import CryptContext
from dotenv import load_dotenv

load_dotenv()
try:
    from azure.storage.blob import BlobSasPermissions, generate_blob_sas
    from azure.storage.blob import BlobServiceClient
    from azure.core.exceptions import ResourceNotFoundError
except ImportError:
    BlobSasPermissions = None
    generate_blob_sas = None
    BlobServiceClient = None
    ResourceNotFoundError = None

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


def _parse_connection_string(connection_string: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for segment in connection_string.split(";"):
        if "=" not in segment:
            continue
        key, value = segment.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def build_readonly_blob_sas_url(blob_url: str, expires_at: datetime | None = None) -> str:
    """
    Build a short-lived read-only SAS URL for a blob.
    Falls back to original URL when Azure credentials are not configured.
    """
    account_name, container_name, blob_name = parse_blob_url(blob_url)
    account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
    if not account_key:
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
        if connection_string:
            conn_parts = _parse_connection_string(connection_string)
            if conn_parts.get("AccountName") == account_name:
                account_key = conn_parts.get("AccountKey")

    if not account_key or not BlobSasPermissions or not generate_blob_sas:
        return blob_url

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


def delete_blob_by_url(blob_url: str) -> bool:
    """
    Delete blob content in Azure Storage by its URL.
    Returns True when a delete request is sent successfully.
    Returns False when blob does not exist.
    Raises ValueError/RuntimeError for configuration or client errors.
    """
    if not blob_url:
        raise ValueError("blob_url is required")

    if not BlobServiceClient:
        raise RuntimeError("Azure Blob SDK is not available")

    _, container_name, blob_name = parse_blob_url(blob_url)
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is not configured")

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

    try:
        blob_client.delete_blob(delete_snapshots="include")
        return True
    except Exception as exc:
        if ResourceNotFoundError and isinstance(exc, ResourceNotFoundError):
            return False
        raise RuntimeError(f"Khong the xoa blob tren Azure: {exc}") from exc