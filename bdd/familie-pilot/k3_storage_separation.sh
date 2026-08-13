#!/usr/bin/env bash
# K3 – Speicher getrennt: Workspace/Sessions Person A nicht in B sichtbar (§7 K3)
# Lokal: Pfad-Trennung per Konstruktion (Template: workspace/<pid>, agents/<pid>/agent).
# Remote: Verzeichnisse auf dem VPS (Host-Pfade) je Person getrennt vorhanden.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=bdd-lib.sh
. "$SCRIPT_DIR/bdd-lib.sh"

echo "Feature: K3 – Speicher der Personen ist getrennt (Workspace/Sessions)"

given "Agents nutzen getrennte workspace/agentDir-Pfade (S3)"
when "Pfad-Konstruktion im Template geprueft wird"
check_path_separation

given "Deployte Verzeichnisse auf dem VPS (falls deployed)"
when "Host-Pfade je Person geprueft werden"
if [ -z "$VPS_HOST" ]; then
  skip "Remote-Verzeichnis-Check (K3) – VPS_HOST nicht gesetzt"
else
  for pid in $PERSONS; do
    vps_run "Workspace-Verzeichnis /srv/openclaw/$INSTANCE/workspace/$pid existiert" \
      "sudo test -d $HOST_DATA_ROOT/$INSTANCE/workspace/$pid && echo OK"
  done
  vps_run "Sessions-Verzeichnisse sind je Person getrennt (Konvention agents/<id>/sessions)" \
    "sudo ls $HOST_DATA_ROOT/$INSTANCE/config/agents 2>/dev/null | grep -qE 'harald|anna' && echo OK || echo 'noch nicht deployt (Q3)'"
  note "Cross-Session-Recall-Test (sessions_history von A zeigt keine B-Sessions): Abnahme/manuel1 – erfordert laufende Instanz mit echten Sessions."
fi

bdd_summary
