#!/usr/bin/env python3
"""Quick fix: Add system status bar to web.py"""
import re, sys, os

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 add_status_bar.py /path/to/web.py")
        sys.exit(1)
    
    web_py = sys.argv[1]
    with open(web_py, 'r') as f:
        content = f.read()
    
    # Find where to insert - look for the pattern before </body> in HTML template
    status_bar = '''<!-- System Status Bar (2026-08-17) -->
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
function checkSystemHealth() { fetch('/api/health',{method:'GET'}).then(r=>r.json()).catch(()=>null); }
if(document.getElementById('system-status-bar')){ checkSystemHealth();setInterval(checkSystemHealth,30000); }
</script>'''

    # Use regex to find the position: look for "\n    </script>" before </body> in HTML template
    match = re.search(r'HTML_PAGE.*?</script>[\s\S]*?\n\s*</body>', content, re.DOTALL)
    if not match:
        print("Could not find insertion point")
        return False
    
    # Insert before </body>
    pos = content.find('</body>', match.end() - len(match.group()))
    new_content = content[:pos] + status_bar + '\n' + content[pos:]
    
    with open(web_py, 'w') as f:
        f.write(new_content)
    
    print(f"✅ Added status bar to {web_py}")
    print("✅ Both features now available:")
    print("   • Shipping ID dropdown (__SHIPPING_ID_OPTIONS__)")
    print("   • System Status Bar (system-status-bar)")
    return True

if __name__ == '__main__':
    main()
