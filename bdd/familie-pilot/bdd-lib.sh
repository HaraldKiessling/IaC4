#!/usr/bin/env bash
# =============================================================================
# bdd-lib.sh – Gemeinsame Helfer fuer die Pilot-BDD-Checks (GH #126, oc4 dev)
# Feature: bdd/familie-pilot/familie_pilot.feature (K1..K9, 15 Szenarien)
# Messmethoden: Konzept iac4-pilot/konzept-pilot-oc1-dev.md §7 (Dateiname
# historisch, Zielinstanz oc4)
#
# Ausfuehrung:
#   - LOKAL (dieser Checkout): Struktur-/Secret-Checks (K2-K6, K9) ohne Deploy
#   - REMOTE (VPS_HOST gesetzt): Deploy-Checks (K1-K4) via SSH (read-only)
# Die Skripte muessen mit Platzhalter-Personen lauffaehig sein: PERSONS oben.
# Hinweis: Die bestehende IaC4-BDD-Suite (scripts/bdd/*.bdd.ps1, GH-Runner,
# qa/bdd-testkonzept.md) bleibt unveraendert; dieses Verzeichnis bildet die
# Szenarien der familie_pilot.feature als zusaetzliche, lokal ausfuehrbare
# Shell-Checks ab (Entscheidung engineer-pro, Konzept §6).
# =============================================================================
set -euo pipefail

# --- Variablen (Platzhalter; per Umgebung ueberschreibbar) -------------------
PILOT_BRANCH="${PILOT_BRANCH:-feature/pilot-familie-oc4-dev}"
INSTANCE="${INSTANCE:-oc4}"
PORT="${PORT:-18792}"
PERSONS="${PERSONS:-person1 person2}"   # Q3 beantwortet: Platzhalter-Personen (nachlieferbar)
DEFAULT_ACCOUNT="${DEFAULT_ACCOUNT:-person1}"
VPS_HOST="${VPS_HOST:-}"                 # leer = nur lokale Checks; z.B. vps-dev.tailcfea8a.ts.net
VPS_USER="${VPS_USER:-deploy-user}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# Container-Pfade (Konzept §3); Host-Pfade: /srv/openclaw/<instance>/...
WORKSPACE_ROOT="/home/node/.openclaw/workspace"
AGENT_DIR_ROOT="/home/node/.openclaw/agents"
HOST_DATA_ROOT="/srv/openclaw"

# --- Zaehler ---------------------------------------------------------------
BDD_PASS=0; BDD_FAIL=0; BDD_SKIP=0
declare -a BDD_FAILURES=()

note()  { printf '  NOTE   %s\n' "$1"; }
pass()  { BDD_PASS=$((BDD_PASS+1)); printf '  ✅ %s\n' "$1"; }
fail()  { BDD_FAIL=$((BDD_FAIL+1)); BDD_FAILURES+=("$1"); printf '  ❌ %s\n' "$1"; }
skip()  { BDD_SKIP=$((BDD_SKIP+1)); printf '  ⏭️  %s\n' "$1"; }
given() { printf '  Given  %s\n' "$1"; }
when()  { printf '  When   %s\n' "$1"; }

# assert_true <beschreibung> <bedingung>
assert_true() { if [ "$2" = "true" ]; then pass "$1"; else fail "$1"; fi; }

# assert_grep <beschreibung> <datei> <egrep-muster>
assert_grep() {
  local desc="$1" file="$2" pattern="$3"
  if grep -qE -- "$pattern" "$file"; then pass "$desc"; else fail "$desc (Muster '$pattern' nicht in $file)"; fi
}

# --- Remote-Helfer (read-only; leerer VPS_HOST => Skip) ---------------------
# vps_run <beschreibung> <kommando>   -> fuehrt Kommando auf dem VPS aus (SSH)
vps_run() {
  local desc="$1" cmd="$2" out rc
  if [ -z "$VPS_HOST" ]; then
    skip "Remote-Check (VPS nicht gesetzt): $desc"
    return 1
  fi
  given "SSH $VPS_USER@$VPS_HOST"
  out="$(ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o LogLevel=ERROR \
         "$VPS_USER@$VPS_HOST" "$cmd" 2>&1)" || rc=$?
  rc="${rc:-0}"
  if [ "$rc" -eq 0 ]; then pass "$desc"; else fail "$desc (rc=$rc): $out"; fi
  return 0
}

# vps_capture <kommando> -> stdout des Kommandos (oder leer bei Fehler)
vps_capture() {
  if [ -z "$VPS_HOST" ]; then echo ""; return 0; fi
  ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o LogLevel=ERROR \
      "$VPS_USER@$VPS_HOST" "$1" 2>/dev/null || true
}

# --- Struktur-Check: Template/group_vars bilden die Pilot-Konfiguration ab ----
# Wird lokal gegen das Repo ausgefuehrt (kein Deploy noetig).
check_config_structure() {
  local tpl="$REPO_ROOT/ansible/roles/openclaw-gateway/templates/openclaw.json.j2"
  local cmp="$REPO_ROOT/ansible/roles/openclaw-gateway/templates/docker-compose.yml.j2"
  local gv="$REPO_ROOT/ansible/group_vars/vps-dev.yml"
  assert_grep "Template: Personen-Agents (oc.person_agents) vorhanden"        "$tpl" "person_agents"
  assert_grep "Template: workspace je Person (S3)"                             "$tpl" "workspace/\\{\\{ pid \\}\\}"
  assert_grep "Template: agentDir je Person (S3)"                              "$tpl" "agents/\\{\\{ pid \\}\\}/agent"
  assert_grep "Template: subagents.allowAgents je Person (Q5)"                 "$tpl" "allowAgents"
  assert_grep "Template: Multi-Account-Telegram (accounts, S4)"                "$tpl" "accounts"
  assert_grep "Template: defaultAccount explizit (K2)"                         "$tpl" "defaultAccount"
  assert_grep "Template: dmPolicy pairing (Security-Default)"                  "$tpl" "dmPolicy"
  assert_grep "Template: bindings top-level (S4)"                              "$tpl" "bindings"
  assert_grep "Template: match.accountId Routing (S4)"                         "$tpl" "accountId"
  assert_grep "Template: Provider-Key als SecretRef \${ENV} (S2/S6)"           "$tpl" "\"apiKey\".*penv"
  assert_grep "Template: memorySearch provider local"                           "$tpl" "\"provider\": \"local\""
  assert_grep "Compose: Provider-Keys als Container-Env (secrets_ref)"        "$cmp" "openclaw_provider_envs"
  assert_grep "Compose: Telegram-Token je Person als Container-Env"           "$cmp" "telegram_accounts"
  assert_grep "Compose: Host-Port loopback-only (Konzept §3 (a))"             "$cmp" "127\\.0\\.0\\.1:"
  assert_grep "group_vars: oc4-Instanz-Eintrag existiert (Port 18792, K1)"     "$gv" "name: oc4"
  assert_grep "group_vars: oc4 Port 18792"                                     "$gv" "port: 18792"
  assert_grep "group_vars: oc4 person_agents Platzhalter person1/person2 (Q3)" "$gv" "person_agents: \[\"person1\", \"person2\"\]"
  assert_grep "group_vars: oc4 telegram_accounts person1/person2"             "$gv" "DEV_OC4_TELEGRAM_BOT_PERSON1"
  assert_grep "group_vars: oc4 secrets_ref aktiv"                              "$gv" "secrets_ref: true"
  assert_grep "group_vars: maxSpawnDepth 2 (S5)"                               "$gv" "maxSpawnDepth: 2"
  assert_grep "group_vars: Q3-Platzhalter-Kommentar dokumentiert"              "$gv" "PLATZHALTER"
  assert_grep "group_vars: oc1 bleibt Vanilla-Baseline (keine person_agents)"  "$gv" "OC1 – Creator/Vanilla-Baseline"
}

# --- Struktur-Check Workflow 05 (K9, #126: oc4-Abdeckung + Multi-Bot) --------
check_workflow05_structure() {
  local wf="$REPO_ROOT/.github/workflows/05-device-approve.yml"
  local ci="$REPO_ROOT/.github/workflows/ci-device-approve.yml"
  assert_grep "WF05: oc4 im E2E-case (Port 18792, K9a)"        "$wf" "oc4\\) E2E_PORT=18792"
  assert_grep "WF05: Secret DEV_OC4_GATEWAY_TOKEN referenziert (K9a)" "$wf" "DEV_OC4_GATEWAY_TOKEN"
  assert_grep "WF05: account-Input (Multi-Bot, K9b)"            "$wf" "account:"
  assert_grep "WF05: --account an approve.py durchgereicht (K9b)" "$wf" '--account "\$APPROVE_ACCOUNT"'
  assert_grep "WF05: Whitelist je Bot/Account TELEGRAM_APPROVE_USERS_ (K9c)" "$wf" "TELEGRAM_APPROVE_USERS_"
  assert_grep "WF05: Account-Whitelist-Fallback dokumentiert"    "$wf" "Fallback"
  assert_grep "CI: ci-device-approve.yml sichert WF05 ab"        "$ci" "05-device-approve.yml"
}

# --- Pfad-Trennung (S3): Workspace/agentDir je Person verschieden ------------
check_path_separation() {
  local tpl="$REPO_ROOT/ansible/roles/openclaw-gateway/templates/openclaw.json.j2"
  local pids=() pid
  for pid in $PERSONS; do pids+=("$pid"); done
  if [ "${#pids[@]}" -ge 2 ]; then
    local first="${pids[0]}" second="${pids[1]}"
    # Konstruktionsbedingt getrennt: Pfade enthalten die Person-Id -> person1/person2 verschieden
    assert_grep "Template: Workspace-Pfad konstruiert aus Person-Id (Trennung S3)" "$tpl" "workspace/\\{\\{ pid \\}\\}"
    assert_grep "Template: agentDir-Pfad konstruiert aus Person-Id (Trennung S3)" "$tpl" "agents/\\{\\{ pid \\}\\}/agent"
    assert_true "Personen-IDs verschieden: $first != $second" "$([ "$first" != "$second" ] && echo true || echo false)"
  fi
  # Konventionelle Session-Pfade (multi-agent.md): ~/.openclaw/agents/<id>/sessions
  note "Sessions liegen konventionsgemaess unter $AGENT_DIR_ROOT/<person>/sessions (getrennt je Person)."
}

# --- Secret-Scan (K5, lokal) ------------------------------------------------
# Sucht echte Secret-Muster in allen getrackten Dateien; .env.example-Platzhalter
# (***, 123456789:AA...) matchen nicht.
SECRET_PATTERNS=(
  'sk-[A-Za-z0-9]{16,}'                       # OpenAI/DeepSeek-artige Keys
  '[0-9]{6,12}:[A-Za-z0-9_-]{30,}'            # Telegram-Bot-Token
  'github_pat_[A-Za-z0-9_]{20,}'              # GH-Fine-Grained-PAT
  'ghp_[A-Za-z0-9]{30,}'                      # GH-Classic-PAT
  'xox[baprs]-[A-Za-z0-9-]{20,}'              # Slack-Tokens
  'AKIA[0-9A-Z]{16}'                          # AWS-Zugaenge
  '-----BEGIN [A-Z ]*PRIVATE KEY-----'        # Private Keys
)

check_secret_scan() {
  local hits="" pat
  for pat in "${SECRET_PATTERNS[@]}"; do
    hits+="$(cd "$REPO_ROOT" && git grep -nIE "$pat" -- . ':!bdd/familie-pilot/README.md' 2>/dev/null || true)"
  done
  if [ -z "$hits" ]; then
    pass "Secret-Scan: keine echten Secret-Werte im Repo (git grep, $SECRET_PATTERNS)"
  else
    fail "Secret-Scan: Treffer gefunden: $(echo "$hits" | tr '\n' ' ' | cut -c1-200)"
  fi
  if [ -f "$REPO_ROOT/.env" ]; then
    fail "Secret-Scan: Datei .env ist im Checkout vorhanden (sollte nie committet werden)"
  else
    pass "Secret-Scan: keine .env-Datei im Checkout"
  fi
  if (cd "$REPO_ROOT" && git ls-files --error-unmatch .env >/dev/null 2>&1); then
    fail "Secret-Scan: .env ist getrackt!"
  else
    pass "Secret-Scan: .env ist NICHT getrackt (git ls-files)"
  fi
  if (cd "$REPO_ROOT" && git ls-files | grep -qE '(^|/)\.env\.example$'); then
    pass "Secret-Scan: .env.example ist committet (Platzhalter)"
  else
    fail "Secret-Scan: .env.example fehlt im Repo"
  fi
  assert_grep "Secret-Scan: .gitignore schliesst .env.* aus" "$REPO_ROOT/.gitignore" "^(\\.env|\\.env\\.\\*)$"
}

# --- Zusammenfassung --------------------------------------------------------
bdd_summary() {
  printf '\n=== BDD-Zusammenfassung: %s pass, %s fail, %s skip ===\n' "$BDD_PASS" "$BDD_FAIL" "$BDD_SKIP"
  if [ "${#BDD_FAILURES[@]}" -gt 0 ]; then
    printf 'Fehlgeschlagen:\n'
    for f in "${BDD_FAILURES[@]}"; do printf '  - %s\n' "$f"; done
    return 1
  fi
  return 0
}
