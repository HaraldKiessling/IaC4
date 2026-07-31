# ADR-022: Ollama-Ressourcenlimits (RAM/CPU/Keep-Alive)

- **Status:** Vorgeschlagen (Proposed) – VPS-Spec **bestätigt** (Harald, 2026-07-31)
- **Datum:** 2026-07-31
- **Kontext:** Ollama wird erster Service (Harald-Entscheidung 2026-07-31). IaC3 (RFC 0016 v0.3) setzte Limits 2 CPU / 4G RAM, Reservations 1 CPU / 2G, `OLLAMA_NUM_PARALLEL=2`, `OLLAMA_KEEP_ALIVE=24h` (Zoo-Indexing-Fix: Modell bleibt geladen, erster Embedding-Request <1s statt 15-30s). Die exakte DEV-VPS-Spec ist in IaC3/IaC4 nicht dokumentiert (nur Hinweis: Swap 2G in vps-baseline → kleinerer VPS). Annahme aus RFC 0016: 4-8 GB RAM.

## Entscheidungsfrage
Welche Docker-Ressourcenlimits bekommt Ollama in IaC4?

## Optionen

### A: IaC3-Werte übernehmen (2 CPU / 4G max, 1 CPU / 2G reserve) — EMPFEHLUNG unter Vorbehalt
- **Fachliche Auswirkungen:** Schutz der anderen Services vor Ollama-Speicherdruck; `nomic-embed-text` ist winzig (~274 MB Modell), 4G-Limit ist großzügig für Embedding-Betrieb und lässt Raum für spätere Chat-Modelle (7-8B quantisiert ~4-6 GB – dann Limit anpassen). `KEEP_ALIVE=24h` hält das Modell im RAM → konstante, schnelle Antworten; kostet bei kleinem VPS dauerhaft RAM (Modell klein, Server-Overhead ~1 GB).
- **Zukunft:** Bei Chat-Modellen Limits pro Service-Szenario nachziehen (ADR-Update).

### B: Reduzierte Limits (1 CPU / 2G max, 1G reserve)
- **Fachliche Auswirkungen:** Sicherer auf 4-GB-VPS, aber: parallele Embedding-Requests (NUM_PARALLEL=2) können OOM-failen; Chat-Modelle später unmöglich; Performance-Spielraum eng.
- **Zukunft:** Muss bei jedem Modell-Add-on nachjustiert werden.

### C: Ohne Limits
- **Fachliche Auswirkungen:** Ollama kann gesamten RAM belegen (Memory-Pressure bis OOM-Kill anderer Container/Host) – verletzt Betriebsstabilität (QZ1-Betriebsziel).
- **Zukunft:** Unkontrollierbares Verhalten bei Modellwechsel; keine Empfehlung.

## Evidenz
- Ollama-Doku: `OLLAMA_KEEP_ALIVE` steuert Entladezeitpunkt, `OLLAMA_NUM_PARALLEL` parallele Requests; Modell-Größe nomic-embed-text ≈ 274 MB
- IaC3-Betriebserfahrung: Pre-Warm + KEEP_ALIVE=24h senkte ersten Request von 15-30s auf ~0,24s (BDD-validiert)
- Docker-Doku: `deploy.resources` als Standard-Limit-Mechanismus für Compose

## Empfehlung
**Option A** – Werte aus IaC3 übernehmen (2C/4G, 1C/2G, PARALLEL=2, KEEP_ALIVE=24h).

**VPS-Spec (Harald, 2026-07-31):** VPS 6-8-240 → **6 vCore / 8 GB RAM / 240 GB NVMe SSD**.
Bewertung: 8 GB RAM sind für 2C/4G-Limits + Reservations 1C/2G komfortabel (Rest ~6 GB für Host, Traefik, Qdrant, spätere Services + OpenClaw nativ). `KEEP_ALIVE=24h` unkritisch (Modell ~274 MB). Spielraum für späteres Chat-Modell (7-8B quantisiert ~4-6 GB): Limit dann auf 6G anheben (ADR-Update).

## Worst-Case / Rollback
- **Worst-Case:** VPS-RAM zu knapp → OOM-Kill des Ollama-Containers oder anderer Container (Memory-Pressure).
  - **Rollback:** Limits in `group_vars` anpassen (z.B. Reservations senken) + `docker compose up -d` (Recreate mit neuen Limits); kurzfristig `OLLAMA_KEEP_ALIVE` reduzieren (Modell entlädt sich früher).
- **Gegenmaßnahme:** Post-Deploy-Check `docker stats` (RAM-Auslastung dokumentieren); OOM-Events via `docker inspect`/`dmesg` prüfen; VPS-Spec als offene Variable geführt.

## Konsequenzen
- Compose-Template: `deploy.resources.limits/reservations` + Env-Variablen (Werte aus `group_vars`)
- Offene Frage an Harald: aktuelle DEV-VPS-Spec (RAM/CPU) – danach ADR finalisieren

## Referenzen
- <https://docs.ollama.com/faq> (KEEP_ALIVE, NUM_PARALLEL)
- <https://docs.docker.com/compose/compose-file/deploy/>
- IaC3 RFC 0016 (Betriebserfahrung Pre-Warm)
