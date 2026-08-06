# Issue-Vorlage: Workflow-05-Erweiterung – Telegram-Device-Approve (VPS dev+prod, alle OC-Instanzen)

> **Hinweis:** Erstellt als Datei (Engineer, 2026-08-06), da `gh`-CLI/Token in der
> Ausführungsumgebung nicht verfügbar waren. Inhalt = fertiger Issue-Body –
> nach GitHub einfügen (Repo `HaraldKiessling/IaC4`) und F1–F7 durch Harald klären.
> Quelle: `konzepte/05-workflow-erweiterung-reviewed.md` (reviewed, alle 17 Befunde aufgelöst).

---

## Motivation (Realfall 2026-08-06)

Am 2026-08-06 wurde eine Request-ID (`b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5`) per
Telegram freigegeben. Auf dem **lokalen/aufrufenden Gateway** war sie NICHT pending
(`pending: []`); ein Remote-Gateway-Zugriff war lokal nicht möglich. Die ID hing an
 einer anderen Instanz – genau der Anwendungsfall, den der **D1-Discovery-Scan**
(Workflow 06) löst: instanzübergreifende Suche über alle enabled Instanzen,
unabhängig vom aufrufenden Gateway. Ohne Discovery wäre der Approve gescheitert,
obwohl die ID im Gesamtsystem existierte.

## Anforderung

Device-Pairing-Freigabe per **Telegram-Nachricht** auslösen (statt nur GH-UI
`workflow_dispatch`) – mit **EINER einzigen ID** (Request-ID aus der Control-UI),
ohne manuelle target/instance-Selektion. Mobil unterwegs gibt es keinen GH-UI-Zugang;
die VPS-Architektur soll flexibler werden (ein VPS für dev+prod, beliebig viele
OC-Instanzen). Auth: nur Owner (Harald).

**Scope:** Telegram-Trigger, VPS kann beide Umgebungen bedienen, Instanzen dynamisch
aus SSoT (`ansible/group_vars/vps-*.yml`), Single-ID-Trigger mit Auto-Ableitung von
target+instance, Auth nur Owner.
**Non-Goals:** Multi-User, eigene Bot-Infrastruktur neu bauen (minimaler Bot via
@BotFather), Device-Registrierung, Control-UI-Änderungen, Echtzeit-Push nach Approve.

## Design (Empfehlung A1 + B1 + C1 + D1)

| Dimension | Wahl | Begründung |
|---|---|---|
| Telegram-Trigger | **A1** `repository_dispatch` via Bot-Webhook | GH-nativ, Audit-Trail, minimaler Bot (A2 verworfen: Chicken-Egg bei neuer Kopplung + kein GH-Audit; A3 = Overhead) |
| VPS dev+prod | **B1** SSoT-gesteuertes Mapping, `target` als Instanz-Attribut | Maximal flexibel, 1 VPS = 1 Env bleibt Spezialfall |
| Dynamische OC | **C1** SSoT-Datei als Validierungsquelle, `type: string` + Regex + SSoT-Check | Beliebig viele Instanzen ohne Workflow-Änderung |
| Single-ID | **D1** Discovery-Scan über alle enabled Instanzen | Operator sendet genau die ID aus der UI |

**Kernlogik (D1):** Workflow liest SSoT-Mapping → SSH auf alle VPS → `openclaw devices
list` auf jeder enabled Instanz → grep nach Request-ID → Fund = Instanz+target+VPS-IP
ermittelt → Approve genau dort. Aktuell 2 VPS × 3 Instanzen = 6 SSH-Calls (~3–5 s extra).

**Neuer Workflow `06-device-approve-telegram.yml` (Zwei-Job-Design):** `discover`
(Auth-Check mit Nicht-Leer-Prüfung VOR Whitelist-Grep; Request-ID-Regex; SSoT-Mapping
via dynamischem Globbing; Tailscale-API `fields=hostname,addresses,lastSeen` und
`-1`-Fallback; UNREACHABLE-Liste) → `approve` (`needs: discover`, Job-Level-Environment
`prod-approve`/`dev-approve`, SSH-Approve `openclaw devices approve`).

**M1a (`05-device-approve.yml`):** SSoT-Validierung, Request-ID-Regex,
Environment-Gate job-level; `instance` bleibt `type: choice` (M1a/M1b-Split).

## Review-Verdikt

🔴 CHANGES REQUESTED (3 Blocker / 6 Major / 6 Minor / 2 Info) → **alle Befunde in v2
aufgelöst oder als Entscheidung/offener Punkt geführt** (`konzepte/05-workflow-erweiterung-reviewed.md` §5).

| ID | Schwere | Befund | Auflösung |
|---|---|---|---|
| 1 | 🔴 Blocker | Auth-Bypass bei leerer Telegram-User-ID | Nicht-Leer-Check vor Whitelist (§2.1) |
| 2 | 🔴 Blocker | Kein echtes Environment-Gate | Zwei-Job-Design, Job-Level-`environment` (§2.1) |
| 3 | 🔴 Blocker | Bot-Regex ungeankert | `^/approve\s+([a-zA-Z0-9_-]{8,64})$` (§2.3) |
| 4 | 🟠 Major | Nummerierungskonflikt 05 | Doku-Bereinigung geplant (Cleanup-PR oder Design-PR) |
| 5 | 🟠 Major | Idempotenz nicht analysiert | V0 vor M3, Ergebnis steuert `\|\| true` vs. Pre-Check |
| 6 | 🟠 Major | Tailscale-API ohne `lastSeen`/`-1`-Fallback | Übernommen aus 04/05 (§2.1) |
| 7 | 🟠 Major | Hartkodierte Dateiliste beim Mapping | `glob('vps-*.yml')` (§2.1) |
| 8 | 🟠 Major | `dev-approve`-Environment fehlt | Environment wird angelegt (ohne Protection, M2) |
| 9 | 🟠 Major | Choice→String bricht UX vor M3 | M1a/M1b-Split (§2.2) |
| 10 | 🟡 Minor | Kein Feedback-Loop Bot→Ergebnis | Dokumentiert, Callback als Folgeausbau |
| 11 | 🟡 Minor | Namenskonvention `oc1-dev` kollidiert | Instanznamen `oc1…` + target-Attribut |
| 12 | 🟡 Minor | Kein Timeout im requests.post | `timeout=10` (§2.3) |
| 13 | 🟡 Minor | Zeilenreferenz Z.50 falsch | Z.55 korrigiert |
| 14 | 🟡 Minor | Verworfener Mapping-Ansatz unklar | Als verworfen gekennzeichnet (DRY/ADR-017) |
| 15 | 🟡 Minor | Unreachable VPS nicht in Fehlerausgabe | `UNREACHABLE`-Liste (§2.1) |
| 16 | ℹ️ Info | F2/F3/F6 vor M1 klären | In offene Fragen übernommen |
| 17 | ℹ️ Info | Discovery macht implizites Mapping explizit (Positiv) | In Ist-Analyse verankert (§1) |

## Migrationsplan

| Schritt | Änderung | Risiko | Abhängigkeit |
|---|---|---|---|
| **V0** | Idempotenz-Check `openclaw devices approve` (doppelte ID) auf vps-dev/oc1 dokumentieren | — | vor M3 (Major #5) |
| **M1a** | 05: SSoT-Validierung + Regex + Environment-Gate, **Choice bleibt** | Niedrig | — |
| **M2** | GH Environments `prod-approve` (Required Reviewer=Harald) + `dev-approve` (ohne Protection) + Secrets `TELEGRAM_APPROVE_USERS`, `GH_DEVICE_APPROVE_PAT` | Niedrig | M1a |
| **M3** | `06-device-approve-telegram.yml` (Zwei-Job-Design, Discovery, korrigierte Auth/Regex) | Mittel | V0, M1a, M2 |
| **M1b** | 05: `instance` choice → string + SSoT-Validierung (erst jetzt!) | Niedrig | M3 stabil (Major #9) |
| **M4** | Telegram-Bot deployen (Hosting nach F1), Secrets zuweisen | Mittel | M3 |
| **M5** | VPS-Combi: `target`-Attribut pro Instanz, Discovery-Logik anpassen | Hoch | M3 stabil; **nur wenn F3 ≤ 3 Monate** |
| **M6** | group_vars → zentrales Mapping konsolidieren (DRY) | Mittel | M5 validiert |

## Offene Entscheidungen (Harald)

- **F1** Bot-Hosting: Cloudflare Worker / systemd auf vps-dev / OC-Skill? → bestimmt M4
- **F2** Prod-Schutz: GH-Environment-Review in UI **oder** Telegram-Rückfrage `/confirm`?
- **F3** VPS-Combi-Zeithorizont ≤ 3 Monate? sonst M5 auskoppeln
- **F4** Discovery parallel vs. sequenziell (Performance vs. Log-Determinismus)
- **F5** Control-UI „Mit Telegram approven"-Button (Upstream-Änderung, optional)
- **F6** `05-device-approve.yml` nach M3 behalten (Fallback) oder deprecaten?
- **F7** Explizite `instance-vps-map.yml` als SSoT (generiert) vs. group_vars-Parsing (aktuell empfohlen)

## Akzeptanzkriterien

- [ ] **Approve via Telegram funktioniert auch dann, wenn die Request-ID nicht auf
      dem lokalen/aufrufenden Gateway pendet** – der Discovery-Scan findet sie auf
      der richtigen Instanz (instanzübergreifend, D1; Realfall 2026-08-06:
      `b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5` lokal `pending: []`)
- [ ] `/approve <request-id>` aus Telegram startet einen GH-Actions-Run (Audit-Trail: wer/wann/was)
- [ ] Nur autorisierte Telegram-User-IDs (Whitelist-Secret) kommen durch; leere User-ID wird abgelehnt
- [ ] Request-IDs mit Shell-Metazeichen werden abgelehnt (Regex, Bot + Workflow)
- [ ] prod-Approve läuft durch das Environment `prod-approve` (Required Reviewer); dev ohne Protection
- [ ] Discovery findet die Request-ID über alle enabled Instanzen (SSoT-dynamisch, kein Hardcoding)
- [ ] VPS-down wird als `UNREACHABLE` in der Fehlermeldung ausgewiesen, ohne stillen Fehler
- [ ] Doppelter Approve derselben ID ist definiert (V0-Ergebnis dokumentiert)
- [ ] Alle Statik-/Unit-Checks grün (actionlint, shellcheck, yamllint, pytest)

## Test-Strategie

1. **Unit/Statik (automatisiert, ohne Tailscale/SSH):** `ci-device-approve.yml` mit
   actionlint + shellcheck + pytest + `bash -n`; pytest für Bot-Regex (positiv/negativ/
   Injection/Whitelist) und SSoT-Parser (enabled-Filter, mehrere VPS-Dateien, M5-target).
2. **Dry-Run (vor M3/M4):** Dispatch mit Dummy-ID → `discover` durchläuft die ganze Kette
   (Auth, Mapping, Tailscale, SSH, List), meldet „nicht gefunden"; `approve` startet nie.
3. **Smoke-Test (nach M2):** echte Request-ID aus der Control-UI per Dispatch, Run in GH
   Actions verfolgen; Idempotenz-V0 auf vps-dev/oc1.
4. **Keine echten Tailscale-/SSH-Produktions-Calls in Tests.**
