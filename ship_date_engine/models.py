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

    def has_any_date(self) -> bool:
        """Return True if at least one date field was extracted."""
        return any(
            getattr(self, f) is not None
            for f in ("invoice_date", "earliest_ship_date", "latest_ship_date", "ship_by_date")
        )

    def __repr__(self) -> str:
        parts = [f"source={self.source_path!r}"]
        if self.shipping_id:
            parts.append(f"shipping_id={self.shipping_id!r}")
        if self.invoice_number:
            parts.append(f"invoice_number={self.invoice_number!r}")
        if self.ship_by_date:
            parts.append(f"ship_by_date={self.ship_by_date.isoformat()!r}")
        parts.append(f"priority={self.priority}")
        return f"InvoiceData({', '.join(parts)})"


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when there are no hard errors."""
        return len(self.errors) == 0

    def __repr__(self) -> str:
        return (
            f"ValidationResult(errors={len(self.errors)}, warnings={len(self.warnings)})"
        )


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

    def __repr__(self) -> str:
        return (
            f"ShippingDecision("
            f"final={self.final_shipping_date.isoformat()!r}, "
            f"earliest={self.earliest_ship_date.isoformat()!r}, "
            f"latest={self.latest_allowable_ship_date.isoformat()!r}, "
            f"conflicts={len(self.conflicts)})"
        )
