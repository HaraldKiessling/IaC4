# ADRs – Architecture Decision Records (IaC4)

> Eine Entscheidung pro ADR. Status: `Vorgeschlagen` → (Harald-Entscheidung) → `Akzeptiert` → ggf. `Superseded`.
> Konvention: `ADR-NNNN-kurzname.md`, Nummern fortlaufend.
> **Review:** 5W-Prüfung (AGENTS.md P3) + Konsistenz-Check durch 🏗️ Architect (2026-07-31) — Befunde vollständig eingearbeitet (Worst-Case/Rollback, Supersedes, Quellen).
> **Neue ADRs ab 2026-07-31** ergänzen die Bestands-Entscheidungen in `docs/arc42/09` (ADR-001..014) — dort per Verweis verlinkt.

| ADR | Thema | Status | Empfehlung |
|-----|-------|--------|------------|
| [0001](ADR-0001-docker-installation.md) | Docker-Installation | Vorgeschlagen | Eigene Tasks + offizielles Docker-Repo |
| [0002](ADR-0002-docker-zugriff-deploy-user.md) | Docker-Zugriff deploy-user | Vorgeschlagen | Keine docker-Gruppe; sudo |
| [0003](ADR-0003-image-pinning.md) | Image-Versionierung | Vorgeschlagen | SemVer-Pinning in group_vars |
| [0004](ADR-0004-https-tailscale-serve.md) | HTTPS-Strategie | Vorgeschlagen | Tailscale Serve (443→80); superseded LE-Bestand |
| [0005](ADR-0005-traefik-dashboard.md) | Traefik-Dashboard | Vorgeschlagen | Sicherer Router auf api@internal + Auth |
| [0006](ADR-0006-traefik-logging.md) | Traefik-Logging | Vorgeschlagen | accessLog JSON→stdout + json-file-Rotation |
| [0007](ADR-0007-ollama-exposition.md) | Ollama-Exposition | Vorgeschlagen | Host-Port 11434 + UFW-CGNAT |
| [0008](ADR-0008-ollama-ressourcenlimits.md) | Ollama-Limits | Vorgeschlagen* | 2C/4G; *VPS-Spec-Frage an Harald offen |
| [0009](ADR-0009-ollama-embedding-modell.md) | Embedding-Modell | Vorgeschlagen | nomic-embed-text (nur ZooCode; Qdrant bleibt 3072d) |
| [0010](ADR-0010-service-deploy-workflow.md) | Deploy-Workflow | Vorgeschlagen | Ein Workflow + Playbook-Selektion |

**Offene Punkte vor Akzeptanz:**
1. Harald: VPS-Spec bestätigen (ADR-0008)
2. Harald: HTTPS-Certificates in Tailscale-Admin-Konsole aktivieren (ADR-0004, Blocker Phase 4)
3. Harald: Entscheidung je ADR (Akzeptieren/Ändern)
