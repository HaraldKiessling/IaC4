# ADR-Detailblätter (IaC4)

> **SSoT:** Alle Architekturentscheidungen werden in `docs/arc42/09_architekturentscheidungen.md` geführt (Tabelle ADR-001..024).
> Diese Dateien sind die **Detailblätter** zu den Entscheidungen ab 2026-07-31 (ADR-015..024, Docker/Traefik/Ollama) — mit Optionen, fachlichen Auswirkungen, Evidenz, Worst-Case/Rollback.
> Status: `Vorgeschlagen` → (Harald-Entscheidung) → `Akzeptiert` → ggf. `Superseded`.
> **Review:** 5W-Prüfung (AGENTS.md P3) + Konsistenz-Check durch 🏗️ Architect (2026-07-31) — Befunde vollständig eingearbeitet (Worst-Case/Rollback, Supersedes, Quellen).

| ADR (arc42/09) | Detail | Thema | Status | Empfehlung |
| --- | --- | --- | --- | --- |
| ADR-015 | [015](ADR-015-docker-installation.md) | Docker-Installation | Vorgeschlagen | Eigene Tasks + offizielles Docker-Repo |
| ADR-016 | [016](ADR-016-docker-zugriff-deploy-user.md) | Docker-Zugriff deploy-user | Vorgeschlagen | Keine docker-Gruppe; sudo |
| ADR-017 | [017](ADR-017-image-pinning.md) | Image-Versionierung | Vorgeschlagen | SemVer-Pinning in group_vars |
| ADR-018 | [018](ADR-018-https-tailscale-serve.md) | HTTPS-Strategie | Vorgeschlagen | Tailscale Serve (443→80); superseded LE-Bestand |
| ADR-019 | [019](ADR-019-traefik-dashboard.md) | Traefik-Dashboard | Vorgeschlagen | Sicherer Router auf api@internal + Auth |
| ADR-020 | [020](ADR-020-traefik-logging.md) | Traefik-Logging | Vorgeschlagen | accessLog JSON→stdout + json-file-Rotation |
| ADR-021 | [021](ADR-021-ollama-exposition.md) | Ollama-Exposition | Vorgeschlagen | Host-Port 11434 + UFW-CGNAT |
| ADR-022 | [022](ADR-022-ollama-ressourcenlimits.md) | Ollama-Limits | Vorgeschlagen* | 2C/4G; *VPS-Spec-Frage an Harald offen |
| ADR-023 | [023](ADR-023-ollama-embedding-modell.md) | Embedding-Modell | Vorgeschlagen | nomic-embed-text (nur ZooCode; Qdrant bleibt 3072d) |
| ADR-024 | [024](ADR-024-service-deploy-workflow.md) | Deploy-Workflow | Vorgeschlagen | Ein Workflow + Playbook-Selektion |

**Offene Punkte vor Akzeptanz:**
1. Harald: VPS-Spec bestätigen (ADR-022)
2. Harald: HTTPS-Certificates in Tailscale-Admin-Konsole aktivieren (ADR-018, Blocker Phase 4)
3. Harald: Entscheidung je ADR (Akzeptieren/Ändern)
