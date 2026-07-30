# 7. Verteilungssicht

## Infrastruktur
```
[Internet]
    │
    ▼ (Port 80/443 via Traefik)
[VPS (Ubuntu 24.04)]
    ├── tailscale0 (100.x.y.z) – Tailscale Mesh
    ├── docker0 (172.17.0.1)   – Docker Bridge
    │
    ├── Container: traefik      → Port 80, 443
    ├── Container: qdrant       → Port 6333, 6334
    ├── Container: code-server  → Port 8443 (via Traefik)
    └── Host-Process: openclaw  → Port 18789 (nur Tailscale)
```

## Netzwerk-Security
| Service | Erreichbar via | Authentifizierung |
|---------|---------------|-------------------|
| Traefik (HTTP/S) | Public (80/443) | LetsEncrypt + Traefik-Auth |
| Qdrant | localhost + Tailscale | Tailscale ACL |
| Code-Server | Tailscale (Traefik-Route) | Traefik-ForwardAuth |
| OpenClaw Gateway | Tailscale (18789) | Tailscale ACL |
| SSH | Tailscale (22) | SSH-Key + Tailscale ACL |
