# Deployment-Stufen & Workflow-Reihenfolge

> **Logische Reihenfolge:** Erst Zugangskanal herstellen, dann härten, dann Services.
> **Kernprinzip:** `03` (Bootstrap) läuft über Public-IP und MUSS vor `02` (Baseline) laufen.

## Stufen-Übersicht

```
Stufe 0: Setup (einmalig, Repo-Ebene)
         → 00-generate-ssh-key.yml   SSH-Key-Paar + Secrets (nur wenn SSH_KEY fehlt)
         → 01-tailscale-terraform.yml Tailscale OAuth-Client (Terraform)

Stufe 1: VPS-Provisioning (Provider, Harald)
         → cloud-config: deploy-user + SSH-Key + UFW (nur SSH offen)
         → KEIN Tailscale (wird via Ansible installiert)
         → VPS via PUBLIC-IP erreichbar 🔓

Stufe 2: 03-tailscale-bootstrap.yml  (via Public-IP) 🔓→🔒
         → SSH-Zugang testen (IaC4-SSH_KEY ↔ cloud-config-Key)
         → Tailscale installieren + joinen (tag:ia3)
         → Node-Cleanup: offline vps-<target> → vps-<target>-old-<ts> (NIE löschen)
         → SSH-Restrict: UFW deny 22 auf Public-IP,
           Allow für Tailscale-CGNAT 100.64.0.0/10
         → SSH NUR noch via Tailscale 🔒

Stufe 3: 02-baseline-deploy.yml      (via Tailscale) 🔒
         → System aktualisieren, Pakete, Timezone, SSH-Härtung
         → Vorbedingung: Tailscale-IP muss existieren (sonst Abbruch:
           „Workflow 03 zuerst ausführen“)

Stufe 4: Docker + Traefik            (Playbook 03-docker-traefik.yml) 🔒
Stufe 5: Services                    (Playbook 04-services.yml: Qdrant, Code-Server) 🔒
Stufe 6: OpenClaw Gateway            (Playbook 05-openclaw.yml) 🔒
```

## Warum 03 vor 02?

1. **03 ist der einzige Workflow über Public-IP** — danach ist der VPS bewusst nur
   noch via Tailscale erreichbar (Lockout-Prävention).
2. **02 kann technisch nicht vor 03 laufen:** Er ermittelt die Tailscale-IP des
   Ziel-Nodes per API. Ein frischer VPS ohne Tailscale hat keine → Abbruch.
3. SSH-Härtung (`PasswordAuthentication no`) vor dem Tailscale-Join wäre riskant:
   Fehlschlag beim Join = VPS ohne Zugangsweg.

## Secrets

| Secret | Zweck | Genutzt in |
|--------|-------|-----------|
| `SSH_KEY` | Private Key (deploy-user) | 02, 03 |
| `VPS_USER` | SSH-User (`deploy-user`) | 02, 03 |
| `VPS_DEV_PUBLIC_IP` / `VPS_PROD_PUBLIC_IP` | Public-IP (nur Stufe 2/03) | 03 |
| `TAILSCALE_TAILNET` | Tailnet (z.B. tailcfea8a.ts.net) | 02, 03 |
| `TAILSCALE_API_KEY` | Tailscale-API (Node-IP, Cleanup, Re-Tag) | 02, 03 |
| `TAILSCALE_OAUTH_CLIENT_ID/SECRET` | OAuth (Runner-Join + Auth-Keys) | 02, 03 |
| `TAILSCALE_HOSTNAME_DEV/PROD` | MagicDNS-Hostnamen (Referenz) | – |

## SSH-Key

- **Private Key:** GH Secret `SSH_KEY` (IaC4 — NICHT das IaC3-Secret!)
- **Public Key:** in `cloud-config.yaml` (beim VPS-Setup eingespielt)
- **Typ:** ED25519 (`iac4-deploy-key-20260730`, Fingerprint SHA256:zNZbl83…)

## Workflow-Reihenfolge (verbindlich)

1. `00-generate-ssh-key.yml`      → einmalig, nur wenn `SSH_KEY` fehlt
2. `01-tailscale-terraform.yml`   → einmalig, OAuth-Client (Plan/Apply)
3. **`03-tailscale-bootstrap.yml`** → pro frischem VPS (Public-IP, schließt SSH 🔒)
4. **`02-baseline-deploy.yml`**   → danach (Tailscale, Härtung)
5. Docker/Traefik → Services → OpenClaw (Playbooks, Workflows folgen Phase 6)
