# 6. Laufzeitsicht

## Deployment-Ablauf (vollständig)

```
                    ╔═══════════════════════╗
                    ║  VPS Neuinstallation  ║
                    ╚═══════════════════════╝
                              │
                    cloud-config.yaml einspielen
                              │
                    SSH via Public-IP 🔓
                              ▼
              ╔═══════════════════════════╗
              ║ Phase 1: Baseline (Ansible) ║
              ╚═══════════════════════════╝
              → System-Update, Pakete, Swap
              → SSH via Public-IP 🔓
                              │
                              ▼
           ╔═══════════════════════════════╗
           ║ Phase 2a: Tailscale-Join (Ansible)║
           ╚═══════════════════════════════╝
           → OAuth-Token → Pre-Auth-Key → tailscale up
           → SSH via Public-IP 🔓
                              │
                              ▼
            ╔══════════════════════════════╗
            ║ Phase 2b: SSH-Restrict 🔒     ║
            ╚══════════════════════════════╝
            → UFW deny 22 (Public-IP dicht)
            → SSH NUR noch via Tailscale 🔒
                              │
                              ▼
            ╔══════════════════════════════╗
            ║ Phasen 2c-e: Docker, Services,║
            ║ OpenClaw (alle via Tailscale) ║
            ╚══════════════════════════════╝
```

## Disaster Recovery
```bash
# 1. VPS neu provisionieren (cloud-config.yaml)
# 2. SSH via Public-IP (Phase 0)
# 3. Ansible-Gesamtdurchlauf (Phasen 1-2e)
git clone https://github.com/HaraldKiessling/IaC4.git
cd IaC4
make deploy target=prod   # < 10 Minuten
# 4. Qdrant-Volume-Restore für Memory-Kontinuität
```
