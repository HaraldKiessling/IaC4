# 8. Querschnittskonzepte

## SSH-Strategie
- **Initial (Phasen 0-2a):** SSH via Public-IP für Bootstrap 🔓
- **Final (ab Phase 2b):** UFW deny 22 auf Public-IP 🔒
- **Dauerhaft:** SSH nur via Tailscale (SSH-Key + Tailscale ACL)
- sudo ohne Passwort für `deploy-user` (für Ansible-Pipelining)
- `requiretty` deaktiviert (für Ansible-Pipelining)

## Secrets-Management
| Secret | Ort | Typ |
|--------|-----|-----|
| GH_TOKEN | GH Actions Secret | PAT (Contents: write) |
| SSH_KEY | GH Actions Secret | ED25519 Private Key |
| TAILSCALE_OAUTH_CLIENT_ID | GH Actions Secret | OAuth-Client-ID |
| TAILSCALE_OAUTH_CLIENT_SECRET | GH Actions Secret | OAuth-Client-Secret |
| TAILSCALE_TAILNET | GH Actions Secret | Tailnet-Name |
| OPENCLAW_LLM_API_KEY | GH Actions Secret | API-Key (noch zu setzen) |
| OPENCLAW_WEBSEARCH_API_KEY | GH Actions Secret | API-Key (noch zu setzen) |

**Nicht in diesem Repo:** Telegram-Bot-Tokens, Ollama-Keys (später)

## Persistenz
- **Qdrant:** Docker-Volume (`qdrant_data`)
- **Code-Server:** Docker-Volume (`code-server-data`)
- **Traefik:** Docker-Volume (`traefik-data`)

## Backup (Tech-Debt)
- Später zu definieren – siehe #11
- `scripts/restore.sh` als Gerüst vorhanden
