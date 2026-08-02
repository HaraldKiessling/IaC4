# Benchmark-Methodik: OC1/OC2/OC3-Vergleichsmessung (Best Practices)

> **Zweck:** Wiederverwendbare Methodik für OpenClaw-Instanz-Vergleichstests (OC1/OC2/OC3 auf vps-dev).
> Basierend auf T1 (2026-08-02, 15 Läufe/45 Runs, Design 04) und T2 (Reasoning-Level-Variable, 12 Läufe/36 Runs).
> Stand: 2026-08-02 · Status: aktiv (konsolidiert aus PR #74/#76 + T2-Auswertung)

## 1. Testaufbau

### 1.1 Instanzen (vps-dev, Ports fix)

| Arm | Instanz | Agent | Modell (Orchestrator) | Rolle |
|---|---|---|---|---|
| OC1 | `oc1` (18789) | `main` | deepseek-v4-flash | Vanilla-Baseline (kein agents.list) |
| OC2 | `oc2` (18790) | `orchestrator` | deepseek-v4-flash | Team-Ist (4 Agents, suggest/Depth 1) |
| OC3 | `oc3` (18791) | `orchestrator` | deepseek-v4-pro | Best-Practice (4 Agents, prefer/Depth 2, Modell-Invertierung) |

Konstanten (Design 01): `maxConcurrent: 4`, `runTimeoutSeconds: 900` — identisch je Arm (Variablenkontrolle).

### 1.2 Voraussetzungen (Checkliste vor jedem Lauf)

- [ ] Alle 3 Instanzen `health` = ok (Gateway-RPC, kein SSH)
- [ ] Token-Datei `/tmp/gw_token.env` vorhanden (35 Zeichen) — **nie ausgeben, nie committen**
- [ ] **BOOTSTRAP.md entfernt** (skipBootstrap aktiv, PR #76) — sonst verfälscht es Denk-Zeit (T1-Befund: OC2 verlor 5/15 Läufe)
- [ ] Snapshot-Bibliothek frisch (neue Seeds je Runde — **Lerneffekt!** Keine Snapshots wiederholen)
- [ ] `reasoningTokens`-Key korrekt (NICHT `reasoning` — T2-Bug: Usage-Spalte war 0)

### 1.3 Clean-Modus (deterministische Startbedingung, Issue #78)

Vor jeder Benchmark-Runde die Instanzen auf definierten Ausgangszustand zurücksetzen (PR #79):

```bash
gh workflow run 04-service-deploy.yml -f target=dev -f playbook=openclaw -f instance=all -f skip_bootstrap=true -f clean=true
```

**Was `clean=true` löscht** (nur Persistenz-State, SSoT bleibt):
- `config/agents/` → Session-Store (`~/.openclaw/agents/<id>/sessions/`), QMD-Index (`.../qmd/`), Agent-Dirs/Auth
- `config/state/` → `openclaw.sqlite` (TaskFlow/Plugin-State)
- `workspace/` → AGENTS.md/MEMORY.md/BOOTSTRAP.md (wird beim Start neu erzeugt)

**Was bleibt:** `openclaw.json` (SSoT), `docker-compose.yml`, Secrets (ENV), `credentials/` (kein OAuth/QR — statische Keys via Template).

**Verifikation nach Clean (Gateway-RPC, kein SSH):**
```bash
openclaw gateway call sessions.list --url wss://vps-dev.tailcfea8a.ts.net:<port> ...   # count=0
openclaw gateway call agents.workspace.list --url ... --params '{"agentId":"..."}'     # frisch
openclaw gateway call health --url ...                                                 # ok
```

**Regeln:**
- `clean` nur mit `target=dev` ohne Zusatz-Approval; PROD-Clean nur mit `confirm_clean_prod=true` (H1)
- Merge-Reihenfolge: PR #76 (skip_bootstrap) VOR PR #79 (clean) — sonst fehlt der skipBootstrap-Konsument
- Nach Clean: erster Agent-Turn je Instanz ist der Benchmark-Task (kein Bootstrap-Ritual, da BOOTSTRAP.md entfernt + skipBootstrap aktiv)

### 1.3 Session-Isolation

- Eindeutige Session-Keys je Lauf: `agent:<id>:benchmark-<runde>-<uuid8>` (verhindert Wiederholungs-Lerneffekt)
- Nach jedem Lauf: Session-Transkripte der Instanzen via `sessions.get` sichern (ROI: vollständige Adjudikation möglich, T1-Lesson)

## 2. Durchführung

### 2.1 Snapshots (Seeds)

- **12 frische Snapshots je Runde** (`snapshot-t<n>.md`): je 2 Seed-Defekte (S1 Hauptdefekt, S2 Zweitdefekt) + 1 Köder (S3, korrekt — kein Fehlalarm erwartet)
- Defekt-Klassen rotieren: Security/Exposition, Idempotenz, Config-Divergenz, Workflow-Security, Pinning, Firewall, Secret-Hygiene, BDD-Asserts…
- **Ground Truths vorab fixieren** (`ground-truth-t<n>.md`): Defekt, Klasse, Schwere + **SHA-256 des Snapshots** (Integrität)
- Task-Format: Snapshot-Text + Zusatzinfo (Kontext-Hinweis) — Zusatzinfo ist der **Kontext-Test** (T1-Befund: OC1 übersieht Kontext-Defekte)

### 2.2 Loop (automatisiert)

```bash
# T2-Muster (Reasoning-Level-Variable)
setsid nohup python3 -u run_benchmark_t2.py > /tmp/benchmark-t2.log 2>&1 < /dev/null &
```

- **Rotation je Lauf** (Design 01 Kap. 6.1): Reihenfolge rotiert (oc2→oc3→oc1, dann oc3→oc1→oc2, …) — gleiche Startbedingungen
- **Level-Rotation**: bei Level-Experimenten je Lauf EIN Level für ALLE 3 Instanzen (Fairness), Level rotiert über Läufe
- **Artefakt-Trennung (Pflicht!):** je Instanz EIGENE Datei `t1-run<lauf>-<inst>.md` — Design-04-T3-Fix (T1-Bug: instanzfremde Dateien wurden überschrieben, nur letzter Schreiber sichtbar)
- Task-Log je Lauf: Input/Output/Reasoning/Total/Dauer je Instanz + Level + Rotation
- Prozess-Hygiene: `setsid nohup` (überlebt Session-Ende; T1-Lesson: Loop starb mit Session, 6 Läufe verloren)

### 2.3 Messgrößen

| Metrik | Quelle | Hinweis |
|---|---|---|
| Latenz (s) | Loop (CLI-Dauer) | je Instanz × Level |
| Tokens (in/out/reasoning/total) | `agentMeta.usage` | **Key: `reasoningTokens`** |
| Kosten (€) | Tokens × Preis | DeepSeek V4 Promo: flash $0.14/$0.28, pro $0.435/$0.87 je 1M; Kurs 1 EUR = 1.14 USD |
| Qualität (S1/S2-Treffer) | Ground-Truth-Adjudikation | automatisiert (Keyword) + Harald-Stichprobe |
| Sub-Agent-Nutzung | Transkript-Scan (`toolCall`-Typen) | 0 Spawns = Team-Modus nicht aktiv (T1-Befund!) |
| Thinking-Tiefe | Transkript-Scan (`thinking`-Blöcke) | Zeichen je Session (T1: OC2 307k vs OC1 78k) |

## 3. Adjudikation

1. **Automatisiert:** Keyword-Matching Artefakt ↔ Ground Truth (S1/S2/S3), 3-stufig (✅/❌)
2. **Manuell (Harald):** Stichprobe ≥ 6–9 Outputs je Runde (100% bei n≤15 machbar)
3. **Blind-Review:** Artefakte ohne Instanz-Kennzeichnung auswerten, Zuordnung NUR im Task-Log
4. **Schwere-Graduierung prüfen:** Blocker vs. Major vs. Minor — Instanzen finden Defekte, stufen aber unterschiedlich (T2-Befund: OC3 fand no_log als Major statt Blocker)

## 4. Auswertung & Reporting

- Gesamtauswertung: Ø Total/Ø Dauer je Instanz × Level
- Qualitäts-Matrix: S1/S2-Treffer je Lauf (S1 ≈ immer 100%, S2 = Differenzierer)
- **Kosten-Gesamtbild** je Instanz (T1: OC3 teuerster Arm trotz weniger Tokens — pro-Orchestrator; T2: OC2 ≈ OC1, da Reasoning normalisiert)
- Lerneffekt-Kontrolle: Snapshots nie wiederholen; bei Abbruch+Resume: aborted Sessions kennzeichnen und NICHT doppelt werten (T1: t10 doppelt gelaufen)

## 4.5 Clean-Modus (deterministische Startbedingung, Issue #78)

Vor JEDER Benchmark-Runde die Instanzen auf Null-Zustand setzen (sonst kontaminieren Session-Historie, QMD-Index und Runtime-State die Messung):

```bash
# Clean auf DEV (empfohlen vor jeder Runde):
gh workflow run 04-service-deploy.yml -f target=dev -f playbook=openclaw -f instance=all -f clean=true
# Clean auf PROD (nur mit Freigabe Harald):
gh workflow run 04-service-deploy.yml -f target=prod -f playbook=openclaw -f instance=all -f clean=true -f confirm_clean_prod=true
```

**Was Clean löscht (evidenzbasiert, OpenClaw-Doku):**
- `config/agents/` → Session-Store, QMD-Index, Agent-Dirs (`~/.openclaw/agents/<id>/{sessions,qmd,agent}`)
- `config/state/` → openclaw.sqlite (TaskFlow/Plugin-State)
- `workspace/` → AGENTS.md/MEMORY.md/BOOTSTRAP.md (wird beim Start neu erzeugt)

**Was Clean NICHT anfasst (SSoT):** `openclaw.json`, `docker-compose.yml`, Secrets (ENV), `credentials/` (statische API-Keys via ENV/Template).

**Verifikation nach Clean:** `sessions.list` → 0, `agents.workspace.list` → leer, alle Instanzen `health=ok`.

**Kombination:** `clean=true` + `skip_bootstrap=true` (PR #76) = BOOTSTRAP.md weg + kein Persistenz-State → sauberster Benchmark-Start.

## 5. Best Practices (konsolidierte Lessons)

| # | Praxis | Lesson (Quelle) |
|---|---|---|
| BP-1 | Artefakte je Instanz trennen | T1: instanzfremde Dateien überschrieben → 22/33 Outputs verloren |
| BP-2 | `setsid nohup` + Log | T1: Loop starb mit Session (PID weg, Log leer) |
| BP-3 | BOOTSTRAP.md entfernen (skipBootstrap) | T1: OC2 5/15 Läufe Ablenkung (307k Thinking-Zeichen) |
| BP-4 | `reasoningTokens` statt `reasoning` | T2: Usage-Spalte 0 (falscher Key) |
| BP-5 | Level × Snapshot ENTKOPPELN (gepaartes Design) | T2: max-Snapshots leichter → Level-Effekt verzerrt |
| BP-6 | Session-Transkripte sichern | T1: einzige vollständige Quelle für Adjudikation |
| BP-7 | Sub-Agent-Completion-Events nicht abwarten | T2: Events kamen nicht an → Ergebnisse via `sessions_history` ziehen |
| BP-8 | Ground-Truth-SHA fixieren | T1: Zuordnung nur über SHA wasserdicht |
| BP-9 | Token nie in Prozess-Args | Env-only (`OPENCLAW_GATEWAY_TOKEN`), ps-sicher |
| BP-10 | Frische Snapshots je Runde | Lerneffekt-Kontamination (gleicher Snapshot 2× gesehen) |
| BP-11 | **Clean-Modus vor jeder Runde** (`clean=true`-Deploy, Issue #78) | Sessions/QMD/State/Workspace der Instanzen = Null-Zustand; SSoT bleibt; PROD nur mit `confirm_clean_prod=true` |

## 6. Referenzen

- Design 01: `iac4-design/01-oc2-oc3-benchmark.md` (Arme, Konstanten, Rotation)
- Design 03: `iac4-design/03-benchmark-durchfuehrung.md` (Ablauf, Adjudikation)
- Design 04: `iac4-design/04-benchmark-ergebnis.md` (PR #74, T1-Ergebnisse)
- Issue #75 (OC2-Nachteile, Reasoning-Level), Issue #29 (Workspace-Isolation)
- Skripte: `benchmark/run_benchmark_t2.py`, `benchmark/snapshots/build_snapshots_t2.py` (lokal, nicht im Repo)
- DeepSeek-Preise (Promo, 2026-08): flash $0.14/$0.28, pro $0.435/$0.87 je 1M Tokens
