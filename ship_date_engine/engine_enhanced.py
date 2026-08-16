"""
Enhanced engine for shipping date determination with improved validation and error handling.
"""
from __future__ import annotations

import logging
from datetime import date

from .date_logic import resolve_shipping_date
from .extraction import extract_invoice_data, ValidationResult as ExtractionValidationResult
from .models import InvoiceData, ShippingDecision, ValidationResult


LOGGER = logging.getLogger(__name__)


def determine_shipping_date(invoice_file_a: str, invoice_file_b: str) -> tuple[list[InvoiceData], ValidationResult, ShippingDecision]:
    """
    Determine shipping date from two invoice files.
    
    Args:
        invoice_file_a: Path to first invoice file
        invoice_file_b: Path to second invoice file
        
    Returns:
        Tuple of (invoices, validation_result, decision)
        
    Raises:
        ValueError: If validation fails or input is invalid
    """
    try:
        invoices = [extract_invoice_data(invoice_file_a), extract_invoice_data(invoice_file_b)]
    except Exception as e:
        LOGGER.error("Failed to extract invoice data: %s", e)
        raise ValueError(f"Failed to process invoice files: {e}") from e
    
    try:
        validation: ValidationResult = validate_invoices(invoices)
    except Exception as e:
        LOGGER.error("Validation error: %s", e)
        raise ValueError(f"Validation failed: {e}") from e
    
    if validation.errors:
        LOGGER.error("Validation failed with errors: %s", validation.errors)
        raise ValueError("Validation failed for invoice inputs") from None
    
    try:
        decision: ShippingDecision = resolve_shipping_date(invoices)
    except Exception as e:
        LOGGER.error("Failed to resolve shipping date: %s", e)
        raise ValueError(f"Failed to determine shipping date: {e}") from e
    
    return invoices, validation, decision


def determine_shipping_date_single(invoice_file: str) -> tuple[list[InvoiceData], ValidationResult, ShippingDecision]:
    """
    Determine shipping date from a single invoice file.
    
    Args:
        invoice_file: Path to invoice file
        
    Returns:
        Tuple of (invoices, validation_result, decision)
        
    Raises:
        ValueError: If validation fails or input is invalid
    """
    try:
        invoices = [extract_invoice_data(invoice_file)]
    except Exception as e:
        LOGGER.error("Failed to extract invoice data: %s", e)
        raise ValueError(f"Failed to process invoice file: {e}") from e
    
    try:
        validation: ValidationResult = validate_invoices(invoices)
    except Exception as e:
        LOGGER.error("Validation error: %s", e)
        raise ValueError(f"Validation failed: {e}") from e
    
    if validation.errors:
        LOGGER.error("Validation failed with errors: %s", validation.errors)
        raise ValueError("Validation failed for invoice input") from None
    
    try:
        decision: ShippingDecision = resolve_shipping_date(invoices)
    except Exception as e:
        LOGGER.error("Failed to resolve shipping date: %s", e)
        raise ValueError(f"Failed to determine shipping date: {e}") from e
    
    return invoices, validation, decision


def validate_invoices(invoices: list[InvoiceData]) -> ValidationResult:
    """
    Validate invoice data.
    
    Args:
        invoices: List of invoice data objects
        
    Returns:
        ValidationResult with errors and warnings
    """
    errors: list[str] = []
    warnings: list[str] = []
    
    if len(invoices) == 0:
        errors.append("No invoices provided")
        return ValidationResult(errors=errors, warnings=warnings)
    
    for idx, invoice in enumerate(invoices):
        # Check for missing required fields
        if not invoice.invoice_number:
            errors.append(f"Invoice {idx + 1}: Missing invoice number")
        
        if not invoice.shipping_id:
            errors.append(f"Invoice {idx + 1}: Missing shipping ID")
        
        # Validate date constraints
        if invoice.earliest_ship_date and invoice.latest_ship_date:
            if invoice.earliest_ship_date > invoice.latest_ship_date:
                errors.append(
                    f"Invoice {idx + 1}: Earliest ship date ({invoice.earliest_ship_date}) "
                    f"is after latest ship date ({invoice.latest_ship_date})"
                )
        
        # Validate ship by date against constraints
        if invoice.ship_by_date:
            if invoice.ship_by_date < invoice.earliest_ship_date:
                warnings.append(
                    f"Invoice {idx + 1}: Ship by date ({invoice.ship_by_date}) is before earliest "
                    f"ship date ({invoice.earliest_ship_date})"
                )
    
    return ValidationResult(errors=errors, warnings=warnings)
