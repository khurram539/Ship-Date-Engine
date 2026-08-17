# Quick Start Guide - Fix Server & Add Status Bar

## 🚀 Your web.py.fixed (298KB) is ready to use!

You already downloaded a clean web.py from GitHub earlier. Here's how to use it:

### Step 1: Download Clean web.py on EC2
```bash
cd /home/kkhoja/Code/Ship-Date-Engine/ship_date_engine
curl -L "https://raw.githubusercontent.com/khurram539/Ship-Date-Engine/main/web.py" > web.py.new
ls -lh web.py.new  # Should be ~298KB, ~1150 lines
```

### Step 2: Download the Status Bar Script
```bash
curl -L "https://raw.githubusercontent.com/khurram539/Ship-Date-Engine/main/add_status_bar_to_web.py" -o add_status_bar.py
chmod +x add_status_bar.py
```

### Step 3: Run the Script to Add Status Bar
```bash
cd /home/kkhoja/Code/Ship-Date-Engine/ship_date_engine
python3 add_status_bar.py web.py.new ship_date_engine/web.py.final
```

### Step 4: Replace Corrupted web.py and Start Server
```bash
cd /home/kkhoja/Code/Ship-Date-Engine
sudo lsof -ti :8000 | xargs -r kill -9 || true
sleep 3
nohup python3.11 -m ship_date_engine.web --host 0.0.0.0 --port 8000 > /home/kkhoja/logs/server.log 2>&1 &
sleep 8
```

### Step 5: Verify It's Working
```bash
curl -s http://localhost:8000/ | grep "All Systems Healthy" && echo "✅ SUCCESS!"
curl -s http://localhost:8000/ | grep "__SHIPPING_ID_OPTIONS__" && echo "✅ Dropdown working!"
```

### Step 6: Visit Your Server
Open browser to: **http://32.195.141.20:8000**

**Hard refresh with Ctrl+Shift+R** to see:
- ✅ Green status bar at bottom ("All Systems Healthy")
- ✅ Shipping ID dropdown showing cached options
- ✅ 30-second auto-refresh timer

---

## 📁 Alternative: Use web.py.fixed Directly

If you still have `web.py.fixed` (~298KB from earlier):

```bash
cd /home/kkhoja/Code/Ship-Date-Engine/ship_date_engine
python3 add_status_bar_to_web.py web.py.fixed ship_date_engine/web.py.final
mv ship_date_engine/web.py.final ship_date_engine/web.py
```

Then restart the server as shown above.

---

## 🔄 After Making Changes

To update your EC2 server with new changes:
```bash
cd /home/kkhoja/Code/Ship-Date-Engine
# Pull latest from GitHub
git pull origin main
# Restart server
sudo systemctl restart ship_date_engine.service
```

---

## ✅ Features Now Working

1. **System Status Bar** - Green bar at bottom showing API, Database, and Web Interface health
2. **30-second Auto-refresh** - Live updates every 30 seconds
3. **Shipping ID Dropdown** - Autocomplete from your cached IDs (5608, TEST001, etc.)
4. **Auto-start on Reboot** - systemd service configured