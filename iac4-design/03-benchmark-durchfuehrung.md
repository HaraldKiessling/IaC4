# Design: Benchmark-Durchführung & Überwachung durch Nova (OC1/OC2/OC3)

- **Status:** Umgesetzt — Nova-Operationsmodell durchgeführt: T1 (15 Läufe/45 Runs, Design 04), T2 (Reasoning-Level), 9er-Runde (Design 07). Referenziert von benchmark-methodik.md
- **Datum:** 2026-08-01 (23:36)
- **Autor:** ✨ Nova (Orchestrator)
- **Bezug:** Design 01-oc2-oc3-benchmark (3 Arme, gemerged `a968a20`), ADR-025, Zugriffs-Design 2026-07-31 (TOOLS.md/MEMORY.md)
- **Anlass (Harald 2026-08-01):** „Gibt es nicht die Möglichkeit, dass du die Tests durchführst und überwachst? Du hast den Gateway-Token, oder ich gebe ihn dir für alle drei. Willst du dafür einen Plan in IaC4 erstellen und reviewen lassen?"

---

## 1. Ziel

Nova führt den OC1/OC2/OC3-Benchmark (T1–T4, Design 01 Kap. 6) **selbst durch und überwacht ihn** — statt ihn nur als Workflow-Design zu beschreiben. Dazu erhält Nova **Gateway-API-Zugriff** auf die 3 DEV-Instanzen (via Tailscale-HTTPS, dedizierte Tokens). Zusätzlich übernimmt Nova zwei weitere reale Auftragstypen (Kap. 5).

## 2. Zugriffs-Design (bewusste Erweiterung, Harald-Freigabe erforderlich)

**Bisher (2026-07-31, TOOLS.md):** Keine direkten VPS-Zugriffe von Nova (kein SSH, kein Tailscale-Ping/Keyscan, keine direkte Felix-Ansprache); alles über IaC4-Workflows.

**Neu (dieses Design):** Nova spricht die 3 Gateways über ihre **Gateway-API** an:
- Transport: **WebSocket via Tailscale-MagicDNS** — `wss://vps-dev.tailcfea8a.ts.net:18789|18790|18791` (Serve terminiert TLS); `https://…/health` nur für Health-Checks. **Kein SSH, kein Host-Zugriff.**
- Auth: `OPENCLAW_GATEWAY_TOKEN` je Instanz (dediziert, s. Kap. 3)
- **Mechanik (korrigiert nach Architect-Review MAJOR-1 — `--gateway`/`--token`-Flags existieren NICHT, verifiziert CLI-Help v2026.7.1-2):**
  - Pro-Aufruf (Standard): `OPENCLAW_GATEWAY_URL=wss://vps-dev.tailcfea8a.ts.net:<port> OPENCLAW_GATEWAY_TOKEN=<token> openclaw agent --agent <id> --message "<task>" --json` (Env-URL + Env-Credential; docs/gateway/remote.md). **Token kommt nie in Prozess-Args** (Env-only → ps-sicher; Reviewer MAJOR-1)
  - Status-Abfragen (health/status/system-presence/cron.*): `OPENCLAW_GATEWAY_URL=<url> OPENCLAW_GATEWAY_TOKEN=<token> openclaw gateway call status` — **Env-only, Token nie in Prozess-Args (ps-sicher, wie bei `openclaw agent`)**; Session-Abfragen: `openclaw agent --session-key <key> --json` (gleiche Env-Mechanik).
  - **NICHT** Gateway-HTTP-Endpunkte (`/v1/chat/completions`) — per Default deaktiviert, würde Config-Änderung je Instanz (= Deploy) erfordern
- **Vertrauensmodell (ehrlich, Architect-Review MAJOR-4):** Token bei `auth.mode: token` = **voller Operator-Zugriff** (operator.admin/write/talk.secrets, Control-UI) — die Grenze „nur Agent-Chat + Status" ist eine **vertragliche Selbstverpflichtung, kein technischer Scope**. Bewusst akzeptiert (Nova = Operator), dokumentiert. **Device-Approval (Reviewer MINOR-11):** Tailscale-Device-Approvals laufen weiterhin via Workflow 05 (`05-device-approve.yml` + requestId) — **kein** zusätzlicher Zugriff nötig; Beleg für Zugriffs-Disziplin. **Technisch bleibende Grenzen:** kein SSH, kein Host-Dateisystem, keine Deployment-Änderungen (nur IaC4-Workflows). Audit-Aussage abgeschwächt: Gateway-Logs sind keine unabhängige Audit-Quelle (Nova könnte sie via API lesen) — unabhängige Kontrolle = Harald-Stichproben + Workflow-Logs.

**Begründung:** Workflow-only macht den Benchmark unpraktikabel (14 Tage, viele Einzel-Tasks, Adjudikation braucht Nova-seitige Orchestrierung). Der Gateway-Zugriff ist der kleinste nötige Eingriff: ein Agent-Chat-Kanal, kein Infrastruktur-Zugriff.

## 3. Token-Management

- **Quelle (Festlegung, Architect-Review MAJOR-5):** Je Instanz ein **separater, Nova-dedizierter Token-Wert** (nicht die Deploy-/Gateway-internen Tokens — Audit-Unterscheidbarkeit, Rotation ohne Deploy-Interferenz). **Erzeugung/Rotation ausschließlich via GH-Secret + Deploy-Workflow** (Template rendert `oc_gateway_token` → ENV → `auth.token`); `config set` im Betrieb ist ausgeschlossen (Container-/Host-Zugriff + V2-ENV-Divergenz, Design 02/Issue #68). Übernahme nach lokal durch Harald in `~/.openclaw/secrets/` (0600). **Übertragungsweg (Reviewer MINOR-8):** Tokens **nie im Chat-Transkript** senden — Harald legt sie direkt in die Secrets-Datei ab oder nutzt einen verschlüsselten Kanal; Nova lädt sie nur aus der Datei in Env (nicht inline in interaktive Shell, Shell-History-Schutz).
- **Aufbewahrung:** NIE im Repo, NIE in `.git/config`, NUR via Env-Variablen (`DEV_OC1_GATEWAY_TOKEN` etc. — existieren bereits als GH-Secrets) oder `~/.openclaw/secrets/` (0600).
- **Rotation:** Bei Verdacht sofort rotieren — es gibt **keinen** Secret-Update-Workflow (Reviewer MINOR-4): `gh secret set DEV_OC<n>_GATEWAY_TOKEN <neu>` + Deploy via `04-service-deploy` (Compose-ENV-Update; ENV gewinnt, V2-Hinweis). Tokens je Instanz getrennt — ein Leak betrifft nur eine Instanz.
- **Audit:** Zugriffe nur über Tailnet. **Wer liest Gateway-Logs (Reviewer MAJOR-3):** Nova hat keinen FS-Zugriff auf den VPS → Log-Auswertung ist **Harald-Aufgabe** (VPS/Tailnet, `docker logs openclaw-<oc>`); Nova-seitig nur eigene Transkripte. **Audit-Unterscheidbarkeit nur mit dedizierten Nova-Tokens** (Kap. 3).

## 4. Benchmark-Durchführung (Nova als Operator)

### 4.1 Ablauf (Design 01 Kap. 6.2, jetzt Nova-ausgeführt)
- **Agent-Ziel je Instanz (Architect MINOR-M7):** OC1 = Default-Agent (kein `agents.list` — Aufruf ohne `--agent` oder `--agent main`); OC2/OC3 = `--agent orchestrator` (Rollen-Team). Benchmark-Sessions mit **eigenem `--session-key`** (`agent:orchestrator:benchmark-t1-<n>` etc.) — reproduzierbar, Recovery-fähig.
1. **T1 – PR-Review (Kern):** Nova erstellt Diff-Snapshot-Datei mit Seed-Defekten (Ground Truth, Design 01 Kap. 6.2 / Kap. 7 Frage 5 — Harald hat Seed-Defekte in F5 bestätigt) → sendet identischen Task an OC1/OC2/OC3 → sammelt Outputs in getrennten Dateien (instanzfremd, Rotation) → **Adjudikation zweistufig (Architect-Review MAJOR-2, Design 01 Kap. 6.2):** Nova adjudiziert vor (Blocker/Nits/Fehlalarme vs. Ground Truth), **Harald adjudiziert 100 % der T1-Outputs** (n=5 × 3 Arme = 15, trivial) — Vier-Augen-Prinzip bleibt am kritischsten Punkt. T2–T4: Nova mit Harald-Sichtprüfung. **Entzerrungs-Pflicht (Reviewer MAJOR-2, Design 01 Kap. 6.1):** Tasks **staffelt (Task-Start versetzt)** starten (nicht gleichzeitig — 3 Instanzen auf 6 vCore/8 GB verrauschen sonst Zykluszeit-Metriken), Reihenfolge je Lauf rotieren (OC1→OC2→OC3, dann OC2→OC3→OC1, …). **Ground-Truth-Trennung (Reviewer MINOR-6):** Seed-Defekt-Liste geht **NICHT** an die Instanzen — Snapshots vor Versand fixieren (SHA-256-Hash dokumentieren), Task ≠ Ground-Truth-Liste. **Zustellung (Architect N3):** Diff-Snapshot via `--message-file` statt Inline-`--message` (kein Shell-Quoting, keine Arg-Längen-Limits).
2. **T2 – Architektur-Review:** identische 5W-Frage an alle 3 → Vergleich gegen Konsens-Urteil (Methodik).
3. **T3 – Implementierung (Ausführungsmodell festgelegt, Architect-Review MAJOR-3; **Freigabe-Punkt Kap. 7 Q5** — Abweichung vom gemergten Design 01):** Remote-Agents haben **kein IaC4-Repo** (privat, keine GH-Credentials im Container) — sie können keine Branches anlegen. **Festlegung Option (a):** Nova implementiert die identische Aufgabe lokal (eigener Worktree je Instanz-Lauf, Issue #29), die Instanz **reviewed den Diff**. T3 testet damit die Review-/Bewertungsfähigkeit an einem echten Diff (Ground Truth = Seed-Defekt-Klasse + Umsetzungsqualität; in Auswertung als T3-Variante dokumentiert, keine Degeneration zu T1).
4. **T4 – Recherche:** identische Web-Recherche (Evidenzpflicht) → Quellenqualität als Ground Truth.
5. **Kovariate (Architect MINOR-M4, Design 02 Entscheidung):** `docker stats` **im BDD-Lauf** (V5) — bewusst NICHT je Task (Design 02 Kap. 6 Empfehlung); Zeitstempel je Task im Task-Log.
6. **Fallback-Kontamination (Architect MINOR-M1):** `openclaw agent` fällt bei Gateway-Fehler still auf **Embedded-Fallback** zurück (`meta.transport: "embedded"` — lokaler Run, anderes Modell/Kontext). Benchmark-Skripte MÜSSEN `meta.transport == "gateway"` im `--json`-Output erzwingen/prüfen und Fallback-Runs **verwerfen**; `--timeout` ≥ 900 s (Instanz-`runTimeoutSeconds`) setzen (CLI-Default 600 s).

### 4.2 Überwachung (Nova)
- **Task-Log (Architect MINOR-M3, Design 01 Kap. 6.3):** Nova führt je Task ein Log (Instanz, Task, Start/Ende, Status ok/fail, Verweis auf Output-Datei) — Session-JSONL hat kein Completion-Status-Feld; Log ist Harald-einsehbar.
- **Output-Hygiene (Reviewer MINOR-7):** Agent-Outputs können Code/Diffs mit Geheimnissen zitieren → **Secret-Scan vor Commit**; Ablage in getrenntem Ordner `benchmark/out/` (nicht im Design-Ordner).
- **Täglich:** Health-Check aller 3 Instanzen (`/health` via Tailscale), Session-Status, Token-Usage der Benchmark-Sessions.
- **Wöchentlich:** Zwischenbericht an Harald (Metrik-Tabelle: Tokens, Zykluszeit, Qualität vs. Ground Truth, Kovariate).
- **Abbruchkriterium (Design 01 Kap. 6.4.6 exakt, Architect MINOR-M2):** Instanz scheitert in **3 aufeinanderfolgenden** T1-Läufen schwer (Delegation/Depth-Fehler, unbrauchbare Outputs) → pausieren, Befund dokumentieren.

### 4.3 Auswertung (nach 14 Tagen)
- Metrik-Tabelle je Arm (Design 01 Kap. 6.3), deskriptive Auswertung (kein Signifikanztest), Entscheidungskriterien Kap. 6.4 (Qualität > Kosten > Zykluszeit, paarweise OC1/OC2/OC3).
- Ergebnis-Doku als PR (Gap-Report, Methodik Schritt 8) — **Harald entscheidet**.

## 5. Weitere reale Auftragstypen (Harald 2026-08-01)

### 5.1 Issue-Relevanz-Prüfung (read-only)
- **Auftrag:** IaC4-Issues prüfen: noch relevant? veraltet? bereits umgesetzt? Doppelt?
- **Vorgehen:** Nova liest Issue + zugehörigen Repo-Stand (main), prüft Relevanz evidenzbasiert (Code-/Doku-Check, keine Annahmen), erstellt **Befund je Issue**.
- **Kriterien-Katalog (Architect MINOR-M5):** „**umgesetzt**" = referenzierter Code/Doku/ADR existiert nicht mehr oder Fix belegt; „**überholt**" = Entscheidung dagegen dokumentiert oder referenzierter Pfad entfernt; „**relevant**" = Zustand in main reproduzierbar; „**unklar**" = keine Evidenz → kein Raten, an Harald zurück. Output je Issue: `#<nr> <Titel> → <Kategorie> + Begründung (Quelle)`.
- **Regel:** NICHTS ins GH-Issue eintragen — Rückmeldung NUR an Harald (z.B. kompakte Liste: relevant / überholt / bereits umgesetzt + Begründung). Bei Umsetzungs-PRs: nur `refs #<nr>` (nie `Fixes`/`Closes` — würde Issue-Status ändern; Reviewer MINOR-9a). Folge-Issues legt **Harald** an, nicht Nova (MINOR-9b, Issue-#37-Konflikt auflösen).

### 5.2 Umsetzung auf Branch mit Review (ohne Issue-Eintrag)
- **Auftrag:** Reale Aufgabe (z.B. Fix aus Issue-Relevanz-Prüfung) auf Feature-Branch umsetzen, Review-Gate durchlaufen, PR erstellen — **ohne** das GH-Issue anzufassen (kein Kommentar, kein Status-Update).
- **Vorgehen:** Standard-Workflow (Worktree, Branch `session-*/<topic>`, Review, PR) — Issue bleibt unberührt; Ergebnis an Harald.
- **Reviewende Stelle (Architect MINOR-M6):** Bei Nova-Implementierung wäre der lokale Architect/Reviewer-Sub-Agent Autor=Reviewer-verletzend. **Festlegung:** Review durch die OC-Instanzen (OC2/OC3 haben `reviewer`-Rollen-Agent; Auftrag via Gateway-API, Kap. 2-Mechanik) ODER durch Harald — je Aufgabe entscheidet Nova, mindestens ein unabhängiger Reviewer muss signieren.

## 6. Risiken & Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|---|---|
| Token-Leak | Dedizierte Tokens je Instanz, Env-only, Rotation bei Verdacht, Tailnet-only |
| Nova führt Tests manipuliert aus (kein Vier-Augen) | Seed-Defekte = harte Ground Truth (unabhängig von Nova); Adjudikation-Ergebnisse werden Harald vorgelegt; Stichproben-Review durch Harald möglich |
| Zugriffs-Ausweitung schleichend | Design-Dokument = Vertrag; Grenzen in Kap. 2 explizit; jede Erweiterung = neues Review |
| Benchmark-Daten verloren | Session-Transkripte je Instanz sichern (T1-Outputs in Repo-Dateien, Worktree) |
| Rate-Limits/Quotas (Reviewer MINOR-10) | DeepSeek/WebSearch-Limits über 14 Tage; 900-s-Timeout + Concurrency 4 als Puffer; bei Limit-Treffer: Task-Log vermerken, Lauf wiederholen |

## 7. Offene Fragen an Harald

0. **Adjudikation (Freigabe-Punkt, Reviewer MINOR-1):** Design 01 legt „Harald oder Zweit-Reviewer" fest; Design 03 schlägt zweistufig vor (Nova vor, Harald 100 % T1) — **Freigabe durch Harald erforderlich**.
1. **Tokens (Kap. 3-Festlegung):** Erzeugst du die 3 Nova-dedizierten Token-Werte (Ablage direkt in `~/.openclaw/secrets/`, 0600 — nie im Chat-Transkript) oder soll ich sie generieren? **Ausrollen ausschließlich via GH-Secret + Deploy-Workflow** (`config set` im Betrieb ist ausgeschlossen — ENV-Divergenz, Design 02 V2/Issue #68).
2. **Seed-Defekte:** Erstelle ich die T1-Snapshots mit Seed-Defekten selbst (Vorschlag: 2 Fehler je Snapshot, Muster aus echten Vorfällen wie Issue #29/N1-Blocker) — oder lieferst du welche?
3. **Frequenz:** T1-Pilot jetzt (1 Lauf je Arm) + dann 14-Tage-Betrieb — passt das?
4. **Issue-Prüfung:** Mit welchem Issue-Set starten (alle offenen IaC4-Issues, oder Prioritätenliste von dir)?
5. **T3-Modell (Architect N3, Freigabe-Punkt):** Abweichung vom gemergten Design 01 (Instanz implementiert → Nova implementiert lokal, Instanz reviewed) — bestätigst du das als Protokoll-Änderung?

## 8. Referenzen & Evidenz

- Design 01-oc2-oc3-benchmark (Kap. 6, gemerged), Design 02 V2/Issue #68 (Token-Divergenz)
- Gateway-API-Ansprache statt Felix/TOOLS.md: Instanz-Ansprache über die Gateway-API (dedizierte Nova-Tokens, Tailscale-HTTPS) — Mechanik in Kap. 2/3 dieses Designs. TOOLS.md existiert nicht mehr; Referenz bereinigt 2026-08-04
- ADR-025 (Gateway-Config/Docker/Multi-Instanz); Token-Assert in `ansible/roles/openclaw-gateway/tasks/instance.yml` (nicht in ADR-025 — Reviewer MINOR-3), PR #56/#64/#70/#72 (Infrastruktur, Kovariate, OC1-Arm)
- Harald-Entscheidungen F2–F5 (2026-08-01; F2 = eigenes PR, F3 = PROD unberührt, F4 = parallel+Kovariate, F5 = Seed-Defekte — Antworten auf Design-01-Fragen; Reviewer MINOR-5)
