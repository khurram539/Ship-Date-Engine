from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


@dataclass
class InvoiceData:
    source_path: str
    shipping_id: str | None = None
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

    def __repr__(self) -> str:
        return (
            f"ShippingDecision("
            f"final={self.final_shipping_date.isoformat()!r}, "
            f"earliest={self.earliest_ship_date.isoformat()!r}, "
            f"latest={self.latest_allowable_ship_date.isoformat()!r}, "
            f"conflicts={len(self.conflicts)})"
        )
