from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .engine import determine_shipping_date
from .output import to_json_output, to_text_output


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Determine shipping date from two invoices")
    parser.add_argument("invoice_a", help="Path to first invoice (PDF, image, or text)")
    parser.add_argument("invoice_b", help="Path to second invoice (PDF, image, or text)")
    parser.add_argument("--json-out", help="Optional output path for JSON result")
    parser.add_argument("--text-out", help="Optional output path for formatted text result")
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s:%(name)s:%(message)s")

    try:
        invoices, validation, decision = determine_shipping_date(args.invoice_a, args.invoice_b)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).exception("Unable to process invoices: %s", exc)
        return 1

    json_output = to_json_output(invoices, validation, decision)
    text_output = to_text_output(invoices, validation, decision)

    if args.json_out:
        Path(args.json_out).write_text(json_output, encoding="utf-8")
    if args.text_out:
        Path(args.text_out).write_text(text_output, encoding="utf-8")

    print(text_output)
    print("\nJSON Output:\n")
    print(json_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
