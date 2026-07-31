# ADR-021: Ollama-Exposition (Port 11434)

- **Status:** Vorgeschlagen (Proposed)
- **Datum:** 2026-07-31
- **Kontext:** Ollama wird **erster Service** auf der Docker/Traefik-Plattform (Priorisierungs-Entscheidung Harald, 2026-07-31 — Migrationsplan Phase 3/4 entsprechend ergänzt). IaC3 (RFC 0016): Host-Port `0.0.0.0:11434:11434`, `OLLAMA_HOST=0.0.0.0`, kein Traefik-Routing. Konsumenten: (a) code-server-Container später, (b) Remote-Clients via Tailscale (z.B. Haralds Rechner, ZooCode), (c) Host-Tools. IaC4-Firewall-Konzept: UFW aktiv mit CGNAT-Allow.

## Entscheidungsfrage
Wie wird die Ollama-API auf dem VPS exponiert?

## Optionen

### A: Host-Port `0.0.0.0:11434` + UFW-Allow aus `100.64.0.0/10` — EMPFEHLUNG (IaC3-Muster, adaptiert)
- **Fachliche Auswirkungen:** Remote-Clients erreichen die API via `http://<host>.ts.net:11434` (Tailscale-Mesh, WireGuard); Host-Tools via `localhost:11434`; Container im `traefik-network` erreichen Ollama über Docker-DNS (`http://ollama:11434`). Security: Tailscale-ACL + UFW-Restrict (nur Tailnet), konsistent mit Traefik-Port-80-Handling. Ollama selbst hat keine Auth → Schutz ausschließlich über Netzwerk-Isolation (akzeptiertes Modell, kein öffentlicher Zugriff).
- **Zukunft:** code-server/ZooCode-Integration ohne Sonderfälle; offen für weitere LLM-Consumer (OpenClaw-Selbsthosting optional).

### B: Nur `127.0.0.1:11434` (Host-Loopback)
- **Fachliche Auswirkungen:** Nur Host-Prozesse erreichen Ollama; **Container** (code-server!) müssten `host-gateway`-Mapping pro Compose-Datei bekommen; Remote-Clients haben gar keinen Zugriff (auch nicht via Tailscale) → API aus dem Tailnet nicht nutzbar.
- **Zukunft:** Jeder neue Container-Consumer braucht Extra-Konfiguration; Remote-Nutzung (z.B. OpenClaw auf anderem Host) blockiert.

### C: Kein Host-Port; nur Docker-Netz + Traefik-Routing
- **Fachliche Auswirkungen:** Maximal isoliert, aber: Ollama hat keine Web-UI; API-Routing über Traefik erzeugt eine Route ohne praktikable Auth (Traefik `forwardAuth` bräuchte einen separaten Auth-Zusatzdienst, BasicAuth ist für API-Clients ungeeignet — Token-Handling fehlt) → Komplexität steigt, ohne die Netzwerk-Isolation von A zu übertreffen; Remote-Clients brauchen Traefik-URL statt Direktport.
- **Zukunft:** Sinnvoll erst bei Multi-Service-LLM-Gateway-Anforderungen (nicht absehbar).

## Evidenz
- Ollama-Doku: Default-Bind `127.0.0.1:11434`; für Container-Exposure `OLLAMA_HOST=0.0.0.0` + Port-Mapping nötig; Warnung vor öffentlicher Exposition ohne Schutzschicht
- Docker-Doku/-Praxis: Loopback-Bindung als lokales Muster; Container-zu-Container via Docker-DNS (netzwerk-intern)
- IaC3-Betrieb: Direktport + Tailscale-Isolation lief stabil (kein unautorisierter Zugriff)

## Empfehlung
**Option A** – Host-Port `0.0.0.0:11434` mit `OLLAMA_HOST=0.0.0.0`, UFW-Regel `allow from 100.64.0.0/10 to any port 11434` (Firewall-Konzept R9). Container-Zugriff über Docker-DNS `ollama:11434` (statt `localhost` – korrigierte Annahme aus RFC 0016).

## Worst-Case / Rollback (Pflicht: Expositions-Entscheidung)
- **Worst-Case:** ACL-/UFW-Fehler (z.B. versehentlich `allow 11434` für alle Quellen oder Funnel aktiviert) → ungeschützte LLM-API ohne Auth im Netz erreichbar (Missbrauch: Rechenzeit, Datenabfluss über Prompts).
  - **Rollback:** UFW-Regel 11434 entfernen + Host-Port-Mapping aus Compose entfernen → Container bleibt über Docker-DNS (`ollama:11434`) für Container-Consumer nutzbar; Remote-Zugriff erst nach Fehleranalyse wieder frei.
- **Gegenmaßnahme:** BDD-Test: Port 11434 von außerhalb des CGNAT-Bereichs nicht erreichbar; UFW-Status-Check im Post-Deploy; Tailscale-ACL-Review (nur `tag:ia4`-Clients).

## Konsequenzen
- UFW-Konzept um Port 11434 erweitern (Firewall-Konzept R9, analog Port 80/8080)
- Ollama-Rolle: Compose mit `ports: ["0.0.0.0:11434:11434"]`
- Architektur-Doku: Zugriffspfade (Docker-DNS für Container, MagicDNS für Remote, localhost für Host)
- Kein Auth-Mechanismus (bewusst: Tailscale-Isolation); dokumentiert als akzeptiertes Restrisiko

## Referenzen
- https://docs.ollama.com/faq
- https://stackoverflow.com/questions/78689283/exposing-11434-port-in-docker-container-to-access-ollama-local-model
- https://github.com/ollama/ollama/issues/6398
