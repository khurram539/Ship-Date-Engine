from __future__ import annotations

import logging

from .date_logic import resolve_shipping_date
from .extraction import extract_invoice_data
from .models import ShippingDecision, ValidationResult
from .validation import validate_invoices

LOGGER = logging.getLogger(__name__)


def determine_shipping_date(invoice_file_a: str, invoice_file_b: str):
    invoices = [extract_invoice_data(invoice_file_a), extract_invoice_data(invoice_file_b)]
    validation: ValidationResult = validate_invoices(invoices)
    if validation.errors:
        LOGGER.error("Validation failed: %s", validation.errors)
        raise ValueError("Validation failed for invoice inputs")
    decision: ShippingDecision = resolve_shipping_date(invoices)
    return invoices, validation, decision


def determine_shipping_date_single(invoice_file: str):
    invoices = [extract_invoice_data(invoice_file)]
    validation: ValidationResult = validate_invoices(invoices)
    if validation.errors:
        LOGGER.error("Validation failed: %s", validation.errors)
        raise ValueError("Validation failed for invoice input")
    decision: ShippingDecision = resolve_shipping_date(invoices)
    return invoices, validation, decision
