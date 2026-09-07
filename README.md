# Ship-Date-Engine

A Python shipping-date analysis tool with a web UI for invoice/workbook uploads, Shipping ID lookup, period-based reporting, and optional totals summaries.

## Features

- Web UI for upload + lookup workflows, backed by an SQLite lookup cache (`ship_date.db`).
- Result tables mirror the uploaded Excel: columns, headers, and order come from the workbook itself.
- Shipping ID lookup shows every matching row across all worksheet tabs (order, fees, refunds, etc.).
- Shipping ID dropdown fills automatically with the IDs found in the chosen file.
- Lookup scope modes:
  - `1 Shipping ID`
  - `All Shipping IDs`
- Period grouping for all-ID reports:
  - daily, weekly, monthly, quarterly, annual
- Totals Summary runs automatically: per-column totals, row coverage, and a table of the rows carrying money data.
- AI Assist runs automatically on lookups (summary, anomalies, recommended next action).
- Recent lookups list with clickable Shipping IDs and CSV export.
- Saved upload reuse: look up IDs later without re-uploading.
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
pip install -r requirements.txt
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

### EC2 hostname deployment

The web UI is currently exposed on the EC2 host `KPLSH000` with the DNS name:

```text
http://kplsh000.kaytheon.com:8000
```

The setup is:

1. Create an `A` record in the `kaytheon.com` DNS zone:

  ```text
  Name: kplsh000
  Type: A
  Value: <EC2 public or Elastic IP>
  TTL: 300
  ```

2. Start the web UI on all network interfaces:

  ```bash
  cd /home/kkhoja/Code/Ship-Date-Engine
  python3.11 -m ship_date_engine.web --host 0.0.0.0 --port 8000
  ```

3. Allow TCP port `8000` in both the EC2 security group's inbound rules and
  the RHEL firewall:

  ```bash
  sudo firewall-cmd --permanent --add-port=8000/tcp
  sudo firewall-cmd --reload
  ```

4. Verify DNS and the local listener:

  ```bash
  dig +short kplsh000.kaytheon.com
  ss -ltnp | grep ':8000'
  curl --max-time 5 http://127.0.0.1:8000
  ```

The DNS record must point to a stable Elastic IP in production. A normal EC2
public IP can change after a stop/start operation. The hostname uses HTTP on
port `8000`; HTTPS requires a reverse proxy or load balancer with a TLS
certificate.

The page supports uploading one invoice/workbook document per request.

Main web workflow:
- Upload one file (or pick a recent Shipping ID from the dropdown — no re-upload needed).
- Choose lookup scope (`1 Shipping ID` or `All Shipping IDs`).
- Choose period (`daily/weekly/monthly/quarterly/annual`) for all-ID reports.
- Click `Calculate Shipping Date`. AI Assist and totals run automatically.

The form shows a loading overlay with ETA while processing.

Shipping ID workflow:
- Choose an `.xlsx` file — the Shipping ID dropdown fills with every ID found in it.
- Pick an ID (or type one) and calculate.
- The result shows one details table per matching row across all tabs, a cross-row Totals Summary, and an AI Assist analysis.
- Results are cached in SQLite for repeated lookups; saved uploads are reused so re-upload is often not required.
- Displayed shipping dates are formatted as `mm-dd-yyyy`.

All Shipping IDs report workflow:
- Upload an `.xlsx` workbook and select `All Shipping IDs`.
- Pick period grouping (daily/weekly/monthly/quarterly/annual).
- The app renders:
  - counts by period
  - Totals Summary (per-column totals with row coverage)
  - Rows With Money Data (the specific rows carrying numeric values)
  - Workbook Rows table mirroring the Excel's own columns, with a totals footer

Supported upload formats:
- TXT
- XML
- XLSX
- XLS (requires `xlrd` package)
- PDF
- Images (PNG/JPG/JPEG/TIF/TIFF/BMP)

AI Assist (automatic):
- Runs on every lookup; no checkbox needed.
- Backends: direct Anthropic API (set `ANTHROPIC_API_KEY`, optional `ANTHROPIC_MODEL_ID`) or AWS Bedrock (AWS credentials/region in the environment, optional `BEDROCK_MODEL_ID`).
- Default Bedrock fallback models prioritize active models (for example `amazon.nova-lite-v1:0`).
- If no AI backend is configured, results render normally with a note that AI assist is unavailable.

Optional outputs:

```bash
python -m ship_date_engine.cli invoice_a.txt invoice_b.txt --json-out result.json --text-out result.txt
```

## REST API (FastAPI)

A separate FastAPI server exposes upload/lookup endpoints backed by the same SQLite cache:

```bash
python run_server.py --host 0.0.0.0 --port 8001
```

See [API_DOCS.md](API_DOCS.md) for endpoints.

For the same EC2 deployment, the API is available on port `8001`:

```bash
python3.11 run_server.py --host 0.0.0.0 --port 8001
```

Allow TCP `8001` in the EC2 security group and RHEL firewall when external API
access is required. The main API URLs are:

```text
http://kplsh000.kaytheon.com:8001/
http://kplsh000.kaytheon.com:8001/docs
http://kplsh000.kaytheon.com:8001/health
```

## Test

```bash
python -m pytest tests/ ship_date_engine/test_engine.py -q
```