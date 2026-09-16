#!/usr/bin/env bash
# One-time VPS setup for the sorarebuddy backend (Debian/Ubuntu).
# Clone the repo to /opt/sorarebuddy first, then run this as root from there:
#   sudo git clone https://github.com/Odoptus77/sorarebuddy /opt/sorarebuddy
#   cd /opt/sorarebuddy && sudo bash deploy/install.sh
set -euo pipefail

APP_DIR=/opt/sorarebuddy
SVC_USER=sorarebuddy

[ "$(id -u)" -eq 0 ] || { echo "Please run as root (sudo)."; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required."; exit 1; }

SRC="$(cd "$(dirname "$0")/.." && pwd)"
if [ "$SRC" != "$APP_DIR" ]; then
  echo "Expected the repo at $APP_DIR (found $SRC)."
  echo "Clone it there:  sudo git clone <repo> $APP_DIR && cd $APP_DIR"
  exit 1
fi

# 1) system user (no login, no home writes)
id -u "$SVC_USER" >/dev/null 2>&1 || \
  useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$SVC_USER"

# 2) writable cache/state dir
install -d -o "$SVC_USER" -g "$SVC_USER" -m 750 /var/lib/sorarebuddy/cache

# 3) env file (secrets) — created once, then edit it
install -d -m 750 /etc/sorarebuddy
if [ ! -f /etc/sorarebuddy/env ]; then
  install -m 600 "$APP_DIR/deploy/env.example" /etc/sorarebuddy/env
  echo ">> Created /etc/sorarebuddy/env — edit it now (SORARE_API_KEY, APP_TOKEN)."
else
  echo ">> Keeping existing /etc/sorarebuddy/env."
fi

# 4) systemd service
install -m 644 "$APP_DIR/deploy/sorarebuddy.service" /etc/systemd/system/sorarebuddy.service
systemctl daemon-reload
systemctl enable sorarebuddy

cat <<EOF

Done. Next:
  1. sudo nano /etc/sorarebuddy/env          # set SORARE_API_KEY + APP_TOKEN
  2. sudo systemctl restart sorarebuddy
  3. sudo systemctl status sorarebuddy        # should be active (running)
  4. curl -s http://127.0.0.1:8080/health      # {"ok": true}

Then put HTTPS in front of it (see deploy/README.md):
  - Caddy (easiest):  deploy/Caddyfile   ->  /etc/caddy/Caddyfile
  - or nginx+certbot: deploy/nginx-sorarebuddy.conf
EOF
