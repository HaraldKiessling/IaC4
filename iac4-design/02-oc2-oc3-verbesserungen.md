# Design: OC2/OC3-Verbesserungen aus beobachteten IaC3-Defiziten

- **Status:** Vorgeschlagen (Review ausstehend)
- **Datum:** 2026-08-01
- **Autor:** ✨ Nova (Orchestrator)
- **Bezug:** IaC3-Betriebs-Lessons (2026-07-16..08-01), ADR-025, RFC 01-oc2-oc3-benchmark, PR #56/#64-Reviews
- **Ziel:** Beobachtete Defizite des IaC3-Deployments analysieren und daraus konkrete Verbesserungen für die IaC4-Instanzen **OC2** (DevOps-Team) und **OC3** (Best-Practice-Referenz) ableiten.

---

## 1. Methode

1. Alle dokumentierten IaC3-Vorfälle/Lessons gesammelt (TOOLS.md, MEMORY.md, Session-Transkripte 2026-07-16..08-01)
2. Jedes Defizit gegen den aktuellen IaC4-main-Stand geprüft (verifiziert 2026-08-01, main `62491b9` + offener PR #64 `dac8bcd`): **bereits adressiert / teilweise / offen**
3. Nur **offene oder teilweise** Defizite werden als Verbesserungsvorschläge für OC2/OC3 übernommen
4. Jeder Vorschlag: Problem → Beleg → Lösung → Auswirkung → Aufwand

---

## 2. Defizit-Analyse (IST gegen IaC4-main)

| # | Defizit (IaC3-Beobachtung) | Beleg | Status in IaC4 | Verbesserung für OC2/OC3? |
|---|---|---|---|---|
| D1 | Gateway ohne Auto-Restart → 6h Downtime nach Prozess-Kill | Vorfall 2026-07-16 (TOOLS.md) | ✅ adressiert: Docker `restart: unless-stopped` (ADR-025) | – |
| D2 | Rollen-Neuinstallation behielt Altlasten (`~/.openclaw`) | IaC3-Lesson (ADR-025 Kontext) | ✅ adressiert: Config-Volume = SSoT, Reinstall = Container+Volume neu | – |
| D3 | Kein Healthcheck im Container → Hänger werden nicht erkannt/restartet | Compose-Template geprüft (2026-08-01): kein `healthcheck` | ⚠️ **teilweise** | ✅ **V1: Docker-Healthcheck** |
| D4 | Secrets in weltlesbarer Compose-Datei (0644) | PR #56 Review (2. Runde, Befund) | ✅ adressiert: Compose mode 0600 (instance.yml) | – |
| D5 | Config-Divergenz: `OPENCLAW_GATEWAY_TOKEN` als ENV dupliziert SSoT openclaw.json; nach `config set` im Betrieb divergieren ENV und Config | PR #56 Review (2. Runde, Befund); Compose-Template geprüft 2026-08-01 | ⚠️ **offen** (nur 0600 gefixt, ENV-Duplikat bleibt) | ✅ **V2: ENV-Entfernung oder Divergenz-Doku** |
| D6 | Kein Teardown-Pfad: `enabled:false` entfernt Container NICHT → Rollback nur manuell | PR #64 Review R2 (M3) + RFC 01 Kap. 4.4; `tasks/main.yml` geprüft (kein Teardown-Task) | ⚠️ **offen** (im RFC als optionaler Folge-Task deklariert) | ✅ **V3: Teardown-Task** |
| D7 | GH-Workflow-Expression mit Empty-String → falsche Instanzen-Erwartung (DEV-BDD rot) | PR #64 Review R2 (W1, selbst gefunden) | ✅ adressiert (Fix in PR #64 `dac8bcd`, ungemerged) | – |
| D8 | BDD-Parsefehler `$Fqdn:` (PowerShell-Interpolation) crashte BDD-Lauf | Sessions 2026-08-01 (`$Fqdn`-Parsefehler, PR #55/#52-Fixes) | ✅ adressiert in main (`${Fqdn}`-Klammerung; Restbestand `$Fqdn` ohne Klammern nur in docker-traefik.bdd.ps1:140 — funktional ok, keine `$Fqdn:`-Fehlerklasse) | – |
| D9 | `group_vars/vps-<target>.yml` wurde im Deploy-Workflow nicht geladen (stiller No-Op) | PR #56 Review R2 (N1-Blocker) | ✅ adressiert (Workflow kopiert nach `/tmp/group_vars/vps.yml`, main `62491b9`) | – |
| D10 | Keine Laufzeit-Verifikation von LLM-Key/Memory nach Deploy (Embedding-Key-Vorfall: `@-`-Literal) | Vorfall 2026-07-17/31 (TOOLS.md) | ⚠️ **teilweise**: Config-Assert existiert (instance.yml), aber kein BDD-Check „Provider-Key wirksam" | ✅ **V4: BDD-Provider-Smoke** |
| D11 | Post-Deploy-Verifikation manuell (Felix ansprechen) | Lesson 2026-07-18 (TOOLS.md) | ✅ adressiert: BDD-Suite + Workflow-Logs | – |
| D12 | Sub-Agent-/Session-Kontext-Blas (Token-Last 82–97% beim Orchestrator) | Session-Token-Metriken 2026-07-31/08-01 | ⚠️ **teilweise**: RFC 01 adressiert via delegationMode (OC3, PR #64) | ✅ **V5: Benchmark-Kovariate CPU/RAM** (RFC 01 Kap. 6.3, offen) |
| D13 | Memory-Backend qmd ohne Backup-Pfad (dateibasiert, nur im Container-Volume) | ADR-025 (memory.backend: qmd), Migrationsplan | ⚠️ **offen** (kein Backup-Konzept für `/srv/openclaw/*/workspace`) | ✅ **V6: Backup-Konzept** (Docs) |

---

## 3. Verbesserungsvorschläge (priorisiert)

### V1 – Docker-Healthcheck für alle Instanzen (P1, Betriebsstabilität)
- **Problem:** `restart: unless-stopped` greift nur bei Prozess-Exit. Ein **hängender** Gateway-Prozess (HTTP antwortet nicht mehr, Prozess lebt) wird nie neu gestartet → gleiche Downtime-Klasse wie IaC3-Vorfall D1, nur anders ausgelöst.
- **Lösung (Review M1 korrigiert):** Docker-Restart-Policies (`unless-stopped`) reagieren **nur auf Prozess-Exit, nicht auf Health-Status** (extern belegt: Docker-Doku, moby/compose #4826). Selbstheilung bei Hängern erfordert daher eines von zwei Mustern:
  - **(a) Selbst-Kill-Healthcheck (empfohlen):** `healthcheck` mit `CMD-SHELL` `curl -f http://localhost:{{ oc.port }}/health || kill -9 1` (Interval 30s, Timeout 5s, Retries 3, Start-Periode 60s) → hängender Container killt sich selbst → Prozess-Exit → Restart-Policy greift (exakt die gewünschte Selbstheilung).
  - **(b) externer Watcher:** systemd-Timer/cron `docker ps -f health=unhealthy` → restart (oder Autoheal-Container); healthcheck dann nur Observability. Mehr Infrastruktur, dafür kein Selbst-Kill im Container.
- **Beleg:** `/health`-Endpoint existiert (BDD O1 nutzt ihn); Restart-Verhalten laut Docker-Doku.
- **Auswirkung:** OC1/OC2/OC3 selbstheilend bei Hängern (Option a). Aufwand: klein (Template + ggf. BDD-Observability-Check).
- **Risiko:** `curl`-Verfügbarkeit im Image (`ghcr.io/openclaw/openclaw:2026.7.1`, Node-Basis) **unverifiziert** — Vorbedingung fürs Implementierungs-PR: im Container prüfen (`docker exec openclaw-oc1 which curl`), Fallback `wget` oder `node -e "fetch(...)"`; erst dann Option (a) finalisieren.

### V2 – Token-Divergenz ENV vs. SSoT beheben (P2, Config-Konsistenz)
- **Problem (korrigiert nach Review R1, Architect MAJOR):** `OPENCLAW_GATEWAY_TOKEN` steht in der Compose-ENV **und** in openclaw.json (`gateway.auth.token`). Die Priorität **ist** dokumentiert: **ENV gewinnt** über Config bei der Startup-Auth-Auflösung (`gateway/secrets.md`: „env token input wins for that runtime"; Prioritätskette ENV → `gateway.auth.token` → `gateway.remote.token`). Das Problem ist dadurch **schärfer**: der in instance.yml fail_msg dokumentierte Betriebsweg `docker exec ... openclaw config set gateway.auth.token <neu>` ist **deterministisch wirkungslos** (silent shadow), solange die ENV-Zeile steht.
- **Lösung (2 Optionen):**
  - **A (empfohlen):** ENV-Zeile entfernen → SSoT = openclaw.json (0600). Prüfen, ob das Image den Token aus openclaw.json akzeptiert (Doku: `gateway.auth.token` ist der Config-Weg).
  - **B:** ENV behalten, aber Divergenz explizit dokumentieren + BDD-Check „ENV-Token == Config-Token" (verhindert stillen Auth-Bruch).
- **Beleg:** PR #56 Review (2. Runde): „ENV-Zeile entfernen (SSoT = openclaw.json) oder Compose-Datei auf 0600" — 0600 wurde umgesetzt, ENV-Frage blieb offen.
- **Auswirkung:** Deterministischer Auth-Zustand für OC2/OC3. Aufwand: klein.
- **Risiko:** Option A könnte den Boot brechen, wenn das Image ENV-Vorrang hat → **erst Test auf DEV (OC1), dann Rollout**.

### V3 – Teardown-Task in der Rolle (P2, Rollback/Operations)
- **Problem:** `enabled: false` skippt die Instanz nur (`when: oc.enabled`); Container, Config-Volume und Tailscale-Serve bleiben stehen. Rollback = manuelles `docker compose down` (RFC 01 Kap. 4.4). Bei Benchmark-Abbrüchen (RFC 01 Kap. 6.4 Abbruchkriterium) ist das ein manueller, fehleranfälliger Schritt.
- **Lösung:** **Eigener Loop** über deaktivierte Instanzen in `tasks/main.yml` (vor dem bestehenden Instanz-Loop, der `enabled:false` via `when` skippt): wenn `oc.enabled == false` und Container existiert → `docker_compose_v2 state: absent` + `tailscale serve --https={{ oc.port }} off`. Idempotenz am Enable-Pfad angleichen: Status-Check via `tailscale serve status` (Muster instance.yml Z. 79–88); `serve --https=<port> off`-Syntax laut Tailscale-Doku. 
- **Beleg:** PR #64 Review R2 (M3): „kein Teardown-Task im gesamten Role-Verzeichnis" (verifiziert); RFC 01 Kap. 4.4.
- **Auswirkung:** OC3-Deaktivierung = 1 Config-Flag statt manueller Eingriffe; Benchmark-Abbruch sauber. Aufwand: mittel.
- **Risiko:** Serve-`off`-Kommando muss idempotent sein (Status-Check wie beim Enable-Pfad).

### V4 – BDD-Provider-Smoke (P3, Laufzeit-Verifikation)
- **Problem:** Der Embedding-Key-Vorfall (Literal `@-`) war erst beim Memory-Search bemerkbar — Config-Assert prüft nur „Key nicht leer", nicht „Key wirksam".
- **Lösung:** BDD-Szenario O5: via `docker exec openclaw-<inst> openclaw models list` (read-only CLI, gibt keine Secrets aus; **setzt Docker-Socket-Zugriff des BDD-SSH-Users voraus** — docker-Gruppe, als Implementierungsdetail prüfen) oder `/health`-Detail prüfen, dass der aktive Provider konfiguriert ist; optional 1 LLM-Call (kostet 1 Request, dafür echter Wirksamkeits-Beweis). Als Benchmark-Kovariate nutzbar.
- **Beleg:** TOOLS.md Secret-Diagnose-Kette (2026-07-17/31): Rohwert → memory status → E2E-Search.
- **Auswirkung:** Stiller Key-Tod wird beim Deploy erkannt statt im Betrieb. Aufwand: klein–mittel.
- **Risiko:** LLM-Call kostet; daher als „optional (Flag)" oder nur OC3.

### V5 – CPU/RAM-Kovariate im BDD-Log (P3, Benchmark-Fairness)
- **Problem:** RFC 01 Kap. 6.3 fordert Ressourcen-Kovariate (Harald-Entscheidung F4: „parallel, Auslastung mitschreiben"), aber es gibt keinen Mechanismus.
- **Lösung:** BDD/Deploy-Log erweitern: `docker stats --no-stream` je Instanz in den BDD-Lauf (O1-Block) aufnehmen → Kovariate für die Token-/Zeit-Metriken des Benchmarks.
- **Beleg:** RFC 01 Kap. 6.1/6.3, Harald-Entscheidung F4 (2026-08-01).
- **Auswirkung:** Benchmark-Ergebnisse interpretierbar (Ressourcen-Engpass sichtbar statt stiller Verfälschung). Aufwand: klein.

### V6 – Backup-Konzept für Instanz-Daten (P3, Dauerhaftigkeit)
- **Problem:** Memory (qmd, dateibasiert) und Workspace liegen unter `/srv/openclaw/<name>/` (Host-Bind-Mount). Ein Container-Loss überlebt das (Bind-Mount bleibt) — aber Host-Verlust oder der dokumentierte Reinstall-Pfad (ADR-025: „Container+Volume neu") löschen die Memory-Daten.
- **Lösung:** Docs-Ergänzung in `docs/arc42/08_querschnittskonzepte.md` (dort existiert bereits „Backup (Tech-Debt), siehe #11") **+ Anbindung an das bestehende `scripts/restore.sh`-Gerüst** (kein Doppel-Konzept an neuem Ort): regelmäßiger Rsync/Tar von `/srv/openclaw/*/workspace` auf ein Backup-Ziel + Wiederherstellungs-Anleitung. Kein neuer Rollen-Code in diesem Schritt (erst Konzept).
- **Beleg:** ADR-025 (memory.backend: qmd, dateibasiert), IaC3-Memory-Vorfall (Embedding-Key, MemorySearch tot → Datenverlust-Risiko real).
- **Auswirkung:** Memory überlebt Container-Verlust. Aufwand: klein (Docs) + später Rolle.

---

## 4. Empfehlung (Reihenfolge)

1. **PR-Bündel 1 (sofort, nach #64-Merge):** V1 (Healthcheck) + V3 (Teardown) — beide rollen-nah, beide schließen Betriebs-/Rollback-Lücken. **Konfliktanalyse (Review):** `docker-compose.yml.j2` und `tasks/main.yml` sind **nicht** in PR #64 (`dac8bcd`) — Bündel 1 ist konfliktfrei. V2 (`openclaw.json.j2`), V4 (`openclaw.bdd.ps1`/`run-all.ps1`) und V5 (`04-bdd-tests.yml`) **überlappen mit PR-#64-Dateien** → bewusst nach #64-Merge sequenziert.
2. **PR-Bündel 2 (nach Bündel 1):** V2 (Token-Divergenz, erst DEV-Test) + V4 (Provider-Smoke) — Config-Konsistenz + Laufzeit-Verifikation.
3. **PR-Bündel 3 (parallel, Docs):** V5 (Kovariate im BDD-Log) + V6 (Backup-Konzept) — Benchmark-Fairness + Dauerhaftigkeit.

**Begründung:** V1/V3 zuerst, weil sie die zwei realen Betriebsrisiken schließen (Hänger-Downtime, manueller Rollback), die aus IaC3-Vorfällen direkt ableitbar sind. V2 braucht einen DEV-Test (Image-Verhalten ENV vs. Config), V4 kostet Requests (bewusst klein halten).

**Benchmark-Neutralität (Review MINOR-6):** V1–V4 und V6 sind **symmetrisch für OC2/OC3** (gleiche Rolle/Templates/BDD für beide Instanzen) und damit benchmark-neutral — sie müssen **vor T1-Start** gemerged sein, damit sie nicht als Confound in die Benchmark-Läufe hineinwirken. V5 (Kovariate) ist der einzige direkte Benchmark-Beitrag (RFC 01 Kap. 6.3).

---

## 5. Offene Fragen an Harald

1. V2 Option A (ENV entfernen) oder B (Divergenz dokumentieren + Check)? — Empfehlung: A nach DEV-Test auf OC1.
2. V4: LLM-Smoke-Call erlaubt (kostet ~1 Request je Deploy) oder nur Config-Prüfung? — Empfehlung: nur OC3 (Benchmark-Instanz), Config-Check für alle.
3. V6: Backup-Ziel vorhanden (z.B. Host-Dir außerhalb Docker) oder reicht Docs-Konzept ohne konkreten Zielpfad?
4. Sollen V1+V3 als ein PR oder getrennt laufen? — Empfehlung: getrennt (Review-freundlich, unabhängig mergbar).
5. V1-Mechanik: Option (a) Selbst-Kill-Healthcheck oder (b) externer Watcher? — Empfehlung: (a) nach curl-Verfügbarkeits-Check im Container (Vorbedingung, Review MINOR-1).

---

## 6. Referenzen & Evidenz

- TOOLS.md (Lessons 2026-07-16/17/18/31, Secret-Diagnose, Post-Deploy-Verifikation)
- MEMORY.md (Gateway-Kill, Embedding-Key, Worktree-Isolation)
- ADR-025 (Deployment-Form, Rollback-Semantik), RFC 01-oc2-oc3-benchmark (Kap. 4.4, 6.1–6.3)
- PR #56 Review R2 (Befunde: Compose-0644, ENV-Duplikat, N1-group_vars)
- PR #64 Reviews R1–R3 (M3-Teardown, W1-Expression, Byte-Identität)
- Compose-Spezifikation (healthcheck/restart-Interaktion), Docker-Doku
- Session-Token-Metriken 2026-07-31/08-01 (B7-Kontext)
