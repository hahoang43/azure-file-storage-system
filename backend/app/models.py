from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, BigInteger
from sqlalchemy.orm import relationship, synonym
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    used_storage = Column(BigInteger, default=0)
    max_storage = Column(BigInteger, default=536870912)  # 512GB in bytes
    folders = relationship("Folder", back_populates="owner")
    files = relationship("File", back_populates="owner")

class Folder(Base):
    __tablename__ = "folders"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    folder_id = synonym("parent_id")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner = relationship("User", back_populates="folders")
    parent = relationship("Folder", remote_side=[id], back_populates="children")
    children = relationship("Folder", back_populates="parent")
    files = relationship("File", back_populates="folder")

class File(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    size = Column(BigInteger, nullable=False)
    content_type = Column(String(255), nullable=False)
    blob_url = Column(String(255), nullable=False)
    is_deleted = Column(Boolean, default=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner = relationship("User", back_populates="files")
    folder = relationship("Folder", back_populates="files")
    sharedd_links=relationship("SharedLink", back_populates="file")

class SharedLink(Base):
    __tablename__ = "shared_links"
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    link = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    file = relationship("File", back_populates="sharedd_links")
    token= Column(String(255), unique=True, nullable=False)
