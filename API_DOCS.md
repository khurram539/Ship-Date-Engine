# Ship Date Engine API Documentation

## Overview

The Ship Date Engine provides a RESTful API for shipping date analysis, lookup, and validation. Built with FastAPI for high performance and modern async support.

## Base URL

```
http://localhost:8000/api/v1
```

## Endpoints

### 1. Root Endpoint

**GET** `/`

Returns service information and available endpoints.

**Response:**
```json
{
  "service": "Ship Date Engine API",
  "version": "v1",
  "endpoints": ["/compute", "/lookup", "/history"]
}
```

---

### 2. Compute Shipping Date

**POST** `/compute`

Upload invoice file(s) and compute the final shipping date.

**Request:**
- `invoice_file`: multipart/form-data - Invoice file to process
- `shipping_id`: optional string - Shipping ID for lookup
- `lookup_mode`: "single" or "all" (default: "single")
- `group_by`: PeriodGrouping enum (default: "daily")
- `enable_ai`: boolean (default: false)
- `include_totals`: boolean (default: false)

**Response Example:**
```json
{
  "success": true,
  "data": {
    "decision": {
      "final_shipping_date": "2026-05-17",
      "earliest_ship_date": "2026-05-12",
      "latest_allowable_ship_date": "2026-05-17",
      "explanation": ["Priority invoice selected"],
      "conflicts": [],
      "selected_priority_invoice": "INV-1002"
    },
    "ai_assist": {
      "insight": "Confidence: High. Risk: None detected."
    },
    "totals_summary": {
      "tax_total": 45.67,
      "shipping_cost_total": 23.12
    }
  }
}
```

---

### 3. Lookup Shipping ID

**POST** `/lookup`

Lookup shipping date by ID from uploaded file.

**Request:**
- `shipping_id`: form data - The shipping ID to lookup
- `file`: multipart/form-data - Optional file with order details
- `cached_only`: boolean (default: false) - Only use cached results

**Response:**
```json
{
  "success": true,
  "data": {
    "shipping_id": "12345",
    "result": {
      "shipping_date": "2026-05-17",
      "status": "found"
    }
  }
}
```

---

### 4. Get Cached Lookup

**GET** `/lookup/{shipping_id}`

Retrieve cached lookup result for a specific shipping ID.

**Query Parameters:**
- `cached_only`: boolean (default: false)

**Response:**
```json
{
  "success": true,
  "data": {
    "shipping_id": "12345",
    "result": {
      "shipping_date": "2026-05-17"
    }
  }
}
```

---

### 5. Delete Cache Entry

**DELETE** `/lookup/{shipping_id}`

Remove cached lookup for a specific shipping ID.

**Response:**
```json
{
  "success": true,
  "data": {
    "deleted": true
  }
}
```

---

### 6. Get Lookup History

**GET** `/history`

Retrieve recent lookup history.

**Query Parameters:**
- `limit`: number (default: 10, range: 1-100)

**Response:**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "shipping_id": "12345",
        "result": {"shipping_date": "2026-05-17"},
        "created_at": "2026-08-16T10:30:00"
      }
    ],
    "count": 1
  }
}
```

---

### 7. Clear History Entry

**DELETE** `/history/{shipping_id}`

Clear specific history entry.

**Response:**
```json
{
  "success": true,
  "data": {
    "deleted": true
  }
}
```

---

### 8. Cleanup History

**POST** `/history/cleanup`

Remove old history entries based on age.

**Query Parameters:**
- `days`: number (default: 30, range: 1-infinity)

**Response:**
```json
{
  "success": true,
  "data": {
    "deleted": 42
  }
}
```

---

### 9. Generate AI Insight

**POST** `/ai/insight`

Generate AI-powered analysis for a shipping ID.

**Request:**
- `shipping_id`: form data - Shipping ID to analyze
- `file`: multipart/form-data - Optional file with order details
- `model_id`: optional string - Override Bedrock model ID

**Response:**
```json
{
  "success": true,
  "data": {
    "shipping_id": "12345",
    "insight": "Analysis shows high confidence in shipping date with no conflicts.",
    "model_used": "amazon.nova-lite-v1:0"
  }
}
```

---

### 10. Validate Invoices

**POST** `/validate`

Validate two invoice files for consistency.

**Request:**
- `file_a`: multipart/form-data - First invoice file
- `file_b`: multipart/form-data - Second invoice file

**Response (Valid):**
```json
{
  "success": true,
  "data": {
    "valid": true,
    "warnings": []
  }
}
```

**Response (Invalid):**
```json
{
  "success": false,
  "error": "Validation failed: ['Invoice 1: Missing shipping ID']"
}
```

---

### 11. Health Check

**GET** `/health`

Check API health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-08-16T15:30:00"
}
```

---

## Error Responses

All endpoints return consistent error format:

### Bad Request (400)
```json
{
  "detail": {
    "success": false,
    "error": "Validation failed: ..."
  }
}
```

### Not Found (404)
```json
{
  "detail": {
    "success": false,
    "error": "Lookup not found for X-123"
  }
}
```

### Server Error (500)
```json
{
  "detail": {
    "success": false,
    "error": "Internal server error: ..."
  }
}
```

---

## Running the API Server

### Installation

```bash
cd Ship-Date-Engine
pip install -r requirements.txt
```

### Start Server

```bash
python run_server.py --host 127.0.0.1 --port 8000
```

Or with auto-reload for development:

```bash
python run_server.py --reload
```

### Access Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## CLI Usage (Legacy)

For command-line usage without the API server:

```bash
python ship_date_engine/cli.py invoice_a.txt invoice_b.txt --json-out result.json
```

---

## Configuration Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIP_DATE_HOST` | `127.0.0.1` | Host to bind the API server |
| `SHIP_DATE_PORT` | `8000` | Port for the API server |
| `SHIP_DATE_API_VERSION` | `v1` | API version prefix |
| `AWS_REGION` | `us-east-1` | AWS region for Bedrock |
| `BEDROCK_MODEL_ID` | `amazon.nova-lite-v1:0` | Bedrock model ID |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

---

## Supported File Formats

- TXT (.txt)
- XML (.xml)
- Excel (.xlsx, .xls)
- PDF (.pdf) - text extraction
- Images (.png, .jpg, .jpeg, .tif, .tiff, .bmp)
