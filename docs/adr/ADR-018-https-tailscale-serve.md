# ADR-018: HTTPS-Strategie (Tailscale Serve vs. HTTP-only)

- **Status:** Vorgeschlagen (Proposed)
- **Datum:** 2026-07-31
- **Kontext:** IaC3 entschied sich in RFC 0029 v0.2/v0.3 für „Traefik HTTP-only + HTTPS-Termination via Tailscale Serve (443 → localhost:80)". IaC4 übernimmt das Grundmodell Tailscale-only (Firewall-Konzept), muss die HTTPS-Frage für die Zielarchitektur (Web-Services: code-server, Qdrant-UI, später OpenClaw) neu bewerten.
- **Supersedes (IaC4-Bestand, veraltet):** `docs/arc42/05` („traefik → Reverse Proxy + LetsEncrypt"), `docs/arc42/07` („Traefik (HTTP/S) | Public (80/443) | LetsEncrypt"), arc42-K10-Ziel „Kein öffentlicher Port außer Traefik (80/443)", LE-ACME-Reste in `ansible/roles/traefik/templates/docker-compose.yml.j2` (Port `443:443`), `ansible/group_vars/all.yml` (`traefik_acme_email`), Netzwerk-Name `traefik-public`. Diese ADR ersetzt alle diese Annahmen (P4-Delta unten).

## Entscheidungsfrage
Wie erhalten Browser-Clients im Tailnet HTTPS-Zugriff auf die Web-Services?

## Optionen

### A: Tailscale Serve (443 → localhost:80) — EMPFEHLUNG (IaC3-Muster)
- **Fachliche Auswirkungen:** Tailscale stellt automatisch gültige Let's-Encrypt-Zertifikate für `*.ts.net`-Namen aus (kein eigenes ACME-Management, keine Rate-Limits); Browser bekommen **Secure Context** (Voraussetzung für Clipboard/Service-Worker/WebRTC in code-server); Serve ist standardmäßig **tailnet-intern** (kein öffentlicher Zugriff, anders als Funnel). Voraussetzung: HTTPS-Certificates einmalig in der Tailscale-Admin-Konsole aktivieren (**Blocker**). Betrieb: `tailscale serve --bg https / http://localhost:80`, in Ansible idempotent (Status prüfen, sonst setzen).
- **Zukunft:** Jeder neue Web-Service profitiert ohne Zusatzaufwand; falls je öffentlicher Zugriff gewünscht: Funnel (bewusst NICHT jetzt).
- **Kommando-Syntax (>= Tailscale 1.52, Umsetzung 2026-07-31):** `tailscale serve --bg http://localhost:80` — HTTPS:443 + Mount `/` sind Defaults (die Legacy-Form `serve --bg https / http://localhost:80` wird von aktuellem CLI abgelehnt).

### B: HTTP-only via MagicDNS (`http://vps-dev…ts.net:80`)
- **Fachliche Auswirkungen:** Minimal (kein Serve-Konfigurationspunkt), aber Browser behandeln den Host als insecure → eingeschränkte Features (Clipboard-API, PWA, einige WebRTC-Fälle); URLs mit Port wirken unprofessionell; keine einheitliche HTTPS-Basis für spätere Services.
- **Zukunft:** Nachrüsten erfordert Umstellung von URLs/Bookmarks/Client-Konfigurationen.

### C: Eigene TLS-Terminierung (Tailscale-Cert-Dateien + Traefik)
- **Fachliche Auswirkungen:** `tailscale cert` liefert Cert/Key (90 Tage, Erneuerung selbst skripten), Traefik übernimmt TLS-Terminierung. Mehr bewegliche Teile (Cert-Rotation, Datei-Rechte, Traefik-TLS-Config) ohne fachlichen Mehrwert gegenüber A.
- **Zukunft:** Doppelte TLS-Ebene (Serve-artig vs. Traefik) → Verwirrung, mehr Fehlerquellen.

## Evidenz
- Tailscale-Doku: HTTPS-Certificates für `*.ts.net` via Let's Encrypt, MagicDNS-Voraussetzung; `tailscale serve` = tailnet-intern, Funnel = öffentlich
- IaC3-Betriebserfahrung: Serve-Ansatz lief stabil, keine Zertifikatsprobleme
- code-server (VS Code Web) benötigt Secure Context für mehrere Features (dokumentierte Anforderung)

## Empfehlung
**Option A** – Tailscale Serve (HTTPS 443 → localhost:80), konfiguriert in der Traefik-Rolle (idempotent, nach Traefik-Start). **Voraussetzung (erledigt 2026-07-31):** HTTPS-Certificates im Tailnet sind bereits aktiviert (IaC3-Betrieb, Bestätigung Harald) — kein Blocker mehr.

## Worst-Case / Rollback (Pflicht: Netzwerk-/Expositions-Entscheidung)
- **Worst-Case 1:** HTTPS-Certificates-Flag im Tailnet nicht aktivierbar → Serve kann kein Zertifikat beziehen, Web-Services nur per HTTP erreichbar (kein Secure Context).
  - **Rollback:** Betrieb läuft weiter über Option B (HTTP-URLs); kein Service-Ausfall, nur Feature-Einschränkung.
- **Worst-Case 2:** Serve-Konfiguration defekt/Proxy down → `https://…ts.net` antwortet nicht.
  - **Rollback:** `tailscale serve --reset` + erneut setzen (idempotenter Playbook-Task); Fallback HTTP-URLs.
- **Gegenmaßnahme:** Post-Deploy-Check `curl -I https://<host>.ts.net` (erwartet 200/30x); Serve-Status im BDD-Test.

## Konsequenzen
- Tailscale-Rolle/Playbook um Serve-Task erweitern (State-Check + `serve --bg`)
- Traefik bleibt HTTP-only (Port 80) – kein TLS in Traefik selbst
- **P4-Delta (bei Phase-3/4-Umsetzung):** LE-Blöcke aus `docker-compose.yml.j2` + `traefik_acme_email` aus `group_vars` entfernen; `docker_network: traefik-public` → `traefik-network` (ADR-015/016-Konsistenz); `arc42/05` Z.10 + `arc42/07` Z.22 + K10-Formulierung aktualisieren („Service-Ports nur via Tailscale, UFW-restricted")
- Doku: Zugriffs-URLs als `https://<host>.ts.net` ohne Port

## Referenzen
- <https://tailscale.com/docs/how-to/set-up-https-certificates>
- <https://tailscale.com/docs/features/tailscale-serve>
- <https://tailscale.com/docs/reference/tailscale-cli>
