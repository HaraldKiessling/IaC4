# Design 06: Multi-Agent-Orchestrierung — was dem Setup fehlt (evidenzbasiert)

> **Status:** Entwurf (Review ausstehend) · **Stand:** 2026-08-03 · **Autor:** Nova (Orchestrator)
> **Auslöser:** Issue #82 · Pilot-Befund Design 05 (mt0): OC2/OC3-Orchestrator macht ~80–90 % der Arbeit selbst, obwohl Sub-Agents verfügbar und Spawns > 0.

## 1. Problem & Root-Cause (Pilot-Befund)

| Metrik | OC2 (Team-Ist) | OC3 (Best-Practice) |
|---|---|---|
| Spawns | 2 | 3 |
| Orchestrator-Anteil an Tokens/ToolCalls | ~95 % | ~90 % |
| Ergebnis | Draft 5/6 | ❌ 0/6 (BP-7) |

**Root-Cause (Repo-Inspektion 2026-08-03):** Die `agents.list`-Einträge in `openclaw.json.j2` enthalten **nur `id`, `name`, `model`** — **keine System-Prompts** (`prompt`-Feld fehlt für Orchestrator, Architect, Engineer Pro, Reviewer). Konsequenzen:

1. Der Orchestrator hat **kein Delegations-Mandat** — kein Prompt sagt ihm „du VERTEILST, du führst nicht aus". LLM-Default ohne Anweisung: selbst machen (Spawn = mehr Aufwand, unsicherer Outcome).
2. Die Sub-Agents haben **keine Rollen-Prompts** — „Architect" ist nur ein Name ohne Verantwortlichkeiten, Methodik, Output-Format.
3. `delegationMode: "suggest"` ist nur eine *Erlaubnis* (darf vorschlagen), kein *Gebot* (muss delegieren) — vgl. OpenClaw-Doku: suggest = „the model may suggest", prefer = „prefer delegation when appropriate".
4. Keine **Output-Contracts**: Sub-Agent-Antworten sind unstrukturiert → Orchestrator muss selbst nacharbeiten statt synthetisieren.

**Fazit:** Das Setup hat die *Struktur* (Agents registriert, allowAgents, Modelle) — es fehlt das *Verhalten* (Prompts, Mandate, Contracts). Das ist der „Out-of-box"-Mangel.

## 2. Evidenz aus Primärquellen

### 2.1 Anthropic — Multi-Agent Research System (2025)
Quelle: https://www.anthropic.com/engineering/multi-agent-research-system

- Orchestrator (Lead) plant, zerlegt in Aspekte, spawns **3–5 Sub-Agents parallel**, synthetisiert + Zitations-Pass. Sub-Agents arbeiten **isoliert** (eigener Kontext, eigene Tools, kein Cross-Talk) und liefern **kondensierte Executive Summaries** („intelligent filters"), keine rohen Logs.
- **Token-Volumen erklärt ~80 % des Erfolgs** (BrowseComp): Multi-Agent gewinnt, weil er mehr Tokens auf das Problem wirft — aber nur bei Aufgaben mit **unabhängigen Parallel-Threads**.
- **90,2 % Verbesserung** ggü. Single-Agent auf internen Research-Evals; ~15× Token-Verbrauch als bewusster Trade-off.
- Lessons: (a) Sub-Agents isolieren (kein gegenseitiges Sehen), (b) Orchestrator = einziger Ort für globalen State, (c) Tool-Scoping je Rolle, (d) strukturierte Outputs.

### 2.2 OpenAI — Orchestrator-Workers / Agents as Tools
Quelle: https://developers.openai.com/api/docs/guides/agents/orchestration

- Orchestrator besitzt die User-Konversation, zerlegt dynamisch, delegiert **bounded Subtasks**, synthetisiert. Workers sind „Tools" — sie antworten nie dem User, liefern strukturierte Ergebnisse.
- **Delegations-Regeln im System-Prompt**: „Analyze → decide: direct or decompose → delegate with minimal context → request structured output → validate → synthesize."
- Workers: single responsibility, stateless, explizites Output-Schema (status/summary/key_points/sources), „ignore anything outside the handoff description".
- Kosten-/Kontext-Kontrolle: „Ask workers to return concise summaries, not full raw data."

### 2.3 Microsoft/Azure + Community-Konsens (Orchestrierungs-Patterns)
Quellen: https://learn.microsoft.com/en-us/agents/architecture/multi-agent-orchestrator-sub-agent · https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns

- **Orchestrator = Source of Truth**: hält Plan-Dokument (Subtasks, Status, Assignments), re-liest es vor jeder Delegation (Context-Rehydration).
- **Persistent Plan Artifact** (`MULTI_AGENT_PLAN.md`-Muster): Status je Subtask (not started/in progress/done).
- **Summarization an Grenzen**: nach jedem Agent-Schritt voller Output ins Log, kompakte Summary in den nächsten Prompt.
- **Quality Gates**: Output-Schema validieren (Format/Relevanz), Retry/Clarification, Circuit Breaker, Timeouts.
- Pipeline-Länge ≤ 3–4 Stufen, Agent-Anzahl ≤ 5–8.

### 2.4 OpenClaw-Doku (Mechanik, lokal verifiziert)
Quellen: `docs/tools/subagents.md` · `docs/gateway/config-agents.md` · `docs/concepts/parallel-specialist-lanes.md`

- `sessions_spawn` ist **non-blocking, push-based**; Requester soll nach Spawns `sessions_yield` aufrufen und die Completion als nächste Message empfangen. **Pilot-Befund (BP-7): Events kamen nicht an → aktives Abrufen (sessions_history) als Fallback nötig** — im Task-Prompt verankern.
- `subagents.delegationMode`: suggest (darf) vs. prefer (bevorzugt) — **kein „must"**; das Mandat muss im Orchestrator-Prompt stehen.
- `subagents.requireAgentId`, `allowAgents`, `maxConcurrent`, `maxSpawnDepth`: existieren; **unbenutzt: Per-Agent-Prompts, Per-Agent-Tool-Policies (der stärkste Hebel für Verteilung).**
- Specialist-Lanes-Prinzip: „Purpose, Non-goals, Chat budget, Handoff rule, Tool-risk rule" — als Lane-Contract je Agent übertragbar.

## 3. Was dem Setup fehlt (Checkliste, aus Evidenz abgeleitet)

| # | Fehlt | Evidenz | Konkret für OC2/OC3 |
|---|---|---|---|
| 1 | **Orchestrator-System-Prompt mit Delegations-Mandat** | Anthropic/OpenAI | „Du bist der Orchestrator. Du VERTEILST Arbeit an deine Spezialisten (architect/engineer-pro/reviewer). Du führst NUR Koordination selbst aus: Planen, Zerlegen, Delegieren, Validieren, Synthetisieren. Fachliche Arbeit (Recherche, Design, Code, Review) delegierst du — auch wenn du sie selbst könntest. Wenn du eine Teilaufgabe selbst ausführst, die ein Spezialist könnte, ist das ein Fehler." |
| 2 | **Rollen-Prompts für Sub-Agents** | Anthropic (isolation, tool-scoping), OpenAI (single responsibility) | Architect: ADR-/Design-Methodik, 5W, Alternativen, Output-Schema. Engineer Pro: IaC4-Regeln, set -euo pipefail, Evidence. Reviewer: Review-Checkliste (Methodik Schritt 6), Befund-Format, Signatur. Jeder: „Du bist Sub-Agent — antworte NIE dem User, liefere strukturiertes Ergebnis an den Orchestrator." |
| 3 | **Output-Contracts (strukturierte Ergebnisse)** | OpenAI (Schema), Anthropic (condensed summaries) | Jeder Sub-Agent liefert: `{status, ergebnis, belege/quellen, offene_punkte}` als kompakte Summary (nicht rohe Logs). Orchestrator validiert vor Synthese. |
| 4 | **Plan-Dokument / State im Orchestrator** | Microsoft/Azure (plan artifact) | Orchestrator führt Plan (Subtasks, Status, Assignments) als Workspace-Datei; re-liest vor Delegation. |
| 5 | **Completion-Handling (BP-7-Fix)** | OpenClaw-Doku + Pilot | Prompt-Regel: „Nach Spawn: `sessions_yield`, dann Ergebnis aktiv via sessions_history holen; nie ohne Ergebnis weiter." |
| 6 | **Tool-Scoping als Verteilungs-Hebel** | Anthropic (tool scoping), Specialist-Lanes | Orchestrator: Koordinations-Tools (sessions_spawn, read, write Plan-Datei) + minimale Fach-Tools; Sub-Agents: volle Fach-Tools (web_search, exec, gh, read). Wenn der Orchestrator kein web_search/exec hat, MUSS er delegieren. |
| 7 | **Verteilungs-Metriken** | Issue #82 Nachweis 2 | Orchestrator-Anteil an Tokens/ToolCalls < 40 %; ≥ 1 Spawn je Teilaufgabe; 0 abgebrochene Läufe; Artefakt-Disziplin 100 %. |

## 4. Umsetzungs-Vorschlag (nächster Schritt, nach Freigabe)

1. `openclaw.json.j2`: `prompt`-Feld je Agent (Orchestrator-Mandat + Rollen-Prompts aus AGENTS.md/methodology.md destilliert), parametrisiert per group_vars.
2. Per-Agent-Tool-Policy (tools.allow/deny): Orchestrator ohne web_search/exec/gh; Sub-Agents mit Fach-Tools.
3. Output-Contract als gemeinsame Prompt-Schablone (JSON-Schema im Prompt).
4. Task-Prompt-Template Design 05 (Anhang A) um Completion-Handling erweitern (bereits in Runde 2+ drin).
5. **Verifikation:** Nachweis 1 = Pilot (vorher, Baseline ~80 % Selbstarbeit) · Nachweis 2 = Benchmark Design 05 Runden L/M/H (nachher, Ziel: Orchestrator < 40 %).

## 5. Offene Fragen an Harald

1. Tool-Scoping scharf (Orchestrator ohne exec/web_search — harte Delegations-Zwang) oder weich (Prompt-Mandat, Tools bleiben)?
2. Rollen-Prompts aus AGENTS.md/methodology.md destillieren (IaC4-konform) — ok?
3. Soll Design 06 die Umsetzung als PR (Template-Erweiterung + group_vars) sofort anstoßen, oder erst nach Benchmark-Runden L/M/H (Nachweis-2-Baseline mit ALTEM Setup messen)?
