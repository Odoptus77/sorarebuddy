#!/usr/bin/env bash
# Pull the latest code and restart backend (+ dashboard if installed).
# Run as root from /opt/sorarebuddy:
#   cd /opt/sorarebuddy && sudo bash deploy/update.sh
set -euo pipefail
APP_DIR=/opt/sorarebuddy
[ "$(id -u)" -eq 0 ] || { echo "Please run as root (sudo)."; exit 1; }
cd "$APP_DIR"
git pull --ff-only
# re-sync the units in case they changed
install -m 644 deploy/sorarebuddy.service /etc/systemd/system/sorarebuddy.service
if [ -f /etc/systemd/system/sorarebuddy-dashboard.service ]; then
  install -m 644 deploy/sorarebuddy-dashboard.service /etc/systemd/system/sorarebuddy-dashboard.service
fi
systemctl daemon-reload
systemctl restart sorarebuddy
sleep 1
systemctl --no-pager --lines=5 status sorarebuddy || true
curl -fsS http://127.0.0.1:8080/health && echo

if systemctl is-enabled --quiet sorarebuddy-dashboard 2>/dev/null; then
  bash deploy/build-dashboard.sh
  systemctl restart sorarebuddy-dashboard
  sleep 3
  echo "dashboard: HTTP $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/) (401 = läuft, Login verlangt)"
fi
