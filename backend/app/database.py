import os
import pymysql
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()

# Cấu hình chuẩn đã test
DB_HOST = "127.0.0.1"
DB_PORT = 3307
DB_USER = "root"
DB_PASSWORD = "Hung123"
DB_NAME = "Mydatabase_cloud"

# Bước tạo Database (Đã bỏ auth_plugin vì Hùng đã chỉnh trong Workbench rồi)
try:
    connection = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD
    )
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    connection.commit()
    cursor.close()
    connection.close()
    print(f"--- DA TAO DATABASE {DB_NAME} THANH CONG ---")
except Exception as e:
    print(f"--- LOI KHI TAO DATABASE: {e} ---")

# Chuỗi kết nối SQLAlchemy (Cũng bỏ auth_plugin luôn cho sạch)
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()