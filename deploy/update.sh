#!/usr/bin/env bash
# Pull the latest code and restart the backend. Run as root from /opt/sorarebuddy:
#   cd /opt/sorarebuddy && sudo bash deploy/update.sh
set -euo pipefail
APP_DIR=/opt/sorarebuddy
[ "$(id -u)" -eq 0 ] || { echo "Please run as root (sudo)."; exit 1; }
cd "$APP_DIR"
git pull --ff-only
# re-sync the unit in case it changed
install -m 644 deploy/sorarebuddy.service /etc/systemd/system/sorarebuddy.service
systemctl daemon-reload
systemctl restart sorarebuddy
sleep 1
systemctl --no-pager --lines=5 status sorarebuddy || true
curl -fsS http://127.0.0.1:8080/health && echo
