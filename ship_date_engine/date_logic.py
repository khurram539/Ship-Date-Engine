from __future__ import annotations

from datetime import date

from .models import InvoiceData, ShippingDecision


def _priority_invoice(invoices: list[InvoiceData]) -> InvoiceData:
    return sorted(
        invoices,
        key=lambda inv: (inv.priority, inv.invoice_date or date.max, inv.source_path),
    )[0]


def resolve_shipping_date(invoices: list[InvoiceData]) -> ShippingDecision:
    priority_invoice = _priority_invoice(invoices)
    conflicts: list[str] = []
    explanation: list[str] = []

    earliest_candidates = [i.earliest_ship_date for i in invoices if i.earliest_ship_date]
    invoice_date_candidates = [i.invoice_date for i in invoices if i.invoice_date]
    if earliest_candidates:
        earliest = max(earliest_candidates)
        explanation.append(
            f"Earliest ship date chosen as the latest earliest-date constraint: {earliest.isoformat()}."
        )
    elif invoice_date_candidates:
        earliest = max(invoice_date_candidates)
        explanation.append(
            f"No explicit earliest ship date provided; using latest invoice date: {earliest.isoformat()}."
        )
    else:
        earliest = date.today()
        explanation.append("No date constraints found; defaulted earliest ship date to today.")

    latest_candidates = [i.latest_ship_date for i in invoices if i.latest_ship_date]
    ship_by_candidates = [i.ship_by_date for i in invoices if i.ship_by_date]
    all_latest = [*latest_candidates, *ship_by_candidates]
    if all_latest:
        latest = min(all_latest)
        explanation.append(
            f"Latest allowable ship date chosen as strictest latest/ship-by constraint: {latest.isoformat()}."
        )
    else:
        latest = earliest
        explanation.append("No latest constraints provided; using earliest date as latest allowable date.")

    po_values = {i.po_number for i in invoices if i.po_number}
    if len(po_values) > 1:
        conflicts.append(f"Conflicting PO numbers {sorted(po_values)}; using priority invoice value.")

    carrier_values = {i.carrier for i in invoices if i.carrier}
    if len(carrier_values) > 1:
        conflicts.append(f"Conflicting carriers {sorted(carrier_values)}; using priority invoice value.")

    ship_by_values = {i.ship_by_date for i in invoices if i.ship_by_date}
    if len(ship_by_values) > 1:
        conflicts.append("Conflicting ship-by dates found; using priority invoice ship-by date.")

    target = priority_invoice.ship_by_date or earliest
    explanation.append(
        f"Target date selected from priority invoice ({priority_invoice.source_path}) as {target.isoformat()}."
    )

    if target < earliest:
        final_date = earliest
        conflicts.append("Priority target date was before earliest allowable date; clamped to earliest.")
    elif target > latest:
        final_date = latest
        conflicts.append("Priority target date was after latest allowable date; clamped to latest.")
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
