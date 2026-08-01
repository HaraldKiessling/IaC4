# Design: OpenClaw-Instanz-Benchmark OC1–OC3 (OC2 vs. OC3, mit OC1-Creator-Baseline)

- **Status:** Vorgeschlagen — Review abgeschlossen: R1 (Architect + Reviewer) eingearbeitet, R2 = ✅ FREIGABE (Reviewer), externer Architect-Review (IaC3-Workspace) = ✅ APPROVE, Befunde N1–N5 eingearbeitet
- **Datum:** 2026-08-01
- **Autor:** ✨ Nova (Orchestrator)
- **Review R1:** 🏗️ Architect (APPROVED MIT BEFUNDEN, 4 MAJOR/7 MINOR) + 🔍 Reviewer (KEINE FREIGABE, 0 Blocker/4 MAJOR/7 MINOR) — Befunde verifiziert und vollständig eingearbeitet (2026-08-01)
- **Bezug:** ADR-025 (Multi-Instanz OC1-OC3), `docs/workflows/methodology.md`, Migrationsplan Phase 5
- **Ziel:** Evidenzbasiertes Design für OC3 („Future Purpose") **und** Vervollständigung von OC2 („DevOps Team"), plus Benchmark-Protokoll für einen kontrollierten Vergleich — **erweitert um OC1 als dritten Arm** (Harald 2026-08-01): Vanilla/Creator-Baseline, testet die These des OpenClaw-Creators (Peter Gyang: „ein einzelner Agent reicht, keine komplexen Orchestratoren").

---

## 1. Ziel & Kontext

Harald (2026-08-01): OC3 bekommt komplett freie Hand für ein neues Modell — **oder** die Community-Evidenz ist so nah an OC2, dass OC3 eine Kopie sein sollte — **oder** OC2 und OC3 werden bewusst unterschiedlich gestaltet, um später im Vergleich ein geeignetes Betriebsmodell zu finden.

**Entscheidung aus Voranalyse (2026-08-01):** Option C — beide Instanzen als kontrolliertes A/B-Experiment gestalten. Begründung:
- Die Community ist **gespalten** in zwei dokumentierte Lager (Orchestrator-Muster vs. Creator-Style), die Doku unterstützt beide. Eine Kopie (Option B) dupliziert Befunde, radikales Neuland (Option A) macht den Vergleich unbrauchbar (zu viele Variablen).
- ADR-025 dokumentiert den Zweck der Multi-Instanz wörtlich als „Untersuchungen".

**Methodik-Transparenz (Review R1):** Der Vergleich ist kein „1-Variable-Experiment" im strengen Sinn — die getestete Variable ist ein **Bündel „Sub-Agent-Betriebskonfiguration"** (Modell-Zuordnung + allowAgents/Rollen-IDs + Delegation/Depth). Dieses Bündel wird bewusst als Einheit getestet (OC2 = Ist-Bündel, OC3 = Best-Practice-Bündel); eine Attribuierung auf einzelne Elemente ist daraus **nicht** ableitbar (Architect MAJOR-2). Alle übrigen Parameter (Infrastruktur, Provider, Secrets, Timeouts, Concurrency, Hardware) werden konstant gehalten.

---

## 2. Ist-Zustand (verifiziert 2026-08-01, main `e3727d0`)

| Instanz | Port | Status | Agents (agents.list) | Primärmodelle |
|---|---|---|---|---|
| OC1 | 18789 | enabled | – (Vanilla) | deepseek |
| OC2 | 18790 | enabled | Orchestrator, Architect, „Engineer Pro", Reviewer | Orchestrator/Engineer: `deepseek-v4-flash`; Architect/Reviewer: `deepseek-v4-pro` |
| OC3 | 18791 | **disabled** | – | deepseek |

Quellen: `ansible/group_vars/vps-dev.yml`, `vps-prod.yml`, `ansible/group_vars/all.yml` (`openclaw_agent_models`), `ansible/roles/openclaw-gateway/templates/openclaw.json.j2`, ADR-025.

**Deployment-Form (ADR-025, Option B):** Docker-Container je Instanz (`ghcr.io/openclaw/openclaw`, gepinnt), Config-Volume `/srv/openclaw/<name>/config` (openclaw.json = SSoT), Workspace-Volume, Ports nur localhost, TLS via Tailscale Serve, Docker-DNS zu Ollama/Qdrant, Memory `qmd` (dateibasiert), Secrets je Instanz als GH-Secrets `<TARGET>_OC<n>_*`.

---

## 3. Befunde am Ist-Zustand (evidenzbasiert)

Die Befunde stammen aus der Config-Analyse (2026-08-01) und den Session-Token-Metriken der letzten 5 Arbeitssessions (31.07.–01.08.). Alle wurden im Review R1 gegen Repo-Stand und lokale Doku verifiziert (siehe Verifikationstabelle in den Review-Berichten).

- **B1 – Modell-Invertierung:** `openclaw_agent_models` setzt Orchestrator/Engineer auf `v4-flash` (billig), Architect/Reviewer auf `v4-pro` (teuer). Die offizielle Doku empfiehlt das Gegenteil — sinngemäß: *„set a cheaper model for sub-agents and keep your main agent on a higher-quality model via `agents.defaults.subagents.model`"* (wörtlich subagents.md Z. 25–27, lokale Installations-Doku 2026-08-01; nicht als wörtliches Zitat aus der Online-Doku belegt). Quelle: [docs.openclaw.ai/tools/subagents](https://docs.openclaw.ai/tools/subagents). ✅ verifiziert (all.yml + subagents.md).
- **B2 – Rollen nur als Prompt, nicht als Agent-IDs (im Analysefenster):** Die realen Sub-Agent-Spawns **im Analysefenster 31.07.–01.08.** liefen alle unter `agentId: orchestrator` (Session-Metadaten). Außerhalb des Fensters (26./29.07.) gab es reale Spawns mit explizitem `agentId: engineer-pro` (Trajectory `5df54eda`, Sessions unter `~/.openclaw/agents/engineer-pro/`) — die Formulierung gilt also **nur für das Analysefenster** (Reviewer MINOR-5). `subagents.allowAgents` ist nicht gesetzt → Default erlaubt nur den Requester-Agent selbst; Spawns mit expliziter Agent-ID sind aktuell blockiert. Die Rollen-Trennung existiert faktisch nur im Task-Prompt.
- **B3 – Orchestrator-Pattern ungenutzt:** `maxSpawnDepth`, `delegationMode`, `maxConcurrent`, `runTimeoutSeconds` sind nirgends konfiguriert (Default: Depth 1, suggest, 8, 0). Der dokumentierte Orchestrator-Pattern (Depth 2) ist damit nicht aktiv. Quelle: [docs.openclaw.ai/tools/subagents](https://docs.openclaw.ai/tools/subagents). ✅ verifiziert (Template hat keinen `subagents`-Key).
- **B4 – Worktree-Isolation selbst gebaut:** Worktree-Handling via eigenem `iac4-worktree-init.sh` (außerhalb des Repos, Session-Arbeitsbereich `~/.openclaw/workspace/scripts/`; Issue #29, Kollisionen real passiert). OpenClaw bietet native **Managed Worktrees** (Branch `openclaw/<name>`, automatische Snapshots, Restore, Hourly-Cleanup, `.worktreeinclude`, `.openclaw/worktree-setup.sh`). Quelle: [docs.openclaw.ai/concepts/managed-worktrees](https://docs.openclaw.ai/concepts/managed-worktrees). ✅ verifiziert.
- **B5 – Kein ACP:** Externe Coding-Harnesses (Claude Code, Codex, Gemini CLI via `@openclaw/acpx`) sind nicht eingerichtet — für schweren Repo-Code der dokumentierte Weg. Quelle: [docs.openclaw.ai/tools/acp-agents](https://docs.openclaw.ai/tools/acp-agents). ✅ verifiziert (Template ohne acp).
- **B6 – Keine Sub-Agent-Tool-Policy:** `tools.subagents` nicht konfiguriert; Doku-Default-Deny (`gateway`, `cron`) ist implizit aktiv, aber nicht explizit dokumentiert. Community-Empfehlung: Deny-Listen + Sandbox für untrusted Agents (amankhan1-Setup-Guide; [GitHub Issue #10010](https://github.com/openclaw/openclaw/issues/10010) als Feature-Request „Agent Teams – Parallel Agent Coordination" — **kein** Scaling-Best-Practices-Beleg, siehe Review R1 MAJOR-4).
- **B7 – Token-Last asymmetrisch (Hypothese):** Orchestrator trägt 82–97% der frischen Tokens pro Session. **Basis:** Summe `input+output` (ohne `cacheRead`/`cacheWrite` — `totalTokens` = input+output+cacheRead+cacheWrite, verifiziert am Session-JSONL; Reviewer MINOR-6). **Kausalaussage als Hypothese gekennzeichnet** (Architect MINOR-5): Thread-Kontext-Nachladen (Cache-Wachstum) + Implementierung im Thread statt Delegation sind plausible Erklärungen, aber aus Token-Metriken nicht beweisbar. `delegationMode: prefer` (Doku: „stay responsive and delegate anything more involved") würde Delegation aktiv fördern.

**Empirische Basis der Metriken:** Session-Transkripte `~/.openclaw/agents/orchestrator/sessions/*.jsonl` (usage je Assistant-Turn), ausgewertet 2026-08-01 (Sessions: IAC4-Architekturplanung, Zoo-Code-Tipps/10 PRs, VPS dev frisch, Main).

---

## 4. Design OC3 — „Best-Practice-Referenz" (vollständig)

### 4.1 Anforderungen
1. Vollständig Doku-konformes Agent-Modell (subagents.md, multi-agent.md)
2. Echte Rollen-Identitäten (Agent-IDs statt Prompt-only) — adressiert B2
3. Kosten-/Qualitäts-Balance — adressiert B1, B7
4. Sicher: Secrets nur via Env, keine Klartext-Tokens in Dateien (Gates: methodology.md Schritt 6)
5. Idempotent deploybar über bestehende Rolle (ADR-025) — kein neuer Infrastruktur-Pfad
6. Messbar: alle Benchmark-Metriken (Kap. 6) auswertbar
7. **Isolation von OC1/OC2 (Review R1, Reviewer MAJOR-2):** Die Template-Erweiterung muss **strikt per-Instanz** wirken — OC1 (Vanilla-Baseline) und OC2 (Kontrollgruppe) dürfen durch OC3-Defaults **nicht** verändert werden. Mechanismus: Instanz-Variablen `oc.subagents_defaults` / `oc.agent_models` mit Default = heutiges Verhalten; kein globales `agents.defaults.subagents`-Rendern ohne Instanz-Conditional.

### 4.2 Alternativen

**A3-1: Creator-Style (Anti-Orchestrator)** — Single-Agent, keine Rollen, keine agents.list, Sub-Agents sparsam (Vorbild: Peter Gyang, [LinkedIn](https://www.linkedin.com/posts/petergyang_peter-openclaw-creators-ai-coding-workflow-activity-7423802347858092032-gJgH)).
- Pro: minimal, billig, entspricht der persönlichen Empfehlung des OpenClaw-Creators.
- Contra: Einzelmeinung gegen Mehrheits-Evidenz; für IaC4-Größe (Review-Gate, Autor≠Reviewer, Issue #37) ist mindestens eine Rollen-Trennung nötig; Vergleich mit OC2 hätte 2+ Variablen (Struktur UND Modell).
- **Bewertung: verworfen für OC3** (zu großer Sprung, Sicherheits-Gate „Autor ≠ Reviewer" nicht abbildbar). Als mögliche OC1-Nachfolge notiert (OC1 = Vanilla-Baseline bleibt unverändert).

**A3-2: Peer-Spezialisten mit eigenen Channels** — 4 unabhängige Agents, je eigener Telegram-Bot/Channel-Binding (Vorbild: Claire Vo/Lenny: „nine agents", [Lenny's Newsletter](https://www.lennysnewsletter.com/p/openclaw-the-complete-guide-to-building); [docs.openclaw.ai/concepts/multi-agent](https://docs.openclaw.ai/concepts/multi-agent)).
- Pro: dokumentiertes Muster (Bindings, isolierte Workspaces), klare Trennung.
- Contra: 4 zusätzliche Telegram-Bots je Target (Secret-/Wartungsaufwand); Koordination bleibt LLM-Entscheidung statt deterministischer Pipeline — für ein Repo mit fester Methodik (Schritt 4→5→6) ungeeignet (dev.to: deterministische Pipelines ohne LLM-Routing schlagen Ad-hoc-Koordination).
- **Bewertung: verworfen für OC3** — Passt zu Multi-Personen-/Multi-Kanal-Betrieb, nicht zu einem Single-Repo-Workflow.

**A3-3: Orchestrator-Pattern nach Doku (EMPFEHLUNG)** — Qualitäts-Orchestrator + billige Rollen-Sub-Agents als echte Agent-IDs, Depth-2-Delegation, Delegation-Preferenz.
- Pro: deckt sich mit der **offiziellen Doku** (maxSpawnDepth 2 = dokumentierter Orchestrator-Pattern; subagents.model-Empfehlung; delegationMode prefer) und mit unserer IaC4-Methodik (Schritt 4–6); die Community-Belege sind ergänzend (deterministische Pipelines: [dev.to](https://dev.to/ggondim/how-i-built-a-deterministic-multi-agent-dev-pipeline-inside-openclaw-and-contributed-a-missing-4ool) — **Vorsicht:** der Artikel argumentiert für deterministische YAML-Pipelines ohne LLM-Routing und belegt damit die **Pipeline-Struktur** unserer Methodik, nicht die Sub-Agent-Hierarchie; die Hierarchie selbst trägt die offizielle Doku, Review R1 MAJOR-4).
- Contra: Orchestrierung = Komplexität (Creator-Gegenstimme); Template-Erweiterung nötig (openclaw.json.j2, per-Instanz).
- **Bewertung: gewählt** — einzige Alternative, die alle Anforderungen (inkl. Anforderung 7) erfüllt.

### 4.3 Empfehlung OC3 (Config-Delta)

```yaml
# group_vars/vps-dev.yml (und vps-prod.yml) – openclaw_instances:
- name: oc3
  enabled: true          # bisher false (Rollback-Hinweis: siehe 4.4!)
  port: 18791
  label: "OC3 – Best-Practice-Referenz (Benchmark)"
  llm_provider: deepseek
  websearch_api_key_env: "DEV_OC3_WEBSEARCH_API_KEY"
  gateway_token_env: "DEV_OC3_GATEWAY_TOKEN"
  telegram_bot_token_env: "DEV_OC3_TELEGRAM_BOT_TOKEN"
  agents: [Orchestrator, Architect, "Engineer Pro", Reviewer]
  # NEU (Template-Erweiterung, per-Instanz):
  subagents_defaults:                 # nur für diese Instanz gerendert (Anforderung 7)
    delegationMode: "prefer"
    maxSpawnDepth: 2
    maxChildrenPerAgent: 5
    maxConcurrent: 4
    runTimeoutSeconds: 900
  agent_models:                       # Instanz-Override, nur für diese Instanz gerendert
    Orchestrator: { primary: "deepseek/deepseek-v4-pro",    fallbacks: ["deepseek/deepseek-v4-flash", "google/gemini-3.5-flash"] }
    Architect:    { primary: "deepseek/deepseek-v4-flash",  fallbacks: ["deepseek/deepseek-v4-pro"] }
    "Engineer Pro": { primary: "deepseek/deepseek-v4-flash", fallbacks: ["deepseek/deepseek-v4-pro"] }
    Reviewer:     { primary: "deepseek/deepseek-v4-flash",  fallbacks: ["deepseek/deepseek-v4-pro"] }
```

```json5
// openclaw.json.j2 – gerendert NUR wenn oc.subagents_defaults gesetzt (per-Instanz-Conditional):
// agents.defaults.subagents.*  ← aus oc.subagents_defaults
// agents.list[]                 ← aus oc.agents + oc.agent_models (Override je Instanz)
// agents.list[orchestrator].subagents.allowAgents: ["orchestrator","architect","engineer-pro","reviewer"]
// tools.subagents.tools.deny: ["cron","gateway"]   (Doku-Default, explizit)
```

**Depth-2-Ablauf (Review R1, Architect MINOR-1) — beabsichtigtes Muster:** Da der Main-Agent selbst der Orchestrator ist, greift `maxSpawnDepth: 2` im **Self-Spawn-Muster**: Main (Depth 0) spawnt Orchestrator-Sub-Agent (Depth 1, bekommt durch Depth≥2 die Session-Tools), der die Spezialisten (Depth 2) spawnt. Alternativ delegiert der Main direkt an Spezialisten (Depth 1) — dann bleibt Depth 2 ungenutzt, aber funktional korrekt. **Beide Lesarten sind mit der Config gültig; der Orchestrator wird per Prompt auf das Self-Spawn-Muster für große Tasks festgelegt** (Doku: Depth-2-Orchestrator aggregiert Kinder und berichtet an Main).

**Template-Arbeit (Folge-Task nach Freigabe, Pflicht aus Review R1):** `openclaw.json.j2` um per-Instanz-`subagents_defaults`/`agent_models` (Conditional, Default = heutiges Verhalten — **OC1/OC2 bleiben byte-identisch gerendert**) + `allowAgents` + `tools.subagents.deny` erweitern; Render-Validierung (`scripts/validate-openclaw-templates.py`) anpassen; BDD-Check erweitern (OC3-Health, OC1/OC2-Config unverändert). Kein neuer Rollen-Code nötig — die Rolle loopt bereits über `openclaw_instances`.

### 4.4 Worst-Case & Rollback (P3, AGENTS.md)
- **Worst-Case 1:** Delegation bricht (Depth-2-Fehler) → Orchestrator liefert nichts mehr, weil er alles delegiert und Kinder fehlschlagen. **Gegenmaßnahme:** `delegationMode` zurück auf `suggest`, `maxSpawnDepth` auf 1 (Config-Änderung, Deploy) — kein Container-Neuaufbau.
- **Worst-Case 2:** Modell-Override inkonsistent (Instanz-Override vs. all.yml) → falsche Modelle deployt. **Gegenmaßnahme:** Render-Validierung im CI (bestehendes Skript) + BDD-Check `openclaw.bdd.ps1` (Health je Instanz).
- **Worst-Case 3:** Template-Regression trifft OC1/OC2 (Anforderung 7 verletzt). **Gegenmaßnahme:** CI-Renderdiff (OC1/OC2-Output vorher/nachher muss identisch sein) als Pflicht-Check im Folge-Task.
- **Rollback-Pfad (korrigiert nach Review R1, Reviewer MAJOR-3):** `enabled: false` **entfernt den Container NICHT** — `tasks/main.yml` skippt die Instanz nur (`when: oc.enabled | default(false)`), es gibt **keinen Teardown-Task** im Repo. Rollback = **manuell** `docker compose -f /srv/openclaw/oc3/docker-compose.yml down` (Config-Volume bleibt erhalten → Re-Enable = alter Zustand). Optional: Teardown-Task in der Rolle als Folge-Task. Kein Prod-Risiko: OC3 läuft nur auf DEV-Target bis Benchmark-Abschluss (PROD-OC3 bleibt disabled).

---

## 5. Design OC2 — Vervollständigung („DevOps Team", Ist + dokumentierte Lücken)

### 5.1 Anforderungen
1. OC2 bleibt **Kontrollgruppe**: Struktur unverändert (Orchestrator/Architect/Engineer/Reviewer als agents.list, Modelle wie Ist-Zustand)
2. Aber: vollständige, dokumentierte Config — aktuell fehlen explizite Werte für Doku-Features (B3, B6)
3. Reproduzierbar und nachvollziehbar („Ist-Zustand eingefroren und dokumentiert")

### 5.2 Alternativen

**A2-1: OC2 komplett unangetastet lassen (nur Doku des Ist-Zustands).**
- Pro: maximale Kontrollgruppen-Reinheit.
- Contra: Timeout-/Concurrency-Defaults (0/8 laut Doku) blieben **Kovariaten** — ein OC3-Task, der >15 Min. läuft oder parallel skaliert, wäre nicht mit OC2 vergleichbar. Der Benchmark hätte eine unkontrollierte zweite Variable.
- **Bewertung: Basis, aber unvollständig.**

**A2-2: OC2 minimal vervollständigen (EMPFEHLUNG) — „Ist-Zustand + konstant gehaltene Rahmenparameter".**
- **Wichtig (Review R1, beide Reviewer MAJOR-1):** Das Delta ist **keine** „Explizitmachung von Doku-Defaults" — zwei Werte weichen bewusst vom Doku-Default ab: `maxConcurrent: 4` (Doku-Default **8**) und `runTimeoutSeconds: 900` (Doku-Default **0 = kein Timeout**). Das ist eine **bewusste Konstant-Haltung**: identische Rahmenbedingungen auf beiden Instanzen, damit Timeout/Concurrency keine Variablen sind. Die Abweichung wird im Benchmark-Bericht ausgewiesen; alternative Variante (Doku-Defaults 8/0 auf OC2) bleibt als Sensitivitäts-Check möglich.
- Explizit setzen: `delegationMode: "suggest"` (Doku-Default), `maxSpawnDepth: 1` (Doku-Default), `maxChildrenPerAgent: 5`, plus die o.g. Konstanten.
- Modelle **unverändert** lassen (Orchestrator/Engineer = flash, Architect/Reviewer = pro) — das IST die Kontrollgruppe; die Invertierung (B1) ist Teil des Vergleichs, nicht der Fix.
- `allowAgents` bleibt ungesetzt (heutiges Verhalten: nur Requester-Agent) — dokumentiert als bewusste Kontrollgruppen-Eigenschaft (B2 bleibt im Vergleich sichtbar).
- Pro: reproduzierbare Kontrollgruppe, gleiche Timeout-/Concurrency-Bedingungen wie OC3, nur die getesteten Variablen unterscheiden sich.
- Contra: verlangt dieselbe per-Instanz-Template-Erweiterung wie OC3 (einmalige Arbeit, dann beide Instanzen bedienbar).
- **Bewertung: gewählt.**

**A2-3: OC2 auf Best-Practice nachrüsten (gleiche Deltas wie OC3).**
- Pro: schnell „perfekt".
- Contra: zerstört die Kontrollgruppe — dann gibt es keinen Vergleich mehr, nur noch zwei ähnliche Instanzen.
- **Bewertung: verworfen** (widerspricht dem Benchmark-Ziel; kann nach dem Vergleich als Gewinner-Konfiguration übernommen werden).

### 5.3 Empfehlung OC2 (Config-Delta)

```yaml
# group_vars/vps-dev.yml – openclaw_instances, OC2-Eintrag erweitert (per-Instanz, Default-Verhalten für OC1 unverändert):
- name: oc2
  enabled: true
  port: 18790
  label: "OC2 – DevOps Team (4 Agents) [Benchmark-Kontrollgruppe]"
  llm_provider: deepseek
  websearch_api_key_env: "DEV_OC2_WEBSEARCH_API_KEY"
  gateway_token_env: "DEV_OC2_GATEWAY_TOKEN"
  telegram_bot_token_env: "DEV_OC2_TELEGRAM_BOT_TOKEN"
  agents: [Orchestrator, Architect, "Engineer Pro", Reviewer]
  subagents_defaults:                 # Konstant-Haltung, KEINE Doku-Defaults (s. 5.2 A2-2)
    delegationMode: "suggest"         # Doku-Default, explizit
    maxSpawnDepth: 1                  # Doku-Default, explizit
    maxChildrenPerAgent: 5            # Doku-Default
    maxConcurrent: 4                  # bewusst ≠ Doku-Default 8 (Konstante)
    runTimeoutSeconds: 900            # bewusst ≠ Doku-Default 0 (Konstante)
  # agent_models: NICHT setzen → erbt all.yml (Ist-Zustand unverändert)
```

### 5.4 Worst-Case & Rollback
- **Worst-Case:** Template-Änderung bricht OC2-Deploy → beide Instanzen betroffen. **Gegenmaßnahme:** Template-Erweiterung strikt additiv + per-Instanz (Default = heutiges Verhalten), Render-Validierung + BDD vor Deploy; Rollback = alten Pin zurück.
- **Rollback:** Config-Volume `/srv/openclaw/oc2/config` ist SSoT; ein Deploy mit alter Template-Version stellt den Ist-Zustand wieder her (ADR-025: Reinstall = Volume neu). `enabled: false` entfernt den Container nicht (s. 4.4).

---

## 6. Benchmark-Protokoll (A/B, kontrolliert)

### 6.1 Design (3 Arme — OC1-Baseline ergänzt, Harald 2026-08-01)
- **Getestete Variable (Bündel, s. Kap. 1):** Sub-Agent-Betriebskonfiguration (Modell-Zuordnung, allowAgents/Rollen-IDs, Delegation/Depth, Vorhandensein von Rollen-Agents).
- **Die 3 Arme (dokumentierte Community-Positionen):**
  - **OC1 – Creator/Vanilla-Baseline:** kein `agents.list` (Single-Agent), `suggest`/Depth-1, keine Rollen-IDs (Peter-Gyang-These). Konstanten identisch zu OC2/OC3 (s. u.).
  - **OC2 – DevOps-Team (Ist, Kontrollgruppe):** 4 Rollen-Agents, `suggest`/Depth-1, keine `allowAgents`.
  - **OC3 – Best-Practice-Referenz:** 4 Rollen-Agents, `prefer`/Depth-2, `allowAgents` + Modell-Invertierung.
  - **Variablen-Paare:** OC1↔OC2 = „Single-Agent vs. Rollen-Team" (bei sonst identischer Sub-Agent-Config); OC2↔OC3 = „Delegation/Depth/Modelle" (bei identischer Team-Struktur). OC1↔OC3 = kombinierter Unterschied.
- **Konstant gehalten (alle 3 Arme):** LLM-Provider (deepseek), Infrastruktur (Docker-Rolle), Secrets-Konvention, Workflow, BDD-Suite, VPS-Hardware, Timeouts (900 s), Concurrency (4), maxChildrenPerAgent (5) — **OC1 erhält dafür explizit dieselben `subagents_defaults` wie OC2** (suggest/1/5/4/900), damit Timeout/Concurrency keine Variable zwischen den Armen sind (bewusste Abweichung vom Doku-Default 8/0, dokumentiert wie OC2).
- **Dauer:** 14 Tage paralleler DEV-Betrieb (ab Freigabe), Auswertung danach.
- **Blindheit (realistisch, Review R1):** Echte Blindheit ist bei Live-PR-Kommentaren nicht herstellbar (GitHub-Metadaten + Stil verraten die Instanz). Stattdessen: **Outputs instanzfremd erfassen** (getrennte Dateien ohne Instanz-Kennzeichnung), Adjudikation durch Harald anhand definierter Ground Truth, Auswertung deskriptiv (s. 6.4). Keine „Blindheit"-Behauptung im Protokoll.
- **Ressourcen-Interferenz (Architect MINOR-4):** Beide Instanzen parallel auf 6 vCore/8 GB verrauschen Zykluszeit-Metriken → Tasks **zeitlich entzerren** (nicht gleichzeitig starten) + `docker stats` als Kovariate im Log.

### 6.2 Aufgaben (identisch je Instanz OC1/OC2/OC3, rotierend, Worktree-Pflicht je Instanz — Issue #29)
1. **T1 – PR-Review (Kern-Test):** **Diff-Snapshot als Datei** je Instanz ausrollen (nicht der Live-PR — beide Reviewer sehen sich sonst gegenseitig, Kontamination; Reviewer MAJOR-4). Seed-Defekte (bewusst eingebaute Fehler) als Ground Truth; Reviewer-Outputs in getrennten Dateien ablegen, Reihenfolge rotieren. Adjudikation: Harald oder Zweit-Reviewer gegen Ground-Truth-Liste.
2. **T2 – Architektur-Review:** gleiche ADR/Design-Frage (5W) durch Architect; Ground Truth = Konsens-Urteil aus IaC4-Methodik.
3. **T3 – Implementierung:** gleiche, klar spezifizierte Aufgabe (z.B. „BDD-Fix nach Spezifikation") — **je Instanz getrennter Worktree/Branch** (Kollisionsgefahr, Issue #29); Ergebnis = Diff + Testlauf.
4. **T4 – Such-/Recherche-Aufgabe:** gleiche Web-Recherche (Evidenzpflicht) — testet Tool-Nutzung; Ground Truth = Quellenqualität (offizielle Doku/Vendor-Docs).

### 6.3 Metriken (je Instanz)
| Metrik | Quelle | Hinweis (Review R1) |
|---|---|---|
| Frische Tokens (Input+Output, ohne Cache) | Session-usage je Turn (`totalTokens = input+output+cacheRead+cacheWrite`, verifiziert) | **Basis für Kostenvergleich** — Kosten-Metrik aktuell nicht erhebbar |
| Kosten (USD) | `usage.cost` | ⚠️ liefert aktuell **0** (keine Preis-Metadaten in `openclaw_provider_models`/Template). **Folge-Task:** Preis-Config ergänzen (Konstante dokumentieren) ODER Metrik auf Token beschränken. Bis dahin: Token-Metriken |
| Zykluszeit (Task-Start→Fertig) | Session-Timestamps + Task-Log | entzerrt starten (6.1) |
| Review-Qualität (echte Blocker/Nits/Fehlalarme) | T1-Outputs vs. Ground Truth | Adjudikation Harald |
| Delegationsrate (Sub-Agent-Turns / Gesamt-Turns) | Session-Metadaten | B7-Check |
| Erfolgsrate (Task ok / gesamt) | **Task-Log** (geführt vom Ausführenden/Harald) — Session-JSONL hat **kein** Completion-Status-Feld (Reviewer MINOR-3) | Quelle explizit führen |

### 6.4 Entscheidungskriterien (vorab festgelegt; deskriptiv, Review R1 MAJOR-3)
**Kein Signifikanztest bei n=5** — der Schwellwert ist ein pragmatisches Abbruch-/Präferenzkriterium, kein statistischer Beleg. Auswertung deskriptiv; bei Bedarf n≥10 T1-Läufe als Verlängerung.
1. **Qualität gewinnt über Kosten:** Instanz mit mehr echten Blockern (≥2 Differenz über ≥5 T1-Läufe, adjudiziert gegen Ground Truth) wird bevorzugt. **Paarweise Rangfolge OC1/OC2/OC3** (jeder gegen jeden), dann Gesamt-Ranking.
2. Bei Qualitäts-Gleichstand: günstigere Instanz (frische Tokens).
3. Bei Gleichstand in 1+2: Zykluszeit.
4. **T2–T4 fließen als Zusatzbefunde ein** (nicht in die Rangfolge; dokumentiert pro Task) — Review R1 MINOR-4.
5. **OC1-Sonderfall:** Gewinnt die Vanilla-Baseline (OC1) — bestätigt die Creator-These empirisch; dann wird bewertet, ob der Mehraufwand von OC2/OC3 (Rollen, Depth) durch Qualitätsgewinn gerechtfertigt ist (Entscheidung Harald).
6. **Abbruchkriterium:** Eine Instanz scheitert in 3 aufeinanderfolgenden T1-Läufen schwer (Delegation/Depth-Fehler, unbrauchbare Outputs) → Instanz pausieren, Befund dokumentieren.

### 6.5 Auswertung & Übergang
- Ergebnis → Entscheidung Harald → Gewinner-Konfiguration auf Produktiv-Instanz übernehmen (PROD-OC1/OC2/OC3 je nach Ausgang), Verlierer-Instanzen als Fallback (`enabled: false` + manueller Teardown, s. 4.4).
- Gap-Report (Methodik Schritt 8) als Issue/PR-Doku.

---

## 7. Offene Fragen an Harald

1. **OC3-Secrets (Stand 2026-08-01 15:40 UTC — korrigiert nach Review R1):** `DEV_OC3_GATEWAY_TOKEN`, `DEV_OC3_WEBSEARCH_API_KEY`, `DEV_OC3_TELEGRAM_BOT_TOKEN` **existieren bereits** (verifiziert via `gh secret list`). Offen: Telegram-Bot für OC3 validieren (BotFather-Token-Test). Hinweis: `DEV_OC3_GATEWAY_TOKEN` ist **Deploy-Pflicht** (hartes `assert` in `instance.yml`), nicht optional.
2. **Template-Erweiterung** (per-Instanz-`subagents_defaults`/`agent_models`, Render-Validierung, BDD, Preis-Config, optional Teardown-Task): als separates PR nach Design-Freigabe — Empfehlung bestätigt? (Review R1: deckt sich mit MINOR-6 „Operationalisierung".)
3. **PROD-OC3** bleibt bis Benchmark-Abschluss `enabled: false` — bestätigt?
4. **VPS-Ressourcen:** 3 Gateways parallel auf DEV (6 vCore/8 GB). Empfehlung (Review R1 MINOR-4): OC3-Start erst nach OC1/OC2-Health-Check, Tasks zeitlich entzerrt, `docker stats` im BDD-Log als Kovariate. OK?
5. **Ground Truth T1:** Seed-Defekte (bewusst eingebaute Fehler in Diff-Snapshots) ok — oder adjudiziert Harald echte PRs nachträglich? (Aufwand: Seed-Defekte = 30 Min. Setup, sauberere Metrik.)

---

## 8. Referenzen & Evidenz

**Offizielle Doku (verifiziert 2026-08-01 gegen die lokale Installations-Doku der laufenden OpenClaw-Instanz unter `/usr/lib/node_modules/openclaw/docs/` — nicht Bestandteil des Repos; identische Inhalte online unter [docs.openclaw.ai](https://docs.openclaw.ai)):**
- [tools/subagents.md](https://docs.openclaw.ai/tools/subagents) — Sub-Agent-Modelle („cheaper model for sub-agents"), delegationMode (suggest/prefer), maxSpawnDepth 2 = Orchestrator-Pattern, maxChildrenPerAgent (Default 5) / maxConcurrent (Default 8), runTimeoutSeconds (Default 0), announce chain, isolated/fork, tools.subagents-Policy (deny gateway/cron), allowAgents (Default: nur Requester)
- [concepts/managed-worktrees.md](https://docs.openclaw.ai/concepts/managed-worktrees) — native Worktrees, Snapshots, Restore, Cleanup, .worktreeinclude
- [tools/acp-agents.md](https://docs.openclaw.ai/tools/acp-agents) — ACP-Harnesses (claude/codex/gemini/opencode), @openclaw/acpx
- [concepts/multi-agent.md](https://docs.openclaw.ai/concepts/multi-agent) — isolierte Agents, Bindings, Workspaces
- [ci.md](https://docs.openclaw.ai/ci) — CI-Gates (preflight, security-fast)

**Community (abgerufen 2026-08-01; Zitate nach Review R1 korrigiert):**
- [dev.to: Deterministic multi-agent dev pipeline](https://dev.to/ggondim/how-i-built-a-deterministic-multi-agent-dev-pipeline-inside-openclaw-and-contributed-a-missing-4ool) — deterministische Pipelines **ohne LLM-Routing** (Beleg für Methodik-Pipeline-Struktur, nicht für Sub-Agent-Hierarchie)
- [GitHub Issue #10010](https://github.com/openclaw/openclaw/issues/10010) — Feature-Request „Agent Teams – Parallel Agent Coordination" (Kontext zu Team-Konzepten; **kein** Best-Practices-Beleg)
- [Lenny's Newsletter (Claire Vo)](https://www.lennysnewsletter.com/p/openclaw-the-complete-guide-to-building) — Peer-Multi-Agent-Muster, Security (loopback, token auth)
- [amankhan1 Substack](https://amankhan1.substack.com/p/how-to-make-your-openclaw-agent-useful) — Security-Hardening, Workspace-Dateien, Deny-Prinzip
- [Peter Gyang (Creator)](https://www.linkedin.com/posts/petergyang_peter-openclaw-creators-ai-coding-workflow-activity-7423802347858092032-gJgH) — Gegenstimme: kein komplexer Orchestrator
- (Entfernt nach Review R1 MAJOR-4: GitHub Discussion #10036 — 404; „Scaling-Best-Practices <5KB"-Beleg — nicht verifizierbar)

**IaC4-intern:**
- ADR-025 (Multi-Instanz, Docker; Rollback-Semantik `enabled`-Flag geprüft: kein Teardown-Task), methodology.md (Schritt 4–6, Autor≠Reviewer), group_vars (Ist-Config), `ansible/roles/openclaw-gateway/tasks/main.yml` (when: oc.enabled), Session-Token-Metriken (2026-07-31/08-01), `~/.openclaw/workspace/TOOLS.md` (außerhalb des Repos; Lessons: Worktree-Isolation Issue #29, Exec-Hygiene)

## Review-Protokoll R1 (2026-08-01)
- 🏗️ Architect: APPROVED MIT BEFUNDEN — 4 MAJOR (Kontrollgruppen-Definition, Variablen-Bündel, Statistik/Blindheit/Ground Truth, Community-Zitate) + 7 MINOR — alle eingearbeitet (Kap. 1, 3, 4.2–4.4, 6.1–6.4, 8)
- 🔍 Reviewer: KEINE FREIGABE (keine Blocker) — 4 MAJOR (OC2-Delta ≠ Doku-Defaults, Template-Isolation, Rollback-Pfad `enabled:false`, T1-Kontamination) + 7 MINOR — alle eingearbeitet (Kap. 4.3–4.4, 5.2–5.4, 6.1–6.3, 7)
- Re-Review: ausstehend (nach Einarbeitung)
