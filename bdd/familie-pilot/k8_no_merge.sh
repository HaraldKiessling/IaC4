#!/usr/bin/env bash
# K8 – Kein Merge nach main waehrend des Pilots (§7 K8) – LOKAL
# Prueft: aktueller Branch == Feature-Branch, keine Merge-Commits main..HEAD,
# Feature-Branch existiert remote, Deploy nur vom Feature-Branch (Doku-Konvention).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=bdd-lib.sh
. "$SCRIPT_DIR/bdd-lib.sh"

echo "Feature: K8 – Kein Merge nach main waehrend des Pilots"

given "Feature-Branch $PILOT_BRANCH ist Deploy-Branch; main bleibt unangetastet"
when "Git-Zustand geprueft wird"
cd "$REPO_ROOT"

CUR="$(git branch --show-current)"
assert_true "Aktueller Branch ist $PILOT_BRANCH (war: $CUR)" "$([ "$CUR" = "$PILOT_BRANCH" ] && echo true || echo false)"

MERGES="$(git log --oneline main..HEAD --merges 2>/dev/null || true)"
assert_true "Keine Merge-Commits main..HEAD" "$([ -z "$MERGES" ] && echo true || echo false)"

if git ls-remote --heads origin "$PILOT_BRANCH" 2>/dev/null | grep -q "$PILOT_BRANCH"; then
  pass "Feature-Branch existiert auf origin"
else
  fail "Feature-Branch $PILOT_BRANCH ist nicht auf origin (Push ausstehend)"
fi

if git log --oneline main..HEAD >/dev/null 2>&1; then
  pass "Commits liegen nur auf dem Feature-Branch (nicht auf main)"
else
  fail "Kein Fortschritt gegenueber main sichtbar"
fi

note "Deploy nach dev ausschliesslich vom Feature-Branch via 04-service-deploy.yml (instance=$INSTANCE) – Konvention dokumentiert in docs/arc42/07."

bdd_summary
