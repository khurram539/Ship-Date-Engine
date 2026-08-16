# Navigate to correct directory
cd /home/kkhoja/Code/Ship-Date-Engine

# Kill any existing servers (be careful with kill -9)
pkill -f "uvicorn" || true
pkill -f "ship_date_engine.web" || true
sleep 3

# Check if ports are now free
netstat -tlnp | grep -E '(:8000|:8001|:8002)' || echo "Ports are free"

# Pull latest code from GitHub
git pull origin main

echo "✅ Code updated from main branch"

# Start REST API server (new, on port 8002)
nohup python3 -m uvicorn ship_date_engine.api:app --host 0.0.0.0 --port 8002 > /tmp/api.log 2>&1 &
echo "✅ REST API starting on port 8002"

# Wait for startup
sleep 5

# Test API health
curl http://localhost:8002/health

echo ""
echo "=== Final Status ==="
ps aux | grep -E "(uvicorn|python)" | grep -v grep
