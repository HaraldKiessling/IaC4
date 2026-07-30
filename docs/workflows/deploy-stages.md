# Deployment-Stufen & SSH-Transition

## Überblick

```
Phase 0: cloud-config beim VPS-Setup
         → deploy-user mit SSH-Key
         → UFW (nur SSH offen)
         → KEIN Tailscale (wird via Ansible installiert)
         → VPS via PUBLIC-IP erreichbar 🔓

Phase 1: Ansible-Baseline (via SSH auf Public-IP)
         → System aktualisieren, Pakete, Swap
         → SSH via Public-IP 🔓

Phase 2a: Tailscale-Join (via SSH auf Public-IP)
         → tailscale installieren & joinen
         → SSH via Public-IP 🔓 (noch offen)

Phase 2b: SSH-Restrict
         → UFW deny 22 🔒
         → SSH NUR noch via Tailscale (MagicDNS)

Phase 2c+: Docker, Services, OpenClaw
         → Alle via Tailscale-SSH 🔒
```

## Secrets für Bootstrap

Für die Phasen 1-2a (vor Tailscale) wird die **öffentliche IP** des VPS benötigt.
Aktuell gesetzt:

| Secret | Wert | Nutzung |
|--------|------|---------|
| `VPS_DEV_HOST` | `vps-dev.tailcfea8a.ts.net` | Nach Phase 2b |
| `VPS_DEV_PUBLIC_IP` | (muss gesetzt werden) | Für Phasen 1-2a |
| `SSH_KEY` | 🔑 (private Key) | SSH-Zugriff |
| `VPS_USER` | `deploy-user` | SSH-User |

Nach Phase 2b wechselt der Workflow automatisch auf `VPS_DEV_HOST`.

## SSH-Key

- **Private Key:** in GH Secret `SSH_KEY`
- **Public Key:** in `cloud-config.yaml` (beim VPS-Setup eingespielt)
- **Typ:** ED25519, generiert 2026-07-30

## Workflow-Reihenfolge

1. `00-generate-ssh-key.yml`           → SSH-Key-Paar generieren + Secrets anlegen (einmalig)
2. `01-baseline-deploy.yml`            → Phase 1 (via Public-IP)
3. `02-tailscale-bootstrap.yml`        → Phase 2a + 2b (via Public-IP, schliesst SSH 🔒)
4. `04-tailscale-terraform.yml`        → Tailscale OAuth + ACLs (Terraform Plan/Apply)
5. Danach: weitere Services via Tailscale
