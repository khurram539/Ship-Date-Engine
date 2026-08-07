"""Data models for Ship Date Engine."""

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Optional


@dataclass
class InvoiceData:
    source_path: str
    shipping_id: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    po_number: Optional[str] = None
    earliest_ship_date: Optional[date] = None
    latest_ship_date: Optional[date] = None
    ship_by_date: Optional[date] = None
    ship_terms: Optional[str] = None
    carrier: Optional[str] = None
    priority: int = 100
    line_items: list[str] = field(default_factory=list)
    raw_fields: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key, value in list(data.items()):
            if isinstance(value, date):
                data[key] = value.isoformat()
        return data


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ShippingDecision:
    final_shipping_date: date
    earliest_ship_date: Optional[date]
    latest_allowable_ship_date: Optional[date]
    explanation: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    selected_priority_invoice: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_shipping_date": self.final_shipping_date.isoformat(),
            "earliest_ship_date": self.earliest_ship_date.isoformat() if self.earliest_ship_date else None,
            "latest_allowable_ship_date": self.latest_allowable_ship_date.isoformat() if self.latest_allowable_ship_date else None,
            "explanation": self.explanation,
            "conflicts": self.conflicts,
            "selected_priority_invoice": self.selected_priority_invoice,
        }
