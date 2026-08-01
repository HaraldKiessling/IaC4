# ADR-019: Traefik-Dashboard/API-Exposition

- **Status:** Angenommen (Accepted, 2026-08-01 – Auth-Mechanismus präzisiert: IP-Allowlist statt BasicAuth)
- **Datum:** 2026-07-31 (Update 2026-08-01)
- **Kontext:** IaC3 hielt das Dashboard Docker-Netzwerk-intern (Port 8080, `api.insecure=true`, kein Host-Port-Publish) – faktisch nur via `docker exec` erreichbar. IaC4 braucht eine klare Entscheidung: Observability (Routing einsehen) vs. Angriffsfläche.

## Entscheidungsfrage
Wie wird das Traefik-Dashboard/API in IaC4 exponiert?

## Optionen

### A: `api.insecure=true`, Port 8080 nicht published (IaC3-IST)
- **Fachliche Auswirkungen:** Kein externer Zugriff (maximal `docker exec traefik curl :8080`), aber: Traefik-Doku bewertet `api.insecure` explizit als „not recommended, testing only" – es umgeht Middlewares und exponiert alle Konfigurationsdaten unauthentifiziert auf dem EntryPoint. Sicher nur durch fehlendes Port-Publishing; jeder zukünftige Port-Publish-Fehler = offene Admin-Oberfläche.
- **Zukunft:** Hohe Fehlertoleranz-Last auf dem Operator (darf Port nie publishen).

### B: Sicheres Dashboard: `api.dashboard=true` (ohne insecure) + eigener Router auf `api@internal` mit Auth-Middleware — EMPFEHLUNG
- **Fachliche Auswirkungen:** Dokumentierter Traefik-Weg: eigener EntryPoint `dashboard` (Port 8080) mit Router `service=api@internal`, Auth via BasicAuth (Credentials aus GH-Secret/.env) und/oder IP-Allowlist (CGNAT). Zusätzlich UFW-Regel: 8080 nur aus `100.64.0.0/10`. Dashboard bleibt Tailscale-only, aber **bedienbar** (Routing/Fehler selbst einsehbar). Metrics-Endpoint (`/metrics`) ist davon getrennt und wird erst bei Monitoring-Bedarf (Phase 6) ergänzt.
- **Zukunft:** Bei Bedarf über Serve-Route erreichbar; Auth ist dann bereits vorhanden; Observability-Basis für Monitoring (Phase 6).

### C: Dashboard komplett deaktivieren (`api.dashboard=false`)
- **Fachliche Auswirkungen:** Minimale Angriffsfläche, aber keine Web-Observability; Fehleranalyse nur über Logs/`docker exec`.
- **Zukunft:** Monitoring-Ausbau (Tech-Debt) müsste komplett neu aufgebaut werden.

## Evidenz
- Traefik-Doku (API/Dashboard): insecure-Modus „not recommended", „testing purpose only"; produktiver Weg = Router auf `api@internal` + Auth-Middleware; Pfade `/api` und `/dashboard` müssen gematcht werden
- Security-Analysen: `api.insecure` ohne Auth = Exposition von Routen/Service-Topologie

## Empfehlung
**Option B** – Dashboard sicher exponiert (Router auf `api@internal`, UFW-Restrict CGNAT, Port 8080 nur Tailnet). Kein `api.insecure`.

**Auth-Mechanismus (Update 2026-08-01):** **IP-Allowlist** (`ipWhiteList`: `100.64.0.0/10` + `127.0.0.1/8`, IaC3-Muster `auth-tailscale-only`) statt BasicAuth. Begründung: Nutzbarkeit im Browser ohne Credential-Verteilung; Schutz = Tailnet (zusätzlich UFW-CGNAT). BasicAuth bleibt als Rollback-Option (GH-Secret `TRAEFIK_DASHBOARD_AUTH` existiert weiter, wird nur nicht mehr referenziert).

## Worst-Case / Rollback (Pflicht: Expositions-Entscheidung)
- **Worst-Case 1:** BasicAuth-Credentials leaken (z.B. in Log/PR) → Unbefugte können Dashboard-Konfiguration lesen.
  - **Rollback:** Credentials rotieren (GH-Secret/.env), Container-Restart; `api.insecure` bleibt in jedem Fall aus.
- **Worst-Case 2:** Versehentliches Port-Publish von 8080 (Config-Fehler) → Dashboard im Netz erreichbar.
  - **Rollback:** UFW-Regel 8080 entfernen (`ufw delete allow from 100.64.0.0/10 to any port 8080`) + Port-Mapping entfernen; Container-Recreate.
- **Gegenmaßnahme:** UFW-Regel + BDD-Check („8080 nur aus CGNAT erreichbar", `ss -tlnp`-Prüfung); Dashboard-Router erfordert Auth (defense-in-depth).

## Konsequenzen
- Static Config: `api.dashboard: true` (kein insecure), eigener `entryPoints.dashboard` (Port 8080)
- Dynamic Config (File-Provider): Router + `ipWhiteList`-Middleware (`100.64.0.0/10`, `127.0.0.1/8`)
- Zugriff: `https://<fqdn>/dashboard/` via Tailscale-Serve-Mounts `/dashboard` + `/api` → `:8080` (kein 404: Router matcht nur am `dashboard`-EntryPoint)
- UFW: `allow from 100.64.0.0/10 to any port 8080` (Firewall-Konzept R8, siehe Doku-PR)
- Metrics-Entrypoint erst bei Monitoring-Bedarf (Phase 6), nicht jetzt

## Referenzen
- <https://doc.traefik.io/traefik/operations/dashboard/>
- <https://doc.traefik.io/traefik/reference/install-configuration/api-dashboard/>
- <https://doc.traefik.io/traefik/observability/access-logs/>
