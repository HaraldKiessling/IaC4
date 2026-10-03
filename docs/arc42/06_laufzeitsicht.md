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

> **Hinweis Upload-Brücke (ADR-027):** In den Phasen 2c-e wird mit dem
> OpenClaw-Deploy auch der Upload-Brücken-Transport gesetzt (Serve-Eintrag
> `tailscale serve --bg --https={{ oc.upload_bridge_https }}` +
> Loopback-Publish `127.0.0.1:<upload_bridge_host_port>:8099`, nur wenn
> `upload_bridge_enabled`). Die Brücke selbst ist **extern** und **kein
> Deploy-Gate** (Deploy bleibt grün, auch ohne laufende Brücke).

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
