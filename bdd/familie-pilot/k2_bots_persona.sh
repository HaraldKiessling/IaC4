#!/usr/bin/env bash
# K2 – >=2 Familienmitglieder je eigener Bot, geroutet auf eigene Persona (§7 K2)
# Lokal: Struktur-Check accounts/bindings/defaultAccount im Template + group_vars.
# Remote: Config-Dump auf dem VPS (openclaw.json) – Accounts/Bindings gerendert.
# Live-Bot-DM-Test (Persona-Identitaet): manuell/abnahme – Tokens fehlen bis Q3.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=bdd-lib.sh
. "$SCRIPT_DIR/bdd-lib.sh"

echo "Feature: K2 – Jeder Personen-Bot routet auf die eigene Agent-Persona"

given "Bindings/Accounts laut familie_pilot.feature (person1<->person1, person2<->person2)"
when "Template + group_vars auf Multi-Account-Struktur geprueft werden"
check_config_structure
assert_grep "group_vars: defaultAccount-Kandidat person1 ist erste Person" \
  "$REPO_ROOT/ansible/group_vars/vps-dev.yml" "person1: \"DEV_OC4_TELEGRAM_BOT_PERSON1\""
assert_grep "group_vars: person2-Account konfiguriert" \
  "$REPO_ROOT/ansible/group_vars/vps-dev.yml" "person2: \"DEV_OC4_TELEGRAM_BOT_PERSON2\""

given "Gerenderte Config auf dem VPS (falls deployed und VPS_HOST gesetzt)"
when "accounts + bindings + defaultAccount im Config-Dump geprueft werden"
if [ -z "$VPS_HOST" ]; then
  skip "Remote-Config-Check (K2) – VPS_HOST nicht gesetzt"
else
  CFG="$HOST_DATA_ROOT/$INSTANCE/config/openclaw.json"
  vps_run "Config-Dump enthaelt accounts (person1/person2) + defaultAccount + bindings" \
    "sudo python3 -c \"
import json,sys
c=json.load(open('$CFG'))
t=c['channels']['telegram']
accs=t.get('accounts',{})
assert sorted(accs.keys())==sorted(['person1','person2']), 'accounts: %s' % list(accs)
assert t.get('defaultAccount')=='person1', 'defaultAccount fehlt'
b={x['agentId']:x['match'].get('accountId') for x in c.get('bindings',[])}
assert b.get('person1')=='person1' and b.get('person2')=='person2', 'bindings: %s' % b
print('OK')
\""
  note "Live-DM-Persona-Test (DM an Bot A antwortet als Persona A): Abnahme/manuell – benoetigt echte Tokens (Q3 offen)."
fi

bdd_summary
