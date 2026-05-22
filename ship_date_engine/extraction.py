from __future__ import annotations

import logging
import re
from datetime import date, datetime
from pathlib import Path

from .models import InvoiceData

LOGGER = logging.getLogger(__name__)

_KEY_ALIASES = {
    "invoice number": "invoice_number",
    "invoice no": "invoice_number",
    "invoice #": "invoice_number",
    "invoice date": "invoice_date",
    "po number": "po_number",
    "po #": "po_number",
    "purchase order": "po_number",
    "earliest ship date": "earliest_ship_date",
    "latest ship date": "latest_ship_date",
    "ship by": "ship_by_date",
    "ship by date": "ship_by_date",
    "ship terms": "ship_terms",
    "shipping terms": "ship_terms",
    "carrier": "carrier",
    "priority": "priority",
}

_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d-%b-%Y"]


def _parse_date(value: str) -> date | None:
    text = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _normalize_key(key: str) -> str:
    return re.sub(r"\s+", " ", key.strip().lower().replace("_", " "))


def _read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".csv", ".json"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError as exc:
            raise ValueError("PDF support requires 'pypdf' package") from exc

        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
        try:
            import pytesseract  # type: ignore
            from PIL import Image  # type: ignore
        except ImportError as exc:
            raise ValueError("Image OCR support requires 'pytesseract' and 'Pillow'") from exc
        return pytesseract.image_to_string(Image.open(path))

    return path.read_text(encoding="utf-8", errors="ignore")


def extract_invoice_data(file_path: str) -> InvoiceData:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Invoice file not found: {file_path}")

    text = _read_text(path)
    invoice = InvoiceData(source_path=str(path))

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("-"):
            invoice.line_items.append(line.lstrip("- "))
            continue

        match = re.match(r"^([A-Za-z0-9 #/_-]+)\s*[:=]\s*(.+)$", line)
        if not match:
            continue

        key, value = match.group(1), match.group(2).strip()
        normalized = _normalize_key(key)
        field_name = _KEY_ALIASES.get(normalized)
        invoice.raw_fields[normalized] = value

        if not field_name:
            continue

        if field_name in {"invoice_date", "earliest_ship_date", "latest_ship_date", "ship_by_date"}:
            parsed = _parse_date(value)
            if parsed:
                setattr(invoice, field_name, parsed)
            else:
                LOGGER.warning("Unrecognized date format for %s in %s: %s", field_name, file_path, value)
        elif field_name == "priority":
            try:
                invoice.priority = int(value)
            except ValueError:
                LOGGER.warning("Invalid priority value in %s: %s", file_path, value)
        else:
            setattr(invoice, field_name, value)

    return invoice
