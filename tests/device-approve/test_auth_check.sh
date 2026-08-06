#!/usr/bin/env bash
# Shell-Tests fuer tools/telegram-approve-bot/auth_check.sh (Design 05, Blocker #1).
# Bewusst ohne bats-Abhaengigkeit: reine Exit-Code-Assertions.
# Fälle: leere User-ID -> exit 1, nicht-whitelisted -> exit 1, ok -> 0, plus
# Regex-/Leerwert-Abwehr (leere ID, leere Whitelist, Injection-Format).
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
run_check 1 "leere TG_USER_ID" -- TG_USER_ID="" REQUEST_ID="req_abc123" AUTHORIZED_USERS="$AUTH"
run_check 1 "fehlende TG_USER_ID" -- REQUEST_ID="req_abc123" AUTHORIZED_USERS="$AUTH"

# 2) Whitelist: nicht autorisiert -> exit 1
run_check 1 "nicht-whitelisted User" -- TG_USER_ID="999999999" REQUEST_ID="req_abc123" AUTHORIZED_USERS="$AUTH"
run_check 1 "leere Whitelist" -- TG_USER_ID="7145674995" REQUEST_ID="req_abc123" AUTHORIZED_USERS=""
run_check 1 "Regex-Injection: '.*' als User-ID" -- TG_USER_ID='.*' REQUEST_ID="req_abc123" AUTHORIZED_USERS="$AUTH"
run_check 1 "nicht-numerische User-ID" -- TG_USER_ID="user123" REQUEST_ID="req_abc123" AUTHORIZED_USERS="$AUTH"

# 3) Request-ID-Regex: Injection-/Format-Angriffe -> exit 1
run_check 1 "Injection: Semikolon-Kette" -- TG_USER_ID="7145674995" REQUEST_ID="req_abc123; rm -rf" AUTHORIZED_USERS="$AUTH"
run_check 1 "Injection: Kommandosubstitution" -- TG_USER_ID="7145674995" REQUEST_ID="\$(rm -rf /)" AUTHORIZED_USERS="$AUTH"
# Bewusst literaler Backtick-String (Injection-Test), keine Expansion gewuenscht.
# shellcheck disable=SC2016
run_check 1 "Injection: Backtick" -- TG_USER_ID="7145674995" REQUEST_ID='`id`' AUTHORIZED_USERS="$AUTH"
run_check 1 "leere Request-ID" -- TG_USER_ID="7145674995" REQUEST_ID="" AUTHORIZED_USERS="$AUTH"
run_check 1 "zu kurze Request-ID" -- TG_USER_ID="7145674995" REQUEST_ID="short" AUTHORIZED_USERS="$AUTH"
run_check 1 "zu lange Request-ID" -- TG_USER_ID="7145674995" REQUEST_ID="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" AUTHORIZED_USERS="$AUTH"

# 4) Autorisiert + valide ID -> exit 0
run_check 0 "autorisiert + valide ID" -- TG_USER_ID="7145674995" REQUEST_ID="req_abc123" AUTHORIZED_USERS="$AUTH"
run_check 0 "Whitelist-Position mittig" -- TG_USER_ID="111111" REQUEST_ID="req_abc123" AUTHORIZED_USERS="$AUTH"

echo "----"
if [ "$FAIL" -ne 0 ]; then
  echo "❌ $TOTAL Checks, mind. 1 Fehler"
  exit 1
fi
echo "✅ Alle $TOTAL Checks bestanden"
