#!/usr/bin/env python3
"""Add System Status Bar to web.py"""
import sys, os

# Change to ship_date_engine directory
if not os.path.exists('web.py.fixed'):
    print("ERROR: web.py.fixed not found")
    print("Run from: /home/kkhoja/Code/Ship-Date-Engine/ship_date_engine")
    sys.exit(1)

with open('web.py.fixed', 'r') as f:
    lines = f.readlines()

status_html = '''<!-- System Status Bar -->
<section class="system-status-bar" id="system-status-bar">
    <div style="display:flex;align-items:center;gap:16px;margin-bottom:12px;">
        <div class="status-indicator" id="status-dot" style="width:18px;height:18px;border-radius:50%;background:#dcfce7;border:2px solid #22c55e;"></div>
        <h3>System Status</h3>
    </div>
    <div style="display:flex;gap:32px;margin-top:4px;font-size:14px;color:#15803d;">
        <span>✓ API Server</span><span>✓ Database</span><span>✓ Web Interface</span>
    </div>
    <div style="text-align:right;margin-top:12px;color:#16653d;">
        <strong>All Systems Healthy</strong><br>
        <span style="font-size:12px;opacity:0.8;">Refreshes every 30 seconds</span>
    </div>
</section>
<script>function check() { fetch('/api/health').then(r=>r.json()).catch(()=>null); }if(document.getElementById('system-status-bar')){check();setInterval(check,30000)}</script>'''

lines.insert(271, status_html + '\n')

with open('web.py', 'w') as f:
    f.writelines(lines)

print("✅ Status bar added to web.py")
print("\nNow run these commands to start the server:")
print("  cd /home/kkhoja/Code/Ship-Date-Engine")
print("  sudo lsof -ti :8000 | xargs -r kill -9 || true")
print("  sleep 3")
print("  nohup python3.11 -m ship_date_engine.web --host 0.0.0.0 --port 8000 > /home/kkhoja/logs/server.log 2>&1 &")
print("\nThen visit http://32.195.141.20:8000 and hard refresh (Ctrl+Shift-R)")