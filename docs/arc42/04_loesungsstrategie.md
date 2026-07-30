# 4. Lösungsstrategie

## Phasen-Modell
```
Phase 0: cloud-config (VPS-Bootstrap, manuell)
  → SSH via Public-IP 🔓

Phase 1: Ansible Baseline (via Public-IP)
  → System-Update, Pakete, Swap

Phase 2a: Ansible Tailscale-Join (via Public-IP)
  → Tailscale installieren + joinen

Phase 2b: SSH-Restrict (UFW deny 22) 🔒
  → VPS nur noch via Tailscale erreichbar

Phase 2c: Docker + Traefik (via Tailscale)
  → Container-Plattform

Phase 2d: Services (via Tailscale)
  → Qdrant, Code-Server

Phase 2e: OpenClaw Minimal (via Tailscale)
  → Gateway, Memory, WebSearch
  
Phase 3: (Zukunft) OpenClaw-Selbstkonfiguration
  → Nur Laufzeit-Daten (Config in Git)
```

## Zentrale Entscheidungen
| Thema | Entscheidung | Begründung |
|-------|-------------|------------|
| Orchestrierung | Ansible (kein K8s) | Einfach, VPS-tauglich, bewährt |
| Netzwerk | Tailscale + OAuth (tag:ci) | Sicher, GH-Runner ohne manuelle Keys |
| Container | Docker Compose | Ausreichend für VPS |
| Secrets | GH Actions Secrets + .env | Kostenlos, einfach |
| Doku | arc42-light (DE) | Strukturiert, pragmatisch |
| SSH-Transition | Public → Tailscale | Security: öffentliches SSH nur initial |
| VPS-User | `deploy-user` (nicht `openclaw`) | Eindeutige Benennung |
