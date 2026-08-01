# BDD-Testkonzept – IaC4

> **Status:** aktiv (ab 2026-07-31)
> **Scope:** Automatisierte Post-Deploy-Verifikation gegen IaC4-VPS (aktuell DEV)
> **Ausführung:** ausschließlich über GitHub Actions Runner (Workflow `04-bdd-tests.yml`) – kein direkter VPS-Zugriff von Workstations/Agents (Zugriffs-Design, 2026-07-31)

---

## 1. Zweck

Maschinelle, wiederholbare Verifikation des IaC4-Deploy-Zustands in **BDD-Form** (Given/When/Then). BDD-Tests sind die automatisierte Ergänzung zu:

- `qa/test-plan.md` (manuelle Checkliste)
- `scripts/verify-deployment.sh` (Smoke-Test, 4 Checks)

Ziel: Jede Phase des Deploy-Modells (0→2e→3) bekommt Feature-Skripte, die den **Ist-Zustand** des VPS gegen die **erwarteten Deploy-Ergebnisse** prüfen – mit maschinenlesbarem Pass/Fail und Logs als Evidenz.

## 2. Prinzipien

1. **BDD-Form:** Jedes Szenario folgt Given → When → Then (Sprache: Deutsch, Konsistenz mit Repo-Doku).
2. **Ausführung über GH Runner:** Der Runner joint das Tailnet (`tag:ci`), löst die VPS-Tailscale-IP per API auf und testet via SSH/API. Nie lokal, nie von Agent-Workstations.
3. **Read-only:** BDD-Tests verändern nichts am VPS (nur Abfragen: ssh, dpkg-query, timedatectl, swapon, Tailscale-API).
4. **Evidenz = Workflow-Log:** Das GH-Actions-Log ist die Verifikationsquelle (kein „glaube ich" – P1).
5. **Rot ist Evidenz:** Ein fehlgeschlagenes Szenario ist ein Befund (Deploy-Lücke **oder** Test-Lücke) und wird über den IaC4-Prozess (Issue/PR) behandelt – nicht wegdiskutiert.
6. **Deterministisch:** Secrets kommen aus GH-Secrets, IPs werden zur Laufzeit ermittelt – keine hartcodierten Werte im Test.

## 3. Testobjekte (aktueller Stand DEV, 2026-07-31)

| Phase | Workflow | Auf dem VPS deployt? | BDD-Feature |
| --- | --- | --- | --- |
| 2a+2b | `02-tailscale-bootstrap.yml` | ✅ ja (Tailscale-Join, tag:ia4, SSH-Restrict) | `tailscale-bootstrap.bdd.ps1` |
| 1 | `03-baseline-deploy.yml` | ✅ ja (System-Baseline) | `system-baseline.bdd.ps1` |
| 2c | `03-docker-traefik.yml` | ❌ nein (Deploy Phase 4 offen); Feature implementiert (PR ADR-015..024) | `docker-traefik.bdd.ps1` (D1-D8) |
| 2d | `04-services.yml` (ollama, qdrant; code-server deaktiviert bis Abnahme) | ❌ nein (Deploy Phase 4 offen); Ollama- **und** Qdrant-Feature implementiert | `docker-traefik.bdd.ps1` (O1-O3), `qdrant.bdd.ps1` (Q1-Q4) |
| 2e | Phase-3-Workflow (geplant) | ❌ nein (OpenClaw) | `openclaw.bdd.ps1` (geplant) |

## 4. Testkatalog (Features & Szenarien)

### Feature: Tailscale-Bootstrap (`tailscale-bootstrap.bdd.ps1`)

| # | Szenario | Then-Assertion |
| --- | --- | --- |
| T1 | SSH via Tailscale erreichbar | Exit 0, Tailscale-Node-Name (`Self.DNSName`) = `vps-<target>` (OS-Hostname ist `ubuntu` – nicht Soll-Quelle), `tailscale ip -4` = `100.x` |
| T2 | Public-SSH geschlossen (SSH-Restrict) | SSH auf Public-IP:22 schlägt fehl |
| T3 | Node online + korrekt getaggt | Tailscale-API: Node existiert, online via `lastSeen`-Frische (< 10 min, Proxy – `online` ist kein gültiges Listen-Feld), Tags enthalten `tag:ia4` (Option A, Exact-Match; Re-Tag durchgeführt 2026-07-31) |
| T4 | Tailscale-Infrastruktur | `NetfilterMode` = 2 (= on, ts-input aktiv), WireGuard lauscht auf UDP 41641, `tailscale0`-Interface existiert |

### Feature: System-Baseline (`system-baseline.bdd.ps1`)

| # | Szenario | Then-Assertion |
| --- | --- | --- |
| B1 | Baseline-Pakete installiert | `dpkg-query` → `install ok installed` für curl, wget, htop, ufw, unzip, fail2ban |
| B2 | Zeitzone korrekt | `timedatectl` → `Europe/Berlin` |
| B3 | Swap aktiv | `swapon --show` enthält `/swapfile` |
| B4 | deploy-user-Sudo funktioniert | `sudo -n true` → Exit 0 |
| B5 | UFW aktiv, öffentliches SSH blockiert | `ufw status verbose`: Status active, keine generische `22/tcp ALLOW IN Anywhere`-Regel (v4 **und** v6), `22/tcp on <public_iface> DENY IN` vorhanden (echtes ufw-Format, v4+v6), CGNAT-Allow `100.64.0.0/10` vorhanden (Defense-in-Depth) |

### Feature: Docker/Traefik/Ollama (`docker-traefik.bdd.ps1`, implementiert 2026-07-31)

| # | Szenario | Then-Assertion |
| --- | --- | --- |
| D1 | Docker Engine + Compose installiert (ADR-015) | `docker version` Server-Version, `docker compose version` v2 |
| D2 | deploy-user NICHT in docker-Gruppe (ADR-016) | `id -nG` enthält kein `docker` |
| D3 | Shared Network (ADR-015) | `docker network ls` enthält `traefik-network` |
| D4 | Traefik-Container läuft (ADR-017/018) | `docker ps` → `Up`, Image `traefik:` |
| D5 | HTTP-only: kein 443-Listener (ADR-018) | `ss -tln` zeigt kein `:443` |
| D6 | Dashboard-Auth greift (ADR-019) | `curl :8080/dashboard/` ohne Auth → HTTP 401 |
| D7 | Firewall Service-Ports: UFW-CGNAT (R7-R9) + DOCKER-USER (R10/R11) | `ufw status verbose` → `ALLOW FROM 100.64.0.0/10` je Port; `iptables -S DOCKER-USER` → CGNAT-ACCEPT + interface-gebundener DROP für 80,8080,11434,6333,6334 |
| D8 | Tailscale Serve aktiv (ADR-018) | `tailscale serve status` → `localhost:80` |
| O1 | Ollama-API erreichbar (ADR-021) | Container `Up`, `GET /api/tags` → 200 |
| O2 | Modell pre-warmed (ADR-023) | `ollama list` enthält `nomic-embed-text` |
| O3 | Embedding schnell (ADR-023) | `POST /api/embeddings` < 2s (Pre-Warm-Wirkung) |
| D9 | Service-Ports von außen NICHT erreichbar (Wirkungs-Check, K1-1) | Runner → `http://<Public-IP>:80/11434/6333` → kein HTTP-Response (Timeout/Filtered) |

### Feature: Qdrant (`qdrant.bdd.ps1`, implementiert 2026-08-01)

| # | Szenario | Then-Assertion |
| --- | --- | --- |
| Q1 | HTTPS 6333 antwortet (TS-TLS-Terminierung) | Runner → `curl -sk --resolve <fqdn>:6333:<ts-ip> https://<fqdn>:6333/` → HTTP 200 |
| Q2 | Zertifikat passt zum MagicDNS-Namen | Runner → `openssl s_client -connect <ts-ip>:6333` → Subject enthält `<fqdn>` (Tailscale-CA) |
| Q3 | Health-Endpoint ok (Qdrant intern HTTP) | `GET http://localhost:6333/healthz` → 200, Body `healthz check passed` (nicht `/health` → 404) |
| Q4 | Collection `zoocode-3072d` existiert (RFC 0034b/#195) | `GET /collections/zoocode-3072d` → status ok, `3072`, `Cosine` |
| Q5 | gRPC-Port 6334 erreichbar (TS-TCP-Forward) | Runner → TCP-Connect `100.x:6334` erfolgreich (WireGuard-verschlüsselt, kein TLS) |

### Geplant (sobald Services deployt sind)
- **CodeServer:** HTTP 200 auf Hostname, Passwort-Auth greift (401 ohne / 200 mit)
- **OpenClaw:** Gateway `/health` → `{"ok":true}`, Agents erreichbar

## 5. Ausführung

- **Workflow:** `04-bdd-tests.yml` (`workflow_dispatch`, Input `target: dev|prod`)
- **Ablauf:** Runner → Tailnet-Join (tag:ci) → IP-Ermittlung (Tailscale-API) → SSH-Key (GH-Secret) → `pwsh run-all.ps1`
- **Skripte:** `scripts/bdd/` – `bdd-lib.ps1` (Helfer), `*.bdd.ps1` (Features), `run-all.ps1` (Aggregator)
- **Exit-Codes:** 0 = alle Szenarien grün; 1 = mind. ein Szenario rot (Workflow failt sichtbar)
- **Timeout:** Job 15 min (SSH-ConnectTimeout 10 s, Public-Port-Test 5 s)
- **Voraussetzungen (Secrets):** `SSH_KEY`, `VPS_USER`, `TAILSCALE_OAUTH_CLIENT_ID/SECRET` (OAuth-only – Access-Token wird aus dem Client-Paar erzeugt, kein API-Key), `TAILSCALE_TAILNET`, `VPS_DEV_PUBLIC_IP` (dev) / `VPS_PROD_PUBLIC_IP` (prod)

## 6. Konventionen

- Dateiname: `<feature>.bdd.ps1` (IaC3-Konvention), UTF-8 ohne BOM, `$ErrorActionPreference = "Stop"` nicht in Feature-Skripten (Assertions fangen Fehler als Then)
- Output: `Given/When/Then`-Zeilen mit ✅/❌, Zusammenfassung (Pass/Fail-Liste) am Ende
- Neue Features: Testkatalog hier erweitern **und** Skript ergänzen (P4-Living-Docs)
- Signatur: BDD-Ausführungen/Kommentare auf GitHub mit Rollen-Signatur (Issue #37)

## 7. Fehlschlag-Workflow (Befund)

1. Roter Szenario → Workflow-Log = Evidenz (welches Then, welcher Detail-Output)
2. Unterscheidung: Deploy-Lücke (VPS weicht vom Soll ab) vs. Test-Lücke (Assertion/Umgebung falsch)
3. Behandlung über IaC4-Prozess: Fix im Repo (Branch → PR → Review → Merge → Deploy), **nie** direkt am VPS
4. Bekannte Grenzen dokumentieren (z. B. T2 abhängig von UFW-Zustand; T2-Negativtest: jeder Nicht-Null-Exit inkl. Netz-/DNS-Fehler gilt als „Port dicht“ – False-Positive möglich, für Smoke akzeptiert; B4 abhängig von sudoers)

## 8. Integration Quality Gates

- BDD-Lauf gehört zu „DEV grün": `qa/quality-gates.md` wird um „✅ BDD-Tests grün (Workflow 04, target=dev)" ergänzt
- Nach jedem Deploy (02/03/Phase 3) ist ein BDD-Lauf die Verifikation (Post-Deploy-Verifikation, Phase 7 Migrationsplan)
- Manuelle Checkliste (`qa/test-plan.md`) bleibt für explorative Tests; BDD ersetzt sie nicht, sondern sichert die Regression
