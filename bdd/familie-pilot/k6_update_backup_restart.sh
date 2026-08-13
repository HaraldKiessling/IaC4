#!/usr/bin/env bash
# K6 – Update-/Backup-/Restart-Prozedur dokumentiert (§7 K6) – LOKAL
# Prueft, dass die Betriebs-Doku (arc42/07 + ADR-025) die Prozeduren nennt.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=bdd-lib.sh
. "$SCRIPT_DIR/bdd-lib.sh"

echo "Feature: K6 – Update-/Backup-/Restart-Prozedur ist dokumentiert"

given "Doku (docs/arc42/07_verteilungssicht.md, docs/adr/ADR-025) beschreibt den Betrieb"
DOC="$REPO_ROOT/docs/arc42/07_verteilungssicht.md"
ADR="$REPO_ROOT/docs/adr/ADR-025-openclaw-deployment.md"

assert_grep "Update: Pin-Variable + Deploy (pull: always) dokumentiert" "$DOC" "openclaw_image_version"
assert_grep "Update: Rollback-Pfad (alten Pin wiederherstellen) dokumentiert" "$DOC" "Rollback"
assert_grep "Backup: Pfade /srv/openclaw/oc1/config + workspace dokumentiert" "$DOC" "/srv/openclaw/$INSTANCE/(config|workspace)"
assert_grep "Backup: Secrets sind SSoT in GH-Secrets (keine Secrets im Backup)" "$DOC" "GH-Secrets"
assert_grep "Restart: docker compose restart openclaw-$INSTANCE dokumentiert" "$DOC" "restart openclaw"
assert_grep "ADR-025: Update-Pfad (Pin -> Deploy) belegt" "$ADR" "Update-Pfad"

bdd_summary
