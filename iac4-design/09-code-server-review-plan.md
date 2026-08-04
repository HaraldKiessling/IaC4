# Review-Plan: Code-Server auf DEV (Issue #65)

> **Status:** Vorschlag (Review ausstehend)
> **Datum:** 2026-08-04 · **Autor:** ✨ Nova (Orchestrator)
> **Bezug:** Issue #65, RFC 0012 (IaC3), ADR-017 (Pinning), ADR-019 (Router-Muster), qa/bdd-testkonzept.md, docs/plans/iac4-migration.md (Phase 3/4)
> **Zweck:** Definiert die Prüfkriterien und den Ablauf des Reviews der Code-Server-Umsetzung, BEVOR sie auf DEV deployed und abgenommen wird.

---

## 1. Review-Objekt (Umsetzungs-PR zu Issue #65)

| # | Artefakt | Pfad | Review-Fokus |
|---|---|---|---|
| R1 | Rolle Code-Server | `ansible/roles/code-server/` (defaults, tasks, templates) | Pinning, Secrets, Idempotenz, kein docker.sock |
| R2 | Router-Konfiguration | `docker-compose.yml.j2` (Traefik-Labels) | Host+PathPrefix `/code`, stripprefix, Priority, Port 8443 |
| R3 | Secrets-Fluss | `ansible/group_vars/all.yml` + GH-Secrets + Workflow-Env-Mapping | `CODE_SERVER_PASSWORD`/`SUDO_PASSWORD` von GH-Secret → Container-Env, kein Default-Credential |
| R4 | Aktivierung | `ansible/playbooks/04-services.yml` | code-server-Rolle aktiv, Reihenfolge (nach ollama/qdrant) |
| R5 | Workspace | Host-Bind `/workspace`, `DEFAULT_WORKSPACE` | frisch auf DEV, kein docker.sock |
| R6 | BDD-Tests | `scripts/bdd/code-server.bdd.ps1` + `qa/bdd-testkonzept.md` | C1 (200 + Auth), C2 (Port dicht von außen) |
| R7 | Doku (P4/Living-Docs) | Migrationsplan, arc42 (bei Bedarf) | „bewusst offen" → deployed, ADR-Bezüge |

## 2. Prüfkriterien (evidenzbasiert, Issue #66)

### 2.1 Pinning (ADR-017, P1)
- **MUSS:** Image = `lscr.io/linuxserver/code-server:{{ code_server_version }}` — Variable in `group_vars/all.yml` (SSoT), **kein `latest`**
- **MUSS:** Aktueller Pin-Wert: `4.131.0-ls354` (code-server 4.131.0, Build 2026-07-30; Quelle: Docker-Hub-Metadaten, abgerufen 2026-08-04 via web_search) — ODER neuerer Stand mit Quellenangabe
- **SOLL:** Upgrade nur via Pin-Bump + PR (ADR-017 Konsequenzen), Release-Notes-Check
- **Prüfung:** `grep code_server_version ansible/group_vars/all.yml`; Template referenziert Variable, kein hartkodierter Tag

### 2.2 Router / Exposition (ADR-019-Muster, IaC3 RFC 0012 v0.3)
- **MUSS:** Rule = `Host(\`<fqdn>\`) && PathPrefix(\`/code\`)` + stripprefix `/code` + `priority=100` (IaC3-Muster, Bugfix 18)
- **MUSS:** `loadbalancer.server.port=8443` (intern; TLS-Terminierung durch Tailscale Serve — TS-TLS, Qdrant-Muster)
- **MUSS:** Kein Host-Port-Publish (kein `ports:` → `8443:8443`); Erreichbarkeit nur via Tailnet/Traefik-Netzwerk
- **MUSS:** UFW/DOCKER-USER: Port 8443 von außen dicht (BDD C2)
- **Prüfung:** Compose-Labels gegen IaC3-Referenz + ADR-019-Konsequenzen; `ss -tlnp` nach Deploy

### 2.3 Secrets (P1, sst.mdc, secrets.mdc)
- **MUSS:** `PASSWORD`/`SUDO_PASSWORD` aus `CODE_SERVER_PASSWORD`/`CODE_SERVER_SUDO_PASSWORD` (GH-Secrets, Env-Lookup wie `code_server_hostname`-Muster) — **kein** `changeme`-Fallback, Fail-Fast-Assert bleibt
- **MUSS:** Workflow `04-service-deploy.yml` mappt die Secrets in die Runner-Env (analog `DEV_OCx_*`-Muster)
- **MUSS:** Keine Secrets im Repo, in Logs oder PR-Body
- **Prüfung:** grep auf `changeme`/Klartext-Passwort; `gh secret list`; Template-Render-Test (Jinja2)

### 2.4 Security (Harald-Entscheidung 2026-08-01)
- **MUSS:** **KEIN** `/var/run/docker.sock`-Mount (auch nicht `:ro`) — Updates ausschließlich über Pin → Deploy-Workflow, Rollback = alten Pin
- **MUSS:** Kein `OPENAI_API_KEY`/`GH_TOKEN`/`GOOGLE_API_KEY`-Env (IaC3-Kompromiss entfällt — nur PASSWORD/SUDO/DEFAULT_WORKSPACE/TZ/PUID/PGID)
- **SOLL:** PUID/PGID explizit (1000), TZ Europe/Berlin (IaC3-Referenz)
- **Prüfung:** Diff gegen IaC3-Compose: jede entfernte Zeile begründet (docker.sock, API-Keys)

### 2.5 Idempotenz & Betrieb (Methodik Schritt 6)
- **MUSS:** 2. Lauf = 1. Lauf (kein Container-Recreate ohne Config-Drift; `docker_compose_v2 state: present`)
- **MUSS:** `restart: unless-stopped`, Named Volume `code-server-data` (Persistenz `/config`)
- **MUSS:** Health-Wait nach Start (Qdrant-Muster: uri-Check mit retries) — Ziel: `GET /code/` → 200
- **Prüfung:** Playbook 2× ausführen (DEV), Diff der Compose-Datei, `docker ps` stabil

### 2.6 BDD (qa/bdd-testkonzept.md)
- **C1:** `https://<fqdn>/code/` → HTTP 200 + Auth greift (Login-Seite/Passwort-Abfrage; TS-TLS, `curl -k --resolve` vom Runner, MagicDNS fehlt)
- **C2:** `http://<Public-IP>:8443/` → kein HTTP-Response (Timeout/Filtered, Wirkungs-Check wie D9)
- **C3 (optional):** `docker ps` → code-server `Up`, Image-Tag = Pin
- **C4:** Plugin-Installation möglich: `install-extension`-Helper vorhanden, `/config/extensions` existiert + beschreibbar (read-only-Check)
- **C5:** sudo für Benutzer aktiv (read-only): `abc` in sudoers (`getent group sudo`), `/config/custom-cont-init.d` existiert; Persistenz-Mechanismus dokumentiert
- **MUSS:** Feature-Skript `code-server.bdd.ps1` in `run-all.ps1` eingebunden, Testkonzept-Tabelle ergänzt
- **Prüfung:** BDD-Lauf via Workflow `04-bdd-tests.yml` (target=dev) grün

### 2.7 Doku (P4/Living-Docs, Issue #66 A.4)
- **MUSS:** Migrationsplan: Checkbox „code-server: Tasks implementieren" + „Code-Server auf DEV deployen" abgehakt
- **MUSS:** `.env.example` enthält CODE_SERVER_*-Zeilen (existiert bereits — prüfen auf Drift)
- **SOLL:** arc42/08 oder ADR-Referenz: code-server-Exposition dokumentiert (falls neue Entscheidung: ADR)
- **Prüfung:** grep auf veraltete „deaktiviert"-Kommentare in 04-services.yml

### 2.8 Plugin-/Extension-Installation (Pflicht-Anforderung, Harald 2026-08-04)
- **MUSS:** Nachträgliche Plugin-Installation über Code-Server-Mechanismen funktioniert:
  - Web-UI: Extensions-View → Install (landet in `/config/extensions`)
  - CLI: `install-extension <id>` (LinuxServer-Helper, `code-server --install-extension --extensions-dir /config/extensions`)
- **MUSS:** Extensions-Pfad = `/config/extensions` (persistent) — Named Volume `code-server-data:/config`; **kein** `--extensions-dir` auf `/app/...` oder HOME (nicht persistent, Pitfall laut LinuxServer-Doku)
- **MUSS:** Extensions überleben Container-Recreate/Image-Update (Pin-Bump) — Verifikation: Extension installieren → Recreate → noch da
- **SOLL:** Optional Auto-Install-Liste via `/config/custom-cont-init.d/` (executable, Shebang; LinuxServer-Mechanismus, IaC3 nutzte custom-cont-init.d)
- **SOLL:** BDD C4 (read-only): `/usr/local/bin/install-extension` existiert, `/config/extensions` existiert + beschreibbar für `abc` (`test -w`)
- **Hinweis:** Runtime-Abhängigkeiten von Extensions (z.B. python3, gcc) sind NICHT Teil der Plugin-Installation — ohne sudo im Container nicht nachinstallierbar; falls benötigt: Basis-Image-Erweiterung separat entscheiden (nicht im Issue-#65-Scope)
- **Prüfung:** Diff gegen IaC3-Compose (dort `custom-cont-init.d`-Mount + `.vsix`-Ordner); Vendor-Doku linuxserver.io (Extension-Installation) als Evidenz

### 2.9 Runtime-Dependencies & Benutzer-Update-Prozess (Pflicht, Harald 2026-08-04 12:09)
- **MUSS:** `SUDO_PASSWORD` gesetzt (Benutzer `abc` in sudoers) — Benutzer kann im Container-Terminal `apt-get install` für Plugin-Runtime-Deps ausführen und Update-/Wartungs-Prozesse starten
- **MUSS:** Persistenz über Container-Recreate/Image-Update (Pin-Bump): `/config/custom-cont-init.d/`-Skripte (root-owned, executable, Shebang) laufen bei jedem Start als root VOR code-server-Start — apt-Pakete aus der Writable-Layer überleben Recreate NICHT, Init-Skripte machen sie dauerhaft (LinuxServer-Mechanismus, [Doku](https://docs.linuxserver.io/general/container-customization/))
- **MUSS:** Benutzer-selbstbedienbar ohne Nova/PR: Mit sudo im Terminal legt der Benutzer eigene Init-Skripte in `/config/custom-cont-init.d/` an → wirken ab nächstem Start (kein docker.sock nötig)
- **MUSS:** Plugin-/Extension-Updates via Code-Server-Mechanismen (Extensions-UI/CLI) funktionieren und persistieren (`/config/extensions`)
- **DOKUMENTIERTE GRENZE:** In-Place-Update der code-server-Binaries (install.sh im Container) = von LinuxServer unsupported + nicht persistent (App liegt im Image) → Container-Image-Update ausschließlich via Pin-Workflow/Deploy (extern, kein docker.sock); Update-Hinweis in der UI ist reine Info
- **Security-Tradeoff (bewusste Entscheidung):** SUDO_PASSWORD = Root-Äquivalent im Container; Schaden begrenzt auf Container + `/workspace`-Bind; KEIN docker.sock → kein Host-Root (besser als IaC3-Kompromiss); Passwort als Env (docker inspect-sichtbar) → Rotation über Pin/Recreate möglich
- **Prüfung:** Diff gegen IaC3-Compose (dort docker.sock + custom-cont-init.d-Mount); Vendor-Doku linuxserver.io Container-Customization

## 3. Review-Ablauf (Methodik Schritt 6, Issue #37/#66)

1. **Autor ≠ Reviewer:** Umsetzung durch 🔧 Engineer (Branch `session-*/code-server-deploy`), Review durch 🔍 Reviewer + 🏗️ Architect (IaC3-Workspace, unabhängig)
2. **Evidenz-Pflicht:** Vendor-Docs (linuxserver.io code-server), Docker-Hub-Tags, ADR-017/019 lesen; keine Annahmen (R1–R5)
3. **Befund-Format:** K1–K3 (Merge-Blocker) vs. K4–K8; 5W, Alternativen (2–4), Button-Empfehlung
4. **Gate 1 (vor Merge):** CI grün + Review-Freigabe dokumentiert im PR-Thread (Signatur-Regel)
5. **Gate 2 (nach Deploy DEV):** BDD grün (C1/C2/C3), Verifikation via Workflow-Log (kein direkter VPS-Zugriff, Zugriffs-Design 2026-07-31)
6. **Abnahme:** Harald-Freigabe (Feature-Parität IaC3: `/code`, Passwort-Auth, Tailnet-only)

## 4. Referenzen & Evidenz

- Issue #65 (Anforderungen, Umfang, Zugriff: `https://vps-dev.tailcfea8a.ts.net/code/`)
- RFC 0012 (IaC3) + `services/code-server/docker-compose.yml` (IaC3-IST, docker.sock = zu entfernender Kompromiss)
- ADR-017 (Pinning, Option B), ADR-019 (Router/Exposition-Muster, Dashboard-Lektion: Serve strippt Mount-Prefixe → Host-Rule-Ansatz)
- Qdrant-Rolle (IaC4-Referenz: Pinning-Variable, Health-Wait, Serve-Muster)
- Web-Recherche 2026-08-04: linuxserver/code-server `latest` = 4.131.0-ls354 (Docker-Hub, multi-arch)
- Web-Recherche 2026-08-04: Extension-Installation/Persistenz (linuxserver.io Doku, coder FAQ): `/config/extensions`, `install-extension`-Helper, `custom-cont-init.d`; code-server hat KEIN Auto-Update (install.sh = offizieller Weg) — Updates nur via Image-Pull (ADR-017-konform)

## 5. Offene Fragen an Harald (falls beim Review unklar)

- ~~Q1~~ **REVIDIERT (Harald 2026-08-04, 12:09):** `SUDO_PASSWORD` **JA** — Benutzer muss Runtime-Dependencies für Plugins im Container installieren können (apt) und Update-Prozesse leichtgewichtig selbst starten können. Security-Tradeoff dokumentiert (§2.9): Container-Root, kein Host-Root (kein docker.sock), Schreibzugriff auf `/workspace`-Bind.
- Q2: Workspace-Inhalt auf DEV: frisch leer ok, oder bestimmte Projekte einbinden (nur `/workspace`-Bind)?
