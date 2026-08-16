from __future__ import annotations

from datetime import date

from .models import InvoiceData, ValidationResult

# Dates outside this window are almost certainly parse errors (Excel serials, typos, etc.).
_REASONABLE_MIN = date(2000, 1, 1)
_REASONABLE_MAX = date(2100, 1, 1)


def _check_date_range(
    invoice: InvoiceData,
    field_name: str,
    value: date,
    result: ValidationResult,
) -> None:
    if value < _REASONABLE_MIN or value > _REASONABLE_MAX:
        result.warnings.append(
            f"{invoice.source_path}: {field_name} {value.isoformat()} is outside the "
            f"expected range ({_REASONABLE_MIN.isoformat()} – {_REASONABLE_MAX.isoformat()})"
        )


def validate_invoices(invoices: list[InvoiceData]) -> ValidationResult:
    result = ValidationResult()
    today = date.today()

    for invoice in invoices:
        # ── Field-presence warnings ──────────────────────────────────────────
        if not invoice.invoice_number:
            result.warnings.append(f"{invoice.source_path}: missing invoice number")
        if not invoice.po_number:
            result.warnings.append(f"{invoice.source_path}: missing PO number")

        # ── Date ordering error ──────────────────────────────────────────────
        if (
            invoice.earliest_ship_date
            and invoice.latest_ship_date
            and invoice.earliest_ship_date > invoice.latest_ship_date
        ):
            result.errors.append(
                f"{invoice.source_path}: earliest ship date is after latest ship date"
            )

        # ── Date sanity range warnings ───────────────────────────────────────
        for field_name in (
            "invoice_date",
            "earliest_ship_date",
            "latest_ship_date",
            "ship_by_date",
        ):
            value: date | None = getattr(invoice, field_name, None)
            if value is not None:
                _check_date_range(invoice, field_name, value, result)

        # ── Ship-by-date-in-the-past warning ────────────────────────────────
        if invoice.ship_by_date and invoice.ship_by_date < today:
            result.warnings.append(
                f"{invoice.source_path}: ship_by_date {invoice.ship_by_date.isoformat()} "
                "is in the past"
            )

        # ── Completely dateless invoice warning ──────────────────────────────
        if not invoice.has_any_date():
            result.warnings.append(
                f"{invoice.source_path}: no date fields found; "
                "shipping date will default to today"
            )

    # ── Cross-invoice PO conflict ────────────────────────────────────────────
    po_numbers = {i.po_number for i in invoices if i.po_number}
    if len(po_numbers) > 1:
        result.warnings.append(f"Conflicting PO numbers: {sorted(po_numbers)}")

    return result
