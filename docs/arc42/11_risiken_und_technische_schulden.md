# 11. Risiken & Technische Schulden

> P6: Keine Workarounds. Was hier steht, wird aktiv verfolgt.

## Technische Schulden
| # | Beschreibung | Priorität | Geplant |
|---|-------------|-----------|---------|
| T-001 | Backup/Disaster-Recovery nicht implementiert | Mittel | Nach Phase-1-Stabilisierung |
| T-002 | OpenClaw-Konfiguration manuell (Phase 3 nicht automatisiert) | Niedrig | Nach Option-B-Migration |
| T-003 | Kein Monitoring/Alerting | Niedrig | Später |
| T-004 | Ollama installiert aber ungenutzt (von IaC3) | Niedrig | Entfernen bei IaC4-Migration |

## Risiken
| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|-------------------|--------|------------|
| VPS-Crash | Gering | Hoch | IaC4-Repo + Make deploy |
| GitHub-Ausfall | Gering | Mittel | Lokales Backup des Repos |
| Tailscale-Ausfall | Sehr gering | Hoch | SSH-Fallback-Key auf VPS |
