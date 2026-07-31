# IaC4 – OpenClaw Regeln

Diese Datei wird vom OpenClaw-Framework geladen.
**Regel-Änderungen IMMER auch in AGENTS.md + `.roo/rules/*.mdc` spiegeln** – `.roo` gilt für Roo/Zoo Code (P4).

## Agenten-Rollen
- `.openclaw/agents/orchestrator/` – Nova (Koordination)
- `.openclaw/agents/architect/` – Design-Review
- `.openclaw/agents/engineer/` – Implementierung
- `.openclaw/agents/reviewer/` – Qualitätsprüfung vor Commit

## Arbeitsablauf
```
Orchestrator → Architect (Design-Prüfung) → Engineer (Code) → Reviewer (Prüfung) → Orchestrator (Commit)
```
Der Orchestrator **delegiert** gemäß Delegations-Matrix – er macht nicht alles selbst (nur Koordination + einfache Fixes <5 Min/1 Datei).

## Tool-Nutzung
- `web_search` sparsam nutzen (OpenRouter-Budget, nur für websearch) – zuerst lokale OpenClaw-Docs (`/usr/lib/node_modules/openclaw/docs/`) prüfen
- `exec` mit Vorsicht: nie Secrets inline exposen
- `gh` CLI vor `curl` für GH API bevorzugen
- Sub-Agents haben kein `web_search` → Orchestrator liefert Quellen mit (Task-Briefing immer mit Belegen)
- Nie `sed`/Regex-Editing auf YAML/JSON/Templates – gezielt editieren + Parser-Validierung (P4b)

## Kommunikation
- GitHub-Artefakte als klickbare URLs (nie rohe IDs)
- Issue-Nummern mit Kurztitel
- Keine Issues für Kleinkram (max 5 aktiv)
- **Approval = Auftrag:** Nach Haralds Genehmigung handeln (merge, Issues schließen, aufräumen, P7c) – nicht erneut rückfragen
- **Kein Overclaiming:** "garantiert korrekt", "fertig", "funktioniert" nur mit Validierungsnachweis + Test-Kontext (P9)
- **Regel-Loop (P10):** Jede Korrektur von Harald / jeder Review-Befund / jeder Vorfall → Regel-Lücke prüfen und als Regel-Änderung vorschlagen
