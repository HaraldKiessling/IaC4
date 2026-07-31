# ADR-0003: Docker-Image-Versionierung (Pinning vs. `latest`)

- **Status:** Vorgeschlagen (Proposed)
- **Datum:** 2026-07-31
- **Kontext:** IaC3 verwendete `traefik:v3.1` und `ollama/ollama:latest`. IaC4-Qualitätsziel QZ1 = Reproduzierbarkeit („Nach einem Crash ist der VPS in <10 Minuten wiederhergestellt"). Ohne Pinning ist ein Wiederaufbau nicht deterministisch.

## Entscheidungsfrage
Wie werden Image-Versionen in IaC4 referenziert (Compose-Templates)?

## Optionen

### A: `latest` (IaC3-IST für Ollama)
- **Fachliche Auswirkungen:** Automatisch neueste Version bei jedem Re-Deploy; aber: `latest` ist mutabel und mehrdeutig („zuletzt gepusht", nicht „neueste stabile Version"), Wiederaufbau kann andere Version liefern → **Reproduzierbarkeit verletzt**; Versions-Skew zwischen DEV/PROD möglich; Security-/Compliance-Tracking schwierig.
- **Zukunft:** Unkontrollierte Breaking Changes bei Container-Recreate; Debugging erschwert.

### B: SemVer-Tags, zentral in `group_vars/all.yml` — EMPFEHLUNG
- **Fachliche Auswirkungen:** `traefik:v3.x.y`, `ollama:0.x.y` als **eine** Variable je Service; Upgrade = bewusster Versions-Bump + PR (Review durch 🔍 Reviewer); reproduzierbarer Wiederaufbau; Dependabot/Renovate kann PRs für Bumps öffnen.
- **Zukunft:** Upgrade-Kadenz steuerbar (Security-Patches zeitnah, Breaking Changes bewusst); DEV/PROD laufen deterministisch gleich.

### C: Digest-Pinning (`@sha256:…`)
- **Fachliche Auswirkungen:** Maximale Reproduzierbarkeit (auch gegen Retagging immun), aber unlesbar in Config/Logs; Update-Prozess umständlich; Overkill für Single-VPS-Betrieb.
- **Zukunft:** Sinnvoll bei strengen Compliance-Anforderungen; hier nicht gefordert.

## Evidenz
- Docker-Blog: `latest` ≠ „neueste Version", Warnung vor Abhängigkeit; Empfehlung: immutable Tags für Deployment
- Docker-Doku (Build best practices) + Community-Konsens: in Produktion nicht mit `latest` deployen; SemVer-Tags als menschlich lesbare Pins
- Praxis: Dependabot/Renovate managen Pinned-Tags als PRs (kontrollierte Updates)

## Empfehlung
**Option B** – SemVer-Tags zentral in `group_vars/all.yml` (`traefik_version`, `ollama_version` …). Kein `latest` in Templates.

## Worst-Case / Rollback
- **Worst-Case 1:** Pinned-Tag existiert nicht (Registry-/Tippfehler) → `docker compose up` schlägt fehl, Container bleibt im letzten Lauf-Zustand.
- **Rollback:** Korrekten Tag in `group_vars` setzen + erneut deployen; `git log` zeigt letzten gültigen Wert.
- **Worst-Case 2:** Upgrade auf neue Version bricht Service (Breaking Change) → **Rollback:** alten Tag per PR zurücksetzen + Re-Deploy; Image bleibt im lokalen Cache, kein Download nötig.
- **Gegenmaßnahme:** Versions-Bump nur mit Release-Notes-Check (Evidence-based Engineering); BDD-Healthchecks nach Deploy.

## Konsequenzen
- Compose-Templates referenzieren `{{ traefik_version }}` / `{{ ollama_version }}`
- Versions-Bump = Feature-Branch + PR (bestehender IaC4-Workflow)
- Upgrade-Log in Commit-Message (z.B. „chore: traefik 3.5.0 → 3.5.1, Quelle: Release-Notes")

## Referenzen
- https://www.docker.com/blog/docker-best-practices-using-tags-and-labels-to-manage-docker-image-sprawl/
- https://docs.docker.com/build/building/best-practices/
- https://nickjanetakis.com/blog/docker-tip-18-please-pin-your-docker-image-versions
