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

Recommended runtime:
- Python 3.10+ (project upgraded and validated on Python 3.11)

Create and use virtual environment:

```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
pip install --upgrade pip
pip install boto3
```

## Live Server (Web UI)

Run a local web server and open it in your browser:

```bash
python -m ship_date_engine.web --host 0.0.0.0 --port 8000
```

Then browse to:

```text
http://<your-server-ip>:8000
```

The page supports uploading one invoice document, with text paste as a fallback.

Shipping ID workflow:
- Enter a Shipping ID and upload your file.
- For Excel `.xlsx`, the app scans worksheet tabs to find a matching Shipping ID and its shipping date.
- If a match is found, the returned shipping date is shown in `mm-dd-yyyy` format.
- Shipping ID results are also cached for quick repeated lookups.
- Displayed shipping dates are formatted as `mm-dd-yyyy` in the web output.

Supported upload formats:
- TXT
- XML
- XLSX
- XLS (requires `xlrd` package)
- PDF
- Images (PNG/JPG/JPEG/TIF/TIFF/BMP)

Optional AI assist:
- Bedrock AI assist is available from the same single form (checkbox).
- Set AWS credentials/region in your environment.
- Optional model override: `BEDROCK_MODEL_ID`.
- Default fallback models prioritize active Bedrock models (for example `amazon.nova-lite-v1:0`).

Optional outputs:

```bash
python -m ship_date_engine.cli invoice_a.txt invoice_b.txt --json-out result.json --text-out result.txt
```

## Test

```bash
python -m unittest -q
```
