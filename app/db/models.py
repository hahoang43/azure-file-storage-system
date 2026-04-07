from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ItemType(str, Enum):
    FOLDER = "folder"
    FILE = "file"


class FileItem(Base):
    __tablename__ = "file_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    item_type: Mapped[ItemType] = mapped_column(SqlEnum(ItemType), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("file_items.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    parent: Mapped["FileItem | None"] = relationship(
        "FileItem",
        remote_side=[id],
        back_populates="children",
    )
    children: Mapped[list["FileItem"]] = relationship(
        "FileItem",
        back_populates="parent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
