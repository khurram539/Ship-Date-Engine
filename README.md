# Ship-Date-Engine

A modular Python application that takes **two invoices** (text, PDF, or image), extracts key fields, validates conflicts/missing data, and determines the correct shipping date with clear reasoning.

## Features

- Parses invoice fields including dates, PO number, shipping terms, carrier, priority, and line items.
- Supports `.txt` out of the box, plus optional:
  - PDF via `pypdf`
  - Image OCR via `pytesseract` + `Pillow`
- Validates missing or conflicting fields.
- Applies shipping date logic for:
  - earliest ship date
  - latest allowable date
  - ship-by date constraints
  - priority-based conflict resolution
- Outputs both:
  - Human-readable formatted text
  - Machine-readable JSON
- Includes logging and input validation.

## Run

```bash
python -m ship_date_engine.cli /path/to/invoice_a.txt /path/to/invoice_b.txt
```

Optional outputs:

```bash
python -m ship_date_engine.cli invoice_a.txt invoice_b.txt --json-out result.json --text-out result.txt
```

## Test

```bash
python -m unittest -q
```
