# ADR-020: Traefik-Logging (accessLog an/aus + Rotation)

- **Status:** Vorgeschlagen (Proposed)
- **Datum:** 2026-07-31
- **Kontext:** IaC3-RFC 0029 ließ die Log-Frage offen (O3: accessLog deaktivieren oder logrotate). IaC4 braucht eine Entscheidung für Diagnose-Fähigkeit ohne Log-Wachstum auf dem VPS.

## Entscheidungsfrage
Wie werden Traefik-Zugriffs- und Systemlogs in IaC4 gehandhabt?

## Optionen

### A: accessLog deaktiviert
- **Fachliche Auswirkungen:** Kein Log-Wachstum, aber Fehler-/Zugriffsanalyse unmöglich (welcher Service 502? welcher Client?); Debugging bei Routing-Problemen deutlich langsamer.
- **Zukunft:** Monitoring-Ausbau (Phase 6) startet ohne historische Daten.

### B: accessLog an → stdout (JSON) + Docker-json-file-Rotation — EMPFEHLUNG
- **Fachliche Auswirkungen:** Traefik schreibt accessLog nach stdout (`accessLog.format=json`, kein filePath) – Docker-Doku-konformes Muster; Rotation über `logging.driver: json-file` mit `max-size: 10m`, `max-file: 3` (pro Container begrenzt, keine eigene logrotate, kein USR1-Handling); Analyse via `docker compose logs traefik`; JSON-Format = parsebar für spätere Log-Shipping (Loki o.ä.). **Ehrliche Einordnung:** json-file-Logs überleben `docker restart`, gehen aber bei Container-Remove/Recreate (z.B. Image-Update) verloren – für Runtime-Diagnose ausreichend; dauerhafte Persistenz erst bei Monitoring-Bedarf via Log-Shipping oder `--log-opt tag`.
- **Zukunft:** Beste Voraussetzung für Monitoring/Alerting ohne Umbau.

### C: accessLog in Datei (Volume) + logrotate + USR1
- **Fachliche Auswirkungen:** Dauerhafte Datei-Logs, aber mehr Komponenten (logrotate-Config, Postrotate-USR1 an Traefik); nur sinnvoll, wenn externe Tools die Dateien direkt lesen müssen – aktuell nicht der Fall.
- **Zukunft:** Zusätzlicher Wartungspunkt ohne aktuellen Nutzen.

## Evidenz
- Traefik-Doku: Rotation ist extern; empfohlenes Docker-Muster = stdout + `json-file`-Driver-Rotation; JSON-Format für Log-Collectoren empfohlen
- Community-Konsens (Traefik-Forum): json-file + stdout als sauberster Docker-Ansatz; USR1 nur bei Datei-Logs nötig

## Empfehlung
**Option B** – accessLog als JSON auf stdout, Rotation über Docker `json-file` (10m × 3) auf Compose-Ebene.

## Worst-Case / Rollback
- **Worst-Case:** Log-Flut (fehlerhafte Route → Endlos-Requests) füllt json-file-Rotation (3×10MB = 30MB max) → keine Plattenfüllung möglich (harte Obergrenze).
  - **Rollback/Reaktion:** Route/Service fixen; Logs via `docker compose logs --since` analysieren; bei Bedarf `max-size` senken.
- **Kein** Datenverlust-Risiko für Services (Logs sind nicht persistent, bewusst).
- **Gegenmaßnahme:** Rotation-Grenzen als Compose-Konstante; BDD-Check `docker inspect` (Log-Driver = json-file).

## Konsequenzen
- Static Config: `accessLog.format=json` (kein filePath)
- Compose: `logging: driver: json-file, options: {max-size: "10m", max-file: "3"}`
- Kein logrotate-Paket nötig

## Referenzen
- <https://doc.traefik.io/traefik/observability/access-logs/>
- <https://doc.traefik.io/traefik/observe/logs-and-access-logs/>
- <https://community.traefik.io/t/traefik-logs-how-best-to-manage/9381>
