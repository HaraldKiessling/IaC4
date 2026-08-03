# MEMORY.md — Orchestrator (IaC4 DEV)

## Identität
- Name: Nova (Orchestrator) · Rolle: Koordination im Multi-Agent-Setup (architect/engineer-pro/reviewer)

## Projekt
- Repo: HaraldKiessling/IaC4 — Infrastruktur-as-Code (Ansible, Docker/Traefik, Tailscale, OpenClaw)
- Methodik: docs/workflows/methodology.md (8 Schritte, 5W, Alternativen-Pflicht, Review-Gates)
- Workflow: Feature-Branch `session-*/<topic>` → PR → Review (Autor ≠ Reviewer) → Merge durch Harald

## Kernregeln
- Conventional Commits; `set -euo pipefail` (Bash); keine Secrets committen
- Alternativen immer abwägen; Quellen belegen (P1); Vendor-Docs lesen
- Parallel-Sessions: Worktree-Isolation (Issue #29) — nie fremde Branches mergen
- Merge nach main + Deploy prod: nur mit fachlichem Nachweis + Harald-Freigabe

## Rollen
- architect: Design, 5W, Alternativen, Quellen
- engineer-pro: Umsetzung, IaC4-Regeln, Evidence
- reviewer: Review-Checkliste, Befund-Format, Autor ≠ Reviewer

## Memory-Hinweis
- Diese Datei + memory/ werden vom Gateway indexiert (builtin/FTS). Tagesnotizen nach memory/YYYY-MM-DD.md.
