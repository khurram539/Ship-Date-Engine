from __future__ import annotations

import json
from datetime import date

from .models import InvoiceData, ShippingDecision, ValidationResult


def _fmt(d: date) -> str:
    return d.strftime("%m-%d-%Y")


def to_json_output(
    invoices: list[InvoiceData],
    validation: ValidationResult,
    decision: ShippingDecision,
) -> str:
    payload = {
        "invoices": [i.to_dict() for i in invoices],
        "validation": {
            "errors": validation.errors,
            "warnings": validation.warnings,
        },
        "decision": decision.to_dict(),
    }
    return json.dumps(payload, indent=2)


def to_text_output(
    invoices: list[InvoiceData],
    validation: ValidationResult,
    decision: ShippingDecision,
) -> str:
    lines = [
        "Shipping Date Engine Result",
        "=" * 26,
        f"Final Shipping Date: {_fmt(decision.final_shipping_date)}",
        f"Earliest Ship Date: {_fmt(decision.earliest_ship_date)}",
        f"Latest Allowable Ship Date: {_fmt(decision.latest_allowable_ship_date)}",
        "",
        "Explanation:",
        *[f"- {step}" for step in decision.explanation],
    ]
    if decision.conflicts:
        lines.extend(["", "Conflicts:", *[f"- {c}" for c in decision.conflicts]])
    if validation.warnings or validation.errors:
        lines.extend(["", "Validation:"])
        lines.extend([f"- ERROR: {e}" for e in validation.errors])
        lines.extend([f"- WARNING: {w}" for w in validation.warnings])
    lines.extend(["", "Invoices:"])
    lines.extend(
        [
            f"- {inv.source_path} (shipping_id={inv.shipping_id or 'N/A'}, invoice={inv.invoice_number or 'N/A'}, po={inv.po_number or 'N/A'}, priority={inv.priority})"
            for inv in invoices
        ]
    )
    return "\n".join(lines)
