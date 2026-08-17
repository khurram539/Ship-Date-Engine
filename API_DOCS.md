# Ship Date Engine API

## Endpoints

### `GET /health`
Returns API health metadata.

### `POST /upload/{shipping_id}`
Uploads an invoice for a shipping ID.

- Multipart field: `invoice`
- Optional form field: `priority` (default `100`)

Validation includes:
- filename sanitization
- allowed extension checks
- upload size limits

### `POST /lookup/{shipping_id}`
Returns any cached lookup result stored for the shipping ID.

### `GET /cache/cleanup?days=30`
Deletes cached lookup rows older than the requested age in days.

## Running locally

```bash
pip install -r requirements.txt
python run_server.py --host 127.0.0.1 --port 8000
```
