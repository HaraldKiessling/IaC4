# 7. Verteilungssicht

## Infrastruktur (final – ab Phase 2b)
```
[Tailnet (Tailscale Mesh 🔒 – HTTPS via Tailscale Serve 443→80)]
    │
    ▼
[VPS (Ubuntu 24.04)]
    ├── tailscale0 (100.x.y.z) – Tailscale Mesh 🔒
    ├── eth0 (Public-IP) – SSH blockiert via UFW 🔒, keine Service-Ports
    ├── docker0 (172.17.0.1)   – Docker Bridge
    │
    ├── Container: traefik      → Port 80 (Tailnet-only, UFW-CGNAT)
    ├── Container: qdrant       → Port 6333, 6334 (lokal + TS)
    ├── Container: code-server  → Port 8443 (via Traefik)
    ├── Container: openclaw-oc1 → Port 18789 (localhost-only, TS-Serve-TLS) – Default-Gateway
    ├── Container: openclaw-oc2 → Port 18790 (localhost-only, TS-Serve-TLS) – DevOps (4 Agents)
    └── Container: openclaw-oc3 → Port 18791 (geplant, enabled=false)
```

## Netzwerk-Security (nach SSH-Transition)
| Service | Erreichbar via | Authentifizierung |
|---------|---------------|-------------------|
| Traefik (HTTP) | Tailscale (Port 80, UFW-CGNAT); HTTPS via Tailscale Serve | Tailscale ACL + BasicAuth (Dashboard, ADR-019) |
| SSH | NUR Tailscale (100.x.y.z:22) | SSH-Key + Tailscale ACL |
| Qdrant | localhost + Tailscale | Tailscale ACL |
| Code-Server | Tailscale (Traefik-Route) | Traefik-ForwardAuth |
| OpenClaw OC1/OC2 | Tailscale via Serve-TLS (18789/18790) | Gateway-Token + Tailscale ACL |
| OpenClaw OC3 | DEV: aktiv (Best-Practice-Referenz, Benchmark – Design 01-oc2-oc3-benchmark); PROD: geplant (disabled bis Benchmark-Abschluss) | Port 18791 |

## SSH-Transition (zeitlich)
| Phase | SSH-Zugriff | Via | Dauer |
|-------|-------------|-----|-------|
| 0 (cloud-config) | 🔓 Öffentliche IP | eth0:22 | Minuten (Setup) |
| 1 (Baseline) | 🔓 Öffentliche IP | eth0:22 | < 2 Min |
| 2a (Tailscale) | 🔓 Öffentliche IP | eth0:22 | < 2 Min |
| 2b (Restrict) | 🔒 Geschlossen | – | < 1 Min |
| 2c+ (Final) | 🔒 Nur Tailscale | tailscale0:22 | dauerhaft |
