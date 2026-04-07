from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
STORAGE_DIR = DATA_DIR / "storage"
DATABASE_PATH = DATA_DIR / "files.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"
