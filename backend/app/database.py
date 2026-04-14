import os
import pymysql
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
load_dotenv()
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", 3306)
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "123456")
DB_NAME = os.getenv("DB_NAME", "Mydatabase_cloud")

# Kiem tra databse co hay khong, khong thi tao 
try:
    connection = pymysql.connect(
        host=DB_HOST,
        port=int(DB_PORT),
        user=DB_USER,
        password=DB_PASSWORD
    )
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    connection.commit()
    cursor.close()
    connection.close()
    print(f" Da tao database {DB_NAME} thanh cong")
except Exception as e:
    print(f" Loi khi tao database: {e}")

#Ket noi den database
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine= create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_folder_parent_column():
    try:
        inspector = inspect(engine)
        folder_columns = {column["name"] for column in inspector.get_columns("folders")}
        if "parent_id" not in folder_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE folders ADD COLUMN parent_id INTEGER NULL"))
    except Exception as exc:
        print(f" Loi khi kiem tra schema folders: {exc}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
