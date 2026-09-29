#!/usr/bin/env bash
# One-time setup of the Next.js dashboard next to the backend (Debian/Ubuntu).
# Prerequisite: the backend is installed (deploy/install.sh) in /opt/sorarebuddy.
# Run as root from there:
#   cd /opt/sorarebuddy && git pull && sudo bash deploy/install-dashboard.sh
set -euo pipefail

APP_DIR=/opt/sorarebuddy
DASH_DIR=$APP_DIR/dashboard
SVC_USER=sorarebuddy

[ "$(id -u)" -eq 0 ] || { echo "Please run as root (sudo)."; exit 1; }
[ -d "$DASH_DIR" ] || { echo "No $DASH_DIR -- run 'git pull' in $APP_DIR first."; exit 1; }
id -u "$SVC_USER" >/dev/null 2>&1 || { echo "Run deploy/install.sh (backend) first."; exit 1; }

# 1) Node.js >= 20.9 (Next.js 16). Ubuntu's own package is too old -> NodeSource 22 LTS.
need_node=1
if command -v node >/dev/null; then
  major=$(node -p 'process.versions.node.split(".")[0]')
  [ "$major" -ge 20 ] && need_node=0
fi
if [ "$need_node" -eq 1 ]; then
  echo ">> Installing Node.js 22 LTS (NodeSource) ..."
  apt-get update -y && apt-get install -y ca-certificates curl gnupg
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi
echo ">> node $(node -v), npm $(npm -v)"

# 2) env file (secrets) -- created once, then edit it
install -d -m 750 /etc/sorarebuddy
if [ ! -f /etc/sorarebuddy/dashboard.env ]; then
  install -m 600 "$APP_DIR/deploy/dashboard.env.example" /etc/sorarebuddy/dashboard.env
  # prefill the backend token from the backend's env, if present
  tok=$(grep -E '^APP_TOKEN=' /etc/sorarebuddy/env 2>/dev/null | cut -d= -f2- || true)
  if [ -n "$tok" ] && [ "$tok" != "replace_with_random_hex" ]; then
    sed -i "s|^SORAREBUDDY_API_TOKEN=.*|SORAREBUDDY_API_TOKEN=$tok|" /etc/sorarebuddy/dashboard.env
  fi
  pw=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)
  sed -i "s|^DASHBOARD_PASSWORD=.*|DASHBOARD_PASSWORD=$pw|" /etc/sorarebuddy/dashboard.env
  echo ">> Created /etc/sorarebuddy/dashboard.env (backend token prefilled, random password set)."
  echo "   Your dashboard login:  user 'nick'  password '$pw'   (change it in that file if you like)"
else
  echo ">> Keeping existing /etc/sorarebuddy/dashboard.env."
fi

# 3) build (as root), then hand the build dir to the service user (Next writes .next/cache)
bash "$APP_DIR/deploy/build-dashboard.sh"

# 4) systemd service
install -m 644 "$APP_DIR/deploy/sorarebuddy-dashboard.service" /etc/systemd/system/sorarebuddy-dashboard.service
systemctl daemon-reload
systemctl enable --now sorarebuddy-dashboard
sleep 3
systemctl --no-pager --lines=5 status sorarebuddy-dashboard || true
code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/ || true)
echo ">> http://127.0.0.1:3000/ -> HTTP $code (401 = läuft, Login verlangt)"

cat <<EOT

Done. Next: route your domain to the dashboard in Caddy (deploy/Caddyfile):
  sudo cp /opt/sorarebuddy/deploy/Caddyfile /etc/caddy/Caddyfile
  sudo nano /etc/caddy/Caddyfile      # your domain (same one as the backend)
  sudo systemctl reload caddy
Then open https://<your-domain>/ and log in.
EOT
