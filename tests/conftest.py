"""Test configuration and fixtures for Ship Date Engine."""

import os
import pytest
import tempfile
from pathlib import Path
from typing import Optional


class TestUtilities:
    """Utility class for creating test files."""

    @staticmethod
    def create_temp_file(content: str, suffix: str = ".txt") -> Path:
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        with open(path, "w") as f:
            f.write(content)
        return Path(path)

    @staticmethod
    def create_invoice_file(
        invoice_number: str,
        shipping_id: Optional[str] = None,
        po_number: Optional[str] = None,
        earliest_ship_date: Optional[str] = None,
        latest_ship_date: Optional[str] = None,
        ship_by_date: Optional[str] = None,
        carrier: Optional[str] = None,
        priority: int = 100,
    ) -> Path:
        lines = [f"Invoice Number: {invoice_number}", f"Shipping ID: {shipping_id or 'N/A'}", f"PO Number: {po_number or 'N/A'}"]
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


class SampleInvoiceData:
    """Sample invoice data for testing."""

    BASIC_INVOICE = "Invoice Number: INV-001\nShipping ID: 12345\nPO Number: PO-2024-001\nEarliest Ship Date: 2026-08-07\nLatest Ship Date: 2026-08-14\nShip By Date: 2026-08-12\nCarrier: UPS\nPriority: 50\n"
    INVOICE_WITH_CONFLICTS = "Invoice Number: INV-002\nShipping ID: 67890\nPO Number: PO-2024-002\nEarliest Ship Date: 2026-08-15\nLatest Ship Date: 2026-08-20\nShip By Date: 2026-08-18\nCarrier: FedEx\nPriority: 75\n"


@pytest.fixture
def sample_invoice_a():
    return TestUtilities.create_temp_file(SampleInvoiceData.BASIC_INVOICE)


@pytest.fixture
def sample_invoice_b():
    return TestUtilities.create_temp_file(SampleInvoiceData.INVOICE_WITH_CONFLICTS)
