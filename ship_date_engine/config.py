"""Configuration for Ship Date Engine."""
import tempfile
from pathlib import Path


class Config:
    """Centralized configuration for Ship Date Engine."""

    # File paths
    RECORDS_PATH = Path(tempfile.gettempdir()) / "ship_date_engine_records.json"
    UPLOADS_DIR = Path(tempfile.gettempdir()) / "ship_date_engine_uploads"
    TEMP_FILES_DIR = Path(tempfile.gettempdir()) / "ship_date_engine_temp"

    # File handling
    MAX_UPLOAD_SIZE_MB = 25
    ALLOWED_EXTENSIONS = {".txt", ".csv", ".xlsx", ".xls", ".pdf"}
    MAX_FILE_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # Processing limits
    MAX_LINE_ITEMS = 1000
    MAX_FIELD_LENGTH = 500
    MAX_INVOICES = 10

    # Date handling
    DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d-%b-%Y"]
    DATE_VALID_MIN_YEAR = 2000
    DATE_VALID_MAX_YEAR = 2100

    # AI/Bedrock configuration
    DEFAULT_ACTIVE_MODELS = [
        "amazon.nova-lite-v1:0",
        "anthropic.claude-3-5-haiku-20241022-v1:0",
        "anthropic.claude-3-haiku-20240307-v1:0",
    ]
    BEDROCK_PROMPT_MAX_WORDS = 120

    @classmethod
    def create_uploads_dir(cls) -> Path:
        """Create uploads directory if it doesn't exist."""
        cls.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        return cls.UPLOADS_DIR
