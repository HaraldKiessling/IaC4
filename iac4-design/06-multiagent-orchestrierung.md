# Design 06: Multi-Agent-Orchestrierung — was dem Setup fehlt (evidenzbasiert)

> **Status:** Überarbeitung nach Review (PR #83, Befunde Major-1…-4 eingearbeitet) · **Stand:** 2026-08-03 · **Autor:** Nova (Orchestrator) · **Review:** 🏗️ (PR #83)
> **Auslöser:** Issue #82 · Pilot-Befund Design 05 (mt0): OC2/OC3-Orchestrator macht ~90–95 % der Arbeit selbst, obwohl Sub-Agents verfügbar und Spawns > 0.

## 1. Problem & Root-Cause (Pilot-Befund)

| Metrik | OC2 (Team-Ist) | OC3 (Best-Practice) |
|---|---|---|
| Spawns | 2 | 3 |
| Orchestrator-Anteil an Tokens/ToolCalls | ~95 % | ~90 % |
| Ergebnis | Draft 5/6 | ❌ 0/6 (BP-7) |

*(Zahlen harmonisiert mit Issue #82: „~80 %" im PR-Body war Tippfehler; korrekt 90–95 %.)*

**Root-Cause (Repo-Inspektion 2026-08-03, verifiziert im Review):** Die `agents.list`-Einträge in `openclaw.json.j2` (Z. 33–39) enthalten **nur `id`, `name`, `model`** — **keine System-Prompts, keine Workspace-Dateien je Agent, keine Per-Agent-Tool-Policies**. Konsequenzen:

1. Der Orchestrator hat **kein Delegations-Mandat** — kein Prompt sagt ihm „du VERTEILST, du führst nicht aus". LLM-Default ohne Anweisung: selbst machen.
2. Die Sub-Agents haben **keine Rollen-Prompts** — „Architect" ist nur ein Name ohne Verantwortlichkeiten, Methodik, Output-Format.
3. `delegationMode: "suggest"` ist nur eine *Erlaubnis*, kein *Gebot* — vgl. OpenClaw-Doku `subagents.md`: *„controls prompt guidance only; it does not change tool policy or enforce delegation"*.
4. Keine **Output-Contracts**: Sub-Agent-Antworten sind unstrukturiert → Orchestrator muss nacharbeiten statt synthetisieren.
5. **Kein Tool-Scoping:** Der Orchestrator hat dieselben Fach-Tools (exec/web_search) wie die Sub-Agents — nichts zwingt ihn zu delegieren. Empirisch: T1 (Design 04) = **0 Spawns in 46 Sessions trotz suggest/prefer**; mt0 = Spawns 2/3, aber 90–95 % Selbstarbeit. Prompt-Guidance allein wirkt nachweislich nicht.

**Fazit:** Das Setup hat die *Struktur* (Agents registriert, allowAgents, Modelle) — es fehlt das *Verhalten* (Prompts, Mandate, Contracts, Tool-Policies).

## 2. Evidenz aus Primärquellen

### 2.1 Anthropic — Multi-Agent Research System (2025)
Quelle: https://www.anthropic.com/engineering/multi-agent-research-system
- Orchestrator (Lead) plant, zerlegt, spawns 3–5 Sub-Agents parallel, synthetisiert. Sub-Agents arbeiten **isoliert**, liefern **kondensierte Executive Summaries**.
- Token-Volumen erklärt ~80 % des Erfolgs (BrowseComp) — nur bei Aufgaben mit unabhängigen Parallel-Threads.
- Lessons: (a) Sub-Agents isolieren, (b) Orchestrator = einziger Ort für globalen State, (c) **Tool-Scoping je Rolle**, (d) strukturierte Outputs.

### 2.2 OpenAI — Orchestrator-Workers / Agents as Tools
Quelle: https://developers.openai.com/api/docs/guides/agents/orchestration
- Orchestrator besitzt die Konversation, delegiert **bounded Subtasks**, synthetisiert. Workers sind „Tools" — antworten nie dem User, liefern strukturierte Ergebnisse.
- Delegations-Regeln **im System-Prompt**; Workers: single responsibility, explizites Output-Schema.

### 2.3 LangGraph — Supervisor-Muster (Community-Standard)
Quellen: https://langchain-ai.github.io/langgraph/concepts/multi_agent/ · https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/
- **Best Practice: Supervisor ohne Domain-Tools** („manager agent, no tools") — Supervisor = reiner Router/Planner, alle Tools liegen bei den Workern.
- „You usually keep the supervisor tool-free when you want a pure planner/orchestrator that doesn't do work itself, need auditability and policy control over tool usage, want clear layering."
- Routing-Regeln im Supervisor-Prompt (Roster + Spezialisierung + Terminierung), strukturierte Routing-Outputs (`{"next": "worker"}`).

### 2.4 Microsoft/Azure + Community-Konsens
Quellen: https://learn.microsoft.com/en-us/agents/architecture/multi-agent-orchestrator-sub-agent · https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns
- Orchestrator = Source of Truth, persistentes Plan-Artefakt, Summarization an Grenzen, Quality Gates, Pipeline ≤ 3–4 Stufen.

### 2.5 OpenClaw-Doku (Mechanik, lokal verifiziert)
Quellen: `docs/tools/subagents.md` · `docs/gateway/config-agents.md` · `docs/concepts/agent-workspace.md` · `docs/gateway/config-tools.md`
- `delegationMode` = **prompt guidance only**; suggest = „standard prompt nudge", prefer = „delegate anything more involved" — beides kein Gebot.
- **`agents.list[].tools.allow/deny` + `alsoAllow` existieren** (`config-tools.md`, `multi-agent-sandbox-tools.md`) → Tool-Scoping technisch umsetzbar.
- **`agents.list[].workspace` existiert** (`agent-workspace.md` Z. 40) → Per-Agent-Workspace mit eigenen `AGENTS.md`/`SOUL.md` ist die native Prompt-Mechanik. **Kein `prompt`-Feld in `agents.list` nachweisbar** (Review-Befund Major-1) → Umsetzung NIE über Config-Prompt, immer über Workspace-Dateien.
- `sessions_spawn` ist non-blocking, push-based; Doku: `sessions_yield` + Completion als nächste Message (Pilot-BP-7: Events kamen nicht an → Timeout-Fallback via `sessions_history`).

## 3. Was dem Setup fehlt (Checkliste)

| # | Fehlt | Evidenz | Konkret für OC2/OC3 |
|---|---|---|---|
| 1 | **Orchestrator-System-Prompt mit Delegations-Mandat** | Anthropic/OpenAI/LangGraph | `AGENTS.md` im Orchestrator-Workspace: „Du VERTEILST, du führst nicht aus. Fachliche Arbeit delegierst du — auch wenn du sie selbst könntest." + Roster der Sub-Agents + Routing-/Terminierungsregeln. |
| 2 | **Rollen-Prompts für Sub-Agents** | Anthropic, OpenAI | Je Sub-Agent eigene Workspace-Datei (`AGENTS.md`): Architect (Design-Methodik, 5W, Alternativen), Engineer (IaC4-Regeln, `set -euo pipefail`, Evidence), Reviewer (Checkliste Methodik Schritt 6, Befund-Format, Signatur). Jeder: „antworte NIE dem User, liefere strukturiertes Ergebnis an den Orchestrator." |
| 3 | **Output-Contracts** | OpenAI (Schema), Anthropic (Summaries) | Jeder Sub-Agent liefert `{status, ergebnis, belege/quellen, offene_punkte}` als kompakte Summary. |
| 4 | **Plan-Dokument / State** | Microsoft | Orchestrator führt Plan (Subtasks/Status) als Workspace-Datei; re-liest vor Delegation. |
| 5 | **Completion-Handling (BP-7-Fix)** | OpenClaw-Doku + Pilot | Regel: „Nach Spawn: `sessions_yield`; kommt keine Completion, nach Timeout via `sessions_history` aktiv abrufen. Nie ohne Ergebnis weiter." (yield zuerst, Polling nur als Fallback) |
| 6 | **Tool-Scoping als Verteilungs-Hebel** | LangGraph (Kern), Anthropic, OpenAI + T1/mt0-Empirie | Orchestrator: nur Koordinations-/Lese-Tools (sessions_*, read, write für Plan) + `AGENTS.md`-Zugriff; **ohne exec/web_search/gh** → MUSS delegieren. Sub-Agents: volle Fach-Tools. |
| 7 | **Verteilungs-Metriken** | Issue #82 | Siehe Kap. 7 (Mess-Methode). |

## 4. Umsetzungs-Vorschlag (nach Freigabe)

1. **Template `openclaw.json.j2` erweitern:** `agents.list[].workspace` je Agent rendern (`workspace/<agent_id>`), `agents.list[].tools.allow/deny` für Orchestrator (scharf: deny `exec`, `web_search`, `web_fetch`, `gh`-fähige Tools; allow `read`, `write`, `sessions_*`, `memory_search`), parametrisiert per `group_vars` (`orchestrator_tool_scope: strict|soft` — Fallback schaltbar).
2. **Workspace-Dateien je Agent:** Orchestrator-`AGENTS.md` (Mandat + Roster + Routing) und je Sub-Agent `AGENTS.md`/`SOUL.md` (Rollen aus `docs/workflows/methodology.md` + AGENTS.md-Regeln destilliert — Freigabe Harald, offene Frage 2). Deployment via Ansible-Template (neue Rolle/Task) oder Bootstrap-Injektion.
3. **Output-Contract** als gemeinsame Prompt-Schablone (JSON-Schema im Prompt).
4. **Task-Prompt-Template Design 05** um Completion-Handling erweitern (yield → Timeout-Fallback).
5. **Verifikation:** Nachweis 1 = Pilot mt0 (Baseline, ~90–95 % Selbstarbeit, Issue #82) · Nachweis 2 = Pilot-Wiederholung mit **identischer Task (Issue #29)** auf OC2/OC3 mit neuem Setup → direkter Vorher/Nachher-Vergleich (Kontrollvariable = Task) · Nachweis 3 = Benchmark Design 05 Runden L/M/H (frische Issues, „kein Issue doppelt" bleibt für Benchmark-Runden gültig).

## 5. Alternativen (Methodik Schritt 4 — Abwägung)

| Option | Beschreibung | Verwerfungsgrund / Bewertung |
|---|---|---|
| **A: Nur `delegationMode: prefer`** | Config-Umstellung ohne Prompts/Tools | **Verworfen (empirisch):** T1 = 0 Spawns in 46 Sessions trotz suggest/prefer. Prompt-Guidance allein wirkt nicht (Doku: „prompt guidance only"). |
| **B: Tool-Scoping allein (ohne Prompts)** | Orchestrator ohne Fach-Tools, keine Rollen-Prompts | **Teilweise:** erzwingt Delegation, aber Sub-Agents bleiben leere Hüllen (keine Rollen/Contracts) → Qualität unkontrolliert. Nur als Zwischenschritt denkbar. |
| **C: Config-`prompt`-Feld je Agent** | System-Prompt direkt in `openclaw.json` | **Verworfen (Review Major-1):** Feld in 2026.7.1 nicht nachweisbar (Doku/Schema/Source) → Schema-Validierungsbruch beim Deploy. |
| **D: Per-Agent-Workspace + AGENTS.md (gewählt)** | Native Mechanik: `agents.list[].workspace` + Workspace-Dateien + Tool-Policy | **Gewählt:** dokumentiert, versionierbar im Repo, deploybar via Ansible, testbar (Doku-Check), keine Phantom-Keys. Kombiniert mit Tool-Scoping. |
| **E: Plugin-Hook `before_prompt_build`** | System-Prompt-Mutation per Plugin | **Nicht bevorzugt:** mächtig, aber außerhalb des IaC4-Templates, schwerer reviewbar; bleibt Eskalationsoption. |

## 6. Offene Fragen an Harald — Analyse + Empfehlung

### Q1: Tool-Scoping scharf oder weich?
**Fachliche Auswirkungen:**
- **Scharf** (Orchestrator ohne exec/web_search/web_fetch/gh): Erzwingt Delegation strukturell — einzige nachweislich wirksame Mechanik (T1: 0 Spawns trotz prefer; mt0: Spawns ja, aber 90–95 % Selbstarbeit, weil Tools da waren). Risiko: wenn Spawns ausfallen (T1-Reprise), kann der Orchestrator gar nichts mehr tun → Pre-Check-Gate nötig (Delegations-Smoke-Test vor Runde 1). Konsequenz dokumentieren: Orchestrator kann nichts selbst verifizieren — gewollt.
- **Weich** (nur Prompt-Mandat, Tools bleiben): Geringeres Risiko, aber empirisch wirkungslos in unserem Setup (T1/mt0). LangGraph-Best-Practice: „keep the supervisor tool-free" für pure Orchestrierung.
- **Pragmatischer Kompromiss:** Default **scharf**, aber über `group_vars` (`orchestrator_tool_scope: strict|soft`) pro Runde umschaltbar — Benchmark misst beide Modi (Kovariate!), kein Repo-Eingriff nötig.

**Empfehlung: scharf als Default (strict), Fallback soft per group_var.** Begründung: einzige empirisch belegte Wirkmechanik; LangGraph/Anthropic/OpenAI-Konsens; Fallback hält Risiko klein.

### Q2: Rollen-Prompts aus AGENTS.md/methodology.md destillieren?
**Fachliche Auswirkungen:**
- Ja, Quellen sind da: `docs/workflows/methodology.md` (Schritte 4–6, Sub-Agent-Einsatz-Tabelle, Issue-#37-Signatur-Regel), `AGENTS.md` (Conventional Commits, `set -euo pipefail`, Evidence-Pflicht), `.roo/rules`-Übernahmen (evidence-based-engineering, alternativen-pflicht).
- Wichtig: Destillation ≠ Kopie — auf die 3 Rollen zugeschnitten (Architect: Design/Alternativen/5W; Engineer: Umsetzung/Evidence; Reviewer: Befundformat/Signatur), inkl. „nie dem User antworten" + Output-Contract.
- Deployment über Ansible-Template (Workspace-Dateien) hält sie versionierbar und reviewbar.

**Empfehlung: Ja.** Best Practice (OpenAI: Delegations-Regeln im System-Prompt; Anthropic: isolierte Sub-Agents) + unsere Methodik liefert die Inhalte bereits; Aufwand klein, Wirkung hoch.

### Q3: Umsetzung sofort oder erst Benchmark-L/M/H mit altem Setup?
**Fachliche Auswirkungen:**
- **Erst Baseline L/M/H (alt):** sauberste Wissenschaft (vollständige Baseline vor Intervention), aber: mt0-Pilot existiert bereits als Baseline (Issue #29, alle 3 Instanzen, read-only) → zusätzliche L/M/H-Runde mit altem Setup kostet Zeit + Tokens und liefert wenig Neues (erwartbar: gleiche ~90–95 %-Selbstarbeit, da Setup unverändert). Zudem hängt der Benchmark-Ablauf an Design 05 (PR #81, noch im Review).
- **Sofort umsetzen:** Pilot-Wiederholung mit identischer Task (Issue #29) = direkter Vorher/Nachher-Vergleich mit maximaler Kontrolle (Task konstant). Danach L/M/H mit frischen Issues als Nachweis 3. Risiko: ohne Baseline-L/M/H fehlt eine Verteilungs-Kurve über Schwierigkeitsgrade im Alt-Zustand — kompensierbar, weil mt0 (L) und T1 (alle Klassen, 0 Spawns) die Alt-Verteilung bereits grob belegen.
- **Deploy-Regel:** Umsetzung läuft auf Feature-Branch → Deploy **DEV** (vps-dev) → Pilot dort. Merge main/Deploy prod erst nach Nachweis + Harald-Freigabe (gilt ohnehin).

**Empfehlung: Sofort umsetzen (Branch → Deploy dev → Pilot mit Issue #29 als Kontroll-Task).** Begründung: Baseline existiert (mt0/T1), Doppel-Messung mit altem Setup = verschwendete Runde; Design 05-Review kann parallel laufen.

## 7. Mess-Methode (Review-Befund Major-4)

- **Orchestrator-Anteil:** je Runde aus Session-Transkripten (BP-6-Sicherung): `Tokens_orchestrator / (Tokens_orchestrator + Σ Tokens_subagents)` und `ToolCalls_orchestrator / Σ ToolCalls_alle` — beide Kennzahlen berichten.
- **Ziel:** Orchestrator-Anteil < 40 % (beide Kennzahlen) · ≥ 1 Spawn je Teilaufgabe · 0 abgebrochene Läufe · Artefakt-Disziplin 100 %.
- **Normierung:** Ressourcen-Kovariate V5 (PR #70) je Instanz mitschreiben (CPU/Last), da spawnender Arm mehr verbraucht.
- **Vergleich:** identische Task (Issue #29) vorher (mt0) vs. nachher (Pilot) — Task als Kontrollvariable fix.

## 8. Abhängigkeiten & Reihenfolge

- **Design 05 (PR #81, OPEN):** Benchmark-Ablauf/Methodik für Nachweis 3; nicht blockierend für Pilot (mt0-Ablauf existiert).
- **PR #80 (OPEN):** Token-Datei-Task; relevant erst für Benchmark-Runden mit Write-Zugriff — Pilot bleibt read-only (kein Block).
- **Reihenfolge:** Design-06-Umsetzung (Branch) → Review → Deploy DEV → Pilot (Issue #29, read-only) → Auswertung → ggf. Design 05-L/M/H → Freigabe → main → prod.

## 9. Review-Befunde → Änderungen

| Befund (PR #83) | Eingearbeitet in |
|---|---|
| Major-1: `prompt`-Feld existiert nicht | Kap. 2.5, 4.1, 5 (Option C verworfen) |
| Major-2: Alternativen fehlen | Kap. 5 (neu) |
| Major-3: Abhängigkeit PR #81 | Kap. 8 (neu) |
| Major-4: Mess-Methode fehlt | Kap. 7 (neu) |
| Minor-1: Zahlen inkonsistent | Kap. 1 (harmonisiert) |
| Minor-2: Polling vs. yield | Kap. 3 #5 (yield zuerst, Fallback) |
| Minor-3: Konsequenz Tool-Scoping | Kap. 6 Q1 |
