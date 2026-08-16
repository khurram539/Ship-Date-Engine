"""Security helpers for Ship Date Engine."""

import re
from pathlib import Path
from typing import Tuple

from .config import Config


class ValidationError(Exception):
    """Custom exception for validation errors."""

    def __init__(self, message: str, field: str = ""):
        self.message = message
        self.field = field
        super().__init__(self.message)


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal attempts."""
    safe_name = Path(filename).name
    if (
        ".." in safe_name
        or "/" in safe_name
        or "\\" in safe_name
        or not safe_name.strip()
    ):
        raise ValidationError("Invalid filename", field="filename")
    return safe_name


def validate_file_content(
    content: str,
    max_length: int = Config.MAX_FIELD_LENGTH,
) -> Tuple[bool, list[str]]:
    """Validate that file content doesn't contain dangerous patterns."""
    warnings = []

    if len(content) > max_length:
        warnings.append(
            f"Content exceeds maximum length of {max_length} characters"
        )

    dangerous_patterns = [
        r"(?i)\b(drop\s+table|delete\s+from|insert\s+into|update\s+)\b",
        r"(?i)\b(select|exec|execute|xp_cmdshell)\b",
        r"(?i)0x[0-9a-f]+",
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, content):
            warnings.append("Potentially dangerous SQL patterns detected")
            break

    return len(warnings) == 0, warnings
