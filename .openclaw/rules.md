# IaC4 – OpenClaw Regeln

Diese Datei wird vom OpenClaw-Framework geladen.

## Agenten-Rollen
- `.openclaw/agents/orchestrator/` – Nova (Koordination)
- `.openclaw/agents/architect/` – Design-Review
- `.openclaw/agents/engineer/` – Implementierung
- `.openclaw/agents/reviewer/` – Qualitätsprüfung vor Commit

## Arbeitsablauf
```
Orchestrator → Architect (Design-Prüfung) → Engineer (Code) → Reviewer (Prüfung) → Orchestrator (Commit)
```

## Tool-Nutzung
- `web_search` vor `web_fetch` bevorzugen (P1)
- `exec` mit Vorsicht: nie Secrets inline exposen
- `gh` CLI vor `curl` für GH API bevorzugen
- Sub-Agents haben kein `web_search` → Orchestrator liefert Quellen mit

## Kommunikation
- GitHub-Artefakte als klickbare URLs (nie rohe IDs)
- Issue-Nummern mit Kurztitel
- Keine Issues für Kleinkram (max 5 aktiv)
