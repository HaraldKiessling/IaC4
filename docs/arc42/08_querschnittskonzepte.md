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
| <T>_<PROVIDER>_API_KEY | GH Actions Secret | LLM-Provider-Keys (T=DEV/PROD; PROVIDER=deepseek/openrouter/openai/google; nur gesetzte werden konfiguriert) |
| <T>_OC<n>_WEBSEARCH_API_KEY | GH Actions Secret | Perplexity-WebSearch je Instanz (optional) |
| <T>_OC<n>_GATEWAY_TOKEN | GH Actions Secret | Gateway-Auth-Token je Instanz (Pflicht, K3-1) |
| <T>_OC<n>_TELEGRAM_BOT_TOKEN | GH Actions Secret | Telegram-Bot je Instanz (optional) |

**Nicht in diesem Repo:** Secret-Werte (nur Env-Referenzen in Workflow/group_vars); Ollama braucht keinen Key (lokal, Docker-DNS)

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
| 01 | Tailscale Terraform (OAuth + ACLs, Merge aus 03+04) | Grundstruktur | PR/Push `terraform/**` + `workflow_dispatch` |
| 02 | Tailscale Bootstrap (Phase 2a+2b) | VPS-Konfiguration | `workflow_dispatch` |
| 03 | Baseline Deploy (Phase 1) | VPS-Konfiguration | `workflow_dispatch` |
| 04 | Service-Deploy (docker-traefik/services/openclaw, ADR-024) | VPS-Konfiguration | `workflow_dispatch` |
| 04b | BDD-Tests (Post-Deploy-Verifikation) | Verifikation | `workflow_dispatch` |
| CI | Lint + Quality Gate | CI | Push/PR auf `main`/`dev` |

### Secret-Abhängigkeiten

Jeder Workflow liest und schreibt bestimmte GitHub Secrets. Die folgende Tabelle zeigt die tatsächliche Nutzung pro Workflow:

| Workflow | READ Secrets | WRITE Secrets |
|----------|--------------|--------------|
| **00** | `GH_TOKEN` | **`SSH_KEY`**, **`SSH_KEY_PUB`** |
| **01** | `TAILSCALE_API_KEY`, `TAILSCALE_TAILNET`, `GH_TOKEN` | **`TAILSCALE_OAUTH_CLIENT_ID`**, **`TAILSCALE_OAUTH_CLIENT_SECRET`** |
| **02** | `SSH_KEY`, `VPS_USER`, `VPS_DEV_PUBLIC_IP` (dev) / `VPS_PROD_PUBLIC_IP` (prod), **`TAILSCALE_OAUTH_CLIENT_ID`**, **`TAILSCALE_OAUTH_CLIENT_SECRET`**, `TAILSCALE_TAILNET` (OAuth-Client-Token) | – |
| **03** | `SSH_KEY`, `VPS_USER`, **`TAILSCALE_OAUTH_CLIENT_ID`**, **`TAILSCALE_OAUTH_CLIENT_SECRET`**, `TAILSCALE_TAILNET` (OAuth-Client-Token; IP via Tailscale-API – keine Public-IP-Secrets) | – |
| **CI** | – | – |

### Logisch zwingende Reihenfolge

Basierend auf den Secret-Abhängigkeiten ergibt sich diese Ausführungsreihenfolge:

```
00 ─────────────────────────────────────────────
   │ WRITE: SSH_KEY, SSH_KEY_PUB               → wird von 02, 03 gelesen
   ↓
01 ─────────────────────────────────────────────
   │ WRITE: TAILSCALE_OAUTH_CLIENT_ID/SECRET    → wird von 02, 03 gelesen
   ↓
02 ─────────────────────────────────────────────
   │ READ: SSH_KEY + OAuth-Secrets → Tailscale install + join + SSH-Restrict (via Public-IP)
   ↓
03 ─────────────────────────────────────────────
   │ READ: SSH_KEY + Tailscale → Phase-1-Baseline via Tailscale-IP
   │ NACH 02: VPS nur noch via Tailscale erreichbar
   ↓
[04 / Phase-3-Service-Workflows – geplant]
```

**Kernregel:** 02 muss VOR 03 laufen (Bootstrap via Public-IP, danach Baseline via Tailscale-IP), 01 muss VOR 02 laufen (OAuth-Secrets), 00 muss VOR 02/03 laufen (SSH_KEY). Die Nummerierung entspricht der Ausführungsreihenfolge: 00 (SSH-Key) → 01 (OAuth/ACL) → 02 (Bootstrap) → 03 (Baseline).



#### P-005: Terraform-State-Cache ist kein echtes Backend
Der Terraform-State wird via GitHub Actions Cache (`actions/cache@v4`) persistiert – kein S3/GCS/Backend.
- **Vorteil:** Keine externe Infrastruktur nötig
- **Limitierung:** Bei parallelen Runs auf demselben Branch kann der Cache inkonsistent werden
- **Empfehlung:** Sobald mehrere Teammitglieder parallel arbeiten, auf ein echtes Terraform-Backend migrieren (z.B. S3 + DynamoDB-Locking)
- Siehe auch: ADR-014, T-006

### Bekannte Probleme

#### P-001: Workflow 01 ignoriert `target`-Input
`VPS_PUBLIC_IP` ist hart auf `${{ secrets.VPS_DEV_PUBLIC_IP }}` gesetzt. Die `target`-Auswahl (dev/prod) wird ignoriert. Workflow 02 hat die korrekte Implementierung mit bedingter IP-Wahl — 01 muss entsprechend gefixt werden.

#### P-002: Workflows 03 und 04 sind redundant
Beide nutzen dasselbe Terraform-Verzeichnis (`terraform/`), lesen und schreiben dieselben Secrets (`TAILSCALE_OAUTH_CLIENT_ID/SECRET`) und verwalten dieselbe Ressource (Tailscale OAuth-Client). Sie können nicht parallel laufen und erzeugen inkonsistente Zustände.

#### P-003: Kein Terraform-Backend in 03 und 04
Terraform State wird nicht persistiert (kein S3, GCS oder alternatives Backend). Jeder GitHub-Actions-Runner startet mit leerem Workspace → `terraform apply` erstellt bei jedem Run einen **neuen** OAuth-Client in Tailscale, ohne den alten zu widerrufen. **17 Runs von 03 + 13 Runs von 04 = ~30 Ghost-Clients in Tailscale.**

#### P-004: Workflow-Nummern inkonsistent
Die Nummerierung `00 → 01 → 02 → 03 → 04` suggeriert eine lineare Reihenfolge. Die tatsächliche Dependency-Kette ist `00 → 03 → 01 → 02`. Siehe Dependency-Graph oben.
✅ **Gelöst (PR #28):** Workflows 02/03 getauscht — Nummerierung = Ausführungsreihenfolge: `00 (SSH-Key) → 01 (Tailscale OAuth) → 02 (Bootstrap, via Public-IP) → 03 (Baseline, via Tailscale-IP)`.
