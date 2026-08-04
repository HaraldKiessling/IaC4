# Benchmark-Runbook (Design 05/07, Runner-basiert)

> **Zweck:** Reproduzierbare Durchführung von Benchmark-Runden (3 OCs, gleiche Aufgabe je Runde)
> **Stand:** 2026-08-04 · Basierend auf 9er-Runde (Design 07)

## Voraussetzungen

- vps-dev erreichbar (Tailscale), alle 3 Instanzen health ok
- Gateway-Token: `/tmp/tok.py` (TOKEN) — nie committen
- GH-Read-Token auf Instanzen deployed (`.gh-read-token`, 0600)
- Repo auf aktuellem main; Skripte in `scripts/benchmark/`

## Ablauf je Runde

```bash
# 1. Runde starten (3 Arme parallel, gleiche Aufgabe)
python3 scripts/benchmark/run-round.py <RUNDE> <ISSUE> "<TITEL>"
# z.B.: python3 scripts/benchmark/run-round.py R1 23 "Tool-Permission-Matrix"

# 2. Auf Abschluss warten (Läufe bis 15 min; OC1/Single kann 600s+ dauern)
#    Bei CLI-Timeout: Session lebt weiter → mit --timeout 900 fortführen:
openclaw agent --agent <id> --session-key <key> --timeout 900 --message "Schreibe Artefakt"

# 3. Synthese sicherstellen (Runner-Follow-up, S-2c)
python3 scripts/benchmark/followup-synthesis.py <runden-ordner>/task-log.json

# 4. Kontaminations-Audit (Quellen-Regel)
python3 scripts/benchmark/audit-sources.py <runden-ordner>/task-log.json <issue>

# 5. Kosten
python3 scripts/benchmark/benchmark-costs.py <runden-ordner>/task-log.json --eur
```

## Pflicht-Schritte (Lessons)

1. **Follow-up IMMER ausführen** — ohne S-2c bleiben 3–4 von 9 Artefakten unvollständig (BP-7/Runner-Turn-Ende)
2. **Audit IMMER nach jeder Runde** — Kontaminationskontrolle verifizieren (Snapshot `9ea618c`, keine PRs/Branches)
3. **Timeout:** Runner-Default 600s; für OC1 (Single-Agent) `--timeout 900` einplanen — Session lebt nach Timeout weiter, kein Datenverlust
4. **Artefakt-Namen exakt:** `#<issue>-<inst>.md` (kein `-draft`, `-plan`) — Detektor prüft das
5. **Kosten sofort nach Lauf** (Clean löscht Sessions!)

## Kontaminationskontrolle (Quellen-Regel im Prompt)

- Nur Repo-Stand `main@9ea618c` (vor Lösungs-PRs) via `raw.githubusercontent.com/.../9ea618c/...`
- VERBOTEN: PRs, Branches, Issue-Kommentare, andere Issues, `iac4-design/05+06`, Memory als Lösungsquelle
- Regel ist im Template `scripts/benchmark/templates/benchmark-task.md` verankert

## Auswertung

- Ergebnisbericht als `iac4-design/07-benchmark-ergebnis-<n>.md` (Vorlage: 07-benchmark-ergebnis-9er.md)
- Metriken: Laufzeit, Artefakt-Größe, Qualität (6 Anforderungen), Kosten (€), Audit, Delegation
