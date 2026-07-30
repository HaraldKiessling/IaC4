# 6. Laufzeitsicht

> Nur für kritische Abläufe ausgefüllt.

## Deployment-Ablauf
```
GH Actions Dispatch
  → Runner prüft Ansible-Syntax
  → Verbindung via Tailscale zum VPS
  → Phase 1: Baseline (Pakete, SSH, Tailscale)
  → Phase 2a: Docker + Traefik
  → Phase 2b: Services (Qdrant, CodeServer)
  → Phase 2c: OpenClaw Gateway
  → Post-Deploy-Verifikation: Health-Check
```

## Disaster Recovery
```bash
# Neuen VPS provisionieren (cloud-config.yaml → SSH-Key)
git clone https://github.com/HaraldKiessling/IaC4.git
cd IaC4
make deploy target=prod   # < 10 Minuten
# Qdrant-Volume-Restore für Memory
```
