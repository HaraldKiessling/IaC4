#!/usr/bin/env bash
# Auth-Check fuer 06-device-approve-telegram.yml (Blocker #1 geloest).
# Ausgelagert aus dem Workflow, damit die Logik unit-testbar ist (Design 05).
#
# Reihenfolge ist sicherheitskritisch:
#   1. Nicht-Leer-Pruefung TG_USER_ID VOR dem Whitelist-Grep (leere User-ID
#      wuerde den Grep '^|,$UID($|,)' auf alles matchen – Auth-Bypass).
#   2. Request-ID-Regex ^[a-zA-Z0-9_-]{8,64}$ (keine Shell-Metazeichen).
#   3. Whitelist-Check gegen TELEGRAM_APPROVE_USERS (kommagetrennt).
#
# Exit: 0 = autorisiert, 1 = abgelehnt (Meldung auf stderr).
# Env:  TG_USER_ID, REQUEST_ID, AUTHORIZED_USERS (Referenz auf GH-Secret
#       TELEGRAM_APPROVE_USERS – niemals Secret-Werte committen).
set -euo pipefail

TG_USER_ID="${TG_USER_ID:-}"
REQUEST_ID="${REQUEST_ID:-}"
AUTHORIZED_USERS="${AUTHORIZED_USERS:-}"

if [ -z "$TG_USER_ID" ]; then
  echo "❌ Keine Telegram-User-ID im Payload" >&2
  exit 1
fi

# Telegram-User-IDs sind numerisch – schliesst Regex-Injection (z.B. '.*')
# im Whitelist-Grep aus (Blocker #1-Haertung).
if ! printf '%s' "$TG_USER_ID" | grep -qE '^[0-9]+$'; then
  echo "❌ Telegram-User-ID muss numerisch sein: '$TG_USER_ID'" >&2
  exit 1
fi

if ! printf '%s' "$REQUEST_ID" | grep -qE '^[a-zA-Z0-9_-]{8,64}$'; then
  echo "❌ Ungültiges Request-ID-Format: '$REQUEST_ID'" >&2
  exit 1
fi

if ! printf '%s' "$AUTHORIZED_USERS" | grep -qE "(^|,)$TG_USER_ID($|,)"; then
  echo "❌ Telegram-User $TG_USER_ID nicht authorisiert" >&2
  exit 1
fi

echo "✅ Auth OK (user=$TG_USER_ID, request=$REQUEST_ID)"
