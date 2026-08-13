#!/usr/bin/env bash
# K7 – Review durchgefuehrt (Autor != Reviewer), Befund dokumentiert (§7 K7) – LOKAL
# Prueft die Repo-Review-Konvention und – falls bereits ein PR existiert – dessen
# Review-Status (gh pr view). Der eigentliche Review ist Prozess (reviewer-Rolle).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=bdd-lib.sh
. "$SCRIPT_DIR/bdd-lib.sh"

echo "Feature: K7 – Unabhaengiger Review mit dokumentiertem Befund"

given "PR fuer $PILOT_BRANCH (Basis main); Reviewer != Autor"
when "Review-Konvention im Repo und PR-Status geprueft werden"

if (cd "$REPO_ROOT" && grep -rqiE "review.*autor|autor.*review|unabhaengig" AGENTS.md .roo/rules/ qa/ 2>/dev/null); then
  pass "Review-Konvention (Autor != Reviewer) ist im Repo dokumentiert"
else
  fail "Review-Konvention nicht in AGENTS.md/.roo/rules/qa gefunden"
fi

if command -v gh >/dev/null 2>&1 && [ -n "${GH_TOKEN:-}" ]; then
  PR="$(cd "$REPO_ROOT" && gh pr view "$PILOT_BRANCH" --json number,baseRefName,reviewDecision 2>/dev/null || true)"
  if [ -n "$PR" ]; then
    if echo "$PR" | grep -q '"baseRefName":"main"'; then
      pass "PR-Basis ist main (K8-konform)"
    else
      fail "PR-Basis ist nicht main: $PR"
    fi
    note "PR-Review-Status: $(echo "$PR" | grep -o '"reviewDecision":"[^"]*"' || echo 'noch kein Review')"
    note "Befund-Dokumentation: im PR-Kommentar/iac4-design-Dokument (Prozess, reviewer-Rolle)."
  else
    skip "Kein PR fuer $PILOT_BRANCH vorhanden (PR-Erstellung ist Orchestrator/Reviewer-Prozess, Konzept §5/§6)"
  fi
else
  skip "gh/Token nicht verfuegbar – PR-Status-Check uebersprungen"
fi

bdd_summary
