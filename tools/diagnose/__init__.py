"""Diagnose-Workflow 06 (Issue #113) – read-only Metrik-Erfassung auf OpenClaw-Instanzen.

Package `tools/diagnose` (Design Phase 11, Workflow 06):
- diagnose.py        – CLI-Fassade (--mode health|sessions|context|tokens|all,
                       --target dev|prod|both, --instance all|ocN, --days,
                       --summary; SSoT aus ansible/group_vars/vps-*.yml, 1 SSH
                       pro VPS via Tailscale, docker exec openclaw-<name> openclaw
                       <read-only-Befehle>; NIE schreibend)
- context_metrics.py – Transkript-JSONL-Auswertung (Input/Output-Tokens je Turn,
                       Cache-Hit-Anteil, Kontext-Groesse, wiederholte Bloecke,
                       Workspace-Einblendungen, Fehler/Latenz)

Workflow: .github/workflows/06-diagnose.yml (workflow_dispatch).
Doku: tools/diagnose/README.md + docs/workflows/diagnose.md.
"""

__version__ = "1.0.0"
