# Diagnose-Workflow 06 – Read-only Issue-#113-Metriken (OC1/OC2/OC3)

> **Zweck:** Read-only-Diagnose der Kontext-/Token-/Cache-Metriken (Issue #113)
> auf den OpenClaw-Instanzen – Vorher/Nachher-Nachmessung nach Deploy des
> Verbesserungs-Branches (Baseline-Evidenz Phase 11, Vorschlag 1).
> **Stand:** 2026-08-10 · Referenz: `tools/diagnose/` + `docs/workflows/benchmark-methodik.md`

## Warum dieser Workflow

Die Baseline-Messung (2026-08-09, main @`4b390e2`) belegte eine Messlücke:
Workflow 05 v3.6 bietet **keinen** Modus für beliebige read-only-SSH- oder
Gateway-RPC-Kommandos. Kontext-Wachstum, Input-Tokens, `cacheRead`, Memory-
Mitschleppen, Heartbeat-Blöcke und Workspace-Dateien pro Turn waren damit
nicht messbar. Workflow 06 schließt diese Lücke auf dem Verbesserungs-Branch.

## Trigger & Inputs

`workflow_dispatch` (manuell, Actions → „06 – Read-only Diagnose“):

| Input | Default | Werte |
|---|---|---|
| `mode` | `all` | `health` \| `sessions` \| `context` \| `tokens` \| `all` |
| `target` | `dev` | `dev` \| `prod` \| `both` |
| `instance` | `all` | `all` oder `oc1`…`ocN` |
| `days` | `7` | Usage-Fenster in Tagen (Modus `tokens`, 1–365) |

## Ablauf (Ein-Job, 1 SSH pro VPS)

1. Checkout + `pyyaml` (SSoT-Parser)
2. Tailscale-Action (`v4.1.3`, OAuth, Tags `tag:ci,tag:ia4` – Muster 05)
3. SSH-Key vorbereiten (`~/.ssh/id_ed25519`, 0600)
4. `tools/diagnose/diagnose.py` mit `--summary`: VPS-IP via Tailscale-API
   (`vps-<target>`/-1-Fallback), je Instanz `docker exec openclaw-<name>
   openclaw <read-only-Befehle>`, JSON auf stdout, Markdown-Tabelle in die
   Job-Summary

Read-only-Kommandos (Auswahl, vollständig in `diagnose.py`):

| Modus | Kommando (im Container) |
|---|---|
| health | `openclaw gateway health --port <p> --json` + `openclaw gateway status --json` |
| sessions | `openclaw sessions --all-agents --json` |
| tokens | `openclaw gateway usage-cost --days <n> --all-agents --json` |
| context | `find … -name '*.jsonl' -path '*session*'` (bounded, `tail -c 300000`, max 20 Dateien) |

## Exit-Code-Vertrag (wie 05)

| Code | Bedeutung |
|---|---|
| 0 | Erfolg – auch „leer/nicht messbar“ (grün, Idempotenz) |
| 1 | Infrastruktur-/Auth-/SSH-Fehler (roter Run) |
| 2 | Validierungs-/Config-Fehler (z. B. keine enabled Instanzen) |

## Sicherheit

- **Nur read-only** – keine approve/reject/remove/delete/clean-Kommandos,
  keine Gateway-Config-Änderung (abgesichert durch Unit-Tests)
- **Keine Secrets in Logs** – Secrets nur als Env-Referenzen
  (`VPS_USER`, `SSH_KEY`, `TS_*`), Skript gibt nie Token/Transkript-Text aus
- Concurrency-Group `diagnose` (getrennt von `device-approve`, seriell)

## Nachmessung (Vorher/Nachher, Issue #113)

1. **Vorher:** Baseline bereits gemessen (Evidenz
   `engineer-pro/evidence-phase11-baseline-20260809.json`, Runs
   31334876470/31334936642/31335030703, main @`4b390e2`)
2. **Nachher (nach Branch-Deploy):** identische Messprozedur erneut ausführen –
   Workflow 06 `--mode all` je Instanz + `scripts/benchmark/measure-session.py`
   (N Turns identischer Prompt, `sessions.get`-Usage je Turn, deterministische
   Session-Keys `agent:<id>:baseline-<runde>-<uuid8>`, Benchmark-Methodik §1.3)
3. **Vergleich:** Werte gegen die Baseline diffen; Instanz-Zustand vor der
   Nachmessung dokumentieren (kein Clean nötig – Sessions der Baseline minimal)

Referenzen: `docs/workflows/benchmark-methodik.md` (§1.3 Session-Isolation,
§2.3 Messgrößen, §4.5 Clean-Modus) · `tools/diagnose/README.md` ·
`scripts/benchmark/benchmark-costs.py` (usage-Felder `input`/`cacheRead`/
`output`/`totalTokens`).
