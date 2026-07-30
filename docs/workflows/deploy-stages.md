# Deployment-Stufen & Branching-Modell

## Branching

```
Feature/BugFix-Branch
       │ PR
       ▼
     DEV (← automatischer Deploy)
       │ PR (grüne CI + DEV-Deploy erforderlich)
       ▼
     MAIN (← nur mit Haralds OK)
       │ workflow_dispatch
       ▼
     PROD (← nur mit Haralds OK)
```

## Deploy-Phasen

| Phase | Playbook | Dauer | Beschreibung |
|-------|----------|-------|-------------|
| 1 | `01-baseline.yml` | < 2 Min | SSH, Pakete, Tailscale-Join |
| 2a | `02-tailscale.yml` | < 1 Min | Tailscale-Auth-Key rotieren |
| 2b | `03-docker-traefik.yml` | < 2 Min | Docker + Traefik Core |
| 2c | `04-services.yml` | < 3 Min | Qdrant, CodeServer |
| 2d | `05-openclaw.yml` | < 3 Min | OpenClaw Gateway |
| 3 | – | Laufzeit | OpenClaw-Selbstkonfiguration (nur Memory/Laufzeit) |

## Deploy-Quellen

| Quelle | Target | Approval |
|--------|--------|----------|
| Feature/BugFix | DEV | ❌ |
| DEV (Branch) | DEV (auto) | ❌ |
| MAIN | DEV (auto) | ❌ |
| MAIN → PROD | PROD | ✅ Harald |

## Quality Gates

Siehe `qa/quality-gates.md`.
