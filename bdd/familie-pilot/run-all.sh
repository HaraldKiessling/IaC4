#!/usr/bin/env bash
# run-all.sh – Fuehrt alle Pilot-BDD-Checks K1..K8 aus (bdd/familie-pilot/)
# Lokal: K1/K2-remote/K3-remote/K4-remote werden ohne VPS_HOST geskippt;
# K5 (Secret-Scan), K2-K4-Strukturteile, K6, K7, K8 laufen komplett lokal.
# Remote: VPS_HOST=vps-dev.tailcfea8a.ts.net ./run-all.sh (Read-only-SSH-Checks).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAILED=0
for k in k1_health k2_bots_persona k3_storage_separation k4_shared_llm_keys \
         k5_secrets_not_in_git k6_update_backup_restart k7_review k8_no_merge; do
  echo ""
  echo "########## $k ##########"
  if ! bash "$SCRIPT_DIR/$k.sh"; then
    FAILED=1
  fi
done
echo ""
if [ "$FAILED" -eq 0 ]; then
  echo "run-all: ALLE K-Checks bestanden (Skips nur bei deploy-abhaengigen Checks ohne VPS_HOST)."
else
  echo "run-all: Mindestens ein K-Check fehlgeschlagen (siehe oben)."
  exit 1
fi
