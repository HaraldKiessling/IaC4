#!/usr/bin/env bash
# K9 – Workflow 05 erweitert: Device-Pairing + mehrere Telegram-Bots auf oc4 (#126)
# Prueft (voll lokal, Konzept §7.1 / K9):
#   (a) oc4-Abdeckung: E2E-case Port 18792 + Secret-Referenz DEV_OC4_GATEWAY_TOKEN
#   (b) Multi-Bot-Genehmigung: account-Input + --account-Durchreichung an die
#       openclaw-CLI (pairing list/approve) – belegt: docs/channels/pairing.md
#       „Multi-account channels take `--account <id>`“ (OpenClaw-Doku, lokal /app/docs)
#   (c) Genehmigungs-Whitelist je Bot/Account: TELEGRAM_APPROVE_USERS_<ACCOUNT>
#       mit Fallback auf TELEGRAM_APPROVE_USERS (dokumentiert im Workflow)
#   - CI-Workflow ci-device-approve.yml (actionlint/shellcheck/pytest) sichert ab
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=bdd-lib.sh
. "$SCRIPT_DIR/bdd-lib.sh"

echo "Feature: K9 – Workflow 05 genehmigt Device-Pairing und mehrere Telegram-Bots auf oc4"

given "Workflow 05-device-approve.yml kennt oc4 (Port 18792) + DEV_OC4_GATEWAY_TOKEN"
when "E2E-case, Secret-Referenz und Multi-Account-Mechanik geprueft werden"
check_workflow05_structure

given "Account-Parameter ist belegt (OpenClaw-Doku: --account <id> fuer Multi-Account-Kanaele)"
if [ -f /app/docs/channels/pairing.md ] && grep -q -- "--account" /app/docs/channels/pairing.md; then
  pass "Beleg: docs/channels/pairing.md – Multi-account channels take --account <id>"
else
  note "Doku /app/docs/channels/pairing.md nicht im Checkout – Beleg entfaellt (nicht-kritisch, K9-Struktur oben)"
fi

# (b) tatsaechliche Durchreichung bis zur CLI-Ebene: approve.py/discovery.py
AP="tools/device-approve/approve.py"
DC="tools/device-approve/discovery.py"
assert_grep "approve.py: --account Argument (Multi-Account)" \
  "$REPO_ROOT/$AP" 'add_argument\("--account"'
assert_grep "approve.py: APPROVE_ACCOUNT-Env-Override" \
  "$REPO_ROOT/$AP" 'APPROVE_ACCOUNT'
assert_grep "approve.py: --account an pairing approve angehaengt (lokal)" \
  "$REPO_ROOT/$AP" '"--account", account'
assert_grep "discovery.py: --account an pairing list/approve angehaengt (remote)" \
  "$REPO_ROOT/$DC" '_account_arg'

# Unit-Tests fuer die neue Mechanik vorhanden (ci-device-approve.yml pytest-Pfad)
assert_grep "Unit-Tests: test_account.py deckt --account ab" \
  "$REPO_ROOT/tests/device-approve/test_account.py" "--account"

bdd_summary
