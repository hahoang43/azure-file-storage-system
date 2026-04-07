from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.config import STORAGE_DIR
from app.db.models import FileItem, ItemType


class FileService:
    def __init__(self, db: Session):
        self.db = db

    def _item_query(self, parent_id: int | None) -> Select[tuple[FileItem]]:
        return (
            select(FileItem)
            .where(FileItem.parent_id == parent_id)
            .order_by(FileItem.item_type.desc(), FileItem.name.asc())
        )

    def list_items(self, parent_id: int | None) -> list[FileItem]:
        if parent_id is not None:
            parent = self.get_item(parent_id)
            if parent.item_type != ItemType.FOLDER:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="parent_id must be a folder",
                )
        return list(self.db.scalars(self._item_query(parent_id)).all())

    def search_items(self, keyword: str, parent_id: int | None = None) -> list[FileItem]:
        query = select(FileItem).where(FileItem.name.ilike(f"%{keyword}%"))
        if parent_id is not None:
            query = query.where(FileItem.parent_id == parent_id)
        return list(self.db.scalars(query.order_by(FileItem.name.asc())).all())

    def get_item(self, item_id: int) -> FileItem:
        item = self.db.get(FileItem, item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        return item

    def create_folder(self, name: str, parent_id: int | None) -> FileItem:
        self._validate_sibling_name(name=name, parent_id=parent_id)

        if parent_id is not None:
            parent = self.get_item(parent_id)
            if parent.item_type != ItemType.FOLDER:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="parent_id must be a folder",
                )

        folder = FileItem(name=name, item_type=ItemType.FOLDER, parent_id=parent_id)
        self.db.add(folder)
        self.db.commit()
        self.db.refresh(folder)
        return folder

    def register_file(
        self,
        name: str,
        parent_id: int | None,
        storage_path: str,
        mime_type: str | None,
    ) -> FileItem:
        self._validate_sibling_name(name=name, parent_id=parent_id)
        if parent_id is not None:
            parent = self.get_item(parent_id)
            if parent.item_type != ItemType.FOLDER:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="parent_id must be a folder",
                )

        file_item = FileItem(
            name=name,
            item_type=ItemType.FILE,
            parent_id=parent_id,
            mime_type=mime_type,
            storage_path=storage_path,
        )
        self.db.add(file_item)
        self.db.commit()
        self.db.refresh(file_item)
        return file_item

    def rename_item(self, item_id: int, new_name: str) -> FileItem:
        item = self.get_item(item_id)
        self._validate_sibling_name(name=new_name, parent_id=item.parent_id, excluded_id=item.id)

        item.name = new_name
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_item(self, item_id: int) -> None:
        item = self.get_item(item_id)
        file_paths = self._collect_file_paths(item)

        self.db.delete(item)
        self.db.commit()

        for path in file_paths:
            if path.exists() and path.is_file():
                path.unlink()

    def breadcrumb(self, folder_id: int | None) -> list[dict]:
        nodes = [{"id": None, "name": "Home"}]
        if folder_id is None:
            return nodes

        current = self.get_item(folder_id)
        if current.item_type != ItemType.FOLDER:
            current = current.parent

        stack: list[FileItem] = []
        while current is not None:
            stack.append(current)
            current = current.parent

        for node in reversed(stack):
            nodes.append({"id": node.id, "name": node.name})
        return nodes

    def _collect_file_paths(self, item: FileItem) -> list[Path]:
        paths: list[Path] = []

        def dfs(node: FileItem):
            if node.item_type == ItemType.FILE and node.storage_path:
                paths.append((STORAGE_DIR / node.storage_path).resolve())
            for child in node.children:
                dfs(child)

        dfs(item)
        return paths

    def _validate_sibling_name(self, name: str, parent_id: int | None, excluded_id: int | None = None):
        query = select(FileItem).where(
            FileItem.parent_id == parent_id,
            FileItem.name == name,
        )
        if excluded_id is not None:
            query = query.where(FileItem.id != excluded_id)

        if self.db.scalar(query) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An item with the same name already exists in this folder",
            )
