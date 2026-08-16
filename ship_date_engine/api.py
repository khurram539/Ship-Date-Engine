"""REST API endpoints for Ship Date Engine."""
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from pathlib import Path
import json

from .db import save_upload, get_cached_lookup, cleanup_old_lookups
from .config import Config

app = FastAPI(title="Ship Date Engine API", version="1.0.0")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


@app.post("/upload/{shipping_id}")
async def upload_invoice(shipping_id: str, invoice: UploadFile = File(...), priority: int = Form(default=100)):
    """Upload an invoice with shipping ID."""
    ext = Path(invoice.filename).suffix.lower()
    if ext not in Config.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid file type")

    upload_dir = Config.UPLOADS_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)
    save_path = upload_dir / invoice.filename
    
    max_bytes = Config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    content = await invoice.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="File too large")
    
    with open(save_path, "wb") as buffer:
        buffer.write(content)
    
    save_upload(invoice.filename, str(save_path), {
        "shipping_id": shipping_id, 
        "priority": priority,
        "size_bytes": len(content)
    })
    return {"message": "Invoice uploaded successfully", "file": str(save_path)}


@app.post("/lookup/{shipping_id}")
async def lookup_shipping(shipping_id: str):
    """Retrieve cached shipping decision for a shipping ID."""
    cached = get_cached_lookup(shipping_id)
    if cached:
        result = json.loads(cached) if isinstance(cached, str) else cached
        return {"shipping_id": shipping_id, "cached": True, "result": result}
    return {"message": "Shipping ID not found in cache", "shipping_id": shipping_id}


@app.get("/cache/cleanup")
async def cleanup_cache(days: int = 30):
    """Clean up old cache entries."""
    count = cleanup_old_lookups(days)
    return {"cleared": count, "days_threshold": days}

__all__ = ["app"]
