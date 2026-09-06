from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ship_date_engine.engine import determine_shipping_date
from ship_date_engine.output import to_json_output, to_text_output


class ShipDateEngineTests(unittest.TestCase):
    def _write_temp(self, content: str) -> str:
        f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
        f.write(content)
        f.flush()
        f.close()
        self.addCleanup(lambda: Path(f.name).unlink(missing_ok=True))
        return f.name

    def test_resolves_priority_and_constraints(self):
        a = self._write_temp(
            "\n".join(
                [
                    "Invoice Number: INV-1001",
                    "Invoice Date: 2026-05-01",
                    "PO Number: PO-500",
                    "Earliest Ship Date: 2026-05-10",
                    "Latest Ship Date: 2026-05-20",
                    "Ship By Date: 2026-05-18",
                    "Carrier: UPS",
                    "Priority: 2",
                ]
            )
        )
        b = self._write_temp(
            "\n".join(
                [
                    "Invoice Number: INV-1002",
                    "Invoice Date: 2026-05-03",
                    "PO Number: PO-500",
                    "Earliest Ship Date: 2026-05-12",
                    "Latest Ship Date: 2026-05-19",
                    "Ship By Date: 2026-05-17",
                    "Carrier: UPS",
                    "Priority: 1",
                ]
            )
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
            "\n".join(
                [
                    "Invoice Number: INV-2001",
                    "Earliest Ship Date: 2026-06-20",
                    "Latest Ship Date: 2026-06-10",
                ]
            )
        )
        b = self._write_temp("Invoice Number: INV-2002")

        with self.assertRaises(ValueError):
            determine_shipping_date(a, b)


if __name__ == "__main__":
    unittest.main()
