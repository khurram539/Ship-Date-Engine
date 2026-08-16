"""REST API endpoints for Ship Date Engine."""
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, Body
from pathlib import Path
import json

from .db import save_upload, get_cached_lookup, cleanup_old_lookups, save_lookup
from .config import Config
from .security import ValidationError, sanitize_filename
from .extraction import extract_invoice_data
from .engine import determine_shipping_date_single

app = FastAPI(title="Ship Date Engine API", version="1.0.0")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

@app.post("/upload/{shipping_id}")
async def upload_invoice(shipping_id: str, invoice: UploadFile = File(...), priority: int = Form(default=100)):
    raw_filename = invoice.filename
    if not raw_filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    try:
        filename = sanitize_filename(raw_filename)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    ext = Path(filename).suffix.lower()
    if ext not in Config.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid file type")

    upload_dir = Config.UPLOADS_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)
    save_path = upload_dir / filename

    max_bytes = Config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    content = await invoice.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="File too large")

    with open(save_path, "wb") as buffer:
        buffer.write(content)

    save_upload(filename, str(save_path), {"shipping_id": shipping_id, "priority": priority, "size_bytes": len(content)})
    return {"message": "Invoice uploaded successfully", "file": str(save_path)}

@app.post("/extract/{shipping_id}")
async def extract_data_endpoint(shipping_id: str):
    try:
        upload_record = get_cached_lookup(shipping_id)
        if not upload_record:
            raise HTTPException(status_code=404, detail=f"No upload found for shipping_id: {shipping_id}")
        if isinstance(upload_record, str):
            upload_data = json.loads(upload_record)
        else:
            upload_data = upload_record
        filepath = Path(upload_data.get("filepath") or "")
        if not filepath.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {filepath}")
        extracted = extract_invoice_data(str(filepath))
        return {"shipping_id": shipping_id, "extracted_fields": extracted.to_dict() if hasattr(extracted, "to_dict") else extracted, "status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

@app.post("/lookup/{shipping_id}")
async def lookup_shipping(shipping_id: str):
    cached = get_cached_lookup(shipping_id)
    if cached:
        result = json.loads(cached) if isinstance(cached, str) else cached
        return {"shipping_id": shipping_id, "cached": True, "result": result}
    return {"message": "Shipping ID not found in cache", "shipping_id": shipping_id}

@app.post("/determine/{shipping_id}")
async def determine_shipping_date_endpoint(shipping_id: str, data: dict = Body(...)):
    try:
        extracted = data.get("extracted_data", {})
        result = determine_shipping_date_single(str(extracted))
        if result is None:
            raise HTTPException(status_code=400, detail="Engine returned no shipping date - check input data")
        save_lookup(shipping_id, result)
        return {"shipping_id": shipping_id, "result": result, "status": "determined"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Determination failed: {str(e)}")

@app.get("/cache/cleanup")
async def cleanup_cache(days: int = 30):
    count = cleanup_old_lookups(days)
    return {"cleared": count, "days_threshold": days}

__all__ = ["app"]
