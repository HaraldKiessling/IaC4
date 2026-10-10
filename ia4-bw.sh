#!/bin/sh
# ia4-bw – Bitwarden-CLI fuer den Agenten-Tresor (ADR-027, Issue #192).
# Von Ansible gerendert, read-only in den Container gemountet (nicht vom Agenten aenderbar).
# Liegt bewusst NICHT auf dem PATH und NICHT in der Exec-Allowlist: jeder Aufruf
# loest eine OpenClaw-Exec-Freigabe (Telegram) aus. Meldet sich selbst an, entsperrt,
# synchronisiert und reicht alle Argumente an das offizielle `bw` weiter.
# create/edit: reines JSON auf stdin wird vorher kodiert (wie `bw encode`).
set -eu

BW="/opt/ia4-bitwarden/cli/bin/bw"
SERVER="https://vault.bitwarden.eu"

if [ -z "${BW_CLIENTID:-}" ] || [ -z "${BW_CLIENTSECRET:-}" ] || [ -z "${BW_PASSWORD:-}" ]; then
  echo "ia4-bw: Agenten-Tresor ist auf dieser Instanz nicht eingerichtet." >&2
  exit 2
fi
[ -x "$BW" ] || { echo "ia4-bw: Bitwarden CLI fehlt ($BW)." >&2; exit 2; }

if "$BW" status 2>/dev/null | grep -q '"status":"unauthenticated"'; then
  "$BW" config server "$SERVER" >/dev/null
  "$BW" login --apikey >/dev/null
fi
BW_SESSION=$("$BW" unlock --passwordenv BW_PASSWORD --raw)
export BW_SESSION
"$BW" sync >/dev/null

case "${1:-}" in
  create|edit|delete|restore|move) _write=1 ;;
  *) _write=0 ;;
esac

set +e
if { [ "${1:-}" = "create" ] && [ $# -eq 2 ]; } || { [ "${1:-}" = "edit" ] && [ $# -eq 3 ]; }; then
  if [ ! -t 0 ]; then
    _data=$(cat)
    case "$_data" in
      \{*|\[*) printf '%s' "$_data" | "$BW" encode | "$BW" "$@" ;;
      *) printf '%s' "$_data" | "$BW" "$@" ;;
    esac
  else
    "$BW" "$@"
  fi
else
  "$BW" "$@"
fi
_rc=$?
set -e

# Sync-Fehler nach erfolgreichem Schreiben darf den Erfolg nicht verdecken (sonst Doppel-Eintrag
# durch erneuten Versuch des Agenten).
if [ "$_write" -eq 1 ]; then "$BW" sync >/dev/null 2>&1 || true; fi
exit "$_rc"