import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. Tải thông tin từ file .env
load_dotenv()

# 2. Lấy URL kết nối Azure từ biến DATABASE_URL
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("❌ Không tìm thấy DATABASE_URL trong file .env")

# 3. Tạo engine kết nối tới Azure
# Thêm pool_pre_ping=True để tự động kết nối lại nếu bị Azure ngắt do treo quá lâu
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 10, "ssl": {}}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 4. Hàm cung cấp Database Session cho các API
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
