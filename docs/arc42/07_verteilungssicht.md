# 7. Verteilungssicht

## Infrastruktur (final – ab Phase 2b)
```
[Internet (nur Traefik 80/443)]
    │
    ▼
[VPS (Ubuntu 24.04)]
    ├── tailscale0 (100.x.y.z) – Tailscale Mesh 🔒
    ├── eth0 (Public-IP) – SSH blockiert via UFW 🔒
    ├── docker0 (172.17.0.1)   – Docker Bridge
    │
    ├── Container: traefik      → Port 80, 443 (Public)
    ├── Container: qdrant       → Port 6333, 6334 (lokal + TS)
    ├── Container: code-server  → Port 8443 (via Traefik)
    └── Host-Process: openclaw  → Port 18789 (nur Tailscale)
```

## Netzwerk-Security (nach SSH-Transition)
| Service | Erreichbar via | Authentifizierung |
|---------|---------------|-------------------|
| Traefik (HTTP/S) | Public (80/443) | LetsEncrypt + Traefik-Auth |
| SSH | NUR Tailscale (100.x.y.z:22) | SSH-Key + Tailscale ACL |
| Qdrant | localhost + Tailscale | Tailscale ACL |
| Code-Server | Tailscale (Traefik-Route) | Traefik-ForwardAuth |
| OpenClaw Gateway | Tailscale (18789) | Tailscale ACL |

## SSH-Transition (zeitlich)
| Phase | SSH-Zugriff | Via | Dauer |
|-------|-------------|-----|-------|
| 0 (cloud-config) | 🔓 Öffentliche IP | eth0:22 | Minuten (Setup) |
| 1 (Baseline) | 🔓 Öffentliche IP | eth0:22 | < 2 Min |
| 2a (Tailscale) | 🔓 Öffentliche IP | eth0:22 | < 2 Min |
| 2b (Restrict) | 🔒 Geschlossen | – | < 1 Min |
| 2c+ (Final) | 🔒 Nur Tailscale | tailscale0:22 | dauerhaft |
