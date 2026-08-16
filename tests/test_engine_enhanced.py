"""Enhanced tests for Ship Date Engine core functionality."""

import json
from pathlib import Path
from datetime import date
import pytest

from ship_date_engine.engine import determine_shipping_date, determine_shipping_date_single
from ship_date_engine.output import to_json_output, to_text_output
from tests.conftest import TestUtilities, SampleInvoiceData


@pytest.mark.integration
class TestShippingDateEngine:
    """Tests for the core shipping date determination logic."""

    def test_resolves_priority_and_constraints(self):
        """Test that priority invoice wins and constraints are respected."""
        file_a = TestUtilities.create_invoice_file(
            "INV-1001", shipping_id="12345",
            earliest_ship_date="2026-05-10", latest_ship_date="2026-05-20", ship_by_date="2026-05-18", priority=2
        )
        file_b = TestUtilities.create_invoice_file(
            "INV-1002", shipping_id="67890",
            earliest_ship_date="2026-05-12", latest_ship_date="2026-05-19", ship_by_date="2026-05-17", priority=1
        )

        invoices, validation, decision = determine_shipping_date(str(file_a), str(file_b))

        assert not validation.errors
        assert decision.earliest_ship_date == date(2026, 5, 12)
        assert decision.latest_allowable_ship_date == date(2026, 5, 17)
        assert decision.final_shipping_date == date(2026, 5, 17)

    def test_missing_fields_handled_gracefully(self):
        """Test that missing fields don't cause failures."""
        file_a = TestUtilities.create_invoice_file("INV-1003", shipping_id="N/A", earliest_ship_date="2026-08-10", priority=100)
        file_b = TestUtilities.create_invoice_file("INV-1004", shipping_id="N/A", priority=50)

        invoices, validation, decision = determine_shipping_date(str(file_a), str(file_b))

        assert not validation.errors
        assert decision.earliest_ship_date is not None


@pytest.mark.integration
class TestOutputFormatting:
    """Tests for output formatting functions."""

    def test_json_output_structure(self):
        """Test JSON output has correct structure."""
        from ship_date_engine.models import ShippingDecision, ValidationResult

        decision = ShippingDecision(
            final_shipping_date=date(2026, 8, 7), earliest_ship_date=None, latest_allowable_ship_date=None,
            explanation=["Test explanation"], conflicts=[], selected_priority_invoice="test-invoice.txt"
        )
        validation = ValidationResult()

        json_output = to_json_output([], validation, decision)
        data = json.loads(json_output)

        assert "invoices" in data
        assert "validation" in data
        assert "decision" in data
