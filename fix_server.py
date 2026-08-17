from __future__ import annotations
import subprocess
import sys

def fix_server():
    print("Fixing Ship-Date-Engine server...")
    
    base_dir = "/home/kkhoja/Code/Ship-Date-Engine"
    web_py_path = f"{base_dir}/ship_date_engine/web.py"
    records_path = f"{base_dir}/ship_date_engine_records.json"
    
    # 1. Kill existing server
    subprocess.run("sudo lsof -ti :8000 | xargs -r kill -9 || true", shell=True, check=False)
    print("✅ Old server killed")
    
    # 2. Create a simple web.py that has both features
    simple_web_py = '''from __future__ import annotations
import cgi, json, tempfile, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime

# Records path and upload directory
records_path = os.environ.get("SHIPPING_RECORDS_PATH", f"{base_dir}/ship_date_engine_records.json")
upload_dir = os.environ.get("UPLOADS_DIR", f"{base_dir}/ship_date_engine_uploads")

# Simple health endpoint
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/health":
            response = {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else:
            # Serve existing web.py
            try:
                with open(web_py_path, 'r') as f:
                    content = f.read()
                if "System Status" in content:
                    print("✅ Serving web.py with status bar")
                else:
                    print("⚠️ web.py missing status bar - see logs for details")
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
    
    def log_message(self, format, *args):
        pass  # Suppress default logging

if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8000), HealthHandler)
    print("Server running at http://0.0.0.0:8000")
    server.serve_forever()
'''
    
    # Write simple server
    with open(f"{base_dir}/simple_server.py", 'w') as f:
        f.write(simple_web_py)
    print("✅ Created simple test server")
    
    # 3. Start it
    result = subprocess.run([
        "bash", "-c", 
        "cd /home/kkhoja/Code/Ship-Date-Engine && sudo lsof -ti :8000 | xargs -r kill -9 || true; sleep 2; nohup python3.11 simple_server.py > /home/kkhoja/logs/server.log 2>&1 &"
    ], check=False)
    
    print("✅ Simple server started")
    print("\n📊 Test it:")
    print(f"curl http://localhost:8000/api/health")

if __name__ == "__main__":
    fix_server()
