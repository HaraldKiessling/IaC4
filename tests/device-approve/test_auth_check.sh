#!/usr/bin/env bash
# Shell-Tests fuer tools/telegram-approve-bot/auth_check.sh (Design 05, Blocker #1).
# Bewusst ohne bats-Abhaengigkeit: reine Exit-Code-Assertions.
# Fälle: leere User-ID -> exit 1, nicht-whitelisted -> exit 1, ok -> 0, plus
# Regex-/Leerwert-Abwehr (leere ID, leere Whitelist, Injection-Format).
#
# B1-Fix (Review 2026-08-06): auth_check.sh prueft NUR die Telegram-User-ID.
# Die Request-ID wird NICHT mehr im Shell-Check validiert (Delegation an
# discovery.py --validate-id, Single Source of Truth) – daher akzeptiert der
# Check hier auch 6-7-stellige Pairing-Kurzcodes (A1B2C3, ABC12DE, QVDCXJEM)
# und UUIDs (b0999c46-…, 2e68bca9-…) als Request-ID (Regressionstests unten).
set -euo pipefail

SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../tools/telegram-approve-bot" && pwd)/auth_check.sh"
AUTH="111111,7145674995,222222"

FAIL=0
TOTAL=0

run_check() {
  # run_check <expected_exit> <desc> -- VAR=... [VAR=...]
  local expected="$1" desc="$2"
  shift 2
  [ "$1" = "--" ] && shift
  local rc=0 out
  TOTAL=$((TOTAL + 1))
  if out=$(env "$@" bash "$SCRIPT" 2>&1); then
    rc=0
  else
    rc=$?
  fi
  if [ "$rc" -ne "$expected" ]; then
    echo "❌ [$desc] erwartet exit=$expected, bekam exit=$rc"
    printf '   %s\n' "$out"
    FAIL=1
  else
    echo "✅ [$desc] exit=$rc"
  fi
}

# 1) Leere / fehlende User-ID -> exit 1 (Blocker #1: Check VOR Whitelist-Grep)
run_check 1 "leere TG_USER_ID" -- TG_USER_ID="" REQUEST_ID="QVDCXJEM" AUTHORIZED_USERS="$AUTH"
run_check 1 "fehlende TG_USER_ID" -- REQUEST_ID="QVDCXJEM" AUTHORIZED_USERS="$AUTH"

# 2) Whitelist: nicht autorisiert -> exit 1
run_check 1 "nicht-whitelisted User" -- TG_USER_ID="999999999" REQUEST_ID="QVDCXJEM" AUTHORIZED_USERS="$AUTH"
run_check 1 "leere Whitelist" -- TG_USER_ID="7145674995" REQUEST_ID="QVDCXJEM" AUTHORIZED_USERS=""
run_check 1 "Regex-Injection: '.*' als User-ID" -- TG_USER_ID='.*' REQUEST_ID="QVDCXJEM" AUTHORIZED_USERS="$AUTH"
run_check 1 "nicht-numerische User-ID" -- TG_USER_ID="user123" REQUEST_ID="QVDCXJEM" AUTHORIZED_USERS="$AUTH"

# 3) B1-Regression (v2.2): Request-ID wird NICHT mehr im Shell-Check geprüft –
#    die Format-Validierung liegt in discovery.py --validate-id (Python).
#    Gueltige Telegram-Kurzcodes (6-12 Zeichen) und Device-UUIDs müssen den
#    Auth-Check ungehindert passieren (Workflow validiert danach per Python).
run_check 0 "Kurzcode QVDCXJEM (8 Zeichen) durchgereicht" -- TG_USER_ID="7145674995" REQUEST_ID="QVDCXJEM" AUTHORIZED_USERS="$AUTH"
run_check 0 "Kurzcode A1B2C3 (6 Zeichen) durchgereicht" -- TG_USER_ID="7145674995" REQUEST_ID="A1B2C3" AUTHORIZED_USERS="$AUTH"
run_check 0 "Kurzcode ABC12DE (7 Zeichen) durchgereicht" -- TG_USER_ID="7145674995" REQUEST_ID="ABC12DE" AUTHORIZED_USERS="$AUTH"
run_check 0 "UUID b0999c46-… durchgereicht" -- TG_USER_ID="7145674995" REQUEST_ID="b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5" AUTHORIZED_USERS="$AUTH"
run_check 0 "UUID 2e68bca9-… durchgereicht" -- TG_USER_ID="7145674995" REQUEST_ID="2e68bca9-4965-4e29-9a9d-d1a12644d644" AUTHORIZED_USERS="$AUTH"

# 4) Autorisiert -> exit 0
run_check 0 "autorisiert" -- TG_USER_ID="7145674995" REQUEST_ID="QVDCXJEM" AUTHORIZED_USERS="$AUTH"
run_check 0 "Whitelist-Position mittig" -- TG_USER_ID="111111" REQUEST_ID="QVDCXJEM" AUTHORIZED_USERS="$AUTH"

echo "----"
if [ "$FAIL" -ne 0 ]; then
  echo "❌ $TOTAL Checks, mind. 1 Fehler"
  exit 1
fi
echo "✅ Alle $TOTAL Checks bestanden"
