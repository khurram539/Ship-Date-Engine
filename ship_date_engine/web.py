from __future__ import annotations

import argparse
import csv
import html
import io
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.parser import BytesFeedParser
from email.policy import compat32
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .ai_assist import generate_insight, generate_lookup_insight
from .config import Config
from .db import get_all_lookups, get_cached_lookup, save_lookup
from .engine import determine_shipping_date_single
from .extraction import list_shipping_date_records, lookup_shipping_date_record_by_id, research_order_id_in_workbook
from .output import to_json_output
from .security import ValidationError, sanitize_filename


# Legacy JSON store; migrated into SQLite on first read
RECORDS_PATH = Config.RECORDS_PATH
UPLOADS_DIR = Config.UPLOADS_DIR


# ── Multipart form parser (replaces deprecated cgi module) ───────────────────

@dataclass
class _FormFile:
    """Represents an uploaded file extracted from a multipart/form-data request."""
    filename: str
    data: bytes
    content_type: str = ""


def _parse_multipart(
    rfile,
    content_type: str,
    content_length: int = -1,
) -> dict[str, "str | _FormFile"]:
    """Parse a multipart/form-data request body without the deprecated :mod:`cgi` module.

    Returns a mapping of field-name → str (text fields) or :class:`_FormFile` (uploads).
    Reads exactly *content_length* bytes from *rfile* when the value is non-negative.
    """
    body = rfile.read(content_length) if content_length >= 0 else rfile.read()

    # Wrap the body in a fake top-level MIME envelope so BytesFeedParser treats
    # it as a multipart message.
    fake_header = (
        f"MIME-Version: 1.0\r\nContent-Type: {content_type}\r\n\r\n"
    ).encode("latin-1")

    parser = BytesFeedParser(policy=compat32)
    parser.feed(fake_header + body)
    msg = parser.close()

    result: dict[str, str | _FormFile] = {}
    payload = msg.get_payload()
    if not isinstance(payload, list):
        return result

    for part in payload:
        if isinstance(part, str):
            continue
        cd = part.get("Content-Disposition", "")
        name_m = re.search(r'name="([^"]*)"', cd) or re.search(r"name=([^\s;]+)", cd)
        if not name_m:
            continue
        name = name_m.group(1)

        filename_m = re.search(r'filename="([^"]*)"', cd)
        raw_bytes: bytes = part.get_payload(decode=True) or b""

        if filename_m:
            result[name] = _FormFile(
                filename=filename_m.group(1),
                data=raw_bytes,
                content_type=part.get_content_type(),
            )
        else:
            result[name] = raw_bytes.decode("utf-8", errors="replace")

    return result


def _form_str(form: dict, key: str, default: str = "") -> str:
    """Safely retrieve a text field from a parsed multipart form."""
    value = form.get(key, default)
    return value if isinstance(value, str) else default


# ── HTML template ─────────────────────────────────────────────────────────────

HTML_PAGE = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Ship Date Engine</title>
  <style>
        :root { --bg:#f6f8fb; --card:#ffffff; --text:#0f172a; --muted:#475569; --accent:#0f766e; --accent-dark:#115e59; --accent-2:#1d4ed8; --border:#dbe4ee; --warm:#f59e0b; }
    * { box-sizing: border-box; }
    body { margin: 0; padding: 24px; font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(160deg, #eef6ff 0%, #f7f9fc 60%, #eefcf8 100%); color: var(--text); }
    .wrap { max-width: min(1720px, 96vw); margin: 0 auto; }
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 18px; padding: 18px; box-shadow: 0 8px 24px rgba(2, 6, 23, 0.06); }
        .hero { display: grid; grid-template-columns: 1.25fr 0.75fr; gap: 18px; margin-bottom: 18px; }
        .hero-panel { padding: 22px; border-radius: 22px; border: 1px solid #d7e3f0; background: linear-gradient(135deg, rgba(255,255,255,0.96) 0%, rgba(240,249,255,0.92) 45%, rgba(236,253,245,0.95) 100%); box-shadow: 0 18px 36px rgba(15, 23, 42, 0.08); }
        .hero-kicker { display: inline-flex; align-items: center; gap: 8px; border-radius: 999px; padding: 6px 12px; background: rgba(15, 118, 110, 0.08); color: #0f766e; font-size: 12px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }
        .hero-kicker::before { content: ''; width: 8px; height: 8px; border-radius: 999px; background: var(--warm); box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.16); }
        .hero-title { margin: 14px 0 10px; font-size: clamp(2rem, 4vw, 3.4rem); line-height: 1.02; letter-spacing: -0.04em; }
        .hero-copy { margin: 0; font-size: 16px; line-height: 1.6; max-width: 60ch; color: var(--muted); }
        .hero-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 18px; }
        .stat-card { background: rgba(255,255,255,0.88); border: 1px solid rgba(148, 163, 184, 0.24); border-radius: 16px; padding: 14px; }
        .stat-label { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: #64748b; }
        .stat-value { display: block; margin-top: 6px; font-size: 18px; font-weight: 700; color: #0f172a; }
        .stat-note { display: block; margin-top: 3px; font-size: 13px; color: var(--muted); }
        .hero-side { display: grid; gap: 12px; }
        .info-card { padding: 16px; border-radius: 18px; border: 1px solid #d7e3f0; background: rgba(255,255,255,0.92); box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05); }
        .info-card h3 { margin: 0 0 8px 0; font-size: 15px; }
        .info-card p { margin: 0; line-height: 1.55; }
        .info-list { margin: 10px 0 0; padding-left: 18px; color: var(--muted); }
        .info-list li { margin: 6px 0; }
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
        .form-section { margin-top: 18px; }
        .form-section:first-child { margin-top: 0; }
        .field-label { display: block; margin-bottom: 7px; color: #1e293b; font-size: 14px; font-weight: 700; }
        .field-help { margin: 6px 0 0; color: #64748b; font-size: 13px; line-height: 1.45; }
        input[type="text"], input[type="file"], select { width: 100%; border: 1px solid var(--border); border-radius: 10px; padding: 10px; background: #fff; color: var(--text); font: inherit; }
        input[type="file"] { padding: 8px; cursor: pointer; }
        input[type="text"]:focus, input[type="file"]:focus, select:focus, button:focus-visible, .tab-btn:focus-visible, .history-link:focus-visible { outline: 3px solid rgba(29, 78, 216, 0.25); outline-offset: 2px; border-color: var(--accent-2); }
    button { margin-top: 16px; background: var(--accent); color: #fff; border: 0; border-radius: 10px; padding: 11px 16px; font-size: 14px; font-weight: 700; cursor: pointer; transition: background 0.15s ease, transform 0.15s ease; }
        button:hover { background: var(--accent-dark); transform: translateY(-1px); }
        button:disabled { cursor: wait; opacity: 0.75; transform: none; }
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
        .tabs { display: flex; gap: 8px; margin-bottom: 18px; border-bottom: 1px solid #e2e8f0; }
        .tab-btn { border: 1px solid #cbd5e1; background: #f8fafc; color: #0f172a; border-radius: 8px; padding: 8px 12px; cursor: pointer; font-weight: 600; }
        .tab-btn.active { background: #0f766e; color: #ffffff; border-color: #0f766e; }
        .tab-panel { display: none; }
        .tab-panel.active { display: block; }
        .history-table { width: 100%; border-collapse: collapse; margin-top: 8px; }
        .history-table th, .history-table td { border: 1px solid #e2e8f0; padding: 8px 10px; text-align: left; vertical-align: top; }
        .table-scroll { overflow-x: auto; }
        .table-scroll .history-table th { white-space: nowrap; }
        .history-table td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
        .history-table tfoot td { font-weight: 700; background: #f8fafc; }
        .history-table th { background: #f8fafc; color: #334155; font-weight: 600; }
        .history-link { color: #0f766e; text-decoration: none; font-weight: 600; }
        .history-link:hover { text-decoration: underline; }
        .export-link { display: inline-block; margin-top: 10px; color: #0f766e; font-size: 13px; text-decoration: none; font-weight: 600; }
        .export-link:hover { text-decoration: underline; }
                .loading-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.62); display: none; align-items: center; justify-content: center; z-index: 1000; }
                .loading-overlay.active { display: flex; }
                .loading-card { width: min(460px, 92vw); background: #ffffff; border-radius: 14px; border: 1px solid #dbe4ee; padding: 18px; box-shadow: 0 12px 32px rgba(2, 6, 23, 0.24); text-align: center; }
                .loading-title { margin: 6px 0 8px 0; font-size: 18px; color: #0f172a; font-weight: 700; }
                .loading-sub { color: #475569; margin: 0; }
                .loading-eta { margin-top: 8px; color: #0f766e; font-weight: 700; }
                .spinner { width: 42px; height: 42px; margin: 0 auto; border: 4px solid #dbeafe; border-top-color: #0f766e; border-radius: 50%; animation: spin 0.9s linear infinite; }
                @keyframes spin { to { transform: rotate(360deg); } }
        .section-label { margin: 18px 0 8px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: #64748b; }
        .section-label:first-child { margin-top: 0; }
        @media (max-width: 900px) { .grid, .hero, .hero-stats { grid-template-columns: 1fr; } }
        @media (max-width: 560px) { body { padding: 12px; } .card, .hero-panel { padding: 14px; border-radius: 14px; } .tabs { gap: 4px; } .tab-btn { flex: 1; padding: 9px 8px; } .hero-title { font-size: 2.25rem; } }
  </style>
</head>
<body>
  <main class=\"wrap\">
        <section class="hero">
            <div class="hero-panel">
                <div class="owner-banner" role="img" aria-label="Kaytheon LLC ownership logo">
                        <svg class="owner-mark" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                                <rect x="14" y="24" width="24" height="52" rx="2" fill="#000000"/>
                                <path d="M38 50 C50 50, 52 38, 66 24 L86 24 C72 33, 66 42, 60 50 C66 58, 72 67, 86 76 L66 76 C52 62, 50 50, 38 50 Z" fill="#f7c044"/>
                                <circle cx="38" cy="50" r="11" fill="#f7c044"/>
                        </svg>
                        <div class="owner-text"><strong>Kaytheon LLC</strong></div>
                </div>
                <div class="hero-kicker">New code update</div>
                <h1 class="hero-title">Ship Date Engine</h1>
                <p class="hero-copy">Upload a workbook or invoice, look up a single Shipping ID, or generate an all-ID summary by period. The web app now reflects the newer parsing and AI-assist workflow, including cached lookups and CSV-friendly exports.</p>
                <div class="hero-stats">
                    <div class="stat-card"><span class="stat-label">Input formats</span><span class="stat-value">TXT, CSV, JSON, XML, XLSX, XLS</span><span class="stat-note">Plus PDF and common image files</span></div>
                    <div class="stat-card"><span class="stat-label">Lookup modes</span><span class="stat-value">Single or all IDs</span><span class="stat-note">Group all-ID reports by period</span></div>
                    <div class="stat-card"><span class="stat-label">Results</span><span class="stat-value">Table + JSON output</span><span class="stat-note">AI assist and totals included</span></div>
                </div>
            </div>
            <div class="hero-side">
                <div class="info-card">
                    <h3>What changed</h3>
                    <ul class="info-list">
                        <li>Result tables now mirror the columns in your uploaded Excel.</li>
                        <li>Single-ID lookups show every matching row across all tabs.</li>
                        <li>Totals Summary highlights which rows carry the money data.</li>
                        <li>Shipping ID dropdown fills from your file automatically.</li>
                    </ul>
                </div>
                <div class="info-card">
                    <h3>Quick workflow</h3>
                    <ul class="info-list">
                        <li>Upload one file per request.</li>
                        <li>Choose single-ID or all-ID mode.</li>
                        <li>AI Assist and totals run automatically.</li>
                    </ul>
                </div>
            </div>
        </section>
        <section class="card">
                                                <p>Upload one invoice file (TXT, CSV, JSON, XML, XLSX, XLS, PDF, or image) and optionally enter a Shipping/Order ID for deep lookup.</p>
            <div class="tabs" role="tablist" aria-label="Ship date tools">
                <button type="button" role="tab" aria-selected="true" class="tab-btn active" id="tab-btn-lookup" onclick="switchTab('lookup')">Lookup</button>
                <button type="button" role="tab" aria-selected="false" class="tab-btn" id="tab-btn-history" onclick="switchTab('history')">Recent Lookups</button>
            </div>
            <section class="tab-panel active" id="tab-lookup" role="tabpanel" aria-labelledby="tab-btn-lookup">
            <form id="lookup-form" method="post" action="/" enctype="multipart/form-data">
                <input type="hidden" name="action" value="compute" />
                <div class="form-section">
                    <label class="field-label" for="invoice-file">Invoice or workbook</label>
                    <p class="field-help">Upload a file to calculate a date or discover Shipping IDs. Accepted: TXT, CSV, JSON, XML, Excel, PDF, and images.</p>
                    <input id="invoice-file" type="file" name="invoice_file" accept=".txt,.csv,.json,.xlsx,.xls,.pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp" />
        </div>
                <div class="form-section">
                    <label class="field-label" for="shipping-id">Shipping ID <span style="font-weight:400;color:#64748b;">(optional for all-ID reports)</span></label>
                    <input id="shipping-id" type="text" name="shipping_id" value="__SHIPPING_ID__" placeholder="e.g. SHIP-2026-0042" autocomplete="off" />
                    <select id="shipping-id-picker" style="margin-top:8px; width:100%;" aria-label="Pick a recent or uploaded Shipping ID">
                        <option value="">— Pick a recent Shipping ID —</option>
                        __SHIPPING_ID_OPTIONS__
                    </select>
                </div>
                <div class="grid form-section">
                    <div>
                        <label class="field-label" for="lookup-mode">Lookup scope</label>
                        <select id="lookup-mode" name="lookup_mode">
                            <option value="single" __LOOKUP_MODE_SINGLE__>1 Shipping ID</option>
                            <option value="all" __LOOKUP_MODE_ALL__>All Shipping IDs</option>
                        </select>
                    </div>
                    <div>
                        <label class="field-label" for="group-by">Group all-ID results by</label>
                        <select id="group-by" name="group_by">
                            <option value="daily" __GROUP_BY_DAILY__>Daily</option>
                            <option value="weekly" __GROUP_BY_WEEKLY__>Weekly</option>
                            <option value="monthly" __GROUP_BY_MONTHLY__>Monthly</option>
                            <option value="quarterly" __GROUP_BY_QUARTERLY__>Quarterly</option>
                            <option value="annual" __GROUP_BY_ANNUAL__>Annual</option>
                        </select>
                    </div>
                </div>
            <button id="submit-btn" type="submit">Calculate Shipping Date</button>
      </form>
    __RESULT__
                        </section>
                        <section class="tab-panel" id="tab-history" role="tabpanel" aria-labelledby="tab-btn-history">
                                <h3>Recent Shipping/Order Lookups</h3>
                                __HISTORY_TABLE__
                                <a href="/export.csv" class="export-link">⬇ Export history as CSV</a>
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
                historyBtn.setAttribute('aria-selected', 'true');
                lookupBtn.setAttribute('aria-selected', 'false');
            } else {
                lookupPanel.classList.add('active');
                historyPanel.classList.remove('active');
                lookupBtn.classList.add('active');
                historyBtn.classList.remove('active');
                lookupBtn.setAttribute('aria-selected', 'true');
                historyBtn.setAttribute('aria-selected', 'false');
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

        function estimateSeconds() {
            const lookupMode = document.getElementById('lookup-mode');
            const groupBy = document.getElementById('group-by');
            const fileInput = document.querySelector('input[name="invoice_file"]');
            const shippingInput = document.querySelector('input[name="shipping_id"]');

            const mode = lookupMode ? lookupMode.value : 'single';
            const period = groupBy ? groupBy.value : 'daily';
            const hasFile = fileInput && fileInput.files && fileInput.files.length > 0;
            const hasShippingId = shippingInput && shippingInput.value.trim().length > 0;

            if (!hasFile && hasShippingId) {
                return 4;
            }

            let seconds = 10;
            if (mode === 'all') {
                if (period === 'weekly') seconds = 16;
                else if (period === 'monthly') seconds = 20;
                else if (period === 'quarterly') seconds = 24;
                else if (period === 'annual') seconds = 28;
            }

            if (hasFile && fileInput && fileInput.files && fileInput.files[0]) {
                const name = fileInput.files[0].name.toLowerCase();
                if (name.endsWith('.xlsx') || name.endsWith('.xls')) {
                    seconds += 4;
                }
            }

            return seconds;
        }

        function showLoadingOverlay() {
            const overlay = document.getElementById('loading-overlay');
            const eta = document.getElementById('loading-eta');
            const submitBtn = document.getElementById('submit-btn');
            if (!overlay || !eta) {
                return;
            }

            let remaining = estimateSeconds();
            eta.textContent = `Estimated wait: ~${remaining}s`;
            overlay.classList.add('active');

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Loading...';
            }

            window.setInterval(() => {
                if (remaining > 1) {
                    remaining -= 1;
                    eta.textContent = `Estimated wait: ~${remaining}s`;
                } else {
                    eta.textContent = 'Finalizing...';
                }
            }, 1000);
        }

        function bindLoadingState() {
            const form = document.getElementById('lookup-form');
            if (!form) {
                return;
            }
            form.addEventListener('submit', () => {
                showLoadingOverlay();
            });
        }

        function bindFileDrivenSuggestions() {
            const fileInput = document.querySelector('input[name="invoice_file"]');
            const picker = document.getElementById('shipping-id-picker');
            const shippingInput = document.querySelector('input[name="shipping_id"]');
            if (!fileInput || !picker || !shippingInput) {
                return;
            }
            picker.addEventListener('change', () => {
                if (picker.value) {
                    shippingInput.value = picker.value;
                }
            });
            fileInput.addEventListener('change', async () => {
                const file = fileInput.files && fileInput.files[0];
                if (!file || !file.name.toLowerCase().endsWith('.xlsx')) {
                    return;
                }
                const data = new FormData();
                data.append('invoice_file', file);
                try {
                    const resp = await fetch('/api/shipping-ids', { method: 'POST', body: data });
                    if (!resp.ok) {
                        return;
                    }
                    const payload = await resp.json();
                    if (!payload.ids || !payload.ids.length) {
                        return;
                    }
                    const placeholder = document.createElement('option');
                    placeholder.value = '';
                    placeholder.textContent = `\u2014 Pick from file (${payload.ids.length} IDs found) \u2014`;
                    picker.replaceChildren(placeholder, ...payload.ids.map((item) => {
                        const opt = document.createElement('option');
                        opt.value = item.id;
                        opt.textContent = item.date ? `${item.id} \u2014 ${item.date}` : item.id;
                        return opt;
                    }));
                } catch (err) {
                    // keep the history-based options on failure
                }
            });
        }

        bindLoadingState();
        bindFileDrivenSuggestions();
    </script>
    <div id="loading-overlay" class="loading-overlay" aria-live="polite" aria-label="Loading results">
        <div class="loading-card">
            <div class="spinner" aria-hidden="true"></div>
            <h3 class="loading-title">Processing request...</h3>
            <p class="loading-sub">Please wait while the server loads and analyzes your data.</p>
            <p id="loading-eta" class="loading-eta">Estimated wait: ~10s</p>
        </div>
    </div>
</body>
</html>
"""


# ── Persistence helpers ───────────────────────────────────────────────────────

def _render(
    shipping_id: str = "",
    result_block: str = "",
    enable_ai: bool = True,
    lookup_mode: str = "single",
    group_by: str = "daily",
    include_totals: bool = False,
) -> bytes:
    history_table = _render_history_table()
    shipping_id_options = _render_shipping_id_options()
    html_doc = (
        HTML_PAGE.replace("__SHIPPING_ID__", html.escape(shipping_id))
        .replace("__SHIPPING_ID_OPTIONS__", shipping_id_options)
        .replace("__LOOKUP_MODE_SINGLE__", "selected" if lookup_mode == "single" else "")
        .replace("__LOOKUP_MODE_ALL__", "selected" if lookup_mode == "all" else "")
        .replace("__GROUP_BY_DAILY__", "selected" if group_by == "daily" else "")
        .replace("__GROUP_BY_WEEKLY__", "selected" if group_by == "weekly" else "")
        .replace("__GROUP_BY_MONTHLY__", "selected" if group_by == "monthly" else "")
        .replace("__GROUP_BY_QUARTERLY__", "selected" if group_by == "quarterly" else "")
        .replace("__GROUP_BY_ANNUAL__", "selected" if group_by == "annual" else "")
        .replace("__HISTORY_TABLE__", history_table)
        .replace("__RESULT__", result_block)
    )
    return html_doc.encode("utf-8")


def _migrate_legacy_records() -> None:
    if not RECORDS_PATH.exists():
        return
    try:
        payload = json.loads(RECORDS_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        payload = {}
    if isinstance(payload, dict):
        existing = get_all_lookups()
        for shipping_id, record in payload.items():
            if shipping_id not in existing and isinstance(record, dict):
                save_lookup(shipping_id, record)
    try:
        RECORDS_PATH.rename(RECORDS_PATH.with_suffix(".json.migrated"))
    except OSError:
        pass


def _load_records() -> dict[str, dict[str, str]]:
    _migrate_legacy_records()
    records = get_all_lookups()
    return {k: v for k, v in records.items() if isinstance(v, dict)}


def _record_shipping_date(
    shipping_id: str, final_shipping_date: str, source_path: str
) -> None:
    _record_shipping_date_with_file(shipping_id, final_shipping_date, source_path, None)


def _record_shipping_date_with_file(
    shipping_id: str,
    final_shipping_date: str,
    source_path: str,
    saved_file_path: str | None,
) -> None:
    if not shipping_id.strip():
        return
    key = shipping_id.strip()
    existing = _lookup_shipping_date(key) or {}
    save_lookup(key, {
        "final_shipping_date": final_shipping_date,
        "source_path": source_path,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "saved_file_path": saved_file_path or existing.get("saved_file_path", ""),
    })


def _record_saved_file(shipping_id: str, saved_file_path: str) -> None:
    if not shipping_id.strip() or not saved_file_path.strip():
        return
    key = shipping_id.strip()
    existing = _lookup_shipping_date(key) or {}
    save_lookup(key, {
        "final_shipping_date": existing.get("final_shipping_date", ""),
        "source_path": existing.get("source_path", saved_file_path),
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "saved_file_path": saved_file_path,
    })


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
    _migrate_legacy_records()
    record = get_cached_lookup(shipping_id.strip())
    return record if isinstance(record, dict) else None


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
    options = []
    for sid, payload in rows[:200]:
        date = payload.get("final_shipping_date", "")
        text = f"{sid} \u2014 {date}" if date else sid
        options.append(
            f"<option value=\"{html.escape(sid)}\">{html.escape(text)}</option>"
        )
    return "".join(options)


# ── Result builders ───────────────────────────────────────────────────────────

def _parse_mmddyyyy_or_serial(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None

    for fmt in ("%m-%d-%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%m-%d-%Y")
        except ValueError:
            continue

    if re.fullmatch(r"\d+(\.\d+)?", text):
        try:
            serial = int(float(text))
            if 30000 <= serial <= 90000:
                converted = datetime(1899, 12, 30) + timedelta(days=serial)
                return converted.strftime("%m-%d-%Y")
        except (ValueError, OverflowError):
            return None
    return None


def _period_bucket(date_text: str, group_by: str) -> str:
    parsed = _parse_mmddyyyy_or_serial(date_text)
    if not parsed:
        return "Unknown"

    dt = datetime.strptime(parsed, "%m-%d-%Y")
    if group_by == "weekly":
        iso_year, iso_week, _ = dt.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    if group_by == "monthly":
        return dt.strftime("%Y-%m")
    if group_by == "quarterly":
        quarter = ((dt.month - 1) // 3) + 1
        return f"{dt.year}-Q{quarter}"
    if group_by == "annual":
        return dt.strftime("%Y")
    return dt.strftime("%m-%d-%Y")


def _parse_amount_value(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    cleaned = text.replace(",", "").replace("$", "").strip()
    if not re.fullmatch(r"[-+]?\d+(\.\d+)?", cleaned):
        return None
    number = float(cleaned)
    return -number if negative else number


def _parse_details_ordered(details: str) -> dict[str, str]:
    """Parse 'header=value | ...' keeping the workbook's column order and headers."""
    fields: dict[str, str] = {}
    for part in (p.strip() for p in details.split(" | ") if p.strip()):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key, value = key.strip(), value.strip()
        if key and value and key not in fields:
            fields[key] = value
    return fields


_HEADER_ACRONYMS = {"id", "sku", "cogs", "sc", "po", "upc", "vat"}


def _pretty_header(key: str) -> str:
    words = key.replace("_", " ").split()
    return " ".join(w.upper() if w in _HEADER_ACRONYMS else w.capitalize() for w in words)


def _is_id_like_key(key: str) -> bool:
    if re.search(r"\b(id|date|number|no|code|sku|type|column)\b", key):
        return True
    compact = re.sub(r"[^a-z0-9]", "", key.lower())
    # catches compact headers like setid/settlementid1 but not paid/prepaid
    return bool(re.search(r"(?<!pa)id\d*$", compact))


def _extract_matches(record: dict) -> list[dict]:
    raw = record.get("matches")
    matches = [m for m in raw if isinstance(m, dict) and m.get("details")] if isinstance(raw, list) else []
    if not matches and record.get("details"):
        matches = [{
            "sheet": record.get("sheet", ""),
            "shipping_date": record.get("shipping_date", ""),
            "details": record.get("details", ""),
        }]
    return matches


def _render_match_tables(matches: list[dict], single_title: str = "Matched Row Details") -> str:
    blocks: list[str] = []
    total = len(matches)
    for idx, match in enumerate(matches, start=1):
        fields = _parse_details_ordered(match.get("details", ""))
        rows_html = "".join(
            f"<tr><th>{html.escape(_pretty_header(k))}</th><td>{html.escape(v)}</td></tr>"
            for k, v in fields.items()
        )
        if not rows_html:
            continue
        sheet = match.get("sheet", "")
        match_date = match.get("shipping_date", "")
        if total == 1:
            title = single_title + (f" — Tab: {sheet}" if sheet else "")
        else:
            title = f"Match {idx} of {total}"
            if sheet:
                title += f" — Tab: {sheet}"
            if match_date:
                title += f" ({match_date})"
        blocks.append(
            f"<h4>{html.escape(title)}</h4>"
            f"<table class=\"lookup-table\">{rows_html}</table>"
        )
    return "".join(blocks)


def _adaptive_totals_block(matches: list[dict]) -> str:
    """Sum numeric fields across matched rows; columns come from the workbook itself."""
    all_fields = [_parse_details_ordered(m.get("details", "")) for m in matches]
    keys: list[str] = []
    for fields in all_fields:
        for key in fields:
            if key not in keys:
                keys.append(key)
    rows_html: list[str] = []
    for key in keys:
        if _is_id_like_key(key):
            continue
        values = [f[key] for f in all_fields if f.get(key, "").strip()]
        if not values:
            continue
        parsed = [_parse_amount_value(v) for v in values]
        if any(p is None for p in parsed):
            continue
        total = sum(p for p in parsed if p is not None)
        rows_html.append(
            f"<tr><th>{html.escape(_pretty_header(key))}</th><td>{total:,.2f}</td></tr>"
        )
    if not rows_html:
        return ""
    return (
        "<h4>Totals Summary</h4>"
        f"<table class=\"lookup-table\">{''.join(rows_html)}</table>"
    )


def _ai_lookup_block(shipping_id: str, shipping_date: str, matches: list[dict]) -> str:
    try:
        insight = generate_lookup_insight(shipping_id, shipping_date, matches)
        return f"<h4>AI Assist</h4><pre>{html.escape(insight)}</pre>"
    except Exception as exc:  # noqa: BLE001
        return f"<h4>AI Assist</h4><pre>AI assist unavailable: {html.escape(str(exc))}</pre>"


def _build_lookup_result_from_file(
    invoice_path: Path,
    shipping_id: str,
    saved_file_path: Path | None = None,
    include_totals: bool = False,
) -> str:
    record = lookup_shipping_date_record_by_id(str(invoice_path), shipping_id)
    if not record:
        cached = _lookup_shipping_date(shipping_id)
        if cached:
            found_date = cached.get("final_shipping_date")
            source_line = (
                f"{html.escape(str(saved_file_path))} (saved file)"
                if saved_file_path is not None
                else "Cached record"
            )
            return (
                "<section class=\"result\">"
                "<h3>Shipping ID Lookup</h3>"
                "<div class=\"lookup-grid\">"
                "<div class=\"lookup-pill\"><div class=\"label\">Shipping ID</div>"
                f"<div class=\"value\">{html.escape(shipping_id)}</div></div>"
                "<div class=\"lookup-pill\"><div class=\"label\">Shipping Date</div>"
                f"<div class=\"value\">{html.escape(found_date or 'N/A')}</div></div>"
                "<div class=\"lookup-pill\"><div class=\"label\">Result</div>"
                "<div class=\"value\">Matched from cache</div></div>"
                "</div>"
                "<h4>Lookup Details</h4>"
                "<table class=\"lookup-table\">"
                f"<tr><th>Source</th><td>{source_line}</td></tr>"
                "</table>"
                "</section>"
            )

        return (
            "<section class=\"result error\">"
            "<h3>Shipping ID Lookup</h3>"
            "<div class=\"lookup-grid\">"
            "<div class=\"lookup-pill\"><div class=\"label\">Shipping ID</div>"
            f"<div class=\"value\">{html.escape(shipping_id)}</div></div>"
            "<div class=\"lookup-pill\"><div class=\"label\">Result</div>"
            "<div class=\"value\">Not found</div></div>"
            "<div class=\"lookup-pill\"><div class=\"label\">Scope</div>"
            "<div class=\"value\">Uploaded workbook tabs</div></div>"
            "</div>"
            "<h4>Lookup Details</h4>"
            "<table class=\"lookup-table\">"
            "<tr><th>Message</th><td>No shipping date found for this Shipping/Order ID across workbook tabs.</td></tr>"
            "<tr><th>Hint</th><td>Check that the workbook includes an Order/Shipping ID column and a Shipping Date column.</td></tr>"
            "</table>"
            "</section>"
        )

    if record.get("status") == "ambiguous":
        ambiguous_matches = _extract_matches(record)
        ambiguous_tables = _render_match_tables(ambiguous_matches, single_title="Matched Row")
        return (
            "<section class=\"result error\">"
            "<h3>Shipping ID Lookup</h3>"
            "<div class=\"lookup-grid\">"
            "<div class=\"lookup-pill\"><div class=\"label\">Shipping ID</div>"
            f"<div class=\"value\">{html.escape(shipping_id)}</div></div>"
            "<div class=\"lookup-pill\"><div class=\"label\">Result</div>"
            "<div class=\"value\">Ambiguous</div></div>"
            "<div class=\"lookup-pill\"><div class=\"label\">Candidate Dates</div>"
            f"<div class=\"value\">{html.escape(record.get('candidates', 'N/A'))}</div></div>"
            "</div>"
            "<h4>Lookup Details</h4>"
            "<table class=\"lookup-table\">"
            "<tr><th>Message</th><td>Multiple valid shipping dates were found for this Shipping ID. "
            "All matched rows are shown below.</td></tr>"
            "</table>"
            f"{ambiguous_tables}"
            "</section>"
        )

    found_date = record.get("shipping_date", "N/A")
    source_sheet = record.get("sheet", "unknown")
    matches = _extract_matches(record)

    _record_shipping_date_with_file(
        shipping_id,
        found_date,
        str(saved_file_path or invoice_path),
        str(saved_file_path) if saved_file_path is not None else None,
    )

    tabs: list[str] = []
    for match in matches:
        sheet = match.get("sheet", "")
        if sheet and sheet not in tabs:
            tabs.append(sheet)

    if len(matches) > 1:
        third_pill = (
            "<div class=\"lookup-pill\"><div class=\"label\">Matches</div>"
            f"<div class=\"value\">{len(matches)} rows across {len(tabs)} tab(s)</div></div>"
        )
    else:
        third_pill = (
            "<div class=\"lookup-pill\"><div class=\"label\">Source Tab</div>"
            f"<div class=\"value\">{html.escape(source_sheet)}</div></div>"
        )

    details_block = _render_match_tables(matches)
    totals_block = _adaptive_totals_block(matches) if include_totals else ""
    ai_block = _ai_lookup_block(shipping_id, found_date, matches)

    return (
        "<section class=\"result\">"
        "<h3>Shipping ID Lookup</h3>"
        "<div class=\"lookup-grid\">"
        "<div class=\"lookup-pill\"><div class=\"label\">Shipping ID</div>"
        f"<div class=\"value\">{html.escape(shipping_id)}</div></div>"
        "<div class=\"lookup-pill\"><div class=\"label\">Shipping Date</div>"
        f"<div class=\"value\">{html.escape(found_date)}</div></div>"
        f"{third_pill}"
        "</div>"
        f"{totals_block}"
        f"{details_block}"
        f"{ai_block}"
        "</section>"
    )


def _build_lookup_result_from_cache(
    shipping_id: str, include_totals: bool = False
) -> str:
    cached = _lookup_shipping_date(shipping_id)
    if not cached:
        for candidate in _iter_saved_upload_files():
            record = lookup_shipping_date_record_by_id(str(candidate), shipping_id)
            if record:
                return _build_lookup_result_from_file(
                    candidate, shipping_id, candidate, include_totals
                )

        return (
            "<section class=\"result error\">"
            "<h3>Shipping ID Lookup</h3>"
            "<pre>No record found for this Shipping/Order ID in cached results or saved uploads. "
            "Upload a workbook to index this ID.</pre>"
            "</section>"
        )

    saved_path = cached.get("saved_file_path", "").strip()
    if saved_path and Path(saved_path).exists():
        return _build_lookup_result_from_file(
            Path(saved_path), shipping_id, Path(saved_path), include_totals
        )

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
        "<tr><th>Lookup Mode</th><td>Cached record (no re-upload required)</td></tr>"
        "</table>"
        "</section>"
    )


def _build_all_lookup_result_from_file(
    invoice_path: Path,
    group_by: str,
    saved_file_path: Path | None = None,
    include_totals: bool = False,
) -> str:
    rows = list_shipping_date_records(str(invoice_path))
    if not rows:
        return (
            "<section class=\"result error\">"
            "<h3>All Shipping IDs</h3>"
            "<pre>No shipping IDs with valid shipping dates were found. "
            "Use an .xlsx workbook with Shipping/Order ID and date columns.</pre>"
            "</section>"
        )

    group_counts: dict[str, int] = {}
    enriched_rows: list[dict] = []

    for row in rows:
        shipping_id = row.get("shipping_id", "")
        shipping_date = row.get("shipping_date", "")
        if shipping_id and shipping_date:
            _record_shipping_date_with_file(
                shipping_id,
                shipping_date,
                str(saved_file_path or invoice_path),
                str(saved_file_path) if saved_file_path is not None else None,
            )
        bucket = _period_bucket(shipping_date, group_by)
        group_counts[bucket] = group_counts.get(bucket, 0) + 1

        enriched_rows.append(
            {
                "shipping_id": shipping_id,
                "shipping_date": shipping_date,
                "period": bucket,
                "source_tab": row.get("sheet", ""),
                "fields": _parse_details_ordered(row.get("details", "")),
            }
        )

    summary_rows = "".join(
        f"<tr><th>{html.escape(bucket)}</th><td>{count}</td></tr>"
        for bucket, count in sorted(group_counts.items())
    )

    # Columns mirror the uploaded workbook: union of headers in first-seen order
    workbook_columns: list[str] = []
    for row in enriched_rows:
        for key in row["fields"]:
            if key not in workbook_columns:
                workbook_columns.append(key)

    def _matches_canonical(row: dict, value: str) -> bool:
        v = value.strip().casefold()
        return v in {
            row["shipping_id"].strip().casefold(),
            row["shipping_date"].strip().casefold(),
        }

    visible_columns: list[str] = []
    for key in workbook_columns:
        cells = [
            (row, row["fields"].get(key, ""))
            for row in enriched_rows
            if row["fields"].get(key, "").strip()
        ]
        if not cells:
            continue
        # skip columns that literally duplicate the canonical ID/date shown up front
        if all(_matches_canonical(row, value) for row, value in cells):
            for row, value in cells:
                # keep the workbook's original casing for the lead Shipping ID cell
                if value.strip().casefold() == row["shipping_id"].strip().casefold():
                    row["shipping_id"] = value.strip()
            continue
        visible_columns.append(key)

    def _is_id_like(key: str) -> bool:
        return _is_id_like_key(key)

    numeric_columns: set[str] = set()
    for key in visible_columns:
        values = [row["fields"].get(key, "").strip() for row in enriched_rows]
        values = [v for v in values if v]
        if values and not _is_id_like(key) and all(
            _parse_amount_value(v) is not None for v in values
        ):
            numeric_columns.add(key)

    multi_tab = len({row["source_tab"] for row in enriched_rows if row["source_tab"]}) > 1

    lead_columns = [("shipping_id", "Shipping ID"), ("shipping_date", "Shipping Date"), ("period", "Period")]
    tail_columns = [("source_tab", "Source Tab")] if multi_tab else []

    header_cells = "".join(
        f"<th>{html.escape(label)}</th>" for _, label in lead_columns
    )
    header_cells += "".join(
        f"<th>{html.escape(_pretty_header(key))}</th>" for key in visible_columns
    )
    header_cells += "".join(
        f"<th>{html.escape(label)}</th>" for _, label in tail_columns
    )

    body_rows_html: list[str] = []
    for row in enriched_rows:
        cells = "".join(
            f"<td>{html.escape(row[key])}</td>" for key, _ in lead_columns
        )
        for key in visible_columns:
            raw = row["fields"].get(key, "")
            if key in numeric_columns and raw:
                parsed = _parse_amount_value(raw)
                cells += f"<td class=\"num\">{parsed:,.2f}</td>"
            else:
                cells += f"<td>{html.escape(raw)}</td>"
        cells += "".join(
            f"<td>{html.escape(row[key])}</td>" for key, _ in tail_columns
        )
        body_rows_html.append(f"<tr>{cells}</tr>")

    footer_html = ""
    totals_summary_block = ""
    if include_totals and numeric_columns:
        sums: dict[str, float] = {}
        counts: dict[str, int] = {}
        for key in numeric_columns:
            parsed_values = [
                parsed
                for parsed in (
                    _parse_amount_value(row["fields"].get(key, ""))
                    for row in enriched_rows
                )
                if parsed is not None
            ]
            sums[key] = sum(parsed_values)
            counts[key] = len(parsed_values)
        footer_cells = "<td>Totals</td>" + "<td></td>" * (len(lead_columns) - 1)
        for key in visible_columns:
            footer_cells += (
                f"<td class=\"num\">{sums[key]:,.2f}</td>"
                if key in numeric_columns
                else "<td></td>"
            )
        footer_cells += "<td></td>" * len(tail_columns)
        footer_html = f"<tfoot><tr>{footer_cells}</tr></tfoot>"

        summary_totals_rows = "".join(
            f"<tr><th>{html.escape(_pretty_header(key))}</th>"
            f"<td>{sums[key]:,.2f}</td>"
            f"<td>{counts[key]} of {len(enriched_rows)} rows</td></tr>"
            for key in visible_columns
            if key in numeric_columns
        )
        totals_summary_block = (
            "<h4>Totals Summary</h4>"
            "<table class=\"lookup-table\">"
            "<thead><tr><th>Field</th><th>Total</th><th>Rows With Data</th></tr></thead>"
            f"<tbody>{summary_totals_rows}</tbody>"
            "</table>"
        )

        money_rows = [
            row
            for row in enriched_rows
            if any(
                _parse_amount_value(row["fields"].get(key, "")) is not None
                for key in numeric_columns
            )
        ]
        if money_rows:
            money_cols = [key for key in visible_columns if key in numeric_columns]
            money_header = (
                "<tr><th>Shipping ID</th><th>Shipping Date</th><th>Tab</th>"
                + "".join(f"<th>{html.escape(_pretty_header(k))}</th>" for k in money_cols)
                + "</tr>"
            )
            money_body = ""
            for row in money_rows[:50]:
                cells = (
                    f"<td>{html.escape(row['shipping_id'])}</td>"
                    f"<td>{html.escape(row['shipping_date'])}</td>"
                    f"<td>{html.escape(row['source_tab'])}</td>"
                )
                for key in money_cols:
                    parsed = _parse_amount_value(row["fields"].get(key, ""))
                    cells += (
                        f"<td class=\"num\">{parsed:,.2f}</td>" if parsed is not None else "<td></td>"
                    )
                money_body += f"<tr>{cells}</tr>"
            truncated_note = (
                f"<p>Showing first 50 of {len(money_rows)} rows with money data.</p>"
                if len(money_rows) > 50
                else ""
            )
            totals_summary_block += (
                f"<h4>Rows With Money Data ({len(money_rows)})</h4>"
                "<div class=\"table-scroll\">"
                "<table class=\"history-table\">"
                f"<thead>{money_header}</thead>"
                f"<tbody>{money_body}</tbody>"
                "</table>"
                "</div>"
                f"{truncated_note}"
            )

    table_block = (
        "<h4>Workbook Rows</h4>"
        "<div class=\"table-scroll\">"
        "<table class=\"history-table\">"
        f"<thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows_html)}</tbody>"
        f"{footer_html}"
        "</table>"
        "</div>"
    )

    return (
        "<section class=\"result\">"
        "<h3>All Shipping IDs</h3>"
        "<div class=\"lookup-grid\">"
        "<div class=\"lookup-pill\"><div class=\"label\">Total Shipping IDs</div>"
        f"<div class=\"value\">{len(rows)}</div></div>"
        "<div class=\"lookup-pill\"><div class=\"label\">Grouping</div>"
        f"<div class=\"value\">{html.escape(group_by.title())}</div></div>"
        "<div class=\"lookup-pill\"><div class=\"label\">Source</div>"
        f"<div class=\"value\">{html.escape(str(saved_file_path or invoice_path))}</div></div>"
        "</div>"
        "<h4>Counts by Period</h4>"
        f"<table class=\"lookup-table\">{summary_rows}</table>"
        f"{totals_summary_block}"
        f"{table_block}"
        "</section>"
    )


def _format_result(
    invoices, validation, decision, enable_ai: bool, shipping_id: str = ""
) -> str:
    json_output = to_json_output(invoices, validation, decision)

    effective_shipping_id = (
        shipping_id.strip() or (invoices[0].shipping_id or "").strip()
    )
    if effective_shipping_id:
        _record_shipping_date(
            effective_shipping_id,
            decision.final_shipping_date.strftime("%m-%d-%Y"),
            invoices[0].source_path,
        )

    ai_block = ""
    if enable_ai:
        try:
            insight = generate_insight(invoices, validation, decision)
            ai_block = (
                "<h3>AI Assist</h3>"
                f"<pre>{html.escape(insight)}</pre>"
            )
        except Exception as exc:  # noqa: BLE001
            ai_block = (
                "<h3>AI Assist</h3>"
                f"<pre>AI assist unavailable: {html.escape(str(exc))}</pre>"
            )

    def _fmt_date(d) -> str:
        return d.strftime("%m-%d-%Y")

    shipping_id_pill = (
        "<div class=\"lookup-pill\"><div class=\"label\">Shipping ID</div>"
        f"<div class=\"value\">{html.escape(effective_shipping_id)}</div></div>"
        if effective_shipping_id
        else ""
    )
    pills_block = (
        "<div class=\"lookup-grid\">"
        f"{shipping_id_pill}"
        "<div class=\"lookup-pill\"><div class=\"label\">Final Shipping Date</div>"
        f"<div class=\"value\">{html.escape(_fmt_date(decision.final_shipping_date))}</div></div>"
        "<div class=\"lookup-pill\"><div class=\"label\">Earliest Ship Date</div>"
        f"<div class=\"value\">{html.escape(_fmt_date(decision.earliest_ship_date))}</div></div>"
        "<div class=\"lookup-pill\"><div class=\"label\">Latest Allowable</div>"
        f"<div class=\"value\">{html.escape(_fmt_date(decision.latest_allowable_ship_date))}</div></div>"
        "</div>"
    )

    decision_rows = "".join(
        f"<tr><th>Step {i}</th><td>{html.escape(step)}</td></tr>"
        for i, step in enumerate(decision.explanation, start=1)
    )
    if decision.selected_priority_invoice:
        decision_rows += (
            "<tr><th>Priority Invoice</th>"
            f"<td>{html.escape(decision.selected_priority_invoice)}</td></tr>"
        )
    decision_block = (
        "<h4>Decision Details</h4>"
        f"<table class=\"lookup-table\">{decision_rows}</table>"
        if decision_rows
        else ""
    )

    issue_rows = "".join(
        f"<tr><th>Error</th><td>{html.escape(e)}</td></tr>" for e in validation.errors
    )
    issue_rows += "".join(
        f"<tr><th>Warning</th><td>{html.escape(w)}</td></tr>" for w in validation.warnings
    )
    issue_rows += "".join(
        f"<tr><th>Conflict</th><td>{html.escape(c)}</td></tr>" for c in decision.conflicts
    )
    issues_block = (
        "<h4>Validation</h4>"
        f"<table class=\"lookup-table\">{issue_rows}</table>"
        if issue_rows
        else ""
    )

    invoice_rows = "".join(
        "<tr>"
        f"<td>{html.escape(Path(inv.source_path).name)}</td>"
        f"<td>{html.escape(inv.shipping_id or 'N/A')}</td>"
        f"<td>{html.escape(inv.invoice_number or 'N/A')}</td>"
        f"<td>{html.escape(inv.po_number or 'N/A')}</td>"
        f"<td>{inv.priority}</td>"
        "</tr>"
        for inv in invoices
    )
    invoices_block = (
        "<h4>Invoices</h4>"
        "<table class=\"history-table\">"
        "<tr><th>Source</th><th>Shipping ID</th><th>Invoice #</th><th>PO #</th><th>Priority</th></tr>"
        f"{invoice_rows}"
        "</table>"
        if invoice_rows
        else ""
    )

    json_block = (
        "<details><summary>JSON Output</summary>"
        f"<pre>{html.escape(json.dumps(json.loads(json_output), indent=2))}</pre>"
        "</details>"
    )

    return (
        "<section class=\"result\">"
        "<h3>Shipping Date Result</h3>"
        f"{pills_block}"
        f"{decision_block}"
        f"{issues_block}"
        f"{invoices_block}"
        f"{ai_block}"
        f"{json_block}"
        "</section>"
    )


def _build_result_from_path(
    invoice_path: Path, enable_ai: bool = False, shipping_id: str = ""
) -> str:
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


def _write_uploaded_file(file_field: _FormFile, prefix: str) -> Path:
    """Write the bytes from a parsed multipart file field to a temp file."""
    try:
        original_name = sanitize_filename(file_field.filename or "uploaded.txt")
    except ValidationError:
        original_name = "uploaded.txt"
    suffix = Path(original_name).suffix or ".txt"

    temp = tempfile.NamedTemporaryFile("wb", suffix=suffix, prefix=prefix, delete=False)
    try:
        temp.write(file_field.data)
        temp.flush()
    finally:
        temp.close()
    return Path(temp.name)


# ── Request handler ───────────────────────────────────────────────────────────

class ShipDateWebHandler(BaseHTTPRequestHandler):

    def _send_html(self, payload: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_shipping_ids_api(self) -> None:
        """Return the Shipping IDs found in an uploaded workbook (for the datalist)."""
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send_json({"error": "multipart form expected"}, status=400)
            return
        content_length = int(self.headers.get("Content-Length", -1))
        form = _parse_multipart(self.rfile, content_type, content_length)
        invoice_file = form.get("invoice_file")
        if not isinstance(invoice_file, _FormFile) or not invoice_file.filename:
            self._send_json({"error": "no file provided"}, status=400)
            return
        file_path = _write_uploaded_file(invoice_file, "suggest_")
        try:
            records = list_shipping_date_records(str(file_path))
        finally:
            file_path.unlink(missing_ok=True)
        seen: set[str] = set()
        ids: list[dict[str, str]] = []
        for rec in records:
            sid = rec.get("shipping_id", "")
            if sid and sid not in seen:
                seen.add(sid)
                ids.append({"id": sid, "date": rec.get("shipping_date", "")})
        self._send_json({"ids": ids})

    def _send_csv_export(self) -> None:
        """Stream the full lookup history as a UTF-8 CSV download."""
        records = _load_records()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Shipping ID", "Shipping Date", "Source", "Last Updated"])
        for sid, payload in sorted(
            records.items(),
            key=lambda x: x[1].get("updated_at", ""),
            reverse=True,
        ):
            writer.writerow([
                sid,
                payload.get("final_shipping_date", ""),
                payload.get("source_path", ""),
                payload.get("updated_at", ""),
            ])

        # UTF-8 BOM so Excel opens it without a converter dialog.
        csv_bytes = "\ufeff".encode("utf-8") + buf.getvalue().encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header(
            "Content-Disposition",
            'attachment; filename="shipping_lookups.csv"',
        )
        self.send_header("Content-Length", str(len(csv_bytes)))
        self.end_headers()
        self.wfile.write(csv_bytes)

    def log_message(self, fmt: str, *args) -> None:  # noqa: ANN001
        # Suppress the default stderr access log — use Python logging instead.
        pass

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json({"status": "ok"})
            return
        if self.path == "/export.csv":
            self._send_csv_export()
            return
        if self.path != "/":
            self._send_html(
                _render("", "", True, "single", "daily", True), status=404
            )
            return
        self._send_html(_render("", "", True, "single", "daily", True))

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/shipping-ids":
            self._handle_shipping_ids_api()
            return

        if self.path != "/":
            self._send_html(
                _render("", "", True, "single", "daily", True), status=404
            )
            return

        content_type = self.headers.get("Content-Type", "")

        if "multipart/form-data" not in content_type:
            error = (
                "<section class=\"result error\">"
                "<h3>Error</h3>"
                "<pre>Unsupported request format. Please submit using the upload form.</pre>"
                "</section>"
            )
            self._send_html(_render("", error, True, "single", "daily", True), status=400)
            return

        content_length = int(self.headers.get("Content-Length", -1))
        form = _parse_multipart(self.rfile, content_type, content_length)

        invoice_file = form.get("invoice_file")
        if not isinstance(invoice_file, _FormFile):
            invoice_file = None

        # AI assist and totals always run; no UI toggles
        enable_ai = True
        include_totals = True
        shipping_id = _form_str(form, "shipping_id")

        lookup_mode = _form_str(form, "lookup_mode", "single").strip().lower()
        if lookup_mode not in {"single", "all"}:
            lookup_mode = "single"

        group_by = _form_str(form, "group_by", "daily").strip().lower()
        if group_by not in {"daily", "weekly", "monthly", "quarterly", "annual"}:
            group_by = "daily"

        file_path: Path | None = None

        try:
            if invoice_file is not None and invoice_file.filename:
                file_path = _write_uploaded_file(invoice_file, "invoice_")

            if file_path is not None:
                if lookup_mode == "all":
                    saved_path = _persist_uploaded_file(file_path, shipping_id or "all")
                    result = _build_all_lookup_result_from_file(
                        file_path, group_by, saved_path, include_totals
                    )
                    self._send_html(
                        _render(shipping_id, result, enable_ai, lookup_mode, group_by, include_totals)
                    )
                    return

                if shipping_id.strip():
                    saved_path = _persist_uploaded_file(file_path, shipping_id)
                    _record_saved_file(shipping_id, str(saved_path))
                    result = _build_lookup_result_from_file(
                        file_path, shipping_id, saved_path, include_totals
                    )
                    self._send_html(
                        _render(shipping_id, result, enable_ai, lookup_mode, group_by, include_totals)
                    )
                    return

                # Spreadsheets have no free-text fields to mine; use structured rows
                if file_path.suffix.lower() == ".xlsx":
                    saved_path = _persist_uploaded_file(file_path, "workbook")
                    result = _build_all_lookup_result_from_file(
                        file_path, group_by, saved_path, include_totals
                    )
                    self._send_html(
                        _render(shipping_id, result, enable_ai, lookup_mode, group_by, include_totals)
                    )
                    return

                result = _build_result_from_path(file_path, enable_ai, shipping_id)
                self._send_html(
                    _render(shipping_id, result, enable_ai, lookup_mode, group_by, include_totals)
                )
                return

            if shipping_id.strip():
                result = _build_lookup_result_from_cache(shipping_id, include_totals)
                self._send_html(
                    _render(shipping_id, result, enable_ai, lookup_mode, group_by, include_totals)
                )
                return

            error = (
                "<section class=\"result error\">"
                "<h3>Error</h3>"
                "<pre>Please upload one file to process, or include a Shipping/Order ID for cached lookup. "
                "For All Shipping IDs mode, upload an .xlsx file.</pre>"
                "</section>"
            )
            self._send_html(
                _render(shipping_id, error, enable_ai, lookup_mode, group_by, include_totals),
                status=400,
            )
        finally:
            if file_path is not None:
                file_path.unlink(missing_ok=True)


# ── CLI entry point ───────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local web UI for Ship Date Engine")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind (default: 8000)"
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), ShipDateWebHandler)
    print(f"Ship Date Engine web UI running at http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
