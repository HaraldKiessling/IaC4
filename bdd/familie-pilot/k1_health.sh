#!/usr/bin/env bash
# K1 – Instanz laeuft auf oc1 (dev), Gateway erreichbar (Konzept §7 K1)
# Remote-Check: Health-Endpunkt, Container-Status, Tailscale-Serve-Route.
# Lokal: nur Skip (kein Deploy-Zugriff) – VPS_HOST setzen fuer echten Check.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=bdd-lib.sh
. "$SCRIPT_DIR/bdd-lib.sh"

echo "Feature: K1 – Gateway der Familien-Instanz ist auf oc1 erreichbar"

given "Docker-Container openclaw-$INSTANCE laeuft auf dem dev-VPS (Tailscale)"
when "Health-Endpunkt und Container-Status werden geprueft"
if [ -z "$VPS_HOST" ]; then
  skip "Remote-Deploy-Check (K1) – VPS_HOST nicht gesetzt (laeuft auf GH-Runner/VPS)"
else
  vps_run "Health: GET https://localhost:$PORT/health -> HTTP 200" \
    "curl -sk --max-time 8 -o /dev/null -w '%{http_code}' https://localhost:$PORT/health | grep -q 200"
  vps_run "Container openclaw-$INSTANCE ist healthy" \
    "docker ps --filter name=^openclaw-$INSTANCE$ --format '{{.Status}}' | grep -qiE 'healthy|up'"
  vps_run "tailscale serve enthaelt Route $PORT -> localhost:$PORT" \
    "tailscale serve status | grep -q 'localhost:$PORT'"
fi

bdd_summary
