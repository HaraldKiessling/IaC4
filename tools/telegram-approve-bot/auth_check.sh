#!/usr/bin/env bash
# Auth-Check fuer den Telegram-Pfad (repository_dispatch) – v2.2, B1-Fix.
# Ausgelagert aus dem Workflow, damit die Logik unit-testbar ist (Design 05).
#
# B1-Fix (Review 2026-08-06): auth_check.sh prueft NUR die Telegram-User-ID.
# Die Request-ID-Validierung ist vollstaendig an die Python-Validierung
# delegiert (tools/device-approve/discovery.py --validate-id = Single Source
# of Truth). Damit blockiert der Shell-Check keine gueltigen 6-7-stelligen
# Telegram-Pairing-Kurzcodes (z.B. A1B2C3, QVDCXJEM) mehr; die Format-Prüfung
# (Kurzcode ^[A-Z0-9]{6,12}$ vs. Device-ID ^[0-9a-fA-F-]{36,128}$) und die
# Injection-Abwehr (Regex lehnt Shell-Metazeichen ab) erfolgen dort einheitlich
# fuer ALLE Pfade (workflow_dispatch + repository_dispatch).
#
# Reihenfolge ist sicherheitskritisch:
#   1. Nicht-Leer-Pruefung TG_USER_ID VOR dem Whitelist-Grep (leere User-ID
#      wuerde den Grep '^|,$UID($|,)' auf alles matchen – Auth-Bypass).
#   2. Numerisch-Pruefung (schliesst Regex-Injection wie '.*' aus).
#   3. Whitelist-Check gegen TELEGRAM_APPROVE_USERS (kommagetrennt).
#
# Exit: 0 = autorisiert, 1 = abgelehnt (Meldung auf stderr).
# Env:  TG_USER_ID, AUTHORIZED_USERS (Referenz auf GH-Secret
#       TELEGRAM_APPROVE_USERS – niemals Secret-Werte committen).
set -euo pipefail

TG_USER_ID="${TG_USER_ID:-}"
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

if ! printf '%s' "$AUTHORIZED_USERS" | grep -qE "(^|,)$TG_USER_ID($|,)"; then
  echo "❌ Telegram-User $TG_USER_ID nicht authorisiert" >&2
  exit 1
fi

echo "✅ Auth OK (user=$TG_USER_ID)"
