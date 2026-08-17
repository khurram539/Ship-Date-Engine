# Ship-Date-Engine

A Python shipping-date analysis tool with a web UI for invoice/workbook uploads, Shipping ID lookup, period-based reporting, and optional totals summaries.

## Features

- Web UI for upload + lookup workflows.
- Shipping ID lookup with clean result cards/tables.
- Lookup scope modes:
  - `1 Shipping ID`
  - `All Shipping IDs`
- Period grouping for all-ID reports:
  - daily, weekly, monthly, quarterly, annual
- Optional totals summary for numeric fields (for example Tax, Transaction Fee, Shipping Cost, Grand Total, Amount).
- Dynamic field/table rendering: empty fields are hidden automatically.
- Saved upload reuse: you can lookup IDs later without re-uploading in common flows.
- Recent lookups list with clickable Shipping IDs.
- Optional Bedrock AI Assist.
- Dates normalized to `mm-dd-yyyy` where applicable.

## CLI Run (Legacy Flow)

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

The page supports uploading one invoice/workbook document per request.

Main web workflow:
- Upload one file.
- Choose lookup scope (`1 Shipping ID` or `All Shipping IDs`).
- Choose period (`daily/weekly/monthly/quarterly/annual`) for all-ID reports.
- Optionally enable `Include totals summary`.
- Click `Calculate Shipping Date`.

The form shows a loading overlay with ETA while processing.

Shipping ID workflow:
- Enter a Shipping ID and upload your file.
- For Excel `.xlsx`, the app scans worksheet tabs to find a matching Shipping ID and its shipping date.
- If a match is found, the returned shipping date is shown in `mm-dd-yyyy` format.
- Shipping ID results are cached for repeated lookups.
- Saved uploads are reused in lookup flows so re-upload is often not required.
- Displayed shipping dates are formatted as `mm-dd-yyyy` in the web output.

All Shipping IDs report workflow:
- Upload an `.xlsx` workbook.
- Select `All Shipping IDs`.
- Pick period grouping (daily/weekly/monthly/quarterly/annual).
- Optional: check `Include totals summary`.
- The app renders:
  - counts by period
  - shipping ID report table
  - additional fields table (only when data exists)
  - totals summary (if enabled and numeric values are present)

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
