# PR-Body: 05 v2.2 – Unified Freigabe: Telegram-Pairing + Device-Approve (ID-basiert)

> **Hinweis:** PR #108 wurde nach Token-Analyse (fine-grained PAT, `Contents: write`)
> per GitHub REST API erstellt (Engineer, 2026-08-06). Branch
> `session-20260806/device-approve-telegram` (Repo `HaraldKiessling/IaC4`),
> Ziel-Branch: `main`. Kein Merge durch den Engineer – Entscheidung Owner/Orchestrator.

---

## Titel

### 05 v2.2 – Unified Freigabe: Telegram-Pairing + Device-Approve (ID-basiert)

## Zusammenfassung

Korrektur-/Abschluss-Implementierung des Workflows 05 auf **Design-Stand v2.2**
(`iac4-design/05-workflow-erweiterung-v2.2.md`, aktuelle Wahrheit). Die frühere
v2.1-Implementierung basierte auf der **widerlegten Annahme** (Telegram-Pairing
in `devices list --json`, einheitliches `openclaw devices approve`). Empirisch
verifiziert (OpenClaw 2026.7.1 + Owner-Pairing-Beleg `QVDCXJEM`):

- Telegram-Pairing = separater CLI-Pfad `openclaw pairing`
  (Discovery `pairing list telegram --json`, Approve `pairing approve telegram <CODE>`)
- Device-Pairing = `openclaw devices` (Discovery `devices list --json`,
  Approve `devices approve <ID>`)
- Zwei ID-Formate: Kurzcode `^[A-Z0-9]{6,12}$` (telegram) und
  Device-ID `^[0-9a-fA-F-]{36,128}$` (device); Typ-Ableitung aus Format,
  expliziter `type`-Input überschreibt

## Änderungen

### M1 – `tools/device-approve/` (v2.2, standalone & lokal testbar)

- **`discovery.py`** (NEU, ersetzt `discovery_core.py`): getrennte
  Discovery-Quellen je Instanz (`pairing list telegram --json` für telegram,
  `devices list --json` für device), Typ-Filter (telegram/device/both),
  `$GITHUB_OUTPUT` (`request_id`, `found_target`, `found_instance`,
  `found_vps_ip`, `found_type`, `derived_type`), lastSeen-`-1`-Fallback,
  UNREACHABLE-Liste, `--validate-id` (Workflow-Step, DRY)
- **`approve_step.py`**: typ-spezifischer SSH-Approve
  (`pairing approve telegram <CODE>` / `devices approve <ID>`),
  Rollen-Trennung (Major #2), Validierung defense-in-depth
- **`approve.py`**: CLI-Fassade – `--discover-only`, `--summary` (JSON stdout +
  Markdown in `$GITHUB_STEP_SUMMARY` per File-Open, Major #3/Δ7), lokaler Modus
  (`APPROVE_LOCAL=1`, openclaw CLI direkt auf dem Gateway)
- **`summary.py`**: Markdown-Generator, typ-spezifische Header
- Echtes Package (`__init__.py` v2.2.0) + `if __name__ == "__main__"`-Einstiege

### M2 – Workflow + Doku

- **`.github/workflows/05-device-approve.yml`** → v2.2: duale Trigger
  (`workflow_dispatch` Inputs id/type/target/instance + `repository_dispatch`
  client_payload), Zwei-Jobs `discover` → `approve` (Environment-Expression,
  `approve_step.py`, request_id aus `needs.discover.outputs`), Job-Summary
- **`.github/workflows/06-device-approve-telegram.yml`** gelöscht
  (v2 ersetzt 05 v1 + 06 v1)
- **`.github/workflows/ci-device-approve.yml`**: actionlint + shellcheck +
  pytest + bash -n für 05 v2, `tools/device-approve/`, `tools/telegram-approve-bot/`
- **`docs/workflows/deploy-stages.md`**: Stale-Referenz „05-openclaw-install"
  bereinigt (OpenClaw-Deployment via 04-service-deploy playbook=openclaw)
- **`docs/plans/issue-device-approve-telegram.md`**: auf v2.2-Stand aktualisiert
  (Usecases A/B/C, Test-IDs, AK, offene Punkte F1a/F1b/F10/F5/F7)

## Tests

- **pytest:** 224 Tests grün (`tests/device-approve/`) – discovery
  (pairing/device-Pfade, Typ-Filter, GITHUB_OUTPUT), approve_step (Mock-SSH,
  typ-spezifische Kommandos), approve.py CLI (--discover-only, --summary,
  lokaler Modus), Bot-/SSoT-Parser, summary
- **shellcheck + bash -n:** `auth_check.sh` + Shell-Tests sauber
- **actionlint:** 05 v2 + CI (lokal geprüft, siehe Belege)
- **Lokale Testläufe (Testbarkeits-Beleg, echte openclaw CLI):**
  `QVDCXJEM` → not_found (Typ telegram), `9df47d69…`/`b0999c46…`/`2e68bca9…`
  → not_found (Typ device) – lokal keine pending Einträge (erwartet)

## Sicherheit

- Regex-Sperre je Typ (disjunkte Formate), `subprocess.run` ohne Shell,
  keine Secrets in Logs
- Environment-Gate: `prod-approve` (Required Reviewer) vs. `dev-approve`
  (ohne Protection) – beide Environments müssen angelegt sein (F7)
- Auth für repository_dispatch: `auth_check.sh` (Whitelist)

## Offene Punkte (nicht in diesem PR)

- F1a (pairing-Eintragsschema), F1b/F5 (Idempotenz), F7 (Environments anlegen),
  F10 (belegt: Sandbox `requests: []`), M4 (Bot-Deployment), M5 (VPS-Combi)

## Checkliste

- [x] Conventional Commits, Evidenz in Commit-Messages
- [x] Keine Secrets committet
- [x] Kein Merge nach main, kein Deploy (Entscheidung Owner/Orchestrator)
