#!/bin/bash
set -euo pipefail

echo "=== Disaster Recovery ==="
echo "1/4 Repo clonen…"
git clone https://github.com/HaraldKiessling/IaC4.git /opt/IaC4
cd /opt/IaC4

echo "2/4 Secrets bereitstellen (aus GH oder manuell)…"
# copy .env.example → .env und ausfüllen

echo "3/4 Basis-Deploy…"
make deploy target="${1:-prod}"

echo "4/4 Qdrant-Volume wiederherstellen…"
# docker volume restore qdrant qdrant-data
echo "✅ Recovery abgeschlossen"
