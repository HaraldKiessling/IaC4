# 5. Bausteinsicht

## Komponenten-Übersicht
```
IaC4
├── Ansible (Provisionierung)
│   ├── vps-baseline (SSH, Pakete, Swap)
│   ├── tailscale (Tailscale-Join)
│   ├── docker (Docker-Engine + Compose)
│   ├── traefik (Reverse Proxy + LetsEncrypt)
│   ├── qdrant (Vektordatenbank)
│   ├── code-server (Web-IDE)
│   └── openclaw-gateway (OpenClaw-Install)
├── GitHub Actions (CI/CD)
│   ├── ci.yml (Lint + Quality Gate)
│   ├── 01-baseline-deploy.yml (Phase 1)
│   ├── 02-service-deploy.yml (Phase 2a/b)
│   ├── 03-openclaw-install.yml (Phase 2c)
│   └── 04-tailscale-terraform.yml (Terraform)
├── Terraform (Tailscale OAuth + ACLs)
├── Docker Compose (Services)
│   ├── traefik/
│   ├── qdrant/
│   └── code-server/
└── Docs (arc42)
```

## Rollen-Verantwortlichkeiten
| Rolle | Verantwortung |
|-------|--------------|
| vps-baseline | Ubuntu-Update, SSH-Härtung, Swap, Zeitzone |
| docker | Docker + Compose installieren, Netzwerk anlegen |
| traefik | Traefik-Container + Config + LetsEncrypt |
| qdrant | Qdrant-Container + Collection (3072d/Cosine) |
| code-server | Code-Server-Container + Reverse-Proxy-Route |
| openclaw-gateway | Node.js + openclaw onboard + Config |
