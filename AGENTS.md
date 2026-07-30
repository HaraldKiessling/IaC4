# IaC4 – Agent Context

**Repository:** HaraldKiessling/IaC4
**Architektur:** arc42-light (Dokumentation in `docs/arc42/`)
**Branching:** Feature/BugFix → PR → DEV → PR → MAIN
**Leitprinzipien:** P1–P7 (siehe docs/arc42/01_einfuehrung_und_ziele.md)

## Wichtige Regeln
- Conventionelle Commits (`feat|fix|docs|chore|refactor|test(scope):`)
- Kein direkter Push auf main. Nur via PR.
- DEV-Deploy autonom (P7). MAIN/PROD-Deploy nur mit Haralds OK.
- P1: Evidenz – jede Behauptung braucht einen Beleg.
- P4: Living Docs – nach Code-Änderungen Doku prüfen.
- P6: Tech-Debt in docs/arc42/11_risiken_und_technische_schulden.md dokumentieren, nie verstecken.

## Repo-Struktur (Überblick)
```
.github/workflows/    → CI/CD (Baseline → Service → OpenClaw)
ansible/              → Playbooks + Rollen (Phase 1+2)
docs/arc42/           → arc42 Architekturdokumentation (DE)
services/             → Docker-Compose-Stacks
terraform/            → Tailscale-OAuth + ACLs
qa/                   → Quality-Gates + Testplan
```
