# 11. Risiken & Technische Schulden

> P6: Keine Workarounds. Was hier steht, wird aktiv verfolgt.

## Technische Schulden
| # | Beschreibung | Priorität | Geplant |
|---|-------------|-----------|---------|
| T-001 | Backup/Disaster-Recovery (Qdrant-Volume) nicht implementiert | Mittel | Nach Phase-2-Stabilisierung |
| T-002 | OpenClaw-Konfiguration manuell (Phase 3 nicht automatisiert) | Niedrig | Nach Option-B-Migration |
| T-003 | Kein Monitoring/Alerting | Niedrig | Später |
| T-004 | ~~Ollama nicht migriert~~ → **SUPERSEDED 2026-07-31:** Ollama wird migriert (erster Service, ADR-021..023) | – | – |
| T-005 | Fehlende API-Secrets (Gemini, OpenRouter) in IaC4 | 🔴 Hoch | Manuell von IaC3 kopieren |
| T-006 | ~~Kein Terraform-Backend~~ ✅ Gefixt: GH-Cache für Terraform-State + 03/04 gemergt | 🔴 Erledigt | Workflow-Restrukturierung (ARC42 K8) |
| T-007 | ~~Workflow 01 ignoriert target=prod~~ ✅ Gefixt: target-basierte IP-Wahl wie in 03 | ✅ Erledigt | Nächster PR (ARC42 K8) |
| T-008 | ~~Workflow 03/04-Redundanz~~ ✅ Gefixt: zu 01-tailscale-terraform.yml gemergt | ✅ Erledigt | Merge zu einem Workflow (ARC42 K8) |

## Risiken
| Risiko | Wahrsch. | Impact | Mitigation |
|--------|----------|--------|------------|
| VPS-Crash | Gering | Hoch | IaC4-Repo + Make deploy (ca. 10 Min) |
| SSH-Lockout bei Tailscale-Ausfall | Sehr gering | 🔴 Hoch | UFW-Fallback-Regel oder IPMI |
| GitHub-Ausfall | Gering | Mittel | Lokales Backup des Repos |
| ADR-010: ACL-Fragmentierung | Mittel | Mittel | Koordinierter ACL-Prozess nötig |
| ADR-027: Agent umgeht Telegram-Freigabe (Zugangsdaten als Umgebungsvariablen im Container, `npx`/API-Zugriff, Agent ändert Freigabe-State zwischen Deploys) | Mittel | 🔴 Hoch | Owner-akzeptiert; Plugin `ia4-vault-approval` erkennt Tresor-Zugriffe am Aufruftext (Suche zeigt ohne Freigabe nur Eintragsnamen; Lesen einmal erlauben oder ablehnen, eine Freigabe erlaubt 10 Min. das Lesen genau dieses Eintrags für alle Agenten der Instanz, auch Cron), Skill/Wrapper/Plugin read-only; Rückfall: Eigenbau-Broker (ADR-027 Option B) |
| ADR-027: Tresor-Zugriff aus Cron-Läufen wird blockiert (niemand kann bestätigen), außer auf einen gerade freigegebenen Eintrag; Fehlalarm bei Befehlen mit dem Wort `bw` | Gering | Gering | Tresor nur in Dialogen nutzen; Erkennungsmuster im Plugin anpassen; Rückbau per Workflow 04 mit `bitwarden_secret=delete` |
