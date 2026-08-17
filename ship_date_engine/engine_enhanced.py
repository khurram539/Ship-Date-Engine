"""
Ship Date Engine - Enhanced backend improvements

This module provides the core shipping date determination logic with 
enhanced security, validation, and performance improvements.
"""

import logging
from pathlib import Path
from typing import List

from .config import Config
from .date_logic import resolve_shipping_date
from .extraction import extract_invoice_data
from .models import ShippingDecision, ValidationResult
from .security import ValidationError, sanitize_filename, validate_file_content
from .validation import validate_invoices

logger = logging.getLogger(__name__)


def determine_shipping_date(invoice_file_a: str, invoice_file_b: str) -> tuple:
    """
    Determine shipping date from two invoice files.
    
    Args:
        invoice_file_a: Path to first invoice file
        invoice_file_b: Path to second invoice file
        
    Returns:
        Tuple of (invoices, validation_result, shipping_decision)
        
    Raises:
        ValueError: If validation fails or input is invalid
    """
    # Validate filenames for security
    try:
        sanitize_filename(Path(invoice_file_a).name)
        sanitize_filename(Path(invoice_file_b).name)
    except ValidationError as e:
        raise ValueError(f"Invalid filename: {e.message}")
    
    logger.info(f"Processing invoices: {Path(invoice_file_a).name}, {Path(invoice_file_b).name}")
    
    # Extract data from both files
    try:
        invoice_a = extract_invoice_data(invoice_file_a)
        invoice_b = extract_invoice_data(invoice_file_b)
    except Exception as e:
        raise ValueError(f"Failed to extract invoice data: {str(e)}")
    
    invoices = [invoice_a, invoice_b]
    
    # Validate extracted data
    validation_result = validate_invoices(invoices)
    if validation_result.errors:
        logger.error("Validation failed: %s", validation_result.errors)
        raise ValueError("Validation failed for invoice inputs")
    
    # Resolve shipping date decision
    shipping_decision = resolve_shipping_date(invoices)
    
    return invoices, validation_result, shipping_decision


def determine_shipping_date_single(invoice_file: str) -> tuple:
    """
    Determine shipping date from a single invoice file.
    
    Args:
        invoice_file: Path to invoice file
        
    Returns:
        Tuple of (invoices, validation_result, shipping_decision)
        
    Raises:
        ValueError: If validation fails or input is invalid
    """
    # Validate filename for security
    try:
        sanitize_filename(Path(invoice_file).name)
    except ValidationError as e:
        raise ValueError(f"Invalid filename: {e.message}")
    
    logger.info(f"Processing single invoice: {Path(invoice_file).name}")
    
    # Extract data from file
    try:
        invoice = extract_invoice_data(invoice_file)
    except Exception as e:
        raise ValueError(f"Failed to extract invoice data: {str(e)}")
    
    invoices = [invoice]
    
    # Validate extracted data
    validation_result = validate_invoices(invoices)
    if validation_result.errors:
        logger.error("Validation failed: %s", validation_result.errors)
        raise ValueError("Validation failed for invoice input")
    
    # Resolve shipping date decision
    shipping_decision = resolve_shipping_date(invoices)
    
    return invoices, validation_result, shipping_decision