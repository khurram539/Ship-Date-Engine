"""Configuration for Ship Date Engine API."""
import tempfile
from pathlib import Path


class Config:
    """Centralized configuration."""

    # File paths
    RECORDS_PATH = Path(tempfile.gettempdir()) / "ship_date_engine_records.json"
    UPLOADS_DIR = Path(tempfile.gettempdir()) / "ship_date_engine_uploads"

    # File handling
    MAX_UPLOAD_SIZE_MB = 25
    ALLOWED_EXTENSIONS = {".txt", ".csv", ".xlsx", ".xls", ".pdf"}

    @classmethod
    def create_uploads_dir(cls):
        """Create uploads directory if it doesn't exist."""
        cls.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        return cls.UPLOADS_DIR


Config.create_uploads_dir()
