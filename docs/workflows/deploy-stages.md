# Deployment-Stufen & SSH-Transition

## SSH-Strategie (RFC 0022/0033)

```
Phase 0: cloud-config → SSH via Public-IP 🔓  (Bootstrap, notwendig)
Phase 1: baseline      → System-Grundsetup
Phase 2a: tailscale    → Tailscale-Join
Phase 2b: ssh-restrict → SSH auf Public-IP blockieren 🔒
Phase 2c-e: docker, services, openclaw  → Nur via Tailscale-SSH
```

Nach Phase 2b ist der VPS **nicht mehr über die öffentliche IP erreichbar**.
SSH/Zugriff nur noch via Tailscale (MagicDNS).

## Branching

```
Feature/BugFix-Branch
       │ PR
       ▼
     DEV (← automatischer Deploy via Tailscale)
       │ PR (grüne CI + DEV-Deploy erforderlich)
       ▼
     MAIN (← nur mit Haralds OK)
       │ workflow_dispatch
       ▼
     PROD (← nur mit Haralds OK)
```

## Qualitäts-Gates

Siehe `qa/quality-gates.md`.
