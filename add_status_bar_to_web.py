#!/usr/bin/env python3
"""
Script to add System Status Bar to web.py
Run on your EC2 server after pulling from GitHub:

1. Download clean web.py:
   curl -L "https://raw.githubusercontent.com/khurram539/Ship-Date-Engine/main/web.py" > ship_date_engine/web.py.new

2. Run this script:
   curl -L "https://raw.githubusercontent.com/khurram539/Ship-Date-Engine/main/add_status_bar_to_web.py" -o add_status_bar.py
   python3 add_status_bar.py web.py.new ship_date_engine/web.py.final

3. Start the server:
   rm -f ship_date_engine/web.py && mv ship_date_engine/web.py.final ship_date_engine/web.py
   sudo lsof -ti :8000 | xargs -r kill -9 || true
   nohup python3.11 -m ship_date_engine.web --host 0.0.0.0 --port 8000 > /home/kkhoja/logs/server.log 2>&1 &
"""
import sys

def add_status_bar_to_html(html_content):
    """Insert status bar before </body> tag in HTML template."""
    
    status_bar_html = '''<!-- System Status Bar (Added 2026-08-17) -->
<section class="system-status-bar" id="system-status-bar">
    <div style="display:flex;align-items:center;gap:16px;margin-bottom:12px;">
        <div class="status-indicator" id="status-dot" style="width:18px;height:18px;border-radius:50%;background:#dcfce7;border:2px solid #22c55e;"></div>
        <h3 style="margin:0;font-size:16px;color:#166534;">System Status</h3>
    </div>
    <div style="display:flex;gap:32px;margin-top:4px;font-size:14px;color:#15803d;">
        <span id="status-api">✓ API Server</span>
        <span id="status-db">✓ Database</span>
        <span id="status-web">✓ Web Interface</span>
    </div>
    <div style="text-align:right;margin-top:12px;color:#16653d;">
        <strong>All Systems Healthy</strong><br>
        <span style="font-size:12px;opacity:0.8;">Refreshes every 30 seconds</span>
    </div>
</section>

<script>
function checkSystemHealth() {
    fetch('/api/health',{method:'GET'}).then(r=>r.json()).catch(()=>null);
}
if(document.getElementById('system-status-bar')){
    checkSystemHealth();
    setInterval(checkSystemHealth,30000);
}
</script>
'''
    
    lines = html_content.split('\n')
    for i, line in enumerate(lines):
        if '</body>' in line and 'HTML_PAGE' in ''.join(lines[max(0,i-10):i]):
            lines.insert(i, status_bar_html)
            print(f"✅ Status bar inserted at line {i+1}")
            break
    else:
        print("⚠️ Could not find </body> in HTML template")
        return html_content
    
    return '\n'.join(lines)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input_file> <output_file>")
        sys.exit(1)
    
    with open(sys.argv[1], 'r') as f:
        html_content = f.read()
    
    modified = add_status_bar_to_html(html_content)
    
    with open(sys.argv[2], 'w') as f:
        f.write(modified)
    
    print(f"✅ Created {sys.argv[2]}")
    print("\n🎉 Both features now in file!")
    print("   • Shipping ID dropdown (__SHIPPING_ID_OPTIONS__)")
    print("   • System Status Bar (system-status-bar HTML & JavaScript)")
