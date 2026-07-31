# IaC4 Testplan

## Workflow-Reihenfolge (verbindlich, docs/workflows/deploy-stages.md)
- [ ] Workflow 02 (Tailscale-Bootstrap) läuft VOR Workflow 03 (Baseline-Deploy)
- [ ] Workflow 03 ohne vorheriges 02: Abbruch mit Vorbedingungs-Meldung („Workflow 02 zuerst!“)
- [ ] Nach Workflow 02: SSH via Public-IP geschlossen (UFW), via Tailscale offen

## Deployment-Tests (manuell via GH Actions Dispatch)
- [ ] Phase 1: Baseline (SSH, Pakete, Swap)
- [ ] Phase 2a: Tailscale-Join
- [ ] Phase 2b: Docker + Traefik (Traefik Dashboard erreichbar?)
- [ ] Phase 2c: Qdrant (Health-Check: localhost:6333/health)
- [ ] Phase 2c: Code-Server (Login-Seite via Traefik?)
- [ ] Phase 2d: OpenClaw Gateway (Health: localhost:18789/health)

## Integrationstests
- [ ] Qdrant-Collection "embeddings" existiert (3072d, Cosine)
- [ ] OpenClaw kann Memory in Qdrant schreiben/lesen
- [ ] Tailscale-Verbindung vom Runner zum VPS
