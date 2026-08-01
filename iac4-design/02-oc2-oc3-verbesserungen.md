# Design: OC2/OC3-Verbesserungen aus beobachteten IaC3-Defiziten

- **Status:** Überarbeitet nach Harald-Einwand (2026-08-01 18:23): Evidenz-Pflicht — nur Änderungen mit **harter Evidenz** (Repo-Fakt, freigegebene Entscheidung, Vendor-Doku) bleiben; IaC3-Analogien ohne IaC4-Beleg werden entfernt. Die beobachteten Vorfälle stammen von der **verschmutzten IaC3-Instanz** — sie sind nicht automatisch IaC4-Defizite.
- **Datum:** 2026-08-01
- **Autor:** ✨ Nova (Orchestrator)
- **Bezug:** IaC4-Repo-Fakten (geprüft 2026-08-01, main `62491b9`), ADR-025, RFC 01-oc2-oc3-benchmark (freigegeben), Harald-Entscheidungen F2-F5, PR #56/#64-Reviews
- **Ziel:** Aus IaC4-eigener Evidenz konkrete Verbesserungen für **OC2** (DevOps-Team) und **OC3** (Best-Practice-Referenz) ableiten — **nicht** IaC3-Verschmutzung nach IaC4 übertragen.

---

## 1. Methode

**Evidenz-Klassen (Harald-Anforderung 2026-08-01: „harte Evidenz für jede Änderung"):**
- **A – Repo-Fakt:** Im IaC4-Repo direkt verifizierbar (grep/Datei), unabhängig von IaC3
- **B – Freigegebene Entscheidung:** RFC 01 / Harald-Entscheidung (dokumentiert, gemerged)
- **C – Vendor-Doku/Mechanik:** Offizielle Docker-/OpenClaw-Doku (extern, verlinkt)
- **D – IaC3-Analogie:** In IaC3 beobachtet, **kein IaC4-Beleg** → wird **nicht** übernommen

**Regel:** Nur Vorschläge mit Evidenz A, B oder C kommen ins Rennen. Klasse-D-Items werden entfernt (auch wenn sie in IaC3 real waren — die IaC3-Instanz ist nachweislich verschmutzt, ihre Defizite sind kein IaC4-Beweis).

**Vorgehen:** Jedes Kandidaten-Defizit gegen IaC4-main geprüft (2026-08-01, main `62491b9` + PR #64 `dac8bcd`); nur mit A/B/C-Evidenz übernommen.

---

## 2. Defizit-Analyse (IST gegen IaC4-main)

| # | Defizit (IaC3-Beobachtung) | Beleg | Status in IaC4 | Verbesserung für OC2/OC3? |
|---|---|---|---|---|
| D1 | Gateway ohne Auto-Restart → 6h Downtime nach Prozess-Kill | Vorfall 2026-07-16 (TOOLS.md) | ✅ adressiert: Docker `restart: unless-stopped` (ADR-025) | – |
| D2 | Rollen-Neuinstallation behielt Altlasten (`~/.openclaw`) | IaC3-Lesson (ADR-025 Kontext) | ✅ adressiert: Config-Volume = SSoT, Reinstall = Container+Volume neu | – |
| D3 | Kein Healthcheck im Container → Hänger werden nicht erkannt/restartet | Compose-Template geprüft (2026-08-01): kein `healthcheck` | ⚠️ **teilweise** | ✅ **V1: Selbstheilung** (Evidenz A+C, optional) |
| D4 | Secrets in weltlesbarer Compose-Datei (0644) | PR #56 Review (2. Runde, Befund) | ✅ adressiert: Compose mode 0600 (instance.yml) | – |
| D5 | Config-Divergenz: `OPENCLAW_GATEWAY_TOKEN` als ENV dupliziert SSoT openclaw.json; nach `config set` im Betrieb divergieren ENV und Config | PR #56 Review (2. Runde, Befund); Compose-Template geprüft 2026-08-01 | ⚠️ **offen** (nur 0600 gefixt, ENV-Duplikat bleibt) | ✅ **V2: Token-Divergenz** (Evidenz A+C) |
| D6 | Kein Teardown-Pfad: `enabled:false` entfernt Container NICHT → Rollback nur manuell | PR #64 Review R2 (M3) + RFC 01 Kap. 4.4; `tasks/main.yml` geprüft (kein Teardown-Task) | ⚠️ **offen** (im RFC als optionaler Folge-Task deklariert) | ✅ **V3: Teardown-Task** (Evidenz A+B) |
| D7 | GH-Workflow-Expression mit Empty-String → falsche Instanzen-Erwartung (DEV-BDD rot) | PR #64 Review R2 (W1, selbst gefunden) | ✅ adressiert (Fix in PR #64 `dac8bcd`, ungemerged) | – |
| D8 | BDD-Parsefehler `$Fqdn:` (PowerShell-Interpolation) crashte BDD-Lauf | Sessions 2026-08-01 (`$Fqdn`-Parsefehler, PR #55/#52-Fixes) | ✅ adressiert in main (`${Fqdn}`-Klammerung; Restbestand `$Fqdn` ohne Klammern nur in docker-traefik.bdd.ps1:140 — funktional ok, keine `$Fqdn:`-Fehlerklasse) | – |
| D9 | `group_vars/vps-<target>.yml` wurde im Deploy-Workflow nicht geladen (stiller No-Op) | PR #56 Review R2 (N1-Blocker) | ✅ adressiert (Workflow kopiert nach `/tmp/group_vars/vps.yml`, main `62491b9`) | – |
| D10 | Keine Laufzeit-Verifikation von LLM-Key/Memory nach Deploy (Embedding-Key-Vorfall: `@-`-Literal) | Vorfall 2026-07-17/31 (TOOLS.md) | ⚠️ **teilweise**: Config-Assert existiert (instance.yml), aber kein BDD-Check „Provider-Key wirksam" | ❌ **V4: gestrichen** (Evidenz D – IaC3-Analogie ohne IaC4-Beleg) |
| D11 | Post-Deploy-Verifikation manuell (Felix ansprechen) | Lesson 2026-07-18 (TOOLS.md) | ✅ adressiert: BDD-Suite + Workflow-Logs | – |
| D12 | Sub-Agent-/Session-Kontext-Blas (Token-Last 82–97% beim Orchestrator) | Session-Token-Metriken 2026-07-31/08-01 | ⚠️ **teilweise**: RFC 01 adressiert via delegationMode (OC3, PR #64) | ✅ **V5: Benchmark-Kovariate** (Evidenz B – Harald-Entscheidung F4) |
| D13 | Memory-Backend qmd ohne Backup-Pfad (dateibasiert, nur im Container-Volume) | ADR-025 (memory.backend: qmd), Migrationsplan | ⚠️ **offen** (kein Backup-Konzept für `/srv/openclaw/*/workspace`) | ❌ **V6: gestrichen** (Evidenz D – theoretisches Risiko, kein Beleg) |

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


### V5 – CPU/RAM-Kovariate im BDD-Log (P3, Benchmark-Fairness)
- **Problem:** RFC 01 Kap. 6.3 fordert Ressourcen-Kovariate (Harald-Entscheidung F4: „parallel, Auslastung mitschreiben"), aber es gibt keinen Mechanismus.
- **Lösung:** BDD/Deploy-Log erweitern: `docker stats --no-stream` je Instanz in den BDD-Lauf (O1-Block) aufnehmen → Kovariate für die Token-/Zeit-Metriken des Benchmarks.
- **Beleg:** RFC 01 Kap. 6.1/6.3, Harald-Entscheidung F4 (2026-08-01).
- **Auswirkung:** Benchmark-Ergebnisse interpretierbar (Ressourcen-Engpass sichtbar statt stiller Verfälschung). Aufwand: klein.


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
3. Sollen V1+V3 als ein PR oder getrennt laufen? — Empfehlung: getrennt (Review-freundlich, unabhängig mergbar).
5. V1-Mechanik: Option (a) Selbst-Kill-Healthcheck oder (b) externer Watcher? — Empfehlung: (a) nach curl-Verfügbarkeits-Check im Container (Vorbedingung, Review MINOR-1).

---

## 6. Referenzen & Evidenz

- TOOLS.md/MEMORY.md (nur als Kontext: die IaC3-Vorfälle sind KEIN IaC4-Beleg — Evidenz-Klassen-Regel)
- MEMORY.md (Gateway-Kill, Embedding-Key, Worktree-Isolation)
- ADR-025 (Deployment-Form, Rollback-Semantik), RFC 01-oc2-oc3-benchmark (Kap. 4.4, 6.1–6.3)
- PR #56 Review R2 (Befunde: Compose-0644, ENV-Duplikat, N1-group_vars)
- PR #64 Reviews R1–R3 (M3-Teardown, W1-Expression, Byte-Identität)
- Compose-Spezifikation (healthcheck/restart-Interaktion), Docker-Doku
- Session-Token-Metriken 2026-07-31/08-01 (B7-Kontext)
