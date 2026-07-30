# 3. Kontext & Abgrenzung

## Systemkontext (initial – Phase 0 bis Phase 2a)
```
[GitHub] ──→ [IaC4 Repo] ──→ [GH Actions Runner]
                                   │
                                   ▼ (SSH via Public-IP 🔓)
                              [VPS (DEV/PROD)]
```

## Systemkontext (final – ab Phase 2b)
```
[GitHub] ──→ [IaC4 Repo] ──→ [GH Actions Runner]
                                   │
                                   ▼ (SSH via Tailscale MagicDNS 🔒)
                            ┌─ [VPS (DEV/PROD)] ─────────────────┐
                            │  ├── tailscale0 (100.x.y.z)        │
                            │  ├── Docker (Traefik, Qdrant, …)  │
                            │  └── Host: OpenClaw Gateway        │
                            └──────────┬─────────────────────────┘
                                       │
                                  [Tailscale Mesh]
                                       │
                              [Haralds Clients (Admin)]
```

## Abgrenzung zu anderen Repos
| Repo | Inhalt | Verwaltet in IaC4? |
|------|--------|-------------------|
| **IaC4** (dieses) | VPS-Baseline, Services, OpenClaw-Deployment | ✅ |
| home-assistant | Home Assistant Konfiguration | ❌ Separates Repo |
| openclaw-config | OpenClaw-Agenten-Konfiguration | ❌ Separates Repo |
| **IaC3** (Legacy) | Altes Setup (wird abgelöst) | ❌ Legacy |

## SSH-Transition
```
Phase 0-2a: SSH via Public-IP 🔓  (Bootstrap, notwendig)
Phase 2b:   SSH blockiert auf Public-IP 🔒
Ab Phase 2c: SSH nur via Tailscale 🔒
```
