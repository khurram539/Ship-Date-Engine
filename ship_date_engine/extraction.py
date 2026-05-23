from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from .models import InvoiceData

LOGGER = logging.getLogger(__name__)

_KEY_ALIASES = {
    "shipping id": "shipping_id",
    "shipment id": "shipping_id",
    "ship id": "shipping_id",
    "order number": "shipping_id",
    "order #": "shipping_id",
    "order id": "shipping_id",
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


def _normalize_lookup_id(value: str) -> str:
    text = value.strip().lower()
    if not text:
        return ""

    compact = re.sub(r"\s+", "", text)
    compact = compact.replace(",", "")

    if re.fullmatch(r"\d+\.0+", compact):
        compact = compact.split(".", 1)[0]

    if re.fullmatch(r"\d+", compact):
        compact = str(int(compact))

    return compact


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


def _parse_date_flexible(value: str) -> date | None:
    parsed = _parse_date(value)
    if parsed:
        if parsed.year < 2000 or parsed.year > 2100:
            return None
        return parsed
    text = value.strip()
    if re.fullmatch(r"\d+(\.\d+)?", text):
        try:
            serial = int(float(text))
            # Guard against treating large numeric IDs (e.g. order numbers) as dates.
            # Excel serial dates for modern business ranges are typically below this bound.
            if 30000 <= serial <= 90000:
                converted = date(1899, 12, 30) + timedelta(days=serial)
                if converted.year < 2000 or converted.year > 2100:
                    return None
                return converted
        except (ValueError, OverflowError):
            return None
    return None


def _normalize_key(key: str) -> str:
    return re.sub(r"\s+", " ", key.strip().lower().replace("_", " "))


def _header_key(header: str, col_idx: int) -> str:
    cleaned = _normalize_key(header)
    return cleaned if cleaned else f"column_{col_idx + 1}"


def _excel_col_to_index(cell_ref: str) -> int | None:
    letters = ""
    for ch in cell_ref:
        if ch.isalpha():
            letters += ch.upper()
        else:
            break

    if not letters:
        return None

    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - ord("A") + 1)
    return index - 1


def _format_detail_value(key: str, value: str) -> str:
    text = value.strip()
    if not text:
        return text

    # Convert numeric/date-like values for date columns (e.g. Excel serials).
    if "date" in key:
        parsed = _parse_date_flexible(text)
        if parsed:
            return parsed.strftime("%m-%d-%Y")
    return text


def _read_xml_text(path: Path) -> str:
    root = ET.fromstring(path.read_text(encoding="utf-8", errors="ignore"))
    lines: list[str] = []

    for element in root.iter():
        if list(element):
            continue
        text = (element.text or "").strip()
        if not text:
            continue
        key = _normalize_key(element.tag.split("}")[-1])
        lines.append(f"{key}: {text}")

    return "\n".join(lines)


def _read_xlsx_text(path: Path) -> str:
    lines: list[str] = []
    shared_strings: list[str] = []

    with zipfile.ZipFile(path) as workbook:
        if "xl/sharedStrings.xml" in workbook.namelist():
            shared_xml = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            for node in shared_xml.iter():
                if node.tag.endswith("}t") and node.text is not None:
                    shared_strings.append(node.text)

        sheet_files = sorted(name for name in workbook.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"))

        for sheet_name in sheet_files:
            sheet_xml = ET.fromstring(workbook.read(sheet_name))
            for row in sheet_xml.iter():
                if not row.tag.endswith("}row"):
                    continue

                row_map: dict[int, str] = {}
                append_idx = 0
                for cell in list(row):
                    if not cell.tag.endswith("}c"):
                        continue

                    col_idx = _excel_col_to_index(cell.attrib.get("r", ""))
                    if col_idx is None:
                        col_idx = append_idx
                    append_idx = max(append_idx, col_idx + 1)

                    cell_type = cell.attrib.get("t")
                    value_node = None
                    for child in list(cell):
                        if child.tag.endswith("}v"):
                            value_node = child
                            break
                        if child.tag.endswith("}is"):
                            text_node = next((n for n in child.iter() if n.tag.endswith("}t") and n.text is not None), None)
                            if text_node is not None:
                                row_map[col_idx] = text_node.text.strip()
                            value_node = None
                            break

                    if value_node is None or value_node.text is None:
                        continue

                    raw_value = value_node.text.strip()
                    if cell_type == "s":
                        try:
                            raw_value = shared_strings[int(raw_value)]
                        except (IndexError, ValueError):
                            pass
                    row_map[col_idx] = raw_value

                if not row_map:
                    continue

                max_col = max(row_map.keys())
                row_values = [row_map.get(i, "") for i in range(max_col + 1)]

                cleaned = [v for v in row_values if v]
                if not cleaned:
                    continue
                if len(cleaned) >= 2:
                    lines.append(f"{cleaned[0]}: {cleaned[1]}")
                else:
                    lines.append(cleaned[0])

    return "\n".join(lines)


def _read_xlsx_rows(path: Path) -> list[tuple[str, list[list[str]]]]:
    sheets: list[tuple[str, list[list[str]]]] = []
    shared_strings: list[str] = []

    with zipfile.ZipFile(path) as workbook:
        names = workbook.namelist()

        if "xl/sharedStrings.xml" in names:
            shared_xml = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            for node in shared_xml.iter():
                if node.tag.endswith("}t") and node.text is not None:
                    shared_strings.append(node.text)

        sheet_titles: dict[str, str] = {}
        if "xl/workbook.xml" in names:
            wb_xml = ET.fromstring(workbook.read("xl/workbook.xml"))
            for node in wb_xml.iter():
                if node.tag.endswith("}sheet"):
                    rid = node.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                    title = node.attrib.get("name", "Sheet")
                    if rid:
                        sheet_titles[rid] = title

        rel_map: dict[str, str] = {}
        if "xl/_rels/workbook.xml.rels" in names:
            rel_xml = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
            for node in rel_xml.iter():
                if node.tag.endswith("}Relationship"):
                    rid = node.attrib.get("Id")
                    target = node.attrib.get("Target")
                    if rid and target:
                        rel_map[rid] = target.lstrip("/")

        ordered_targets: list[tuple[str, str]] = []
        for rid, title in sheet_titles.items():
            target = rel_map.get(rid)
            if not target:
                continue
            if not target.startswith("xl/"):
                target = f"xl/{target}"
            ordered_targets.append((title, target))

        if not ordered_targets:
            fallback = sorted(
                name for name in names if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
            )
            ordered_targets = [(Path(name).stem, name) for name in fallback]

        for title, sheet_path in ordered_targets:
            if sheet_path not in names:
                continue
            sheet_xml = ET.fromstring(workbook.read(sheet_path))
            rows: list[list[str]] = []

            for row in sheet_xml.iter():
                if not row.tag.endswith("}row"):
                    continue

                row_map: dict[int, str] = {}
                append_idx = 0
                for cell in list(row):
                    if not cell.tag.endswith("}c"):
                        continue

                    col_idx = _excel_col_to_index(cell.attrib.get("r", ""))
                    if col_idx is None:
                        col_idx = append_idx
                    append_idx = max(append_idx, col_idx + 1)

                    cell_type = cell.attrib.get("t")
                    value = ""

                    inline_node = next((n for n in cell.iter() if n.tag.endswith("}is")), None)
                    if inline_node is not None:
                        text_node = next((n for n in inline_node.iter() if n.tag.endswith("}t") and n.text is not None), None)
                        if text_node is not None:
                            value = text_node.text.strip()

                    if not value:
                        value_node = next((n for n in cell.iter() if n.tag.endswith("}v") and n.text is not None), None)
                        if value_node is not None:
                            value = value_node.text.strip()

                    if cell_type == "s" and value:
                        try:
                            value = shared_strings[int(value)]
                        except (ValueError, IndexError):
                            pass

                    row_map[col_idx] = value

                if not row_map:
                    continue

                max_col = max(row_map.keys())
                row_values = [row_map.get(i, "") for i in range(max_col + 1)]

                while row_values and not row_values[-1]:
                    row_values.pop()

                if row_values:
                    rows.append(row_values)

            sheets.append((title, rows))

    return sheets


def _read_xls_text(path: Path) -> str:
    try:
        import xlrd  # type: ignore
    except ImportError as exc:
        raise ValueError("Legacy .xls support requires 'xlrd' package. Prefer .xlsx when possible.") from exc

    workbook = xlrd.open_workbook(str(path))
    lines: list[str] = []
    for sheet in workbook.sheets():
        for row_idx in range(sheet.nrows):
            values = [str(v).strip() for v in sheet.row_values(row_idx) if str(v).strip()]
            if not values:
                continue
            if len(values) >= 2:
                lines.append(f"{values[0]}: {values[1]}")
            else:
                lines.append(values[0])
    return "\n".join(lines)


def lookup_shipping_date_record_by_id(file_path: str, shipping_id: str) -> dict[str, str] | None:
    path = Path(file_path)
    shipping_id_key = _normalize_lookup_id(shipping_id)
    if not shipping_id_key:
        return None

    suffix = path.suffix.lower()

    if suffix == ".xlsx":
        sheets = _read_xlsx_rows(path)
        shipping_headers = {
            "shipping id",
            "shipment id",
            "ship id",
            "order number",
            "order #",
            "order no",
            "order #/id",
            "order id",
            "sales order",
        }
        date_headers = {
            "shipping date",
            "ship date",
            "ship by date",
            "final shipping date",
            "actual ship date",
            "promised ship date",
            "delivery date",
        }
        matches: list[dict[str, str]] = []

        for sheet_name, rows in sheets:
            if not rows:
                continue

            header_idx = -1
            shipping_col = -1
            date_col = -1
            header_row: list[str] = []

            for idx, row in enumerate(rows[:50]):
                normalized = [_normalize_key(cell) for cell in row]
                local_shipping_col = -1
                local_date_col = -1

                for col, cell in enumerate(normalized):
                    if local_shipping_col < 0 and any(h in cell for h in shipping_headers):
                        local_shipping_col = col
                    if local_date_col < 0 and any(h in cell for h in date_headers):
                        local_date_col = col

                if local_shipping_col >= 0 and local_date_col >= 0:
                    header_idx = idx
                    shipping_col = local_shipping_col
                    date_col = local_date_col
                    header_row = row
                    break

                if local_shipping_col >= 0 and header_idx < 0:
                    header_idx = idx
                    shipping_col = local_shipping_col
                    date_col = local_date_col
                    header_row = row

            if header_idx >= 0 and shipping_col >= 0:
                for row in rows[header_idx + 1 :]:
                    if shipping_col >= len(row):
                        continue
                    candidate_id = _normalize_lookup_id(row[shipping_col])
                    if candidate_id != shipping_id_key:
                        continue

                    shipping_date = ""
                    if 0 <= date_col < len(row):
                        raw_date = row[date_col].strip()
                        parsed = _parse_date_flexible(raw_date)
                        shipping_date = parsed.strftime("%m-%d-%Y") if parsed else raw_date

                    if not shipping_date:
                        row_dates = [
                            parsed.strftime("%m-%d-%Y")
                            for parsed in (_parse_date_flexible(cell) for cell in row)
                            if parsed
                        ]
                        if row_dates:
                            shipping_date = sorted(set(row_dates))[0]

                    if not shipping_date:
                        continue

                    detail_pairs: list[str] = []
                    for col_idx, value in enumerate(row):
                        value_text = value.strip()
                        if not value_text:
                            continue
                        header = header_row[col_idx] if col_idx < len(header_row) else ""
                        key = _header_key(header, col_idx)
                        detail_pairs.append(f"{key}={_format_detail_value(key, value_text)}")
                    details = " | ".join(detail_pairs)

                    matches.append(
                        {
                            "shipping_date": shipping_date,
                            "sheet": sheet_name,
                            "details": details,
                        }
                    )

            if not matches:
                for row in rows:
                    normalized_cells = [_normalize_lookup_id(cell) for cell in row]
                    if shipping_id_key not in normalized_cells:
                        continue

                    row_dates: list[str] = []
                    for cell in row:
                        parsed = _parse_date_flexible(cell)
                        if parsed:
                            row_dates.append(parsed.strftime("%m-%d-%Y"))

                    if len(row_dates) == 1:
                        row_details = " | ".join(
                            f"column_{idx + 1}={cell}"
                            for idx, cell in enumerate(row)
                            if cell
                        )
                        matches.append(
                            {
                                "shipping_date": row_dates[0],
                                "sheet": sheet_name,
                                "details": row_details,
                            }
                        )
                    elif len(row_dates) > 1:
                        matches.append(
                            {
                                "status": "ambiguous",
                                "shipping_id": shipping_id,
                                "candidates": ", ".join(sorted(set(row_dates))),
                            }
                        )

        if not matches:
            return None

        explicit_ambiguous = next((m for m in matches if m.get("status") == "ambiguous"), None)
        if explicit_ambiguous is not None:
            return explicit_ambiguous

        distinct_dates = sorted({m.get("shipping_date", "") for m in matches if m.get("shipping_date")})
        if len(distinct_dates) > 1:
            return {
                "status": "ambiguous",
                "shipping_id": shipping_id,
                "candidates": ", ".join(distinct_dates),
            }

        chosen = matches[0]
        chosen["status"] = "ok"
        chosen["shipping_id"] = shipping_id
        return chosen

    invoice = extract_invoice_data(str(path))
    current_id = _normalize_lookup_id(invoice.shipping_id or "")
    if current_id and current_id == shipping_id_key:
        if invoice.ship_by_date:
            return {
                "status": "ok",
                "shipping_id": shipping_id,
                "shipping_date": invoice.ship_by_date.strftime("%m-%d-%Y"),
                "sheet": "invoice",
            }
        if invoice.latest_ship_date:
            return {
                "status": "ok",
                "shipping_id": shipping_id,
                "shipping_date": invoice.latest_ship_date.strftime("%m-%d-%Y"),
                "sheet": "invoice",
            }
        if invoice.earliest_ship_date:
            return {
                "status": "ok",
                "shipping_id": shipping_id,
                "shipping_date": invoice.earliest_ship_date.strftime("%m-%d-%Y"),
                "sheet": "invoice",
            }
    return None


def research_order_id_in_workbook(file_path: str, order_id: str) -> dict[str, str]:
    path = Path(file_path)
    order_id_key = _normalize_lookup_id(order_id)
    if not order_id_key:
        return {
            "order_id": order_id,
            "scanned_tabs": "0",
            "hits": "0",
            "summary": "No order ID provided.",
        }

    if path.suffix.lower() != ".xlsx":
        return {
            "order_id": order_id,
            "scanned_tabs": "1",
            "hits": "0",
            "summary": "Detailed multi-tab research is available for .xlsx files.",
        }

    sheets = _read_xlsx_rows(path)
    hit_lines: list[str] = []

    for sheet_name, rows in sheets:
        for row_idx, row in enumerate(rows, start=1):
            normalized_cells = [_normalize_lookup_id(cell) for cell in row]
            if order_id_key not in normalized_cells:
                continue

            row_dates: list[str] = []
            for cell in row:
                parsed = _parse_date_flexible(cell)
                if parsed:
                    row_dates.append(parsed.strftime("%m-%d-%Y"))

            preview = " | ".join(cell.strip() for cell in row if cell.strip())
            date_part = f" | dates={', '.join(sorted(set(row_dates)))}" if row_dates else ""
            hit_lines.append(f"{sheet_name}#R{row_idx}: {preview}{date_part}")

    if not hit_lines:
        summary = "Order ID not found in any scanned tab."
    else:
        summary = "\n".join(hit_lines)

    return {
        "order_id": order_id,
        "scanned_tabs": str(len(sheets)),
        "hits": str(len(hit_lines)),
        "summary": summary,
    }


def lookup_shipping_date_by_id(file_path: str, shipping_id: str) -> str | None:
    record = lookup_shipping_date_record_by_id(file_path, shipping_id)
    if not record:
        return None
    if record.get("status") != "ok":
        return None
    return record.get("shipping_date")


def list_shipping_date_records(file_path: str) -> list[dict[str, str]]:
    path = Path(file_path)
    if path.suffix.lower() != ".xlsx":
        return []

    shipping_headers = {
        "shipping id",
        "shipment id",
        "ship id",
        "order number",
        "order #",
        "order no",
        "order #/id",
        "order id",
        "sales order",
    }
    date_headers = {
        "shipping date",
        "ship date",
        "ship by date",
        "final shipping date",
        "actual ship date",
        "promised ship date",
        "delivery date",
    }

    records: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for sheet_name, rows in _read_xlsx_rows(path):
        if not rows:
            continue

        header_idx = -1
        shipping_col = -1
        date_col = -1
        header_row: list[str] = []

        for idx, row in enumerate(rows[:50]):
            normalized = [_normalize_key(cell) for cell in row]
            local_shipping_col = -1
            local_date_col = -1

            for col, cell in enumerate(normalized):
                if local_shipping_col < 0 and any(h in cell for h in shipping_headers):
                    local_shipping_col = col
                if local_date_col < 0 and any(h in cell for h in date_headers):
                    local_date_col = col

            if local_shipping_col >= 0 and local_date_col >= 0:
                header_idx = idx
                shipping_col = local_shipping_col
                date_col = local_date_col
                header_row = row
                break

            if local_shipping_col >= 0 and header_idx < 0:
                header_idx = idx
                shipping_col = local_shipping_col
                date_col = local_date_col
                header_row = row

        if header_idx < 0 or shipping_col < 0:
            continue

        for row in rows[header_idx + 1 :]:
            if shipping_col >= len(row):
                continue

            raw_id = row[shipping_col].strip()
            shipping_id = _normalize_lookup_id(raw_id)
            if not shipping_id:
                continue

            shipping_date = ""
            if 0 <= date_col < len(row):
                parsed = _parse_date_flexible(row[date_col].strip())
                if parsed:
                    shipping_date = parsed.strftime("%m-%d-%Y")

            if not shipping_date:
                first_date = next((d for d in (_parse_date_flexible(cell) for cell in row) if d), None)
                if first_date:
                    shipping_date = first_date.strftime("%m-%d-%Y")

            if not shipping_date:
                continue

            dedupe_key = (shipping_id, shipping_date, sheet_name)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            detail_pairs: list[str] = []
            for col_idx, value in enumerate(row):
                value_text = value.strip()
                if not value_text:
                    continue
                header = header_row[col_idx] if col_idx < len(header_row) else ""
                key = _header_key(header, col_idx)
                detail_pairs.append(f"{key}={_format_detail_value(key, value_text)}")

            records.append(
                {
                    "shipping_id": shipping_id,
                    "shipping_date": shipping_date,
                    "sheet": sheet_name,
                    "details": " | ".join(detail_pairs),
                }
            )

    records.sort(key=lambda item: (item.get("shipping_date", ""), item.get("shipping_id", "")))
    return records


def _read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".csv", ".json"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".xml":
        return _read_xml_text(path)

    if suffix == ".xlsx":
        return _read_xlsx_text(path)

    if suffix == ".xls":
        return _read_xls_text(path)

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
