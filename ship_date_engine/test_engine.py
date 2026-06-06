from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from ship_date_engine.engine import determine_shipping_date, determine_shipping_date_single
from ship_date_engine.output import to_json_output, to_text_output
from ship_date_engine.validation import validate_invoices
from ship_date_engine.models import InvoiceData
from ship_date_engine.date_logic import resolve_shipping_date


class _TempInvoiceMixin:
    """Helper that writes temporary text invoices and registers cleanup."""

    def _write_temp(self, content: str) -> str:
        f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
        f.write(content)
        f.flush()
        f.close()
        self.addCleanup(lambda: Path(f.name).unlink(missing_ok=True))
        return f.name


# ── Core engine tests ─────────────────────────────────────────────────────────

class TestShipDateEngine(_TempInvoiceMixin, unittest.TestCase):

    def test_resolves_priority_and_constraints(self):
        a = self._write_temp(
            "\n".join([
                "Invoice Number: INV-1001",
                "Invoice Date: 2026-05-01",
                "PO Number: PO-500",
                "Earliest Ship Date: 2026-05-10",
                "Latest Ship Date: 2026-05-20",
                "Ship By Date: 2026-05-18",
                "Carrier: UPS",
                "Priority: 2",
            ])
        )
        b = self._write_temp(
            "\n".join([
                "Invoice Number: INV-1002",
                "Invoice Date: 2026-05-03",
                "PO Number: PO-500",
                "Earliest Ship Date: 2026-05-12",
                "Latest Ship Date: 2026-05-19",
                "Ship By Date: 2026-05-17",
                "Carrier: UPS",
                "Priority: 1",
            ])
        )

        invoices, validation, decision = determine_shipping_date(a, b)
        self.assertFalse(validation.errors)
        self.assertEqual(decision.earliest_ship_date.isoformat(), "2026-05-12")
        self.assertEqual(decision.latest_allowable_ship_date.isoformat(), "2026-05-17")
        self.assertEqual(decision.final_shipping_date.isoformat(), "2026-05-17")

        payload = json.loads(to_json_output(invoices, validation, decision))
        self.assertEqual(payload["decision"]["final_shipping_date"], "2026-05-17")
        self.assertIn("Final Shipping Date", to_text_output(invoices, validation, decision))

    def test_validation_error_when_earliest_after_latest(self):
        a = self._write_temp(
            "\n".join([
                "Invoice Number: INV-2001",
                "Earliest Ship Date: 2026-06-20",
                "Latest Ship Date: 2026-06-10",
            ])
        )
        b = self._write_temp("Invoice Number: INV-2002")

        with self.assertRaises(ValueError):
            determine_shipping_date(a, b)

    def test_single_invoice_mode(self):
        """determine_shipping_date_single should work without a second file."""
        f = self._write_temp(
            "\n".join([
                "Invoice Number: INV-3001",
                "Invoice Date: 2026-07-01",
                "Earliest Ship Date: 2026-07-10",
                "Ship By Date: 2026-07-15",
            ])
        )

        invoices, validation, decision = determine_shipping_date_single(f)
        self.assertFalse(validation.errors)
        self.assertEqual(len(invoices), 1)
        self.assertEqual(decision.final_shipping_date.isoformat(), "2026-07-15")

    def test_no_dates_defaults_to_today(self):
        """When no date fields are present the decision should fall back to today."""
        a = self._write_temp("Invoice Number: INV-4001")
        b = self._write_temp("Invoice Number: INV-4002")

        invoices, validation, decision = determine_shipping_date(a, b)
        self.assertFalse(validation.errors)
        self.assertEqual(decision.final_shipping_date, date.today())

    def test_conflicting_po_numbers_produces_warning(self):
        a = self._write_temp(
            "\n".join([
                "Invoice Number: INV-5001",
                "PO Number: PO-AAA",
                "Invoice Date: 2026-08-01",
            ])
        )
        b = self._write_temp(
            "\n".join([
                "Invoice Number: INV-5002",
                "PO Number: PO-BBB",
                "Invoice Date: 2026-08-02",
            ])
        )

        invoices, validation, decision = determine_shipping_date(a, b)
        self.assertFalse(validation.errors)
        self.assertTrue(
            any("Conflicting PO" in w for w in validation.warnings),
            "Expected a conflicting-PO warning",
        )

    def test_priority_lower_number_wins(self):
        """Priority 1 beats priority 99 when ship_by dates differ."""
        a = self._write_temp(
            "\n".join([
                "Invoice Number: INV-6001",
                "Invoice Date: 2026-09-01",
                "Earliest Ship Date: 2026-09-05",
                "Ship By Date: 2026-09-20",
                "Priority: 99",
            ])
        )
        b = self._write_temp(
            "\n".join([
                "Invoice Number: INV-6002",
                "Invoice Date: 2026-09-01",
                "Earliest Ship Date: 2026-09-05",
                "Ship By Date: 2026-09-10",
                "Priority: 1",
            ])
        )

        invoices, validation, decision = determine_shipping_date(a, b)
        self.assertEqual(decision.final_shipping_date.isoformat(), "2026-09-10")


# ── Output format tests ───────────────────────────────────────────────────────

class TestOutputFormat(_TempInvoiceMixin, unittest.TestCase):

    def _make_invoices(self):
        a = self._write_temp(
            "\n".join([
                "Invoice Number: INV-OUT-01",
                "Invoice Date: 2026-10-01",
                "Earliest Ship Date: 2026-10-05",
                "Ship By Date: 2026-10-12",
            ])
        )
        b = self._write_temp(
            "\n".join([
                "Invoice Number: INV-OUT-02",
                "Invoice Date: 2026-10-02",
                "Earliest Ship Date: 2026-10-06",
                "Ship By Date: 2026-10-15",
            ])
        )
        return determine_shipping_date(a, b)

    def test_json_output_has_required_keys(self):
        invoices, validation, decision = self._make_invoices()
        payload = json.loads(to_json_output(invoices, validation, decision))
        self.assertIn("invoices", payload)
        self.assertIn("validation", payload)
        self.assertIn("decision", payload)
        for key in (
            "final_shipping_date",
            "earliest_ship_date",
            "latest_allowable_ship_date",
            "explanation",
            "conflicts",
        ):
            self.assertIn(key, payload["decision"], f"Missing key in decision: {key}")

    def test_text_output_contains_sections(self):
        invoices, validation, decision = self._make_invoices()
        text = to_text_output(invoices, validation, decision)
        for section in ("Final Shipping Date", "Earliest Ship Date", "Explanation", "Invoices"):
            self.assertIn(section, text, f"Missing section in text output: {section}")

    def test_dates_formatted_mm_dd_yyyy(self):
        invoices, validation, decision = self._make_invoices()
        text = to_text_output(invoices, validation, decision)
        # All dates in text output should be mm-dd-yyyy (not iso)
        import re
        dates = re.findall(r"\d{2}-\d{2}-\d{4}", text)
        self.assertTrue(len(dates) > 0, "Expected at least one mm-dd-yyyy date in output")


# ── Validation tests ──────────────────────────────────────────────────────────

class TestValidation(unittest.TestCase):

    def _invoice(self, **kwargs) -> InvoiceData:
        defaults = {"source_path": "test.txt"}
        defaults.update(kwargs)
        return InvoiceData(**defaults)

    def test_missing_invoice_number_warning(self):
        inv = self._invoice(invoice_date=date(2026, 1, 1))
        result = validate_invoices([inv])
        self.assertFalse(result.errors)
        self.assertTrue(any("missing invoice number" in w for w in result.warnings))

    def test_missing_po_number_warning(self):
        inv = self._invoice(invoice_number="INV-1")
        result = validate_invoices([inv])
        self.assertFalse(result.errors)
        self.assertTrue(any("missing PO number" in w for w in result.warnings))

    def test_no_dates_generates_warning(self):
        inv = self._invoice(invoice_number="INV-1", po_number="PO-1")
        result = validate_invoices([inv])
        self.assertFalse(result.errors)
        self.assertTrue(any("no date fields found" in w for w in result.warnings))

    def test_earliest_after_latest_is_error(self):
        inv = self._invoice(
            earliest_ship_date=date(2026, 6, 20),
            latest_ship_date=date(2026, 6, 10),
        )
        result = validate_invoices([inv])
        self.assertTrue(result.errors)
        self.assertFalse(result.ok)

    def test_ok_property(self):
        inv = self._invoice(
            invoice_number="INV-1",
            po_number="PO-1",
            invoice_date=date(2026, 1, 1),
        )
        result = validate_invoices([inv])
        self.assertTrue(result.ok)


# ── date_logic unit tests ─────────────────────────────────────────────────────

class TestDateLogic(unittest.TestCase):

    def _inv(self, **kwargs) -> InvoiceData:
        return InvoiceData(source_path="test.txt", **kwargs)

    def test_uses_strictest_latest_constraint(self):
        """Latest allowable date = min of all latest/ship-by dates."""
        invoices = [
            self._inv(
                invoice_date=date(2026, 3, 1),
                earliest_ship_date=date(2026, 3, 5),
                latest_ship_date=date(2026, 3, 20),
                ship_by_date=date(2026, 3, 15),
                priority=1,
            ),
            self._inv(
                invoice_date=date(2026, 3, 1),
                earliest_ship_date=date(2026, 3, 5),
                latest_ship_date=date(2026, 3, 18),
                priority=2,
            ),
        ]
        decision = resolve_shipping_date(invoices)
        # Strictest latest is min(2026-03-20, 2026-03-15, 2026-03-18) = 2026-03-15
        self.assertEqual(decision.latest_allowable_ship_date.isoformat(), "2026-03-15")

    def test_uses_latest_earliest_constraint(self):
        """Earliest allowable date = max of all earliest_ship_dates."""
        invoices = [
            self._inv(
                earliest_ship_date=date(2026, 4, 5),
                ship_by_date=date(2026, 4, 20),
                priority=1,
            ),
            self._inv(
                earliest_ship_date=date(2026, 4, 12),
                ship_by_date=date(2026, 4, 25),
                priority=2,
            ),
        ]
        decision = resolve_shipping_date(invoices)
        # Max of (2026-04-05, 2026-04-12) = 2026-04-12
        self.assertEqual(decision.earliest_ship_date.isoformat(), "2026-04-12")

    def test_clamps_target_below_latest(self):
        """If priority ship_by exceeds the latest constraint, clamp to latest."""
        invoices = [
            self._inv(
                earliest_ship_date=date(2026, 5, 1),
                latest_ship_date=date(2026, 5, 10),
                ship_by_date=date(2026, 5, 30),  # beyond latest
                priority=1,
            ),
        ]
        decision = resolve_shipping_date(invoices)
        self.assertEqual(decision.final_shipping_date.isoformat(), "2026-05-10")
        self.assertTrue(any("clamped" in c.lower() for c in decision.conflicts))


if __name__ == "__main__":
    unittest.main()
