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
#   bash scripts/validate/persona-check.sh            – echter Scan (CI-Guard)
#   bash scripts/validate/persona-check.sh --selftest – Selbsttest beider Fälle
#
# Exit-Codes:
#   0 – keine Persona-Namen gefunden (CI-Guard grün)
#   1 – Persona-Namen gefunden (CI-Guard rot, Fundstellen werden ausgegeben)
set -euo pipefail

FORBIDDEN_PATTERN='nova|felix|petrus'
SEED_DIR="${SEED_DIR:-ansible/roles/openclaw-gateway/files/agent-workspaces}"

# run_check <dir> – scannt <dir> auf Persona-Namen, gibt Fundstellen aus
#   return 0: keine Treffer
#   return 1: Treffer gefunden (FEHLER-Zeile + Fundstellen)
run_check() {
  local dir="$1"
  local hits
  hits=$(grep -rniE "$FORBIDDEN_PATTERN" "$dir" --include='*.md' || true)

  if [ -n "$hits" ]; then
    echo "FEHLER: Persona-Namen gefunden in <$dir>:"
    echo "$hits"
    return 1
  fi

  echo "OK: keine Persona-Namen in <$dir>"
  return 0
}

# Modus: --selftest – beide Fälle in einem temporären Fixture-Verzeichnis nachweisen
if [ "${1:-}" = "--selftest" ]; then
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT

  mkdir -p "$tmp/dirty" "$tmp/clean"
  printf '%s\n' 'Name: Nova (Orchestrator)' >"$tmp/dirty/seed.md"
  printf '%s\n' '# Clean' >"$tmp/clean/seed.md"

  set +e
  run_check "$tmp/dirty"
  rc_dirty=$?
  set -e

  set +e
  run_check "$tmp/clean"
  rc_clean=$?
  set -e

  if [ "$rc_dirty" -ne 1 ]; then
    echo "SELFTEST FEHLGESCHLAGEN: dirty rc=$rc_dirty (erwartet 1)"
    exit 1
  fi

  if [ "$rc_clean" -ne 0 ]; then
    echo "SELFTEST FEHLGESCHLAGEN: clean rc=$rc_clean (erwartet 0)"
    exit 1
  fi

  echo "SELFTEST OK: beide Faelle bestaetigt (dirty→Exit 1, clean→Exit 0)"
  exit 0
fi

# Standard-Modus: echter Scan der deployten Seed-Dateien
run_check "$SEED_DIR"
