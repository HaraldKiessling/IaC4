# 5. Bausteinsicht

## Komponenten-Übersicht
```
IaC4
├── Ansible (Provisionierung, 6 Rollen)
│   ├── vps-baseline      → SSH, Pakete, Swap
│   ├── tailscale          → Tailscale-Join
│   ├── docker             → Docker-Engine + Compose
│   ├── traefik            → Reverse Proxy (HTTP-only, Port 80, Tailscale-only)
│   ├── qdrant             → Vektordatenbank (3072d, Cosine)
│   ├── code-server        → Web-IDE
│   └── openclaw-gateway   → OpenClaw-Gateways (Docker-Container, Multi-Instanz OC1-OC3)
├── GitHub Actions (CI/CD, 5 Workflows)
│   ├── ci.yml                               → Lint + Quality Gate
│   ├── 00-generate-ssh-key.yml              → SSH-Key-Paar generieren
│   ├── 01-tailscale-terraform.yml           → Tailscale OAuth + ACLs (Terraform Plan/Apply)
│   ├── 02-tailscale-bootstrap.yml           → Phase 2a+2b (via Public-IP, schliesst SSH)
│   └── 03-baseline-deploy.yml               → Phase 1 (via Tailscale-IP)
├── Terraform (Tailscale OAuth-Client)
│   └── oauth-client.tf                      → Erzeugt Client (tag:ci)
├── Docker Compose (Services)
│   ├── services/traefik/    → Reverse Proxy
│   ├── services/qdrant/     → Vektordatenbank
│   └── services/code-server/ → Web-IDE
└── Docs (arc42)
```

## Rollen-Verantwortlichkeiten
| Rolle | Verantwortung | Abhängigkeit |
|-------|--------------|-------------|
| vps-baseline | Ubuntu-Update, SSH-Härtung, Swap | – |
| tailscale | Tailscale installieren + joinen | vps-baseline |
| docker | Docker + Compose installieren | tailscale |
| traefik | Traefik-Container + Config | docker |
| qdrant | Qdrant-Container + Collection (3072d/Cosine) | docker |
| code-server | Code-Server-Container + Reverse-Proxy-Route | docker, traefik |
| openclaw-gateway | Docker-Container (ghcr.io/openclaw/openclaw, gepinnt); je Instanz Config+Workspace unter /srv/openclaw/<name>/ | docker, traefik-network, ollama, qdrant |
