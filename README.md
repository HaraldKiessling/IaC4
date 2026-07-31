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

# 4. Basis-Deploy (nach Workflow 02: Tailscale-Bootstrap)
make deploy-dev
```

## Workflows

| Workflow | Trigger | Beschreibung |
|----------|---------|-------------|
| `00-generate-ssh-key.yml` | Dispatch | SSH-Key-Paar generieren + Secrets (einmalig) |
| `01-tailscale-terraform.yml` | Dispatch | Tailscale-OAuth + ACLs (Terraform Plan/Apply) |
| `02-tailscale-bootstrap.yml` | Dispatch | Phase 2a+2b: Tailscale install + join + SSH-Restrict (via Public-IP) |
| `03-baseline-deploy.yml` | Dispatch | Phase 1: System-Baseline (via Tailscale-IP) |
| `ci.yml` | Push + PR | Lint + YAML + LivingDocs-Check |

> **Ausführungsreihenfolge:** `00` → `01` → `02` (Bootstrap) → `03` (Baseline).
> Workflow 02 **MUSS vor** Workflow 03 laufen – die Baseline verbindet sich via Tailscale-IP.

## Deployment-Stufen

Siehe [`docs/workflows/deploy-stages.md`](docs/workflows/deploy-stages.md) für das komplette Branching-Modell.

## Lizenz

Privat – Harald Kiessling
