# 9. Architekturentscheidungen

> Alle Entscheidungen fachlich begründet (P1: Evidenz).
> Sortiert nach Abhängigkeit (Grundlage → detail).

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

## Abhängigkeitsgraph (vereinfacht)
```
ADR-001 (arc42)
  └── ADR-002 (Monorepo)
        ├── ADR-004 (Ansible) → ADR-005 (Phasen) → ADR-006 (SSH-Transition)
        │                                           └── ADR-007 (cloud-config)
        │                     → ADR-012 (OpenClaw Minimal)
        │                     → ADR-013 (Config Reproduzierbarkeit)
        └── ADR-008 (TS OAuth) → ADR-009 (tag:ci)
                               └── ADR-010 (kein ACL-Management)
ADR-003 (deploy-user)
ADR-011 (Gemini-Embedding)
```
