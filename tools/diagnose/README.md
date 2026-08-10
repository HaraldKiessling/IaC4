# tools/diagnose – Read-only Diagnose (Issue #113, Workflow 06)

Read-only-Metrik-Erfassung auf den OpenClaw-Instanzen (dev/prod) für die
Kontext-Optimierung (Issue #113). Teil des Verbesserungs-Branches
`session-20260809/context-optimierung` (Phase 11).

## Zweck

Die Baseline-Evidenz (Phase 11) hat gezeigt: Workflow 05 v3.6 hat **keinen**
read-only-Modus für beliebige SSH-/Gateway-RPC-Kommandos. Damit waren
Kontext-Wachstum, Input-Tokens, `cacheRead`, Memory-Mitschleppen,
Heartbeat-Blöcke und Workspace-Dateien pro Turn **nicht messbar**. Dieses
Paket + Workflow 06 schließt genau diese Lücke (Baseline-Evidenz,
Vorschlag 1).

## Dateien

| Datei | Zweck |
|---|---|
| `diagnose.py` | CLI-Fassade: `--mode health\|sessions\|context\|tokens\|all`, `--target dev\|prod\|both`, `--instance all\|ocN`, `--days`, `--summary`. SSoT aus `ansible/group_vars/vps-*.yml`, 1 SSH pro VPS via Tailscale, `docker exec openclaw-<name> openclaw <read-only-Befehle>`. NIE schreibend. |
| `context_metrics.py` | Transkript-JSONL-Auswertung: Input/Output-Tokens je Turn (DeepSeek- und OpenAI-Format), Cache-Hit-Anteil (`prompt_cache_hit_tokens`/`cacheReadTokens`), Kontext-Größe je Turn, wiederholte Blöcke (H1/H2), Workspace-/Memory-Einblendungen (AGENTS.md/MEMORY.md/SOUL.md/IDENTITY.md/USER.md), Fehler/Latenz |
| `README.md` | diese Datei |

Workflow: `.github/workflows/06-diagnose.yml` (workflow_dispatch).
Doku: `docs/workflows/diagnose.md`. Nachmess-Skript (Turns + `sessions.get`):
`scripts/benchmark/measure-session.py`.

## Sicherheits-Design

- **Nur read-only-Kommandos** – kein `approve`/`reject`/`remove`/`delete`/
  `clean`, keine Gateway-Config-Änderung; abgesichert durch Unit-Test
  (`tests/diagnose/test_diagnose.py::test_commands_never_mutating`,
  Wort-Whitelist negativ).
- **Keine Secrets in Logs** – Secrets nur als Env-Referenzen im Workflow,
  Token werden nie ausgegeben; Metriken enthalten nie Transkript-Text
  (nur Aggregate/Hashes, abgesichert durch
  `tests/diagnose/test_context_metrics.py::test_no_secrets_in_output`).
- Exit-Code-Vertrag (wie 05): 0 = Erfolg (auch „leer/nicht messbar“ – grün,
  Idempotenz), 1 = Infrastruktur-/Auth-/SSH-Fehler, 2 = Validierungs-/Config-
  Fehler.
- Concurrency-Group `diagnose` – getrennt von `device-approve` (kein
  Blockieren der Freigabe-Kette).

## Lokale Ausführung

```bash
# Ohne Tailscale/SSH (Unit-Tests, reine Funktionen):
python3 -m pytest tests/diagnose/ -q

# Mit SSH-Zugang (Workflow-Äquivalent):
python3 tools/diagnose/diagnose.py --mode all --target dev --instance all \
  --vps-user "$VPS_USER" --ssh-key ~/.ssh/id_ed25519 \
  --ts-tailnet "$TS_TAILNET" \
  --ts-client-id "$TS_CLIENT_ID" --ts-client-secret "$TS_CLIENT_SECRET" \
  --repo-root . --summary
```

## Messbare Metriken (Modus `all`)

| Metrik | Quelle | Modus |
|---|---|---|
| Gateway-Health | `openclaw gateway health/status` | health |
| Session-Anzahl je Instanz | `openclaw sessions --all-agents --json` | sessions |
| Usage-Totals (Tage-Fenster) | `openclaw gateway usage-cost` | tokens |
| Input/Output-Tokens je Turn | Transkript-Usage (`usage.*`) | context/tokens |
| Cache-Hit-Anteil | `prompt_cache_hit_tokens`/`cacheReadTokens` | context/tokens |
| Kontext-Größe je Turn | Zeichen-Schätzung der Text-Blöcke | context |
| Wiederholte Blöcke (H1/H2) | normalisierter Text-Hash, ≥ 100 Zeichen | context |
| Workspace-/Memory-Einblendungen | Marker AGENTS.md/MEMORY.md/… | context |
| Fehler/Latenz | Fehler-Records, duration-Felder | context |

Defensiv: kaputte JSON-Zeilen werden übersprungen, unbekannte Feldnamen
ignoriert – das Tool meldet, was es messen konnte (Nicht-Messbares als
`not_found`/0, nie geraten).
