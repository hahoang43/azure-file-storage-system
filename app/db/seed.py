from app.db.models import FileItem, ItemType


def seed_initial_data(db):
    exists = db.query(FileItem).first()
    if exists:
        return

    docs = FileItem(name="Documents", item_type=ItemType.FOLDER, parent_id=None)
    images = FileItem(name="Images", item_type=ItemType.FOLDER, parent_id=None)
    db.add_all([docs, images])
    db.flush()

    python_folder = FileItem(name="Python", item_type=ItemType.FOLDER, parent_id=docs.id)
    note = FileItem(
        name="welcome.txt",
        item_type=ItemType.FILE,
        parent_id=docs.id,
        mime_type="text/plain",
        storage_path="welcome.txt",
    )

    db.add_all([python_folder, note])
    db.commit()
