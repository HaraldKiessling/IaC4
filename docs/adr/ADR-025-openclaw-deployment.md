# ADR-025: OpenClaw-Deployment-Form (nativ/systemd vs. Docker-Container)

- **Status:** Vorgeschlagen (Proposed)
- **Datum:** 2026-07-31
- **Kontext:** Migrationsplan Phase 5 – „OpenClaw Minimal" auf DEV (Gateway + Memory + WebSearch). IaC3-Betrieb: OpenClaw lief **nativ**, aber als Standalone-Prozess ohne systemd (Vorfall 2026-07-16: 6h Downtime durch fehlende Prozess-Verwaltung). IaC4 baut parallel eine Docker-Plattform (ADR-015..024) für Traefik/Ollama/Qdrant/code-server. Frage: Läuft OpenClaw selbst als Container oder nativ?

## Entscheidungsfrage
Wie wird das OpenClaw-Gateway auf dem IaC4-VPS betrieben?

## Optionen

### A: Nativ (Host) + systemd mit Hardening — EMPFEHLUNG (openclaw-ansible-Muster)
- **Fachliche Auswirkungen:** OpenClaw läuft direkt auf dem Host als systemd-Service mit Hardening (`NoNewPrivileges`, `PrivateTmp`, unprivilegierter Service-User, Auto-Start/Restart). Das ist der **von OpenClaw dokumentierte Produktivweg** für VPS-Deployments. Docker auf dem Host bleibt als **Sandbox-Backend** nutzbar (`agents.defaults.sandbox`), ohne das Gateway zu containerisieren. Ollama/Qdrant direkt via `localhost:11434`/`localhost:6333` erreichbar (kein `host.docker.internal` nötig). Update-Pfad: Standard-Installer (`install/updating`), idempotent. Voraussetzung: Node 24 (NodeSource-Repo; Ubuntu-apt-Node 18 reicht nicht).
- **Zukunft:** openclaw-ansible als Referenz für Härtungs-Updates; Sandbox-Ausbau ohne Gateway-Umbau möglich; konsistent mit arc42/07 (Host-Process openclaw, Port 18789 nur Tailscale).

### B: Docker-Container (`ghcr.io/openclaw/openclaw`, gepinnt)
- **Fachliche Auswirkungen:** Isoliertes Image (non-root `node`-User, `tini` als PID 1), Reproduzierbarkeit via Image-Tag (vgl. ADR-017). Aber: OpenClaw-Doku positioniert Docker explizit als „optional … isolated, **throwaway** gateway environment or a host without local installs"; Setup-Flow (`.env`-Sync, Compose, Volumes `OPENCLAW_CONFIG_DIR`/`WORKSPACE_DIR`/`AUTH_PROFILE_SECRET_DIR`), Ollama-Zugriff bräuchte `host.docker.internal`-Mapping; Container-Restart-Politik + Volume-Persistenz = zusätzliche Betriebspunkte; Sandbox-Docker-Socket-Frage (nie Host-Socket in Sandbox-Container mounten).
- **Zukunft:** Sinnvoll für Wegwerf-/Test-Umgebungen; für den Dauerbetrieb des zentralen Gateways mehr Komplexität ohne fachlichen Gewinn.

### C: `openclaw-ansible`-Playbook direkt als Abhängigkeit
- **Fachliche Auswirkungen:** Fertiges Playbook (eigener `openclaw`-User, UFW-Regeln, Tailscale). Aber: externe Repo-Abhängigkeit (Supply-Chain, Update-Zyklus fremd), überschreibt IaC4-Design (deploy-user, Firewall-Konzept R1-R9, Tailscale-OAuth-Workflows) → Konflikt mit bestehenden IaC4-Entscheidungen.
- **Zukunft:** Nicht kompatibel mit IaC4-SSoT; nur als **Referenz/Muster** für die eigene Rolle sinnvoll.

## Evidenz
- OpenClaw-Docs `install/ansible`: „The gateway runs directly on the host, not in Docker. Agent sandboxing is optional; this playbook installs Docker because it is the default sandbox backend."; systemd-Hardening-Liste; Node-Anforderung (22.22.3+/24.15+/25.9+, Node 24 empfohlen)
- OpenClaw-Docs `install/docker`: „Docker is optional. Use it for an isolated, throwaway gateway environment"; `host.docker.internal`-Mapping für Host-Provider (Ollama/LM Studio); Persistenz-Details (Config/Workspace/Auth-Secret-Verzeichnisse)
- IaC3-Betriebserfahrung: nativ ohne systemd → Vorfall 2026-07-16 (6h Downtime); Lehre: Prozess-Management ist Pflicht

## Empfehlung
**Option A** – OpenClaw nativ als systemd-Service, Hardening-Muster aus openclaw-ansible adaptiert (eigener Service-User, `NoNewPrivileges`, `PrivateTmp`), Docker bleibt Sandbox-Backend. Umsetzung als eigene `roles/openclaw-gateway` (IaC4-Struktur), Node 24 via NodeSource. Kein `openclaw-ansible`-Repo als Dependency (Option C nur Muster).

## Worst-Case / Rollback
- **Worst-Case 1:** Gateway-Update defekt → Gateway startet nicht.
  - **Rollback:** `~/.openclaw`-Backup vor Update (Config/Workspace/State), alten Installer-Stand wiederherstellen; `systemctl restart openclaw`; kein Netzwerk-/Lockout-Risiko (Port 18789 Tailscale-only, UFW unverändert).
- **Worst-Case 2:** systemd-Unit-Hardening zu strikt (Service startet nicht).
  - **Rollback:** Unit-Anpassung (z.B. `PrivateTmp` deaktivieren), `systemctl daemon-reload && restart`; BDD-Check `systemctl is-active openclaw`.
- **Gegenmaßnahme:** Post-Deploy-Verifikation (Phase 7): `systemctl status` + `/healthz`-Check via Tailscale; Config in Git (SSoT), Laufzeit-Daten auf dem VPS.

## Konsequenzen
- `roles/openclaw-gateway` implementiert native Installation (Installer + systemd-Unit), NICHT Container
- Node 24 via NodeSource-Repo (Baseline-abhängig)
- Ollama-/Qdrant-Integration über `localhost` (ADR-021/ADR-011-kompatibel); kein `host.docker.internal`
- Sandbox-Option (`agents.defaults.sandbox`) später via Docker-Plattform (ADR-015) möglich
- P4: arc42/07 (Host-Process openclaw) bleibt korrekt; Migrationsplan Phase 5 referenziert diese ADR

## Referenzen
- https://docs.openclaw.ai/install/ansible
- https://docs.openclaw.ai/install/docker
- https://github.com/openclaw/openclaw-ansible
