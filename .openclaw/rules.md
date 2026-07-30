# IaC4 – OpenClaw Rules

Diese Datei wird vom OpenClaw-Framework geladen.
Ergänzt AGENTS.md um framework-spezifische Regeln.

## Tool-Nutzung
- `web_search` vor `web_fetch` bevorzugen (P1)
- `exec` mit Vorsicht: nie Secrets inline exposen
- `gh` CLI vor `curl` für GH API bevorzugen

## Kommunikation
- GitHub-Artefakte als klickbare URLs (nie rohe IDs)
- Issue-Nummern mit Kurztitel (#123 Feature-X, nicht #123)
- Keine Issues für Kleinkram (max 5 aktiv)

## Fehlerkultur
- Fehler passieren → dokumentieren in memory/YYYY-MM-DD.md
- Wiederholungsfehler → Regel in AGENTS.md oder TOOLS.md
- Schwere Fehler (>1h) → zwingend neue Regel
