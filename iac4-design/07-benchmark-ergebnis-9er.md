# Design 07: Benchmark-Ergebnis — 9er-Runde (3 Aufgaben × 3 OCs, Kontaminationskontrolle)

> **Status:** Ergebnisbericht · **Datum:** 2026-08-03/04 · **Durchführung:** Nova (Orchestrator)
> **Setup:** main @ `9fdfc64`-Basis · Kontaminationskontrolle (Snapshot `9ea618c` + Quellen-Regel + Audit)
> **Arme:** OC1 = Vanilla flash (Single) · OC2 = Team all-flash · OC3 = Team Mix (Arch/Rev pro) · Thinking: Orch/Eng medium, Arch/Rev high

## 1. Testaufbau

- **3 Runden, gleiche Aufgabe je Runde für alle 3 OCs** (Design 05): R1 = #23 (Tool-Permission-Matrix, L), R2 = #42 (Done-Nachweis, M), R3 = #65 (Code-Server DEV, H)
- Runner: `scripts/benchmark/run-round.py` → `followup-synthesis.py` (S-2c) → `audit-sources.py` (Kontrolle) → `benchmark-costs.py`
- Kontaminationskontrolle: nur Repo-Stand `9ea618c` (vor Lösungs-PRs), keine PRs/Branches/Issue-Kommentare/Design-05+06; Memory nur als Kontext

## 2. Ergebnisse (alle 9 Artefakte vollständig)

| Runde | Metrik | OC1 (Vanilla) | OC2 (Team flash) | OC3 (Team Mix) |
|---|---|---|---|---|
| **R1** #23 | Laufzeit (s) | 602* | 77 | 60 |
| | Artefakt | ✅ 31,0 KB | ✅ 26,6 KB | ✅ 24,8 KB |
| | Qualität (6 Anf.) | 6/6 | 6/6 | 6/6 |
| | Kosten (€) | 0,053 | 0,093 | 0,550 |
| **R2** #42 | Laufzeit (s) | 345 | 98 | 144 |
| | Artefakt | ✅ 47,1 KB | ✅ 58,0 KB | ✅ 42,9 KB |
| | Qualität | 6/6 | 6/6 | 6/6 |
| | Kosten (€) | 0,092 | 0,141 | 0,711 |
| **R3** #65 | Laufzeit (s) | 379 | 91 | 59 |
| | Artefakt | ✅ 33,6 KB | ✅ 36,5 KB | ✅ 34,2 KB |
| | Qualität | 6/6 | 6/6 | 6/6 |
| | Kosten (€) | 0,100 | 0,234 | 1,045 |
| **Summe** | **Kosten (€)** | **0,245** | **0,468** | **2,306** |

*OC1-R1: CLI-Timeout 600s erreicht → Fortsetzung mit `--timeout 900` auf derselben Session (lebt weiter, kein Verlust).

## 3. Kontaminations-Audit

- **Alle 9 Läufe: 0 Verletzungen** (keine PR-/Branch-/Issue-Kommentar-/Design-05+06-Zugriffe)
- OC1-R1 nutzte explizit Snapshot `9ea618c` („15 verifizierte IST-Fakten")
- Hinweis: Audit erkennt URL-/gh-basierte Zugriffe; git-clone-Varianten für Folge-Benchmarks erweitern

## 4. Review-Befunde (echtes Review aller 9)

1. **Setup reproduzierbar:** 9/9 Artefakte vollständig (18/18 Qualität je Arm), kein Ausfall.
2. **OC2 (Team all-flash) = bester Gesamt-Arm:** 18/18 bei 0,47 € — bestes Kosten-Nutzen.
3. **OC3 (pro für Arch/Rev) rechtfertigt den Preis NICHT:** 2,31 € (5–9×) bei gleicher Qualität.
4. **OC1 (Single flash) solide + günstigste:** 18/18 für 0,25 €, aber langsamer (345–602s vs. 59–144s).
5. **Qualität ≠ Delegationsgrad:** OC1 (2 Subs) und OC3 (13 Subs) beide 6/6 — Delegation kostet, steigert hier nicht messbar die Qualität.
6. **Runner-Follow-up (S-2c) unverzichtbar:** 3–4 von 9 Läufen brauchten Follow-up; ohne wären Artefakte unvollständig.
7. **CLI-Timeout-Lesson:** `openclaw agent`-Default 600s zu kurz für Single-Agent → `--timeout 900` im Runner.

## 5. Empfehlungen

1. **OC2-Konfiguration (Team all-flash) als DEV-Default** — beste Qualität/Kosten.
2. **OC3-pro optional deaktivierbar** (kein nachweisbarer Mehrwert in dieser Messung).
3. **Runner + Audit in Methodik festschreiben** (Skripte sind Repo-Bestand).
4. **n≥2 für Signifikanz** (n=1 je Runde bleibt Limit); Folge-Runden mit frischen Issues.

## 6. Bezug

- Design 05 (`05-multitask-benchmark.md`), Design 06 (`06-multiagent-orchestrierung.md`)
- Methodik (`docs/workflows/benchmark-methodik.md` inkl. Kostenmessung 4b)
- Skripte: `scripts/benchmark/` (run-round, followup-synthesis, audit-sources, benchmark-costs, templates/benchmark-task.md)
