from __future__ import annotations

import argparse
import cgi
import html
import json
import re
import shutil
import tempfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .ai_assist import generate_bedrock_insight
from .engine import determine_shipping_date_single
from .extraction import lookup_shipping_date_record_by_id, research_order_id_in_workbook
from .output import to_json_output, to_text_output


RECORDS_PATH = Path(tempfile.gettempdir()) / "ship_date_engine_records.json"
UPLOADS_DIR = Path(tempfile.gettempdir()) / "ship_date_engine_uploads"


HTML_PAGE = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Ship Date Engine</title>
  <style>
    :root { --bg:#f6f8fb; --card:#ffffff; --text:#0f172a; --muted:#475569; --accent:#0f766e; --border:#dbe4ee; }
    * { box-sizing: border-box; }
    body { margin: 0; padding: 24px; font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(160deg, #eef6ff 0%, #f7f9fc 60%, #eefcf8 100%); color: var(--text); }
    .wrap { max-width: 1100px; margin: 0 auto; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 18px; box-shadow: 0 8px 24px rgba(2, 6, 23, 0.06); }
        .owner-banner { display: flex; align-items: center; gap: 14px; margin-bottom: 10px; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 10px; background: linear-gradient(90deg, #fff 0%, #f8fafc 100%); }
        .owner-mark { width: 56px; height: 56px; flex: 0 0 56px; }
        .owner-text { font-size: 14px; color: #334155; letter-spacing: 0.02em; }
        .owner-text strong { color: #0f172a; }
        .site-footer { margin-top: 14px; border-top: 1px solid #e2e8f0; padding-top: 12px; color: #334155; font-size: 13px; }
        .site-footer .brand { font-weight: 700; color: #0f172a; }
        .site-footer .disclaimer { margin-top: 8px; line-height: 1.5; }
    h1 { margin-top: 0; margin-bottom: 8px; }
    p { color: var(--muted); }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
        input[type="text"] { width: 100%; border: 1px solid var(--border); border-radius: 10px; padding: 10px; }
    button { margin-top: 12px; background: var(--accent); color: #fff; border: 0; border-radius: 10px; padding: 10px 14px; font-size: 14px; cursor: pointer; }
    .result { margin-top: 14px; }
    pre { white-space: pre-wrap; word-wrap: break-word; background: #0b1220; color: #dbeafe; border-radius: 10px; padding: 12px; overflow: auto; }
        .error pre { background: #3f0d10; color: #fee2e2; }
        .lookup-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 8px; margin-bottom: 12px; }
        .lookup-pill { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px; }
        .lookup-pill .label { color: #64748b; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }
        .lookup-pill .value { color: #0f172a; font-weight: 600; margin-top: 3px; word-break: break-word; }
        .lookup-table { width: 100%; border-collapse: collapse; margin-top: 8px; }
        .lookup-table th, .lookup-table td { border: 1px solid #e2e8f0; padding: 8px 10px; text-align: left; vertical-align: top; }
        .lookup-table th { width: 180px; background: #f8fafc; color: #334155; font-weight: 600; }
        .lookup-hits { margin-top: 8px; padding-left: 18px; }
        .lookup-hits li { margin-bottom: 6px; color: #0f172a; }
        .tabs { display: flex; gap: 8px; margin-bottom: 14px; }
        .tab-btn { border: 1px solid #cbd5e1; background: #f8fafc; color: #0f172a; border-radius: 8px; padding: 8px 12px; cursor: pointer; font-weight: 600; }
        .tab-btn.active { background: #0f766e; color: #ffffff; border-color: #0f766e; }
        .tab-panel { display: none; }
        .tab-panel.active { display: block; }
        .history-table { width: 100%; border-collapse: collapse; margin-top: 8px; }
        .history-table th, .history-table td { border: 1px solid #e2e8f0; padding: 8px 10px; text-align: left; vertical-align: top; }
        .history-table th { background: #f8fafc; color: #334155; font-weight: 600; }
        .history-link { color: #0f766e; text-decoration: none; font-weight: 600; }
        .history-link:hover { text-decoration: underline; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main class=\"wrap\">
    <section class=\"card\">
            <div class="owner-banner" role="img" aria-label="Kaytheon LLC ownership logo">
                <svg class="owner-mark" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                    <rect x="14" y="24" width="24" height="52" rx="2" fill="#000000"/>
                    <path d="M38 50 C50 50, 52 38, 66 24 L86 24 C72 33, 66 42, 60 50 C66 58, 72 67, 86 76 L66 76 C52 62, 50 50, 38 50 Z" fill="#f7c044"/>
                    <circle cx="38" cy="50" r="11" fill="#f7c044"/>
                </svg>
                <div class="owner-text"><strong>Kaytheon LLC</strong></div>
            </div>
      <h1>Ship Date Engine</h1>
                        <p>Upload one invoice file (TXT, XML, XLSX, XLS) and optionally enter a Shipping/Order ID for deep lookup.</p>
            <div class="tabs">
                <button type="button" class="tab-btn active" id="tab-btn-lookup" onclick="switchTab('lookup')">Lookup</button>
                <button type="button" class="tab-btn" id="tab-btn-history" onclick="switchTab('history')">Recent Lookups</button>
            </div>
            <section class="tab-panel active" id="tab-lookup">
            <form id="lookup-form" method="post" action="/" enctype="multipart/form-data">
                <input type="hidden" name="action" value="compute" />
                <div>
                    <h3>Invoice File</h3>
                    <input type="file" name="invoice_file" accept=".txt,.xml,.xlsx,.xls,.pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp" />
        </div>
                <div>
                    <h3>Shipping ID</h3>
                    <input type="text" name="shipping_id" list="shipping-id-suggestions" value="__SHIPPING_ID__" placeholder="e.g. SHIP-2026-0042" />
                    <datalist id="shipping-id-suggestions">
                        __SHIPPING_ID_OPTIONS__
                    </datalist>
                </div>
                <div style="margin-top:10px;">
                    <label>
                        <input type="checkbox" name="enable_ai" __ENABLE_AI__ /> Enable Bedrock AI Assist
                    </label>
                </div>
        <button type=\"submit\">Calculate Shipping Date</button>
      </form>
    __RESULT__
                        </section>
                        <section class="tab-panel" id="tab-history">
                                <h3>Recent Shipping/Order Lookups</h3>
                                __HISTORY_TABLE__
                        </section>
                        <footer class="site-footer">
                            <div class="disclaimer">
                                Disclaimer: This application is owned by Kaytheon LLC. It provides operational estimates and lookup assistance only, may be updated at any time, and does not replace your official source systems. Always verify shipping dates and business decisions before acting.
                            </div>
                        </footer>
    </section>
  </main>
    <script>
        function switchTab(name) {
            const lookupPanel = document.getElementById('tab-lookup');
            const historyPanel = document.getElementById('tab-history');
            const lookupBtn = document.getElementById('tab-btn-lookup');
            const historyBtn = document.getElementById('tab-btn-history');

            if (name === 'history') {
                historyPanel.classList.add('active');
                lookupPanel.classList.remove('active');
                historyBtn.classList.add('active');
                lookupBtn.classList.remove('active');
            } else {
                lookupPanel.classList.add('active');
                historyPanel.classList.remove('active');
                lookupBtn.classList.add('active');
                historyBtn.classList.remove('active');
            }
        }

        function useHistoryId(orderId) {
            const shippingInput = document.querySelector('input[name="shipping_id"]');
            const lookupForm = document.getElementById('lookup-form');
            if (shippingInput) {
                shippingInput.value = orderId;
            }
            switchTab('lookup');
            if (lookupForm) {
                lookupForm.submit();
                return;
            }
            if (shippingInput) {
                shippingInput.focus();
            }
        }
    </script>
</body>
</html>
"""


def _render(
    shipping_id: str = "",
    result_block: str = "",
    enable_ai: bool = True,
) -> bytes:
    history_table = _render_history_table()
    shipping_id_options = _render_shipping_id_options()
    html_doc = (
        HTML_PAGE.replace("__SHIPPING_ID__", html.escape(shipping_id))
        .replace("__ENABLE_AI__", "checked" if enable_ai else "")
        .replace("__SHIPPING_ID_OPTIONS__", shipping_id_options)
        .replace("__HISTORY_TABLE__", history_table)
        .replace("__RESULT__", result_block)
    )
    return html_doc.encode("utf-8")


def _load_records() -> dict[str, dict[str, str]]:
    if not RECORDS_PATH.exists():
        return {}
    try:
        payload = json.loads(RECORDS_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_records(records: dict[str, dict[str, str]]) -> None:
    RECORDS_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")


def _record_shipping_date(shipping_id: str, final_shipping_date: str, source_path: str) -> None:
    _record_shipping_date_with_file(shipping_id, final_shipping_date, source_path, None)


def _record_shipping_date_with_file(
    shipping_id: str,
    final_shipping_date: str,
    source_path: str,
    saved_file_path: str | None,
) -> None:
    if not shipping_id.strip():
        return
    records = _load_records()
    existing = records.get(shipping_id.strip(), {})
    records[shipping_id.strip()] = {
        "final_shipping_date": final_shipping_date,
        "source_path": source_path,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "saved_file_path": saved_file_path or existing.get("saved_file_path", ""),
    }
    _save_records(records)


def _record_saved_file(shipping_id: str, saved_file_path: str) -> None:
    if not shipping_id.strip() or not saved_file_path.strip():
        return

    records = _load_records()
    existing = records.get(shipping_id.strip(), {})
    records[shipping_id.strip()] = {
        "final_shipping_date": existing.get("final_shipping_date", ""),
        "source_path": existing.get("source_path", saved_file_path),
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "saved_file_path": saved_file_path,
    }
    _save_records(records)


def _sanitize_id_for_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned[:80] or "lookup"


def _escape_js_single_quoted(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _persist_uploaded_file(file_path: Path, shipping_id: str) -> Path:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = _sanitize_id_for_filename(shipping_id)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    suffix = file_path.suffix or ".dat"
    target = UPLOADS_DIR / f"{safe_id}_{timestamp}{suffix}"
    shutil.copy2(file_path, target)
    return target


def _iter_saved_upload_files(limit: int = 50) -> list[Path]:
    if not UPLOADS_DIR.exists():
        return []

    files = [path for path in UPLOADS_DIR.iterdir() if path.is_file()]
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return files[:limit]


def _lookup_shipping_date(shipping_id: str) -> dict[str, str] | None:
    if not shipping_id.strip():
        return None
    return _load_records().get(shipping_id.strip())


def _render_history_table() -> str:
    records = _load_records()
    if not records:
        return "<p>No lookup history yet.</p>"

    rows: list[tuple[str, dict[str, str]]] = sorted(
        records.items(),
        key=lambda item: item[1].get("updated_at", ""),
        reverse=True,
    )

    body_rows = []
    for shipping_id, payload in rows[:100]:
        safe_id = html.escape(shipping_id)
        safe_id_js = _escape_js_single_quoted(shipping_id)
        body_rows.append(
            "<tr>"
            f"<td><a href=\"#\" class=\"history-link\" onclick=\"useHistoryId('{safe_id_js}'); return false;\">{safe_id}</a></td>"
            f"<td>{html.escape(payload.get('final_shipping_date', 'N/A'))}</td>"
            f"<td>{html.escape(payload.get('source_path', 'N/A'))}</td>"
            f"<td>{html.escape(payload.get('updated_at', 'N/A'))}</td>"
            "</tr>"
        )

    return (
        "<table class=\"history-table\">"
        "<thead><tr><th>Shipping/Order ID</th><th>Shipping Date</th><th>Source</th><th>Last Updated</th></tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )


def _render_shipping_id_options() -> str:
    records = _load_records()
    if not records:
        return ""

    rows: list[tuple[str, dict[str, str]]] = sorted(
        records.items(),
        key=lambda item: item[1].get("updated_at", ""),
        reverse=True,
    )
    options = [f"<option value=\"{html.escape(shipping_id)}\"></option>" for shipping_id, _ in rows[:200]]
    return "".join(options)


def _build_lookup_result_from_file(invoice_path: Path, shipping_id: str, saved_file_path: Path | None = None) -> str:
    record = lookup_shipping_date_record_by_id(str(invoice_path), shipping_id)
    if not record:
        cached = _lookup_shipping_date(shipping_id)
        if cached:
            found_date = cached.get("final_shipping_date")
            source_line = (
                f"Source: {html.escape(str(saved_file_path))} (saved file)"
                if saved_file_path is not None
                else "Source: cached record"
            )
            return (
                "<section class=\"result\">"
                "<h3>Shipping ID Lookup</h3>"
                f"<pre>Shipping ID: {html.escape(shipping_id)}\n"
                f"Shipping Date: {html.escape(found_date or 'N/A')}\n"
                f"{source_line}</pre>"
                "</section>"
            )

        return (
            "<section class=\"result error\">"
            "<h3>Shipping ID Lookup</h3>"
            "<pre>No shipping date found for this Shipping/Order ID across workbook tabs.\n"
            "Check that the workbook includes an Order/Shipping ID column and a Shipping Date column.</pre>"
            "</section>"
        )

    if record.get("status") == "ambiguous":
        return (
            "<section class=\"result error\">"
            "<h3>Shipping ID Lookup</h3>"
            f"<pre>Ambiguous results for Shipping ID {html.escape(shipping_id)}.\n"
            f"Candidate dates: {html.escape(record.get('candidates', 'N/A'))}.\n"
            "Please provide a more specific file/filter.</pre>"
            "</section>"
        )

    found_date = record.get("shipping_date", "N/A")
    source_sheet = record.get("sheet", "unknown")
    details = record.get("details", "")

    _record_shipping_date_with_file(
        shipping_id,
        found_date,
        str(saved_file_path or invoice_path),
        str(saved_file_path) if saved_file_path is not None else None,
    )

    details_rows = ""
    if details:
        def _pretty_label(raw: str) -> str:
            cleaned = raw.replace("_", " ").strip()
            return " ".join(part.capitalize() for part in cleaned.split())

        parts = [p.strip() for p in details.split("|") if p.strip()]
        rendered_rows: list[str] = []
        field_index = 1
        for part in parts:
            if "=" in part:
                key, value = part.split("=", 1)
                rendered_rows.append(
                    f"<tr><th>{html.escape(_pretty_label(key.strip()))}</th><td>{html.escape(value.strip())}</td></tr>"
                )
            else:
                rendered_rows.append(
                    f"<tr><th>Field {field_index}</th><td>{html.escape(part)}</td></tr>"
                )
                field_index += 1
        details_rows = "".join(rendered_rows)

    details_block = (
        "<h4>Matched Row Details</h4>"
        f"<table class=\"lookup-table\">{details_rows}</table>"
        if details_rows
        else ""
    )

    return (
        "<section class=\"result\">"
        "<h3>Shipping ID Lookup</h3>"
        "<div class=\"lookup-grid\">"
        "<div class=\"lookup-pill\"><div class=\"label\">Shipping ID</div>"
        f"<div class=\"value\">{html.escape(shipping_id)}</div></div>"
        "<div class=\"lookup-pill\"><div class=\"label\">Shipping Date</div>"
        f"<div class=\"value\">{html.escape(found_date)}</div></div>"
        "<div class=\"lookup-pill\"><div class=\"label\">Source Tab</div>"
        f"<div class=\"value\">{html.escape(source_sheet)}</div></div>"
        "</div>"
        f"{details_block}"
        "</section>"
    )


def _build_lookup_result_from_cache(shipping_id: str) -> str:
    cached = _lookup_shipping_date(shipping_id)
    if not cached:
        # Fallback for new Shipping IDs: search the most recent saved uploads.
        for candidate in _iter_saved_upload_files():
            record = lookup_shipping_date_record_by_id(str(candidate), shipping_id)
            if record:
                return _build_lookup_result_from_file(candidate, shipping_id, candidate)

        return (
            "<section class=\"result error\">"
            "<h3>Shipping ID Lookup</h3>"
            "<pre>No record found for this Shipping/Order ID in cached results or saved uploads. Upload a workbook to index this ID.</pre>"
            "</section>"
        )

    saved_path = cached.get("saved_file_path", "").strip()
    if saved_path and Path(saved_path).exists():
        return _build_lookup_result_from_file(Path(saved_path), shipping_id, Path(saved_path))

    found_date = cached.get("final_shipping_date", "N/A")
    source_path = cached.get("source_path", "cached")
    updated_at = cached.get("updated_at", "N/A")

    return (
        "<section class=\"result\">"
        "<h3>Shipping ID Lookup</h3>"
        "<div class=\"lookup-grid\">"
        "<div class=\"lookup-pill\"><div class=\"label\">Shipping ID</div>"
        f"<div class=\"value\">{html.escape(shipping_id)}</div></div>"
        "<div class=\"lookup-pill\"><div class=\"label\">Shipping Date</div>"
        f"<div class=\"value\">{html.escape(found_date)}</div></div>"
        "<div class=\"lookup-pill\"><div class=\"label\">Source</div>"
        f"<div class=\"value\">{html.escape(source_path)}</div></div>"
        "</div>"
        "<h4>Lookup Details</h4>"
        "<table class=\"lookup-table\">"
        f"<tr><th>Last Updated</th><td>{html.escape(updated_at)}</td></tr>"
        f"<tr><th>Lookup Mode</th><td>Cached record (no re-upload required)</td></tr>"
        "</table>"
        "</section>"
    )


def _format_result(invoices, validation, decision, enable_ai: bool, shipping_id: str = "") -> str:
    text_output = to_text_output(invoices, validation, decision)
    json_output = to_json_output(invoices, validation, decision)

    effective_shipping_id = shipping_id.strip() or (invoices[0].shipping_id or "").strip()
    if effective_shipping_id:
        _record_shipping_date(
            effective_shipping_id,
            decision.final_shipping_date.strftime("%m-%d-%Y"),
            invoices[0].source_path,
        )

    ai_block = ""
    if enable_ai:
        try:
            insight = generate_bedrock_insight(invoices, validation, decision)
            ai_block = (
                "<h3>AI Assist (AWS Bedrock)</h3>"
                f"<pre>{html.escape(insight)}</pre>"
            )
        except Exception as exc:  # noqa: BLE001
            ai_block = (
                "<h3>AI Assist (AWS Bedrock)</h3>"
                f"<pre>AI assist unavailable: {html.escape(str(exc))}</pre>"
            )

    shipping_id_block = (
        f"<p><strong>Shipping ID:</strong> {html.escape(effective_shipping_id)}</p>"
        if effective_shipping_id
        else ""
    )

    return (
        "<section class=\"result\">"
        f"{shipping_id_block}"
        "<h3>Text Output</h3>"
        f"<pre>{html.escape(text_output)}</pre>"
        "<h3>JSON Output</h3>"
        f"<pre>{html.escape(json.dumps(json.loads(json_output), indent=2))}</pre>"
        f"{ai_block}"
        "</section>"
    )


def _build_result_from_path(invoice_path: Path, enable_ai: bool = False, shipping_id: str = "") -> str:
    try:
        invoices, validation, decision = determine_shipping_date_single(str(invoice_path))
        return _format_result(invoices, validation, decision, enable_ai, shipping_id)
    except Exception as exc:  # noqa: BLE001
        return (
            "<section class=\"result error\">"
            "<h3>Error</h3>"
            f"<pre>{html.escape(str(exc))}</pre>"
            "</section>"
        )


def _write_uploaded_file(file_field: cgi.FieldStorage, prefix: str) -> Path:
    original_name = file_field.filename or "uploaded.txt"
    suffix = Path(original_name).suffix or ".txt"
    data = file_field.file.read() if file_field.file else b""

    temp = tempfile.NamedTemporaryFile("wb", suffix=suffix, prefix=prefix, delete=False)
    try:
        temp.write(data)
        temp.flush()
    finally:
        temp.close()
    return Path(temp.name)


class ShipDateWebHandler(BaseHTTPRequestHandler):
    def _send_html(self, payload: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/":
            self._send_html(_render("", "", True), status=404)
            return
        self._send_html(_render("", "", True))

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/":
            self._send_html(_render("", "", True), status=404)
            return

        content_type = self.headers.get("Content-Type", "")
        enable_ai = True

        if "multipart/form-data" in content_type:
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": content_type,
                },
            )

            invoice_file = form["invoice_file"] if "invoice_file" in form else None
            enable_ai = form.getfirst("enable_ai", "") == "on"
            shipping_id = form.getfirst("shipping_id", "")

            file_path = None

            try:
                if invoice_file is not None and getattr(invoice_file, "filename", None):
                    file_path = _write_uploaded_file(invoice_file, "invoice_")

                if file_path is not None:
                    if shipping_id.strip():
                        saved_path = _persist_uploaded_file(file_path, shipping_id)
                        _record_saved_file(shipping_id, str(saved_path))
                        result = _build_lookup_result_from_file(file_path, shipping_id, saved_path)
                        self._send_html(_render(shipping_id, result, enable_ai))
                        return

                    result = _build_result_from_path(file_path, enable_ai, shipping_id)
                    self._send_html(_render(shipping_id, result, enable_ai))
                    return

                if shipping_id.strip():
                    result = _build_lookup_result_from_cache(shipping_id)
                    self._send_html(_render(shipping_id, result, enable_ai))
                    return

                error = (
                    "<section class=\"result error\">"
                    "<h3>Error</h3>"
                    "<pre>Please upload one file to process or include a Shipping/Order ID for cached lookup.</pre>"
                    "</section>"
                )
                self._send_html(_render(shipping_id, error, enable_ai), status=400)
                return
            finally:
                if file_path is not None:
                    file_path.unlink(missing_ok=True)

        error = (
            "<section class=\"result error\">"
            "<h3>Error</h3>"
            "<pre>Unsupported request format. Please submit using the upload form.</pre>"
            "</section>"
        )
        self._send_html(_render("", error, True), status=400)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local web UI for Ship Date Engine")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), ShipDateWebHandler)
    print(f"Ship Date Engine web UI running at http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
