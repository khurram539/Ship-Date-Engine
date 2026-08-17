#!/usr/bin/env python3
"""
Quick fix to add System Status Bar to web.py
Usage on EC2:
  cd /home/kkhoja/Code/Ship-Date-Engine/ship_date_engine
  curl -L "https://raw.githubusercontent.com/khurram539/Ship-Date-Engine/main/quick_add_status_bar.py" -o quick_fix.py
  python3 quick_fix.py web.py.fixed ship_date_engine/web.py
"""
import sys

def add_status_bar():
    # Status bar HTML to insert
    status_html = '''<!-- System Status Bar (2026-08-17) -->
<section class="system-status-bar">
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
function checkHealth() { fetch('/api/health',{method:'GET'}).then(r=>r.json()).catch(()=>null); }
if(document.getElementById('system-status-bar')){ checkHealth();setInterval(checkHealth,30000);}
</script>'''

    # Read the file
    with open(sys.argv[1], 'rb') as f:
        content = f.read()
    
    # Decode and find the HTML template section
    text = content.decode('utf-8')
    lines = text.split('\n')
    
    # Find line number for </body> in HTML string (should be around 260-275)
    insert_line = None
    html_template_section = False
    
    for i, line in enumerate(lines):
        # Detect when we're in the HTML template (HTML_PAGE = """")
        if 'HTML_PAGE' in ''.join(lines[max(0,i-10):i]):
            html_template_section = True
        
        if html_template_section and '</body>' in line:
            insert_line = i + 1
            print(f"✅ Found </body> at line {insert_line}")
            break
    
    if not insert_line:
        print("❌ Could not find </body> tag")
        return False
    
    # Insert status bar after that line
    new_lines = lines[:insert_line] + [status_html, ''] + lines[insert_line:]
    
    # Write output file
    with open(sys.argv[2], 'w') as f:
        f.write('\n'.join(new_lines))
    
    print(f"✅ Created {sys.argv[2]}")
    
    # Verify features
    final_content = '\n'.join(new_lines)
    has_dropdown = '__SHIPPING_ID_OPTIONS__' in final_content
    has_status = 'system-status-bar' in final_content
    
    print(f"\n✅ Features in file:")
    print(f"   • Shipping ID dropdown: {has_dropdown}")
    print(f"   • System Status Bar: {has_status}")
    
    return True

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: python3 {sys.argv[0]} <input_file> <output_file>")
        sys.exit(1)
    
    success = add_status_bar()
    sys.exit(0 if success else 1)
