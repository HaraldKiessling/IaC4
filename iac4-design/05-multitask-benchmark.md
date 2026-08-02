# Design 05: Multi-Task-Parallel-Benchmark mit echten Issues (OC1/OC2/OC3)

> **Status:** Entwurf (Review ausstehend) · **Stand:** 2026-08-02 · **Autor:** Nova (Orchestrator)
> **Zweck:** Benchmark-Konzept — mehrere reale Aufgaben gleichzeitig auf allen 3 Instanzen (OC1/OC2/OC3), jede Instanz bearbeitet eine andere Aufgabe. Misst Orchestrierungs- und Parallel-Fähigkeit, nicht nur Einzelaufgaben-Lösung.

## 1. Motivation & Abgrenzung zu T1/T2

| Aspekt | T1/T2 (Design 03/04) | Design 05 (dieses Konzept) |
|---|---|---|
| Input | Künstliche Snapshots mit Seed-Defekten | **Echte Issues aus dem IaC4-Backlog** |
| Aufgaben je Lauf | 1 identische Aufgabe für alle 3 Arme | **3 verschiedene Aufgaben parallel** (1 je Arm) |
| Gemessene Fähigkeit | Defekt-Findung | **Orchestrierung**: Sub-Agent-Einsatz, Aufgaben-Organisation, Konzept-Qualität |
| Realismus | Synthetisch | Echte Anforderungen, echter Repo-Kontext (read-only) |
| Output | Defekt-Befund | **Umsetzungsplan/Architektur-Entwurf/Review-Artefakt** (Markdown im Workspace) |

**These:** Echte, parallel verteilte Aufgaben fordern die Orchestrator-Instanzen (OC2/OC3) stärker als Snapshot-Defekt-Suche — Sub-Agent-Delegation (architect/engineer/reviewer) wird bei umfangreichen Issues zum Differenzierer. OC1 (Vanilla-Baseline, keine Rollen-Agents) zeigt den Team-Vorteil als Kontrast.

## 2. Testaufbau

### 2.1 Arme (unverändert, vps-dev)

| Arm | Instanz | Agent | Modell (Orchestrator) | Rolle |
|---|---|---|---|---|
| OC1 | `oc1` (18789) | `main` | deepseek-v4-flash | Vanilla-Baseline (kein agents.list) |
| OC2 | `oc2` (18790) | `orchestrator` | deepseek-v4-flash | Team-Ist (4 Agents, suggest/Depth 1) |
| OC3 | `oc3` (18791) | `orchestrator` | deepseek-v4-pro | Best-Practice (4 Agents, prefer/Depth 2, Modell-Invertierung) |

Konstanten (Design 01): `maxConcurrent: 4`, `runTimeoutSeconds: 900` — identisch je Arm (Variablenkontrolle).

### 2.2 Task-Pool (Kandidaten-Issues, Stand 2026-08-02)

Eignungskriterien: kein offener PR (frei), read-only-tauglich (Analyse/Plan/Design, kein Repo-Write nötig), Sub-Agent-Potenzial (mehrere Teilaspekte → Delegation), klare Anforderungen (Bewertbarkeit).

| Issue | Titel | Komplexität | Sub-Agent-Potenzial | Besonderheit |
|---|---|---|---|---|
| [#65](https://github.com/HaraldKiessling/IaC4/issues/65) | Code-Server auf DEV deployen | **H** | Hoch (Rolle+Router+ADR+Risiko) | Haralds Wunschkandidat; IaC3-Referenz vorhanden |
| [#42](https://github.com/HaraldKiessling/IaC4/issues/42) | Done-Nachweis: Parser-Gate + Absichts-Assertions | **M** | Hoch (Vorfall-Analyse + Test-Design) | Methodik-Thema, BDD-Bezug |
| [#32](https://github.com/HaraldKiessling/IaC4/issues/32) | Regelsystem: Risiko-Klassifikation + Review-Gates | **M** | Hoch (Konzept + Regel-Entwürfe) | Sicherheits-Thema |
| [#29](https://github.com/HaraldKiessling/IaC4/issues/29) | Parallel-Session-Kollisionen verifizieren | **M/L** | Mittel (git-Analyse, mehrere Prüfpfade) | Thematisch meta (Parallelität) |
| [#24](https://github.com/HaraldKiessling/IaC4/issues/24) | BDD-Tests für OpenClaw-Deployment | **M** | Mittel (5 Testfälle) | Tests gegen laufende Instanz |
| [#23](https://github.com/HaraldKiessling/IaC4/issues/23) | Tool-Permission-Matrix | **L** | Mittel (Matrix + Begründung) | Doku/Analyse |
| [#66](https://github.com/HaraldKiessling/IaC4/issues/66) | Evidenzbasierte Reviews (Anforderungen) | **M** | Mittel (Review-Kriterien) | Review-Thema |
| [#68](https://github.com/HaraldKiessling/IaC4/issues/68) | Betriebs-Backlog (Selbstheilung/Token-Divergenz/Teardown) | **H** | Hoch (3 Teilbereiche) | Aus PR #67 ausgegliedert |
| [#75](https://github.com/HaraldKiessling/IaC4/issues/75) | OC2-Nachteile T1 + dynamisches Reasoning-Level | **L** | Mittel (Analyse + Idee) | Meta-Benchmark-Thema |

### 2.3 Aufgaben-Zuordnung & Rotation

- **Runde** = 3 parallele Läufe (OC1/OC2/OC3), je Arm genau 1 Issue.
- **Rotation über Runden:** Kein Arm bearbeitet dasselbe Issue zweimal; über 3 Runden durchläuft jeder Arm jede Komplexitäts-Klasse (H/M/L) → Fairness trotz ungleicher Schwierigkeit.
- **Runde 1 (Vorschlag, Freigabe Harald):** OC1→#42 (M), OC2→#65 (H), OC3→#32 (M). Alternative: OC3→#65 (schwerster Task an stärkstem Arm).
- **Prompt-Template** standardisiert (Anhang A): Issue-Body als Input + Rahmenbedingungen (read-only, Artefakt-Format, Sub-Agents, Token-Zugriff).

### 2.4 Rahmenbedingungen (alle Läufe)

1. **Read-only GH-Token** (`.gh-read-token` im Workspace) — Probe 2026-08-02 bestätigt: Lesen (Issues/Repo/Workflows/Check-Runs) 200 ✅, Schreiben 403 ❌. Reicht für Analyse-Artefakte vollständig.
2. **Artefakte:** Markdown im Instanz-Workspace unter `benchmark/mt<runde>/<issue>-<inst>.md` — **je Instanz eigene Datei** (Design-04-T3-Fix: Artefakt-Trennung).
3. **Session-Isolation:** eindeutige Session-Keys `agent:<id>:benchmark-mt<runde>-<uuid8>` (verhindert Wiederholungs-Lerneffekt).
4. **Clean vor Runde** (PR #79) — deterministische Startbedingung. ⚠️ Clean löscht `workspace/` → `.gh-read-token` wird durch den Deploy-Datei-Task NACH Clean neu angelegt (Reihenfolge im Play verifiziert, PR #80). Vor Lauf 1 verifizieren.
5. **Parallel-Start:** alle 3 Läufe gleichzeitig via `openclaw agent` (Background). Ressourcen-Sharing (1 VPS) ist **bewusste Kovariate** (siehe 5).
6. **Kein Repo-Write:** Artefakte bleiben im Workspace; keine Branches/PRs durch die Instanzen. (Voll-Umsetzung später durch Nova auf Basis der Artefakte — Option, siehe 7.)

## 3. Messgrößen (Erweiterung Methodik 2.3)

| Metrik | Quelle | Hinweis |
|---|---|---|
| Latenz (s) | Loop (CLI-Dauer) | je Instanz × Issue |
| Tokens (in/out/reasoning/total) | `agentMeta.usage` | **Key: `reasoningTokens`** (T2-Bug) |
| Kosten (€) | Tokens × Preis | DeepSeek V4: flash $0.14/$0.28, pro $0.435/$0.87 je 1M; 1 EUR = 1.14 USD |
| **Anforderungs-Abdeckung (%)** | Issue-Checkboxen/-Anforderungen als Ground-Truth-Ersatz | **Neu:** je Issue vor Lauf fixierte Checkliste; automatisiert (Keyword) + manuell |
| IaC4-Konformität | Artefakt-Review | ADR-Bezug, Regeln (secrets/ssh/evidence), keine Verbotsverletzung |
| Sub-Agent-Nutzung | Transkript-Scan (`toolCall`-Typen) | Spawns, Rollen (architect/engineer/reviewer), Depth |
| **Zeit bis erster Spawn** | Transkript-Zeitstempel | **Neu:** Orchestrierungs-Latenz |
| Artefakt-Qualität | Blind-Review | Struktur, Vollständigkeit, Begründungen, Alternativen |

**Normierung:** Komplexitäts-Gewicht H=3 / M=2 / L=1 → `Anforderungs-Score / Komplexität` je Arm (Fairness bei ungleichen Issues).

## 4. Adjudikation

1. **Ground-Truth-Ersatz:** je Issue eine Checkliste der Anforderungen (aus Issue-Body, vor Lauf fixiert, SHA-256 gesichert).
2. **Automatisiert:** Keyword-Matching Artefakt ↔ Anforderung (3-stufig ✅/⚠️/❌).
3. **Manuell (Harald):** Stichprobe ≥ 6–9 Artefakte je Runde.
4. **Blind-Review:** Artefakte ohne Instanz-Kennzeichnung; Zuordnung nur im Task-Log (T1-Praxis).
5. **Sub-Agent-Wertung:** Spawn-Zahl ≠ Qualität — Transkript-Belege (Delegation sinnvoll eingesetzt?) statt reiner Zählung (T1-Befund: 0 Spawns = Team-Modus inaktiv).

## 5. Fairness & Variablenkontrolle

- Gleiche Prompt-Struktur (Template Anhang A), gleiche Konstanten (maxConcurrent/runTimeout).
- Aufgaben-Rotation über Runden; kein Issue doppelt.
- **Ressourcen-Sharing:** 3 parallele Läufe auf einem VPS → Latenz nicht absolut vergleichbar. Gegenmaßnahmen: O5-Ressourcen-Kovariate (PR #70) mitschneiden; relative Latenz (je Lauf) statt absoluter; Reihenfolge-Effekte durch Rotation.
- **Rate-Limits:** GH read-only 5000 req/h — unkritisch; bei 503/504 Retry im Prompt (T1-Lesson: aborted Läufe kennzeichnen, nicht doppelt werten).
- **Kontext-Kovariate:** Issue-Body wird komplett in den Prompt gegeben (kein versteckter Kontext — bewusste Abweichung vom T1-Kontext-Test, da echte Anforderungen vollständig sein müssen).

## 6. Risiken & Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|---|---|
| Lerneffekt: Issue wird durch Benchmark „verbraucht" | Artefakte sind verwertbare Lösungsskizzen → danach echte Umsetzung durch Nova (Write, PR) auf Basis des Gewinner-Artefakts |
| OC1 hat keine Rollen-Agents → Spawn-Versuche scheitern/entfallen | OC1 als Single-Agent-Baseline werten; Spawn-Versuche (0) sind Messwert, kein Fehler |
| Clean löscht `.gh-read-token` | Deploy-Reihenfolge verifizieren (Datei-Task nach Clean); Pre-Check vor Runde |
| GitHub-503/Downtime | Retry im Prompt (3×), Lauf als `aborted` kennzeichnen |
| Artefakt-Kollision (Instanzen schreiben gleiche Datei) | Eindeutige Pfade je Instanz (`<issue>-<inst>.md`); Artefakt-Trennung Pflicht |
| Sub-Agent-Spawns dauern lang (Depth 2) | runTimeout 900s; Überwachung via Task-Log (kein stiller Tod) |
| Ressourcen-Engpass (3 Läufe parallel, 1 VPS) | Kovariate messen; bei OOM: Runde wiederholen, gekennzeichnet |

## 7. Offene Fragen an Harald

1. **Runde-1-Zuordnung:** OC3 auf #65 (schwerster Task an stärkstem Arm) oder OC2 (Team-Ist vs. pro-Orchestrator-Vergleich auf H)?
2. **Anzahl Runden:** 1 Pilot (Konzept-Validierung) oder direkt 3 (volle Rotation)?
3. **Artefakt-Verwertung:** Gewinner-Artefakte danach von mir in echte PRs überführen (Write-Token vorhanden)?
4. **Voll-Umsetzungs-Benchmark** (später): eigener Write-Token `DEV_OC_BENCH_WRITE_TOKEN` (Branch/PR-Scope) — gewünscht?

## 8. Review-Gates (vor Durchführung)

- [ ] 🏗️ Architect-Review: Konzept-Vollständigkeit, 5W, Alternativen
- [ ] 🔍 Reviewer-Review: Methodik-Konsistenz, Variablenkontrolle, Checkliste, Risiken
- [ ] ✨ Harald-Freigabe
- [ ] Pre-Check: Health 3×, Token-Datei vorhanden, Clean-Zustand verifiziert

## Anhang A: Task-Prompt-Template (je Instanz)

```
Du bist der <ARM>-Arm eines Benchmark-Laufs (Multi-Task, Design 05).
Aufgabe: Bearbeite Issue <#NN> (<Titel>) bis zum Artefakt — KEINE Repo-Änderungen.

Kontext (read-only, nie ausgeben):
- GH-Read-Token: /home/node/.openclaw/workspace/.gh-read-token (nur lesen, nie zeigen)
- IaC4-Repo: https://github.com/HaraldKiessling/IaC4 (Issues/Contents/Workflows via API)
- Eigene Rolle: <OC1: Single-Agent / OC2: Orchestrator mit Architect+Engineer+Reviewer / OC3: wie OC2, prefer-Delegation>

Artefakt (Pflicht, Markdown):
/home/node/.openclaw/workspace/benchmark/mt<R>/<issue>-<inst>.md
1) Anforderungs-Analyse (Issue-Checkliste, priorisiert)
2) Lösungs-Design (IaC4-konform: ADR-Bezug, Regeln, Alternativen mit Begründung)
3) Risiko-Analyse (Security/Idempotenz/Regression)
4) Umsetzungs-Plan (Schritte, Dateien, Tests, Review-Punkte)
5) Review-Notiz (Selbst-Review + Sub-Agent-Befunde falls genutzt)

Rahmen:
- Nutze Sub-Agents (architect/engineer/reviewer), wo sie deinen Output verbessern.
- Token-Wert NIE ausgeben. Kein Schreiben ins Repo. Kein git push.
- Bei GitHub-503: bis 3× retry, dann weiterarbeiten.
- Beende mit: Artefakt-Pfad + Kurzfassung (3-5 Sätze) + Sub-Agent-Statistik (Anzahl Spawns, Rollen).
```
