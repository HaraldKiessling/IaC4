# IaC4 – Infrastructure-as-Code für VPS + Entwicklungstools

> **Status:** Initial-Setup (Phase 0)
> **Branch:** main
> **Architektur:** arc42-light (siehe [`docs/arc42/`](docs/arc42/))

## Übersicht

IaC4 ist die zweite Generation von Haralds IaC-Setup. Es managed:

- **VPS-Baseline** (Ubuntu, SSH, Pakete, Tailscale)
- **Docker & Traefik** (Container-Plattform)
- **Services** (Qdrant, Code-Server, OpenClaw-Gateway)
- **Terraform** (Tailscale-OAuth, ACLs)

**Nicht hier:** Home Assistant, OpenClaw-Agenten-Konfiguration – eigene Repos.

## Prinzipien

| # | Prinzip | Bedeutung |
|---|---------|-----------|
| P1 | **Evidenz** | Jede Behauptung braucht einen Beleg |
| P2 | **Konzepte vor Code** | Mit Review-Pflicht |
| P3 | **Review mit 5W** | Alternativen, Priorisierung, Eskalation |
| P4 | **Living Docs** | Doku immer aktuell (arc42) |
| P5 | **Gap-Analysen** | Regelmäßiger IST-SOLL-Abgleich |
| P6 | **Nachhaltigkeit** | Keine Workarounds, Tech-Debt dokumentieren |
| P7 | **Autonome Entwicklung** | DEV-first, technische Entscheidungsfreiheit |

## Quickstart

```bash
# 1. Repository clonen
git clone https://github.com/HaraldKiessling/IaC4.git
cd IaC4

# 2. Secrets setzen (GH Actions → Settings → Secrets)
# Siehe .env.example für alle benötigten Secrets

# 3. VPS provisionieren (cloud-config.yaml.template anpassen)
# Siehe docs/workflows/deploy-stages.md

# 4. Basis-Deploy
make deploy target=dev
```

## Workflows

| Workflow | Trigger | Beschreibung |
|----------|---------|-------------|
| `01-baseline-deploy.yml` | Dispatch | Phase 1: System-Baseline |
| `02-service-deploy.yml` | Dispatch | Phase 2a/b: Docker, Traefik, Services |
| `03-openclaw-install.yml` | Dispatch | Phase 2c: OpenClaw-Gateway |
| `04-tailscale-terraform.yml` | Dispatch | Tailscale-OAuth + ACLs |
| `ci.yml` | Push + PR | Lint + YAML + LivingDocs-Check |

## Deployment-Stufen

Siehe [`docs/workflows/deploy-stages.md`](docs/workflows/deploy-stages.md) für das komplette Branching-Modell.

## Lizenz

Privat – Harald Kiessling
