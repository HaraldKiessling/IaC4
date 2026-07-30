# 9. Architekturentscheidungen

> Alle Entscheidungen fachlich begründet (P1: Evidenz).

| # | Entscheidung | Begründung | Datum |
|---|-------------|------------|-------|
| ADR-001 | **arc42-light statt RFC/ADR-System** | In IaC3 führte das RFC-System zu Overhead und Inkonsistenz. arc42 ist etablierter Standard, pragmatisch und auf das Nötigste reduzierbar | 2026-07-30 |
| ADR-002 | **Monorepo für IaC4** | Entwicklungstools teilen sich Dependencies und Workflows. Projekte (Home Assistant, OpenClaw-Config) separat, da eigenständige Lebenszyklen | 2026-07-30 |
| ADR-003 | **Ansible (kein K8s)** | VPS-Umgebung, Docker Compose reicht. K8s wäre overengineered für 1-2 Server | 2026-07-30 |
| ADR-004 | **Gemini-Embedding-001 (3072d, Cosine)** | Bereits in ZooCode etabliert, hervorragende Qualität, Qdrant-Support out-of-box | 2026-07-30 |
| ADR-005 | **Phase-1/2-Trennung** | OpenClaw-Deploy >10 Min war NoGo (IaC3). Trennung reduziert Basis-Deploy auf <2 Min | 2026-07-30 |
| ADR-006 | **Tailscale-OAuth + ACLs via Terraform** | Bewährt aus IaC3, erlaubt GH-Runner TS-Netzwerkbeitritt ohne Key-Manual-Jonglage | 2026-07-30 |
| ADR-007 | **Config-Reproduzierbarkeit: Option C** | Phase 1+2 in Git/Ansible, Phase 3 nur Laufzeit. Später Option B (Git-Integration im Agent) | 2026-07-30 |
