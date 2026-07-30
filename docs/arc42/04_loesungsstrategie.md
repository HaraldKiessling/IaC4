# 4. Lösungsstrategie

## Ansatz
- **Phase 1:** Klassisches Ansible-CLI-Deployment (System-Baseline, Tailscale)
- **Phase 2:** Ansible-Rollen für Docker, Traefik, Services
- **Phase 3:** OpenClaw zur Laufzeit (nur Memory/Sessions – Konfiguration in Git)

## Entscheidungen
| Thema | Entscheidung | Begründung |
|-------|-------------|------------|
| Orchestrierung | Ansible (kein K8s) | Einfach, VPS-tauglich, bewährt |
| Netzwerk | Tailscale + OAuth | Sicher, kein öffentlicher SSH nötig |
| Container | Docker Compose | Ausreichend für VPS |
| Secrets | GH Actions Secrets + .env | Kostenlos, einfach |
| Doku | arc42-light (DE) | Strukturiert, pragmatisch |
