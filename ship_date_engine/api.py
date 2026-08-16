"""
REST API backend for Ship Date Engine using FastAPI.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from fastapi import (
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .ai_assist import generate_bedrock_insight
from .config import Config
from .db import (
    cleanup_old_lookups,
    delete_lookup,
    get_all_lookups,
    get_cached_lookup,
    save_lookup,
)
from .engine_enhanced import determine_shipping_date, determine_shipping_date_single
from .extraction import list_shipping_date_records, lookup_shipping_date_record_by_id, research_order_id_in_workbook
from .models import InvoiceData, ShippingDecision, ValidationResult


LOGGER = logging.getLogger(__name__)


class PeriodGrouping(str, Enum):
    """Period grouping options for reports."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class ComputeRequest(BaseModel):
    """Request model for compute endpoint."""
    invoice_file: UploadFile = Field(..., description="Invoice file to process")
    shipping_id: Optional[str] = Field(None, description="Shipping ID lookup")
    lookup_mode: str = Field(default="single", description="Lookup mode: 'single' or 'all'")
    group_by: PeriodGrouping = Field(default=PeriodGrouping.DAILY, description="Period grouping for reports")
    enable_ai: bool = Field(False, description="Enable AI assist")
    include_totals: bool = Field(False, description="Include totals summary")


class ShippingDateResponse(BaseModel):
    """Response model containing shipping date decision."""
    final_shipping_date: str
    earliest_ship_date: str
    latest_allowable_ship_date: str
    explanation: list[str]
    conflicts: list[str]
    selected_priority_invoice: Optional[str] = None


class LookupResult(BaseModel):
    """Response model for lookup operations."""
    shipping_id: str
    result: dict
    cached: bool


class HistoryItem(BaseModel):
    """History item for recent lookups."""
    shipping_id: str
    result: dict
    created_at: str


def format_date_iso(date_obj: date) -> str:
    """Format date as ISO string."""
    return date_obj.isoformat() if date_obj else ""


def extract_invoices_from_files(file_paths: list[str]) -> list[InvoiceData]:
    """Extract invoice data from multiple files."""
    invoices = []
    for path in file_paths:
        try:
            invoices.append(extract_invoice_data(path))
        except Exception as e:
            LOGGER.error(f"Failed to extract from {path}: {e}")
            raise ValueError(f"Failed to process file: {e}") from e
    return invoices


def generate_api_response(
    status_code: int,
    success: bool,
    data: Optional[dict] = None,
    error_msg: Optional[str] = None,
) -> dict:
    """Generate standard API response."""
    if success:
        return {"success": True, "data": data}
    else:
        return {"success": False, "error": error_msg}


def create_app() -> "FastAPI":
    """Create and configure FastAPI application."""
    config = Config.get()
    
    app = FastAPI(
        title="Ship Date Engine API",
        description="REST API for shipping date analysis",
        version=config.api_version,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "service": "Ship Date Engine API",
            "version": app.version,
            "endpoints": ["/compute", "/lookup", "/history"]
        }
    
    @app.post(
        "/compute",
        response_model=dict,
        status_code=status.HTTP_200_OK,
        summary="Compute shipping date from invoice files",
        description="Upload invoice file(s) and compute the final shipping date"
    )
    async def compute_shipping_date(
        request: Request,
        data: ComputeRequest = Depends(),
        invoices: list[InvoiceData] = Depends()
    ):
        """Compute shipping date from uploaded invoice files."""
        try:
            validation: ValidationResult = validate_invoices(invoices)
            if validation.errors:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"success": False, "error": f"Validation failed: {validation.errors}"}
                )
            
            decision: ShippingDecision = resolve_shipping_date(invoices)
            
            response_data: dict[str, any] = {
                "decision": decision.to_dict(),
                "validation": validation.to_dict() if hasattr(validation, 'to_dict') else {},
            }
            
            # Generate AI insight if enabled
            if data.enable_ai:
                try:
                    ai_insight = generate_bedrock_insight(invoices, validation, decision)
                    response_data["ai_assist"] = {"insight": ai_insight}
                except RuntimeError as e:
                    LOGGER.warning("AI assist failed: %s", e)
                    response_data["ai_assist"] = {"error": str(e)}
            
            # Generate totals summary if enabled
            if data.include_totals:
                response_data["totals_summary"] = generate_totals_summary(invoices, decision)
            
            return generate_api_response(status.HTTP_200_OK, True, response_data)
        
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Compute failed: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"success": False, "error": str(e)}
            )
    
    @app.post("/lookup")
    async def lookup_shipping_id(
        shipping_id: str = Form(...),
        file: UploadFile = File(None),
        cached_only: bool = Query(False)
    ):
        """Lookup shipping date by ID."""
        # Check cache first if requested
        if cached_only and shipping_id:
            cached_result = get_cached_lookup(shipping_id)
            if cached_result:
                return generate_api_response(True, True, {"shipping_id": shipping_id, "result": cached_result})
        
        # Attempt file upload
        result_data = None
        if file and file.filename:
            try:
                contents = await file.read()
                # For actual file processing, save to temp and process
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=file.filename or ".txt", delete=False) as tmp:
                    tmp.write(contents)
                    tmp_path = tmp.name
                
                result_data = research_order_id_in_workbook(tmp_path, shipping_id)
                if result_data:
                    save_lookup(shipping_id, result_data)
                
                Path(tmp_path).unlink()
            
            except Exception as e:
                LOGGER.error("File processing failed: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"success": False, "error": str(e)}
                )
        else:
            # Simulated lookup for demo
            result_data = {
                "shipping_id": shipping_id,
                "status": "lookup_required",
                "message": "File upload not provided"
            }
        
        return generate_api_response(True, True, {"shipping_id": shipping_id, "result": result_data})
    
    @app.get("/lookup/{shipping_id}")
    async def get_lookup(
        shipping_id: str = Path(...),
        cached_only: bool = Query(False)
    ):
        """Get cached lookup result."""
        result = get_cached_lookup(shipping_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "error": f"Lookup not found for {shipping_id}"}
            )
        return generate_api_response(True, True, {"shipping_id": shipping_id, "result": result})
    
    @app.delete("/lookup/{shipping_id}")
    async def delete_lookup_cache(
        shipping_id: str = Path(...),
    ):
        """Delete cached lookup."""
        deleted = delete_lookup(shipping_id)
        return generate_api_response(True, True, {"deleted": bool(deleted)})
    
    @app.get("/history")
    async def get_history(
        limit: int = Query(10, ge=1, le=100),
    ):
        """Get recent lookup history."""
        history = get_all_lookups(limit)
        return generate_api_response(True, True, {"items": history, "count": len(history)})
    
    @app.delete("/history/{shipping_id}")
    async def clear_history(
        shipping_id: str = Path(...),
    ):
        """Clear history entry."""
        deleted = delete_lookup(shipping_id)
        return generate_api_response(True, True, {"deleted": bool(deleted)})
    
    @app.post("/history/cleanup")
    async def cleanup_history(
        days: int = Query(30, ge=1, le="infinity"),
    ):
        """Clean up old history entries."""
        deleted_count = cleanup_old_lookups(days)
        return generate_api_response(True, True, {"deleted": deleted_count})
    
    @app.post("/ai/insight")
    async def generate_insight(
        shipping_id: str = Form(...),
        file: UploadFile = File(None),
        model_id: Optional[str] = Query(None)
    ):
        """Generate AI insight for a shipping ID."""
        # Process file to get invoice data
        invoices, validation, decision = None, None, None
        
        if file and file.filename:
            try:
                import tempfile
                contents = await file.read()
                with tempfile.NamedTemporaryFile(suffix=file.filename or ".txt", delete=False) as tmp:
                    tmp.write(contents)
                    tmp_path = tmp.name
                
                invoices = [extract_invoice_data(tmp_path)]
                validation = validate_invoices(invoices) if invoices else ValidationResult()
                decision = resolve_shipping_date(invoices) if invoices else None
                
                Path(tmp_path).unlink()
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"success": False, "error": str(e)}
                )
        
        if not decision:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "error": "No decision data to analyze"}
            )
        
        try:
            insight = generate_bedrock_insight(invoices or [], validation, decision)
            
            return generate_api_response(True, True, {
                "shipping_id": shipping_id,
                "insight": insight,
                "model_used": model_id or Config.get().bedrock_model_id
            })
        
        except RuntimeError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"success": False, "error": str(e)}
            )
    
    @app.post("/validate")
    async def validate_invoices(
        file_a: UploadFile = File(...),
        file_b: UploadFile = File(...)
    ):
        """Validate two invoice files."""
        # Process and validate
        try:
            temp_files, invoices = [], []
            
            for idx, file in enumerate([file_a, file_b], 1):
                if not file.filename:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"success": False, "error": f"Missing filename for file {idx}"}
                    )
                
                contents = await file.read()
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=file.filename, delete=False) as tmp:
                    tmp.write(contents)
                    temp_files.append(tmp.name)
                
                try:
                    invoices.append(extract_invoice_data(tmp.name))
                except Exception as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"success": False, "error": f"Failed to process file {idx}: {e}"}
                    )
            
            validation = validate_invoices(invoices)
            
            # Cleanup temp files
            for path in temp_files:
                Path(path).unlink()
            
            if validation.errors:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"success": False, "errors": validation.errors}
                )
            
            return generate_api_response(True, True, {
                "valid": len(validation.errors) == 0,
                "warnings": validation.warnings
            })
        
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error("Validation failed: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"success": False, "error": str(e)}
            )
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    
    return app


def create_database_tables():
    """Initialize database tables."""
    from .db import init_db
    init_db()


if __name__ == "__main__":
    import uvicorn
    
    # Create and start the API server
    app = create_app()
    config = Config.get()
    
    LOGGER.info(f"Starting Ship Date Engine API on http://{config.host}:{config.port}")
    
    uvicorn.run(
        "ship_date_engine.api:create_app",
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
        reload=False,
    )
