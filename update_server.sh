#!/usr/bin/env bash
# Update the Ship Date Engine server: pull latest main, test, restart, verify.
set -euo pipefail

REPO_DIR="/home/kkhoja/Code/Ship-Date-Engine"
HEALTH_URL="http://127.0.0.1:8000/health"
PROC_PATTERN="ship_date_engine.web"

cd "$REPO_DIR"

echo "==> Checking working tree"
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "ERROR: uncommitted changes in $REPO_DIR — commit or stash them first." >&2
    exit 1
fi

echo "==> Pulling latest main"
git fetch origin
BEFORE=$(git rev-parse --short HEAD)
git pull --ff-only origin main
AFTER=$(git rev-parse --short HEAD)

if [[ "$BEFORE" == "$AFTER" ]]; then
    echo "Already up to date at $AFTER"
else
    echo "Updated $BEFORE -> $AFTER"
    git --no-pager log --oneline "$BEFORE..$AFTER"
fi

echo "==> Running tests"
python3 -m pytest tests/ ship_date_engine/test_engine.py -q

echo "==> Restarting server (systemd auto-respawns)"
OLD_PID=$(pgrep -f "$PROC_PATTERN" || true)
if [[ -n "$OLD_PID" ]]; then
    kill $OLD_PID
else
    echo "No running server found; systemd should start it."
fi

echo "==> Waiting for server"
for i in $(seq 1 15); do
    sleep 2
    if curl -sf -o /dev/null "$HEALTH_URL"; then
        NEW_PID=$(pgrep -f "$PROC_PATTERN" || true)
        echo "OK: server healthy (PID ${NEW_PID:-unknown}) at commit $AFTER"
        exit 0
    fi
done

echo "ERROR: server did not become healthy after restart. Check: systemctl status ship-date-engine" >&2
exit 1
