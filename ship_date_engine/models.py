from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


@dataclass
class InvoiceData:
    source_path: str
    invoice_number: str | None = None
    invoice_date: date | None = None
    po_number: str | None = None
    earliest_ship_date: date | None = None
    latest_ship_date: date | None = None
    ship_by_date: date | None = None
    ship_terms: str | None = None
    carrier: str | None = None
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
    earliest_ship_date: date
    latest_allowable_ship_date: date
    explanation: list[str]
    conflicts: list[str]
    selected_priority_invoice: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_shipping_date": self.final_shipping_date.isoformat(),
            "earliest_ship_date": self.earliest_ship_date.isoformat(),
            "latest_allowable_ship_date": self.latest_allowable_ship_date.isoformat(),
            "explanation": self.explanation,
            "conflicts": self.conflicts,
            "selected_priority_invoice": self.selected_priority_invoice,
        }
