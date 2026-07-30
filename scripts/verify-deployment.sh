#!/bin/bash
set -euo pipefail

echo "=== Post-Deploy-Verifikation ==="
TARGET="${1:-dev}"
VPS="vps-${TARGET}.tailcfea8a.ts.net"

echo "1/4 VPS erreichbar via Tailscale?"
ssh "deploy-user@${VPS}" "hostname && uptime" || { echo "❌"; exit 1; }

echo "2/4 Docker läuft?"
ssh "deploy-user@${VPS}" "docker info >/dev/null 2>&1 && echo '✅'" || { echo "❌"; exit 1; }

echo "3/4 Qdrant erreichbar?"
curl -sf "http://${VPS}:6333/health" >/dev/null && echo "✅" || { echo "❌"; exit 1; }

echo "4/4 OpenClaw Gateway?"
curl -sf "http://${VPS}:18789/health" >/dev/null && echo "✅" || { echo "❌"; exit 1; }

echo "=== ✅ Alle Checks bestanden ==="
