#!/usr/bin/env bash
# OS update for the Ship Date Engine server (RHEL 9 / dnf).
# Usage: ./os_update.sh          — check + install updates
#        ./os_update.sh --check  — only show available updates
set -euo pipefail

HEALTH_URL="http://127.0.0.1:8000/health"

echo "==> Checking for available updates"
# dnf check-update exits 100 when updates exist, 0 when none
set +e
sudo dnf check-update --refresh
STATUS=$?
set -e

if [[ $STATUS -eq 0 ]]; then
    echo "System is already up to date."
    exit 0
elif [[ $STATUS -ne 100 ]]; then
    echo "ERROR: dnf check-update failed (exit $STATUS)" >&2
    exit "$STATUS"
fi

if [[ "${1:-}" == "--check" ]]; then
    echo "Updates are available. Run ./os_update.sh to install."
    exit 0
fi

echo "==> Installing updates"
sudo dnf upgrade -y

echo "==> Removing unneeded packages"
sudo dnf autoremove -y

echo "==> Checking whether a reboot is required"
if ! sudo needs-restarting -r; then
    echo ""
    echo "REBOOT REQUIRED. Run: sudo reboot"
    echo "(ship-date-engine.service is enabled and will start automatically after reboot)"
else
    echo "No reboot required."
    SERVICES=$(sudo needs-restarting -s 2>/dev/null | grep -v '^$' || true)
    if [[ -n "$SERVICES" ]]; then
        echo "Services that should be restarted:"
        echo "$SERVICES"
    fi
fi

echo "==> Verifying web app health"
if curl -sf -o /dev/null "$HEALTH_URL"; then
    echo "OK: Ship Date Engine is healthy."
else
    echo "WARNING: web app not responding at $HEALTH_URL — check: systemctl status ship-date-engine" >&2
fi
