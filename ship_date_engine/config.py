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
    MAX_FILE_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    
    # Security/Validation fields (required by security.py)
    MAX_FIELD_LENGTH = 500          # Maximum length for any single field
    MAX_LINE_ITEMS = 1000           # Maximum number of line items
    MAX_INVOICES = 10              # Maximum invoices per batch
    
    @classmethod
    def create_uploads_dir(cls):
        """Create uploads directory if it doesn't exist."""
        cls.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        return cls.UPLOADS_DIR


# Initialize on import
Config.create_uploads_dir()
