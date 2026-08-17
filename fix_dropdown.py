#!/usr/bin/env python3
"""Add API endpoint for shipping IDs and auto-refresh dropdown"""
import re

# Read current web.py
with open('ship_date_engine/web.py', 'r') as f:
    content = f.read()

# 1. Add API endpoint in do_GET method (after /health check)
api_endpoint_code = '''
        # New: Return all cached shipping IDs
        if self.path == "/api/shipping-ids":
            records = json.loads((RECORDS_PATH).read_text()) if RECORDS_PATH.exists() else {}
            ids = sorted(records.keys())
            self._send_json({"ids": ids})
            return
'''

# Insert after the /health endpoint in do_GET
old_health = '        if self.path == "/health":\n            self._send_json({"status": "ok"})\n            return'
new_health = old_health + api_endpoint_code.strip()
content = content.replace(old_health, new_health)

# 2. Update JavaScript to fetch shipping IDs after page load
dropdown_script = '''// Auto-refresh dropdown with cached IDs on page load and after uploads
function updateShippingIDDropdown() {
    fetch('/api/shipping-ids', {method: 'GET'})
        .then(response => response.json())
        .then(data => {
            const ids = data.ids || [];
            if (ids.length === 0) return;
            
            const datalist = document.querySelector('[id="shipping-id-suggestions"]');
            if (!datalist) return;
            
            // Clear existing options
            datalist.innerHTML = '';
            
            // Add all IDs as options
            ids.forEach(id => {
                const option = document.createElement('option');
                option.value = id;
                option.textContent = id;
                datalist.appendChild(option);
            });
            
            console.log(`Updated dropdown with ${ids.length} shipping IDs`);
        })
        .catch(err => console.log('Dropdown update skipped:', err));
}

// Call on page load
if (document.getElementById('system-status-bar') || true) {
    updateShippingIDDropdown();
}

// Also refresh dropdown after upload completes (when results show)
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(updateShippingIDDropdown, 500);
});'''

# Find the existing status bar script section and add dropdown update there
old_script = "if(document.getElementById('system-status-bar')){checkHealth();setInterval(checkHealth,30000)}"
new_script = old_script + "\nupdateShippingIDDropdown()"
content = content.replace(old_script, new_script)

# Write updated web.py
with open('ship_date_engine/web.py', 'w') as f:
    f.write(content)

print("✅ Added /api/shipping-ids endpoint")
print("✅ Updated JavaScript to auto-refresh dropdown")
print("\nThe dropdown will now automatically show all cached shipping IDs!")
print("Run: cd /home/kkhoja/Code/Ship-Date-Engine && sudo systemctl restart ship_date_engine.service")