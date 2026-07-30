# 12. Glossar

| Begriff | Bedeutung |
|---------|-----------|
| arc42 | Template für Architekturdokumentation |
| **DEV** | Entwicklungs-VPS für autonome Deployments |
| **PROD** | Produktiv-VPS (nur mit Haralds OK) |
| **deploy-user** | VPS-Benutzer (sudo + SSH-Key) |
| **Phase 0** | cloud-config Bootstrap (User, SSH, UFW) |
| **Phase 1** | Ansible Baseline (System, Pakete, Swap) |
| **Phase 2a** | Tailscale-Join (Ansible) |
| **Phase 2b** | SSH-Restrict (UFW deny 22) 🔒 |
| **Phase 2c–e** | Docker, Traefik, Services, OpenClaw |
| **Phase 3** | (Zukunft) OpenClaw-Selbstkonfiguration |
| **SSH-Transition** | Übergang Public-IP SSH → Tailscale-Only |
| **Tailscale** | Mesh-VPN auf Basis von WireGuard |
| **tag:ci** | Tailscale-Tag für CI-Runner (GH Actions) |
| **OAuth-Client** | Tailscale-Client für GH Runner-Authentifizierung |
| **Traefik** | Reverse Proxy mit automatischem LetsEncrypt |
| **Qdrant** | Vektordatenbank für Embeddings |
| **Code-Server** | VS Code als Web-IDE |
| **OpenClaw Gateway** | Orchestrator-Agent für IaC-Automation |
| **P1–P7** | Leitprinzipien (Evidenz, Living Docs, etc.) |
| **GitOps** | Deployment-Status = Repository-Status |
