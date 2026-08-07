from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List
from datetime import date
import re


class InvoiceData(BaseModel):
    """Pydantic model for validated invoice data."""
    source_path: str = Field(..., description="Source file path")
    shipping_id: Optional[str] = Field(default=None, description="Shipping/Order ID")
    invoice_number: Optional[str] = Field(default=None, description="Invoice number")
    invoice_date: Optional[date] = Field(default=None, description="Invoice date")
    po_number: Optional[str] = Field(default=None, description="Purchase Order number")
    earliest_ship_date: Optional[date] = Field(
        default=None, description="Earliest possible ship date"
    )
    latest_ship_date: Optional[date] = Field(
        default=None, description="Latest allowed ship date"
    )
    ship_by_date: Optional[date] = Field(default=None, description="Ship by deadline")
    ship_terms: Optional[str] = Field(default=None, description="Shipping terms")
    carrier: Optional[str] = Field(default=None, description="Carrier name")
    priority: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Priority score (lower is higher priority)"
    )
    line_items: List[str] = Field(
        default_factory=list, 
        max_length=Config.MAX_LINE_ITEMS,
        description="List of line item descriptions"
    )
    raw_fields: dict = Field(
        default_factory=dict,
        max_length=100,
        description="Raw field mappings from file"
    )
    
    @field_validator("shipping_id")
    @classmethod
    def validate_shipping_id(cls, v):
        if v:
            # Clean and validate shipping ID format
            cleaned = re.sub(r"[^\w.-]", "", v)
            if not cleaned:
                raise ValueError("Shipping ID cannot be empty after cleaning")
            return cleaned
        return v
    
    @field_validator("carrier")
    @classmethod
    def validate_carrier(cls, v):
        if v and len(v) > 100:
            raise ValueError("Carrier name exceeds maximum length of 100 characters")
        return v
    
    @model_validator(mode="after")
    def validate_dates_consistency(self):
        """Ensure date fields have logical relationships."""
        if self.earliest_ship_date and self.latest_ship_date:
            if self.earliest_ship_date > self.latest_ship_date:
                raise ValueError(
                    f"Earliest ship date ({self.earliest_ship_date}) cannot be "
                    f"after latest ship date ({self.latest_ship_date})"
                )
        return self
    
    def to_dict(self) -> dict:
        """Convert to plain dict with date serialization."""
        from dataclasses import asdict, is_dataclass
        import datetime
        
        data = self.model_dump()
        for key, value in data.items():
            if isinstance(value, (date, datetime.datetime)):
                data[key] = value.isoformat()
        return data


class ValidationResult(BaseModel):
    """Pydantic model for validation results."""
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0
    
    def add_error(self, message: str):
        self.errors.append(message)
    
    def add_warning(self, message: str):
        self.warnings.append(message)
    
    def to_dict(self) -> dict:
        return {"errors": self.errors, "warnings": self.warnings}


class ShippingDecision(BaseModel):
    """Pydantic model for shipping decision results."""
    final_shipping_date: date
    earliest_ship_date: Optional[date]
    latest_allowable_ship_date: Optional[date]
    explanation: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    selected_priority_invoice: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to plain dict."""
        result = self.model_dump()
        for key, value in result.items():
            if isinstance(value, (date,)):
                result[key] = value.isoformat()
        return result
