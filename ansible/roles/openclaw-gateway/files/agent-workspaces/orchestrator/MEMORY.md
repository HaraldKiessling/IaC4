# MEMORY.md — Orchestrator (IaC4 DEV, Multi-Agent-Setup)

## Umgebung / Instanzrolle
- Zweck: DEV-Benchmark-Arm eines Multi-Agent-Team-Setups (orchestrator/architect/engineer-pro/reviewer)
- Funktional definierte Rollen; keine Persona-Identität, keine Ich-Perspektive (siehe AGENTS.md)

## Projekt
- Repo: HaraldKiessling/IaC4 — Infrastruktur-as-Code (Ansible, Docker/Traefik, Tailscale, OpenClaw)
- Methodik: docs/workflows/methodology.md (8 Schritte, 5W, Alternativen-Pflicht, Review-Gates)
- Workflow: Feature-Branch `session-*/<topic>` → PR → Review (Autor ≠ Reviewer) → Merge durch Owner

## Kernregeln
- Conventional Commits; `set -euo pipefail` (Bash); keine Secrets committen
- Alternativen immer abwägen; Quellen belegen (P1); Vendor-Docs lesen
- Parallel-Sessions: Worktree-Isolation — nie fremde Branches mergen
- Merge nach main + Deploy prod: nur mit fachlichem Nachweis + Owner-Freigabe

## Rollen (funktional)
- architect: Design, 5W, Alternativen, Quellen
- engineer-pro: Umsetzung, IaC4-Regeln, Evidence
- reviewer: Review-Checkliste, Befund-Format, Autor ≠ Reviewer

## Memory-Hinweis
- Diese Datei + memory/*.md werden vom Gateway indexiert (qmd/lokal). Tagesnotizen nach memory/YYYY-MM-DD.md.
