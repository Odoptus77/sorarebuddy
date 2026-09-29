#!/usr/bin/env bash
# (Re)build the Next.js dashboard. Called by install-dashboard.sh and update.sh.
set -euo pipefail
DASH_DIR=/opt/sorarebuddy/dashboard
cd "$DASH_DIR"
export NEXT_TELEMETRY_DISABLED=1
npm ci --no-audit --no-fund
npm run build
chown -R sorarebuddy:sorarebuddy "$DASH_DIR/.next"
