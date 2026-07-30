# 8. Querschnittskonzepte

## Security
- SSH-Only via Tailscale (kein öffentlicher SSH-Port)
- sudo ohne Passwort für deploy-user (für Ansible-Pipelining)
- `requiretty` deaktiviert (für Ansible-Pipelining)
- Secrets in GH Actions (nie im Repo)

## Secrets-Management
| Secret | Ort | Typ |
|--------|-----|-----|
| GH_TOKEN | GH Actions Secret + .env | PAT |
| TAILSCALE_* | GH Actions Secret | OAuth/API |
| OPENCLAW_LLM_API_KEY | GH Actions Secret | API-Key |
| SSH-Keys | GH Actions Secret + .ssh/ | ED25519 |

## Persistenz
- **Qdrant:** Docker-Volume (`qdrant_data`)
- **Code-Server:** Docker-Volume (`code-server-data`)
- **Traefik:** Docker-Volume (`traefik-data`)

## Backup
(Später zu definieren – siehe #11 Technische Schulden)
