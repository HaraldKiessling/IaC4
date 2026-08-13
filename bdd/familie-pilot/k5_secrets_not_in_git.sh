#!/usr/bin/env bash
# K5 – Secrets liegen nicht in Git (§7 K5) – komplett LOKAL ausfuehrbar
# git grep auf Secret-Muster, .gitignore-Ausschluss, .env.example-Existenz.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=bdd-lib.sh
. "$SCRIPT_DIR/bdd-lib.sh"

echo "Feature: K5 – Keine Secret-Werte im committeten Repository"

given "Feature-Branch $PILOT_BRANCH ist gepusht; Repo enthaelt nur Platzhalter"
when "Secret-Scan + .gitignore/.env.example-Pruefung ausgefuehrt werden"
check_secret_scan

bdd_summary
