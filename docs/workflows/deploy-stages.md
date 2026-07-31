# Deployment-Stufen & SSH-Transition

## Überblick

> **Wichtig:** Die Workflow-Nummern (`00`–`03`) = **Ausführungsreihenfolge**.
> Die Phasen-Nummern (Phase 0–2c) beschreiben den VPS-Lifecycle (Playbook-Namen) und
> sind **nicht** die Ausführungsreihenfolge. Seit PR #26 (MagicDNS-Umstellung) läuft die
> Baseline **nach** dem Tailscale-Join: **Workflow 02 (Bootstrap) MUSS vor
> Workflow 03 (Baseline) ausgeführt werden.**

```
Ausführungsreihenfolge (Workflows):

Phase 0: cloud-config beim VPS-Setup
         → deploy-user mit SSH-Key
         → UFW (nur SSH offen)
         → KEIN Tailscale (wird via Ansible installiert)
         → VPS via PUBLIC-IP erreichbar 🔓

Workflow 02 – Phase 2a: Tailscale-Join (via SSH auf Public-IP)
         → tailscale installieren & joinen
         → SSH via Public-IP 🔓 (noch offen)

Workflow 02 – Phase 2b: SSH-Restrict
         → UFW deny 22 🔒
         → SSH NUR noch via Tailscale (MagicDNS)

Workflow 03 – Phase 1: Ansible-Baseline (via SSH auf Tailscale-IP 🔒)
         → System aktualisieren, Pakete, Swap

Phase 2c+: Docker, Services, OpenClaw
         → Alle via Tailscale-SSH 🔒
```

## Secrets für Bootstrap

Für Workflow 02 (Phasen 2a/2b, vor Tailscale) wird die **öffentliche IP** des VPS benötigt.
Aktuell gesetzt:

| Secret | Wert | Nutzung |
|--------|------|---------|
| `SSH_KEY` | 🔑 (private Key) | SSH-Zugriff (Workflows 02, 03) |
| `VPS_USER` | `deploy-user` | SSH-User (Workflows 02, 03) |
| `VPS_DEV_PUBLIC_IP` | (muss gesetzt werden) | Workflow 02 (Bootstrap) – Phasen 2a/2b |
| `VPS_PROD_PUBLIC_IP` | (PROD) | Workflow 02, target=prod |
| `TAILSCALE_OAUTH_CLIENT_ID` / `TAILSCALE_OAUTH_CLIENT_SECRET` | OAuth-Client (tag:ci) | Runner-Join + Auth-Key-Erzeugung (02, 03) |
| `TAILSCALE_TAILNET` | z.B. `tailcfea8a.ts.net` | Tailnet (02, 03) |
| `TAILSCALE_API_KEY` | API-Token | Tailscale-API: IP-Resolution, Cleanup/Rename, Re-Tag (02, 03) |

Nach Phase 2b läuft alles via Tailscale. Workflow 03 löst die VPS-IP per **Tailscale-API**
aus dem Node-Hostnamen (`vps-dev`) auf – ein `VPS_DEV_HOST`-Secret ist dafür nicht nötig.

## SSH-Key

- **Private Key:** in GH Secret `SSH_KEY`
- **Public Key:** in `cloud-config.yaml` (beim VPS-Setup eingespielt)
- **Typ:** ED25519, generiert 2026-07-30

## Workflow-Reihenfolge

1. `00-generate-ssh-key.yml`           → SSH-Key-Paar generieren + Secrets anlegen (einmalig)
2. `01-tailscale-terraform.yml`        → Tailscale OAuth + ACLs (Terraform Plan/Apply, einmalig)
3. `02-tailscale-bootstrap.yml`        → Phase 2a + 2b (via Public-IP, schliesst SSH 🔒)
4. `03-baseline-deploy.yml`            → Phase 1 (via Tailscale-IP 🔒)
5. Danach: weitere Services via Tailscale (04-service-deploy, 05-openclaw-install geplant)
