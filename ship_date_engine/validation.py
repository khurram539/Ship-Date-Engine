from __future__ import annotations

from .models import InvoiceData, ValidationResult


def validate_invoices(invoices: list[InvoiceData]) -> ValidationResult:
    result = ValidationResult()
    for invoice in invoices:
        if not invoice.invoice_number:
            result.warnings.append(f"{invoice.source_path}: missing invoice number")
        if not invoice.po_number:
            result.warnings.append(f"{invoice.source_path}: missing PO number")
        if invoice.earliest_ship_date and invoice.latest_ship_date and invoice.earliest_ship_date > invoice.latest_ship_date:
            result.errors.append(
                f"{invoice.source_path}: earliest ship date is after latest ship date"
            )

    po_numbers = {i.po_number for i in invoices if i.po_number}
    if len(po_numbers) > 1:
        result.warnings.append(f"Conflicting PO numbers: {sorted(po_numbers)}")

    return result
