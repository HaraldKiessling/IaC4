# 9. Architekturentscheidungen

> Alle Entscheidungen fachlich begründet (P1: Evidenz).
> Sortiert nach Abhängigkeit (Grundlage → detail).
>
> **Detail-ADRs:** Entscheidungen ab 2026-07-31 (ADR-015..024, Docker/Traefik/Ollama) haben ihre Detaildokumente in `docs/adr/` (Nummern nahtlos an diese Tabelle anschließend). Diese Tabelle bleibt SSoT für alle Architekturentscheidungen.

| # | Entscheidung | Abhängig von | Begründung | Datum |
|---|-------------|-------------|------------|-------|
| ADR-001 | **arc42-light statt RFC/ADR-System** | – | In IaC3 führte das RFC-System zu Overhead und Inkonsistenz. arc42 ist etablierter Standard, pragmatisch | 2026-07-30 |
| ADR-002 | **Monorepo für IaC4** | ADR-001 | Entwicklungstools teilen sich Dependencies. Projekte (HA, OC-Config) separat | 2026-07-30 |
| ADR-003 | **VPS-User: deploy-user** | – | Eindeutige Benennung, keine Verwechslung mit openclaw-Agent | 2026-07-30 |
| ADR-004 | **Ansible (kein K8s)** | ADR-002 | VPS-Umgebung, Docker Compose reicht | 2026-07-30 |
| ADR-005 | **Phase-1/2/3-Trennung** | ADR-004 | OpenClaw-Deploy >10 Min war NoGo (IaC3) | 2026-07-30 |
| ADR-006 | **SSH-Transition (Public → Tailscale)** | ADR-005 | Security: Öffentliches SSH nur initial, dann Block | 2026-07-30 |
| ADR-007 | **cloud-config ohne Tailscale** | ADR-006 | Tailscale-Install via Ansible (kontrolliert), nicht in cloud-config | 2026-07-30 |
| ADR-008 | **Tailscale-OAuth (tag:ci) via Terraform** | ADR-002 | GH-Runner TS-Beitritt ohne manuelle Keys | 2026-07-30 |
| ADR-009 | **OAuth-Client mit tag:ci (nicht tag:ia4)** | ADR-008 | tag:ia4 existiert noch nicht in ACL. tag:ci ist etabliert | 2026-07-30 |
| ADR-010 | **ACL nicht mehr in IaC4-Terraform** | ADR-008 | ACL-Overwrite hat ia3+ha-Regeln gelöscht. ACL-Management braucht koordinierten Prozess | 2026-07-30 |
| ADR-011 | **Gemini-Embedding-001 (3072d, Cosine)** | – | Bereits in ZooCode etabliert, hervorragende Qualität | 2026-07-30 |
| ADR-012 | **OpenClaw-Minimal (Gateway + Memory)** | ADR-005 | Nur LLM-Keys, Memory, WebSearch. Kein Felix/Petrus | 2026-07-30 |
| ADR-013 | **Config-Reproduzierbarkeit: Option C** | ADR-005 | Phase 1+2 in Git/Ansible, Phase 3 nur Laufzeit. Später B | 2026-07-30 |
| ADR-014 | **Workflow-Struktur überarbeitet** | ADR-005 (Phasen), ADR-008 (OAuth) | ✅ Alle 4 Massnahmen umgesetzt: 03+04 gemergt (01), Terraform-State-Cache via GH Cache, 02 target-Fix, Workflows neu nummeriert (00→01→02→03). Siehe arc42 K8. | 2026-07-30 |
| ADR-015 | **Docker-Installation: eigene Tasks + offizielles Repo** | ADR-004 | Schlank, transparent, keine Community-Collection; Docker-Doku als SSoT. Detail: [docs/adr/ADR-015](adr/ADR-015-docker-installation.md) | 2026-07-31 |
| ADR-016 | **Kein deploy-user in docker-Gruppe (sudo)** | ADR-003, ADR-015 | docker-Gruppe = root-Äquivalent ohne Audit; sudo-Logging. Detail: [docs/adr/ADR-016](adr/ADR-016-docker-zugriff-deploy-user.md) | 2026-07-31 |
| ADR-017 | **Image-Pinning: SemVer-Tags in group_vars** | ADR-015 | Reproduzierbarkeit (QZ1); kein `latest` in Templates. Detail: [docs/adr/ADR-017](adr/ADR-017-image-pinning.md) | 2026-07-31 |
| ADR-018 | **HTTPS via Tailscale Serve (443→80)** | ADR-006, ADR-015 | Secure Context ohne eigenes ACME; superseded LE-Bestand. Detail: [docs/adr/ADR-018](adr/ADR-018-https-tailscale-serve.md) | 2026-07-31 |
| ADR-019 | **Traefik-Dashboard sicher (api@internal + Auth)** | ADR-018 | Kein `api.insecure`; Router + BasicAuth + UFW-Restrict. Detail: [docs/adr/ADR-019](adr/ADR-019-traefik-dashboard.md) | 2026-07-31 |
| ADR-020 | **Traefik-Logging: accessLog JSON→stdout, json-file-Rotation** | ADR-019 | Docker-konform, parsebar für Monitoring. Detail: [docs/adr/ADR-020](adr/ADR-020-traefik-logging.md) | 2026-07-31 |
| ADR-021 | **Ollama-Exposition: Host-Port 11434 + UFW-CGNAT** | ADR-015, ADR-018 | Tailscale-only; Container via Docker-DNS. Detail: [docs/adr/ADR-021](adr/ADR-021-ollama-exposition.md) | 2026-07-31 |
| ADR-022 | **Ollama-Limits: 2C/4G, KEEP_ALIVE=24h** | ADR-021 | Schutz der anderen Services; *VPS-Spec-Frage offen*. Detail: [docs/adr/ADR-022](adr/ADR-022-ollama-ressourcenlimits.md) | 2026-07-31 |
| ADR-023 | **Embedding: nomic-embed-text (768d, nur ZooCode)** | ADR-021 | CPU-tauglich, bewährt; Qdrant bleibt 3072d (ADR-011). Detail: [docs/adr/ADR-023](adr/ADR-023-ollama-embedding-modell.md) | 2026-07-31 |
| ADR-024 | **Ein Service-Deploy-Workflow (Playbook-Selektion)** | ADR-014 | Ein Wartungspunkt; Migration zu Reusable ab 5 Playbooks. Detail: [docs/adr/ADR-024](adr/ADR-024-service-deploy-workflow.md) | 2026-07-31 |

## Abhängigkeitsgraph (vereinfacht)
```
ADR-001 (arc42)
  └── ADR-002 (Monorepo)
        ├── ADR-004 (Ansible) → ADR-005 (Phasen) → ADR-006 (SSH-Transition)
        │                                           └── ADR-007 (cloud-config)
        │                     → ADR-012 (OpenClaw Minimal)
        │                     → ADR-013 (Config Reproduzierbarkeit)
        │                     └── ADR-014 (Workflow-Struktur)
        └── ADR-008 (TS OAuth) → ADR-009 (tag:ci)
                               └── ADR-010 (kein ACL-Management)
ADR-003 (deploy-user)
ADR-011 (Gemini-Embedding)
```
| ADR-014 | **Workflow-Struktur überarbeiten** | ADR-005 (Phasen), ADR-008 (OAuth) | Analyse der 6 Workflows ergab Nummerierungskonflikte (00→01→02→03→04 falsch), 03/04-Redundanz, fehlendes Terraform-Backend (State flüchtig) und Bug in 01 (target ignoriert). Siehe arc42 K8 (CI/CD-Workflows) für Details. Notwendige Massnahmen: (1) 03+04 zu einem Workflow mergen, (2) Terraform-Backend konfigurieren, (3) 01 target-Fix, (4) Workflows neu nummerieren nach Dependency-Kette. | 2026-07-30 |
