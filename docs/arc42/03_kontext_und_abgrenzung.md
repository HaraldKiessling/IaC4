# 3. Kontext & Abgrenzung

## Systemkontext
```
[GitHub] ──→ [IaC4 Repo] ──→ [GH Actions Runner]
                                   │
                                   ▼ (via Tailscale)
                              [VPS (DEV/PROD)]
                                   │
                            ┌──────┼──────┐
                            ▼      ▼      ▼
                        [Docker] [Qdrant] [OpenClaw]
                                   │
                                   ▼
                              [Tailscale Mesh]
```

## Abgrenzung zu anderen Repos
| Repo | Inhalt | Verwaltet in IaC4? |
|------|--------|-------------------|
| **IaC4** (dieses) | VPS-Baseline, Services, OpenClaw-Deployment | ✅ |
| home-assistant | Home Assistant Konfiguration | ❌ Separates Repo |
| openclaw-config | OpenClaw-Agenten-Konfiguration | ❌ Separates Repo |
