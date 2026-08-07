# Ship Date Engine - Test Utilities and Fixtures
"""
Utility functions and fixtures for testing Ship Date Engine.
"""

import json
import tempfile
from pathlib import Path

import pytest

from ship_date_engine.config import Config
from ship_date_engine.extraction import extract_invoice_data
from ship_date_engine.models import ShippingDecision, ValidationResult


class TestUtilities:
    """Utility class for creating test files."""
    
    @staticmethod
    def create_temp_file(content: str, suffix: str = ".txt") -> Path:
        """Create a temporary file with the given content."""
        fd, path = tempfile.mkstemp(suffix=suffix)
        try:
            with open(path, 'w') as f:
                f.write(content)
            return Path(path)
        except Exception:
            os.close(fd)
            raise
    
    @staticmethod
    def create_invoice_file(
        invoice_number: str,
        shipping_id: str | None = None,
        po_number: str | None = None,
        earliest_ship_date: str | None = None,
        latest_ship_date: str | None = None,
        ship_by_date: str | None = None,
        carrier: str | None = None,
        priority: int = 100,
    ) -> Path:
        """Create a test invoice file with specified fields."""
        lines = [
            f"Invoice Number: {invoice_number}",
            f"Shipping ID: {shipping_id or 'N/A'}",
            f"PO Number: {po_number or 'N/A'}",
        ]
        
        if earliest_ship_date:
            lines.append(f"Earliest Ship Date: {earliest_ship_date}")
        if latest_ship_date:
            lines.append(f"Latest Ship Date: {latest_ship_date}")
        if ship_by_date:
            lines.append(f"Ship By Date: {ship_by_date}")
        if carrier:
            lines.append(f"Carrier: {carrier}")
        lines.append(f"Priority: {priority}")
        
        return TestUtilities.create_temp_file("\n".join(lines))
    
    @staticmethod
    def load_invoice(content: str) -> dict:
        """Load and parse invoice content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(content)
            f.flush()
            return extract_invoice_data(f.name).model_dump()


class SampleInvoiceData:
    """Sample invoice data for testing."""
    
    BASIC_INVOICE = """Invoice Number: INV-001
Shipping ID: 12345
PO Number: PO-2024-001
Earliest Ship Date: 2026-08-07
Latest Ship Date: 2026-08-14
Ship By Date: 2026-08-12
Carrier: UPS
Priority: 50
"""
    
    INVOICE_WITH_CONFLICTS = """Invoice Number: INV-002
Shipping ID: 67890
PO Number: PO-2024-002
Earliest Ship Date: 2026-08-15
Latest Ship Date: 2026-08-20
Ship By Date: 2026-08-18
Carrier: FedEx
Priority: 75
"""
    
    INVOICE_MISSING_FIELDS = """Invoice Number: INV-003
Shipping ID: 11111
Earliest Ship Date: 2026-08-10
Priority: 100
"""
