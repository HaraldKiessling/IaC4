#!/usr/bin/env bash
# K4 – Geteilte LLM-Keys funktionieren fuer alle Agents (§7 K4)
# Lokal: SecretRef-Konstruktion im Template (kein Plaintext), Env-Durchreichung in
# docker-compose.yml.j2, kein sk- im gerenderten Config-Pfad.
# Remote: Config-Dump auf dem VPS enthaelt nur "${ENV}"-SecretRef, keinen Plaintext-Key.
# Live-LLM-Call: Abnahme (erfordert laufende Instanz + echte Keys im Container).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=bdd-lib.sh
. "$SCRIPT_DIR/bdd-lib.sh"

echo "Feature: K4 – Beide Agents loesen denselben geteilten Provider-Key auf"

given "models.providers.*.apiKey ist SecretRef \${ENV} (oc1: secrets_ref)"
when "Template auf SecretRef-Konstruktion und Plaintext-Freiheit geprueft wird"
TPL="$REPO_ROOT/ansible/roles/openclaw-gateway/templates/openclaw.json.j2"
CMP="$REPO_ROOT/ansible/roles/openclaw-gateway/templates/docker-compose.yml.j2"
assert_grep "Template: apiKey als \${ENV}-SecretRef (Kurzform)" "$TPL" "\"apiKey\".*'\\$\\{'.*penv"
if grep -qE '"apiKey": "sk-|apiKey.*sk-[A-Za-z0-9]{16,}' "$TPL"; then
  fail "Template enthaelt Plaintext-Key-Muster"
else
  pass "Template rendert keine Plaintext-Keys (nur \${ENV}-SecretRef oder leer)"
fi
assert_grep "Compose: Provider-Env wird in den Container durchgereicht" "$CMP" "{{ penv }}"
assert_grep "Compose: Telegram-Token-Env wird durchgereicht" "$CMP" "{{ acc_env }}"

given "Gerenderte Config auf dem VPS (falls deployed)"
when "Config-Dump auf Plaintext-Keys geprueft wird"
if [ -z "$VPS_HOST" ]; then
  skip "Remote-Config-Check (K4) – VPS_HOST nicht gesetzt"
else
  CFG="$HOST_DATA_ROOT/$INSTANCE/config/openclaw.json"
  vps_run "Config-Dump enthaelt keinen Plaintext-API-Key" \
    "sudo grep -qE 'apiKey.*sk-[A-Za-z0-9]{16,}' $CFG && exit 1 || grep -q '\\${DEV_DEEPSEEK_API_KEY}' $CFG"
  note "Live-LLM-Call (beide Personen-Agents): Abnahme/manuell – erfordert laufende Instanz (K1) + echte Keys."
fi

bdd_summary
