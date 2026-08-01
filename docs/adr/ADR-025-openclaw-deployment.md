# ADR-025: OpenClaw-Deployment-Form (Docker-Container, Multi-Instanz)

- **Status:** Angenommen (Accepted, 2026-08-01; Revision der Vorgängerversion vom 2026-07-31)
- **Datum:** 2026-07-31 (revidiert 2026-08-01)
- **Kontext:** Migrationsplan Phase 5 – „OpenClaw" auf DEV. IaC3-Betrieb: OpenClaw lief nativ (ohne systemd → Vorfall 2026-07-16, 6h Downtime) und eine Rollen-Neuinstallation behielt **alte Konfigurationen** (IaC3-Lesson: Altlasten in `~/.openclaw`). Harald 2026-08-01: **Multi-Instanz**-Betrieb für Untersuchungen (mehrere Gateways, nicht Agents) + Recherche zu offizieller Ansible-/Docker-Installation.

## Entscheidungsfrage
Wie wird das OpenClaw-Gateway auf dem IaC4-VPS betrieben — und wie werden mehrere Instanzen parallel betrieben?

## Faktenlage (geprüft 2026-08-01)
- **openclaw-ansible** (v2.0.0): installiert das Gateway **host-based** (Node/pnpm + systemd), Docker nur als Sandbox-Backend. Es gibt **keine** offizielle „Ansible + Docker-Gateway"-Kombination.
- **Offizieller Docker-Weg** existiert: `ghcr.io/openclaw/openclaw` (gepinnte Version-Tags) + Compose + Volumes (`install/docker`), Setup via `scripts/docker/setup.sh`, ClawDock-Helfer.
- **IaC3-Lesson:** Host-Installation hinterlässt Konfig-Altlasten bei Reinstall → Container-Instanz mit explizitem Config-Volume = sauberer Reinstall (Container/Volume neu).

## Optionen

### A: Nativ (Host) + systemd (Vorgänger-Empfehlung)
- Wie bisher: Node 24 via NodeSource, Installer, systemd-Unit (Hardening-Muster openclaw-ansible).
- **Nachteile (heute entscheidend):** Altlasten-Problem aus IaC3 bleibt (Host-`~/.openclaw`, pnpm-Global-State); Multi-Instanz = mehrere User/Home-Dirs + Units (fummelig); Host-Angriffsfläche (Node/pnpm).

### B: Docker-Container, gepinnt, Multi-Instanz — EMPFEHLUNG (neu)
- Pro Instanz: **ein Container** (`ghcr.io/openclaw/openclaw:<version>`, ADR-017-Pin) + **ein Config-Volume** (Host-Bind-Mount `/srv/openclaw/<name>/config` mit `openclaw.json` = SSoT) + **ein Workspace** (`/srv/openclaw/<name>/workspace`).
- Ports binden nur an **localhost**; **Tailscale Serve terminiert TLS** (`--https=<port>`, beliebige Ports im Tailnet, heute verifiziert) → `https://<fqdn>:<port>/`.
- Container im **traefik-network** → Ollama/Qdrant via Docker-DNS (`http://ollama:11434`, `http://qdrant:6333`); **kein `host.docker.internal`** nötig (alle Dienste containerisiert).
- **Memory:** `memory.backend: qmd` = eingebautes Default-Backend (dateibasiert, kein Qdrant nötig – belegt durch laufende lokale Instanz). Qdrant-Anbindung (Collection `zoocode-3072d`) ist bewusst später (Migrationsplan B11); Docker-DNS `http://qdrant:6333` steht dafür bereit.
- Multi-Instanz: Liste `openclaw_instances` in group_vars (OC1/OC2/OC3), Ansible-Loop erzeugt Container + Config + Serve.
- **Reinstall = Container + Volume neu** → keine Altlasten (löst IaC3-Problem).
- **Worst-Case:** Image-Update defekt → Container-Rollback via alten Pin; Volumes bleiben; kein Host-Schaden.
- **Update-Pfad:** Pin-Variable ändern → Deploy (`pull: always` + Recreate); Gateway-interne Updates (`openclaw update`-Äquivalent) möglich.

### C: openclaw-ansible als Abhängigkeit
- Verworfen (wie bisher): überschreibt IaC4-Design (deploy-user, Firewall-Konzept, OAuth-Workflows), host-based, keine Multi-Instanz-Struktur. Nur als Muster.

## Empfehlung
**Option B** – Docker-Container (gepinnt, ADR-017), Multi-Instanz über `openclaw_instances`-Liste, TS-Serve-TLS, Bind-Mounts unter `/srv/openclaw/<name>/`, Docker-DNS zu Ollama/Qdrant. Umsetzung als `roles/openclaw-gateway` (Loop über Instanzen, `enabled`-Flag für geplante Instanzen wie OC3).

## Konsequenzen
- Rolle `openclaw-gateway`: Container-Deploy pro Instanz (Compose-Template, openclaw.json.j2, Health-Wait, Serve-Task)
- Instanz-Struktur: OC1 (Default, WebUI+Telegram+Memory+WebSearch+LLM), OC2 (zusätzlich Agents orchestrator/architect/reviewer/engineer), OC3 (DEV: aktiv als Best-Practice-Referenz seit 2026-08-01, RFC 01-oc2-oc3-benchmark; PROD: disabled bis Benchmark-Abschluss)
- Secrets je Instanz als GH-Secrets (`OC<n>_TELEGRAM_BOT_TOKEN`, `OC<n>_LLM_API_KEY`, `OC<n>_WEBSEARCH_API_KEY`); Workflow reicht sie als env durch
- Kein Host-Node/pnpm mehr; alte native Rolle ersetzt
- BDD: `openclaw.bdd.ps1` (Health je Instanz via HTTPS, Ports von außen dicht, Serve-Routen)
- arc42/07: OpenClaw als Container, Ports 18789/18790/18791 nur Tailnet

## Referenzen
- <https://docs.openclaw.ai/install/docker>
- <https://docs.openclaw.ai/install/ansible> (host-based, Stand 2026-08-01)
- <https://github.com/openclaw/openclaw-ansible> (v2.0.0)
- IaC3-Lesson (2026-07-16/18): Prozess-Management + Altlasten bei Reinstall
