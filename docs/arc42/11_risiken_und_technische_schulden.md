# 11. Risiken & Technische Schulden

> P6: Keine Workarounds. Was hier steht, wird aktiv verfolgt.

## Technische Schulden
| # | Beschreibung | Priorität | Geplant |
|---|-------------|-----------|---------|
| T-001 | Backup/Disaster-Recovery (Qdrant-Volume) nicht implementiert | Mittel | Nach Phase-2-Stabilisierung |
| T-002 | OpenClaw-Konfiguration manuell (Phase 3 nicht automatisiert) | Niedrig | Nach Option-B-Migration |
| T-003 | Kein Monitoring/Alerting | Niedrig | Später |
| T-004 | Ollama nicht migriert (von IaC3, aktuell ungenutzt) | Niedrig | Entfernen bei IaC4-Migration |
| T-005 | Fehlende API-Secrets (Gemini, OpenRouter) in IaC4 | 🔴 Hoch | Manuell von IaC3 kopieren |

## Risiken
| Risiko | Wahrsch. | Impact | Mitigation |
|--------|----------|--------|------------|
| VPS-Crash | Gering | Hoch | IaC4-Repo + Make deploy (ca. 10 Min) |
| SSH-Lockout bei Tailscale-Ausfall | Sehr gering | 🔴 Hoch | UFW-Fallback-Regel oder IPMI |
| GitHub-Ausfall | Gering | Mittel | Lokales Backup des Repos |
| ADR-010: ACL-Fragmentierung | Mittel | Mittel | Koordinierter ACL-Prozess nötig |
