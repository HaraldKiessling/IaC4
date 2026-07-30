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

## CI/CD-Workflows

### Workflow-Übersicht

| # | Name | Phase | Trigger |
|---|------|-------|---------|
| 00 | SSH-Key-Paar generieren | Grundstruktur | `workflow_dispatch` |
| 01 | Baseline Deploy | VPS-Konfiguration | `workflow_dispatch` |
| 02 | Tailscale Bootstrap | VPS-Konfiguration | `workflow_dispatch` |
| 03 | OAuth-Client (erzeugen/prüfen) | Grundstruktur | `workflow_dispatch` |
| 04 | Tailscale Terraform (OAuth + ACLs) | Grundstruktur | PR/Push auf `terraform/**` + `workflow_dispatch` |
| CI | Lint + Quality Gate | CI | Push/PR auf `main`/`dev` |

### Secret-Abhängigkeiten

Jeder Workflow liest und schreibt bestimmte GitHub Secrets. Die folgende Tabelle zeigt die tatsächliche Nutzung pro Workflow:

| Workflow | READ Secrets | WRITE Secrets |
|----------|--------------|--------------|
| **00** | `GH_TOKEN` | **`SSH_KEY`**, **`SSH_KEY_PUB`** |
| **01** | `SSH_KEY`, `VPS_USER`, `VPS_DEV_PUBLIC_IP` | – |
| **02** | `SSH_KEY`, `VPS_USER`, `VPS_DEV_PUBLIC_IP`/`VPS_PROD_PUBLIC_IP`, **`TAILSCALE_OAUTH_CLIENT_ID`**, **`TAILSCALE_OAUTH_CLIENT_SECRET`**, `TAILSCALE_TAILNET` | – |
| **03** | `GH_TOKEN`, `TAILSCALE_API_KEY`, `TAILSCALE_TAILNET` | **`TAILSCALE_OAUTH_CLIENT_ID`**, **`TAILSCALE_OAUTH_CLIENT_SECRET`** |
| **04** | `TAILSCALE_API_KEY`, `TAILSCALE_TAILNET`, `GH_TOKEN` | **`TAILSCALE_OAUTH_CLIENT_ID`**, **`TAILSCALE_OAUTH_CLIENT_SECRET`** |
| **CI** | – | – |

### Logisch zwingende Reihenfolge

Basierend auf den Secret-Abhängigkeiten ergibt sich diese Ausführungsreihenfolge:

```
00 ─────────────────────────────────────────────
   │ WRITE: SSH_KEY, SSH_KEY_PUB               → wird von 01, 02 gelesen
   ↓
03 ─────────────────────────────────────────────
   │ WRITE: TAILSCALE_OAUTH_CLIENT_ID/SECRET    → wird von 02 gelesen
   ↓
01 ─────────────────────────────────────────────
   │ READ: SSH_KEY → deployed Baseline via SSH auf public-IP
   ↓
02 ─────────────────────────────────────────────
   │ READ: SSH_KEY + OAuth-Secrets → Tailscale install + SSH restrict
   │ NACH 02: VPS nur noch via Tailscale erreichbar
   ↓
[04 / Phase-3-Service-Workflows – geplant]
```

**Kernregel:** 03 muss VOR 02 laufen (OAuth-Secrets), 01 muss VOR 02 laufen (SSH-Zugriff via public-IP). Die aktuelle Nummerierung (00→01→02→03→04) suggeriert eine falsche Reihenfolge.

### Bekannte Probleme

#### P-001: Workflow 01 ignoriert `target`-Input
`VPS_PUBLIC_IP` ist hart auf `${{ secrets.VPS_DEV_PUBLIC_IP }}` gesetzt. Die `target`-Auswahl (dev/prod) wird ignoriert. Workflow 02 hat die korrekte Implementierung mit bedingter IP-Wahl — 01 muss entsprechend gefixt werden.

#### P-002: Workflows 03 und 04 sind redundant
Beide nutzen dasselbe Terraform-Verzeichnis (`terraform/`), lesen und schreiben dieselben Secrets (`TAILSCALE_OAUTH_CLIENT_ID/SECRET`) und verwalten dieselbe Ressource (Tailscale OAuth-Client). Sie können nicht parallel laufen und erzeugen inkonsistente Zustände.

#### P-003: Kein Terraform-Backend in 03 und 04
Terraform State wird nicht persistiert (kein S3, GCS oder alternatives Backend). Jeder GitHub-Actions-Runner startet mit leerem Workspace → `terraform apply` erstellt bei jedem Run einen **neuen** OAuth-Client in Tailscale, ohne den alten zu revoken. **17 Runs von 03 + 13 Runs von 04 = ~30 Ghost-Clients in Tailscale.**

#### P-004: Workflow-Nummern inkonsistent
Die Nummerierung `00 → 01 → 02 → 03 → 04` suggeriert eine lineare Reihenfolge. Die tatsächliche Dependency-Kette ist `00 → 03 → 01 → 02`. Siehe Dependency-Graph oben.
