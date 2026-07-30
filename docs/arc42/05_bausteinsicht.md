# 5. Bausteinsicht

## Komponenten-Übersicht
```
IaC4
├── Ansible (Provisionierung, 6 Rollen)
│   ├── vps-baseline      → SSH, Pakete, Swap
│   ├── tailscale          → Tailscale-Join
│   ├── docker             → Docker-Engine + Compose
│   ├── traefik            → Reverse Proxy + LetsEncrypt
│   ├── qdrant             → Vektordatenbank (3072d, Cosine)
│   ├── code-server        → Web-IDE
│   └── openclaw-gateway   → OpenClaw-Install
├── GitHub Actions (CI/CD, 4 Workflows)
│   ├── ci.yml                               → Lint + Quality Gate
│   ├── 01-baseline-deploy.yml               → Phase 1 (via Public-IP)
│   ├── 02-tailscale-bootstrap.yml           → Phase 2a+2b (via Public-IP, schliesst SSH)
│   └── 04-tailscale-terraform.yml           → Terraform OAuth-Client
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
| openclaw-gateway | Node.js + openclaw onboard + Config | docker, qdrant |
