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
| **Traefik** | Reverse Proxy, HTTP-only (Port 80), HTTPS via Tailscale Serve (ADR-018) |
| **Qdrant** | Vektordatenbank für Embeddings |
| **Code-Server** | VS Code als Web-IDE |
| **OpenClaw Gateway** | Orchestrator-Agent für IaC-Automation |
| **OC-Instanz** | Eine von drei OpenClaw-Gateway-Instanzen (oc1–oc3) je VPS, also sechs über DEV und PROD |
| **Betriebs-Secret** | Geheimnis, das IaC4 beim Deploy einer Instanz mitgibt (API-Key, Token); Quelle sind GH Secrets |
| **Agenten-Zugangsdaten** | Logins, mit denen sich ein Agent zur Laufzeit selbst bei einem Dienst anmeldet (z. B. ein Bankportal); liegen im Agenten-Tresor, nie in GH Secrets |
| **Agenten-Tresor** | Eigenes Bitwarden-Konto nur für die OC-Instanzen; alle Instanzen (DEV und PROD) sehen dieselben Einträge |
| **Freigabe** | Haralds Bestätigung per Telegram-Knopf, bevor ein Agent auf den Agenten-Tresor zugreift (einmalig oder dauerhaft, OpenClaw-Exec-Freigabe; keine harte Grenze, siehe ADR-027) |
| **P1–P7** | Leitprinzipien (Evidenz, Living Docs, etc.) |
| **GitOps** | Deployment-Status = Repository-Status |
