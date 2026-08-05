#!/usr/bin/env bash
# persona-check.sh – Persona-Check für deployte Seed-Dateien (CI-Guard, Entscheid 8b)
#
# Zweck:
#   Verhindert, dass Persona-Namen (nova, felix, petrus) in deployte
#   Agent-Workspace-Seed-Dateien (ansible/roles/openclaw-gateway/files/agent-workspaces)
#   einfließen. Diese Dateien werden per Ansible auf die Zielsysteme deployt;
#   ein Persona-Name dort würde den identitätsneutralen Seed (Memory v3.1,
#   Design-Konzept memory-neu-deployment-v3.1, Frage 8b) verletzen.
#
# Aufruf:
#   bash scripts/validate/persona-check.sh
#
# Exit-Codes:
#   0 – keine Persona-Namen gefunden (CI-Guard grün)
#   1 – Persona-Namen gefunden (CI-Guard rot, Fundstellen werden ausgegeben)
set -euo pipefail

FORBIDDEN_PATTERN='nova|felix|petrus'
SEED_DIR='ansible/roles/openclaw-gateway/files/agent-workspaces'

hits=$(grep -rniE "$FORBIDDEN_PATTERN" "$SEED_DIR" --include='*.md' || true)

if [ -n "$hits" ]; then
  echo "FEHLER: Persona-Namen in deployten Seed-Dateien:"
  echo "$hits"
  exit 1
fi

echo "OK: keine Persona-Namen (nova|felix|petrus) in deployten Seed-Dateien"
exit 0
