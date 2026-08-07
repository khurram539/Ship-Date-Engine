"""
Comprehensive tests for Ship Date Engine core functionality.

Coverage targets:
- Invoice data extraction and validation
- Shipping date resolution logic
- Conflict detection and handling
- Error cases and edge conditions
"""

import json
from pathlib import Path
from datetime import date

import pytest

from ship_date_engine.config import Config
from ship_date_engine.engine_enhanced import determine_shipping_date, determine_shipping_date_single
from ship_date_engine.models import ShippingDecision, ValidationResult
from ship_date_engine.output import to_json_output, to_text_output
from tests.conftest import TestUtilities, SampleInvoiceData


class TestShippingDateEngine:
    """Tests for the core shipping date determination logic."""
    
    def test_resolves_priority_and_constraints(self):
        """Test that priority invoice wins and constraints are respected."""
        # Create two invoices with different priorities
        file_a = TestUtilities.create_invoice_file(
            "INV-1001",
            shipping_id="12345",
            earliest_ship_date="2026-05-10",
            latest_ship_date="2026-05-20",
            ship_by_date="2026-05-18",
            priority=2
        )
        
        file_b = TestUtilities.create_invoice_file(
            "INV-1002",
            shipping_id="67890",
            earliest_ship_date="2026-05-12",
            latest_ship_date="2026-05-19",
            ship_by_date="2026-05-17",
            priority=1  # Higher priority
        )
        
        invoices, validation, decision = determine_shipping_date(str(file_a), str(file_b))
        
        # Validate no errors
        assert not validation.errors
        assert len(validation.warnings) == 0
        
        # Check date resolution
        assert decision.earliest_ship_date == date(2026, 5, 12)
        assert decision.latest_allowable_ship_date == date(2026, 5, 17)
        assert decision.final_shipping_date == date(2026, 5, 17)
    
    def test_missing_fields_handled_gracefully(self):
        """Test that missing fields don't cause failures."""
        file_a = TestUtilities.create_invoice_file(
            "INV-1003",
            shipping_id="N/A",  # Missing
            earliest_ship_date="2026-08-10",  # Only this date
            priority=100
        )
        
        file_b = TestUtilities.create_invoice_file(
            "INV-1004",
            shipping_id="N/A",
            priority=50
        )
        
        invoices, validation, decision = determine_shipping_date(str(file_a), str(file_b))
        
        assert not validation.errors
        # Should default to earliest date when no constraints exist
        assert decision.earliest_ship_date is not None
    
    def test_conflicting_po_numbers(self):
        """Test handling of conflicting PO numbers."""
        file_a = TestUtilities.create_invoice_file(
            "INV-1005",
            shipping_id="A123",
            po_number="PO-A",
            priority=2
        )
        
        file_b = TestUtilities.create_invoice_file(
            "INV-1006",
            shipping_id="B456",
            po_number="PO-B",  # Different PO
            priority=1
        )
        
        invoices, validation, decision = determine_shipping_date(str(file_a), str(file_b))
        
        # Conflicting PO should generate warning
        assert not validation.errors
        assert any("conflict" in w.lower() for w in validation.warnings)
    
    def test_date_clamping(self):
        """Test that dates are clamped to valid range."""
        file_a = TestUtilities.create_invoice_file(
            "INV-1007",
            shipping_id="C789",
            earliest_ship_date="2026-09-01",  # Way in future
            latest_ship_date="2026-08-05",  # In past (relative to today)
            priority=1
        )
        
        invoices, validation, decision = determine_shipping_date(
            str(file_a),
            str(file_a)  # Same file for both inputs
        )
        
        assert not validation.errors
        # Date should be clamped to valid range
        assert date(2026, 8, 5) <= decision.final_shipping_date <= date(2026, 9, 1)


class TestOutputFormatting:
    """Tests for output formatting functions."""
    
    def test_json_output_structure(self):
        """Test JSON output has correct structure."""
        # Create minimal decision
        from ship_date_engine.models import ShippingDecision, ValidationResult
        decision = ShippingDecision(
            final_shipping_date=date(2026, 8, 7),
            earliest_ship_date=date(2026, 8, 5),
            latest_allowable_ship_date=date(2026, 8, 14),
            explanation=["Test explanation"],
            conflicts=[],
            selected_priority_invoice="test-invoice.txt"
        )
        
        validation = ValidationResult()
        
        json_output = to_json_output([], validation, decision)
        data = json.loads(json_output)
        
        assert "invoices" in data
        assert "validation" in data
        assert "decision" in data
        assert "final_shipping_date" in data["decision"]
    
    def test_text_output_clarification(self):
        """Test text output is human-readable."""
        from ship_date_engine.models import ShippingDecision, ValidationResult
        decision = ShippingDecision(
            final_shipping_date=date(2026, 8, 7),
            earliest_ship_date=None,
            latest_allowable_ship_date=None,
            explanation=["Test step 1", "Test step 2"],
            conflicts=[],
            selected_priority_invoice=None
        )
        
        validation = ValidationResult()
        
        text_output = to_text_output([], validation, decision)
        
        assert "Final Shipping Date" in text_output
        assert "Explanation:" in text_output
        for step in decision.explanation:
            assert f"- {step}" in text_output


class TestConfigValidation:
    """Tests for configuration validation."""
    
    def test_config_values(self):
        """Test that config has expected values."""
        assert Config.MAX_UPLOAD_SIZE_MB > 0
        assert len(Config.ALLOWED_EXTENSIONS) >= 1
        assert Config.MAX_LINE_ITEMS > 0
        assert Config.DATE_VALID_MIN_YEAR < date.today().year
        assert Config.DATE_VALID_MAX_YEAR > date.today().year


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_invoice_files(self):
        """Test handling of empty or minimal invoice files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("")
            file_a = Path(f.name)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("\n")
            file_b = Path(f.name)
        
        # Should raise ValueError due to missing required fields
        with pytest.raises(ValueError):
            determine_shipping_date(str(file_a), str(file_b))
        
        # Cleanup
        file_a.unlink(missing_ok=True)
        file_b.unlink(missing_ok=True)
    
    def test_same_file_for_both_inputs(self):
        """Test that the same file can be used for both inputs."""
        file_content = SampleInvoiceData.BASIC_INVOICE
        file_path = TestUtilities.create_temp_file(file_content)
        
        invoices, validation, decision = determine_shipping_date(
            str(file_path),
            str(file_path)
        )
        
        assert len(invoices) == 1
        assert not validation.errors