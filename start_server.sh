#!/bin/bash
echo "Starting Ship Date Engine Web Server..."
cd /home/kkhoja/Code/Ship-Date-Engine
python3.11 -m ship_date_engine.web --host 0.0.0.0 --port 8000 > /tmp/server.log 2>&1 &
sleep 5
if lsof -i :8000 | grep -q LISTEN; then
    echo "✓ Server started on http://0.0.0.0:8000"
else
    echo "✗ Failed. Check /tmp/server.log"
fi