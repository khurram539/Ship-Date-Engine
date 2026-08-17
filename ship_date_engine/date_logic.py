"""date_logic — resolve the final shipping date from one or more InvoiceData objects.

Priority convention
-------------------
``InvoiceData.priority`` is an integer where **lower means higher priority** (think
HTTP quality values).  The default is ``100``; setting a document to ``1`` makes it
the authoritative source for resolving conflicts such as duplicate PO numbers or
conflicting ship-by dates.
"""
from __future__ import annotations

from datetime import date

from .models import InvoiceData, ShippingDecision


def _priority_invoice(invoices: list[InvoiceData]) -> InvoiceData:
    """Return the highest-priority invoice (lowest ``priority`` value).

    Ties are broken by:
    1. The invoice date (earlier date wins, i.e. more established document).
    2. The source file path (alphabetical, for deterministic results in tests).

    ``date.max`` is used as a sentinel so invoices with no date sort *after*
    those that have one.
    """
    return sorted(
        invoices,
        key=lambda inv: (inv.priority, inv.invoice_date or date.max, inv.source_path),
    )[0]


def resolve_shipping_date(invoices: list[InvoiceData]) -> ShippingDecision:
    """Compute the final shipping date from a list of invoices.

    Algorithm
    ---------
    * **Earliest allowable date** — the *latest* ``earliest_ship_date`` across all
      invoices (i.e. the strictest lower bound that satisfies every source).
      Falls back to the latest ``invoice_date``, then today.
    * **Latest allowable date** — the *earliest* ``latest_ship_date`` or
      ``ship_by_date`` across all invoices (strictest upper bound).
      Falls back to the earliest date when no upper constraint exists.
    * **Target date** — the ``ship_by_date`` of the highest-priority invoice,
      clamped into the [earliest, latest] window.
    """
    priority_invoice = _priority_invoice(invoices)
    conflicts: list[str] = []
    explanation: list[str] = []

    # ── Determine earliest allowable date ────────────────────────────────────
    earliest_candidates = [i.earliest_ship_date for i in invoices if i.earliest_ship_date]
    invoice_date_candidates = [i.invoice_date for i in invoices if i.invoice_date]

    if earliest_candidates:
        earliest = max(earliest_candidates)
        explanation.append(
            f"Earliest ship date chosen as the latest earliest-date constraint: "
            f"{earliest.isoformat()}."
        )
    elif invoice_date_candidates:
        earliest = max(invoice_date_candidates)
        explanation.append(
            f"No explicit earliest ship date provided; using latest invoice date: "
            f"{earliest.isoformat()}."
        )
    else:
        earliest = date.today()
        explanation.append("No date constraints found; defaulted earliest ship date to today.")

    # ── Determine latest allowable date ──────────────────────────────────────
    latest_candidates = [i.latest_ship_date for i in invoices if i.latest_ship_date]
    ship_by_candidates = [i.ship_by_date for i in invoices if i.ship_by_date]
    all_latest = [*latest_candidates, *ship_by_candidates]

    if all_latest:
        latest = min(all_latest)
        explanation.append(
            f"Latest allowable ship date chosen as strictest latest/ship-by constraint: "
            f"{latest.isoformat()}."
        )
    else:
        latest = earliest
        explanation.append(
            "No latest constraints provided; using earliest date as latest allowable date."
        )

    # ── Collect conflicts ─────────────────────────────────────────────────────
    po_values = {i.po_number for i in invoices if i.po_number}
    if len(po_values) > 1:
        conflicts.append(
            f"Conflicting PO numbers {sorted(po_values)}; using priority invoice value."
        )

    carrier_values = {i.carrier for i in invoices if i.carrier}
    if len(carrier_values) > 1:
        conflicts.append(
            f"Conflicting carriers {sorted(carrier_values)}; using priority invoice value."
        )

    ship_by_values = {i.ship_by_date for i in invoices if i.ship_by_date}
    if len(ship_by_values) > 1:
        conflicts.append("Conflicting ship-by dates found; using priority invoice ship-by date.")

    # ── Select target date from priority invoice ──────────────────────────────
    target = priority_invoice.ship_by_date or earliest
    explanation.append(
        f"Target date selected from priority invoice ({priority_invoice.source_path}) "
        f"as {target.isoformat()}."
    )

    # ── Clamp target into [earliest, latest] window ───────────────────────────
    if target < earliest:
        final_date = earliest
        conflicts.append(
            "Priority target date was before earliest allowable date; clamped to earliest."
        )
    elif target > latest:
        final_date = latest
        conflicts.append(
            "Priority target date was after latest allowable date; clamped to latest."
        )
    else:
        final_date = target

    explanation.append(f"Final shipping date resolved to {final_date.isoformat()}.")

    return ShippingDecision(
        final_shipping_date=final_date,
        earliest_ship_date=earliest,
        latest_allowable_ship_date=latest,
        explanation=explanation,
        conflicts=conflicts,
        selected_priority_invoice=priority_invoice.source_path,
    )
