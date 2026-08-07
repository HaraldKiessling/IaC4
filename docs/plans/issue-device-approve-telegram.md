# Issue-Vorlage: 05 – Unified Freigabe: Telegram-Pairing + Device-Approve (ID-basiert) v2.2

> **Hinweis:** Erstellt als Datei (Engineer, 2026-08-06), da `gh`-CLI/Token in der
> Ausführungsumgebung nicht verfügbar waren. Inhalt = fertiger Issue-Body – nach
> GitHub einfügen (Repo `HaraldKiessling/IaC4`). Stand v2.2 (korrigiert nach
> CLI-Fakten + Owner-Pairing-Beleg).
> Quelle: `iac4-design/05-workflow-erweiterung-v2.2.md` (aktuelle Wahrheit) +
> `konzepte/05-workflow-v2-reviewed.md` (v2.1, soweit nicht durch v2.2 überholt).

---

## Übersicht

Ein Workflow für BEIDE Freigabetypen:

- **Telegram-DM-Pairing** → `openclaw pairing approve telegram <KURZCODE>`
- **Device-Pairing** → `openclaw devices approve <HEX-ID>`

Typ-Ableitung automatisch aus ID-Format:

- Kurzcode `^[A-Z0-9]{6,12}$` (z.B. `QVDCXJEM`) → telegram
- Device-ID `^[0-9a-fA-F-]{36,128}$` (z.B. `9df47d697653…`, auch UUID-Stil) → device

**v2.2-Korrektur:** Die v2.1-Annahme (Telegram-Pairing erscheint in
`devices list --json` und wird mit `devices approve` freigegeben) war FALSCH.
Empirisch verifiziert (2026-08-06): `openclaw pairing` ist ein separater
CLI-Befehlspfad, Telegram-Pairing nutzt Kurzcodes.

## Motivation (Realfall 2026-08-06)

Am 2026-08-06 wurde eine Request-ID (`b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5`)
per Telegram freigegeben. Auf dem **lokalen/aufrufenden Gateway** war sie NICHT
pending (`pending: []`). Die ID hing an einer anderen Instanz – genau der
Anwendungsfall, den der **instanzübergreifende Discovery-Scan** löst: Suche über
alle enabled Instanzen, unabhängig vom aufrufenden Gateway. Zusätzlich lieferte
der Owner (2026-08-06) den realen Pairing-Beleg:
`openclaw pairing approve telegram QVDCXJEM` (Pairing-Code `QVDCXJEM`,
Telegram-User `7145674995`) – damit ist die Trennung Telegram-Pairing vs.
Device-Pairing empirisch belegt.

## Usecases

### Usecase A: Telegram-Pairing per Kurzcode

1. Harald startet Workflow mit `id = QVDCXJEM`, `type = auto`
2. Typ-Ableitung: Kurzcode-Match → `telegram`
3. Discovery: `openclaw pairing list telegram --json` auf allen enabled Instanzen
4. Fund: Code `QVDCXJEM` auf `dev/oc1` → Outputs gesetzt
5. Approve: `openclaw pairing approve telegram QVDCXJEM` via SSH
6. Summary: Pairing-Code + Instanz + VPS

### Usecase B: Device-Approve per Device-ID

1. Harald startet Workflow mit
   `id = 9df47d697653fb4069407734e06849b342738ed3e9ec4b172402aca911925392`
2. Typ-Ableitung: Hex-Format → `device`
3. Discovery: `openclaw devices list --json` auf allen enabled Instanzen
4. Fund: deviceId auf `prod/oc2` → Outputs mit `found_target=prod`
5. Environment-Gate `prod-approve` greift (Required Reviewer)
6. Approve: `openclaw devices approve 9df47d69…` via SSH
7. Summary: Device-ID + Instanz + VPS

### Usecase C: Expliziter Typ-Override

1. Harald übergibt `id = b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5`, `type = device`
2. UUID-Format (Bindestriche) → von `auto` als device abgeleitet (oder explizit)
3. Discovery nur in `devices list`, nicht in `pairing list`
4. Gleicher Ablauf wie Usecase B

## Technische Details

### CLI-Befehle (verifiziert, OpenClaw 2026.7.1 + Owner-Beleg)

| Zweck | Befehl |
|-------|--------|
| Telegram Pairing-Requests listen | `openclaw pairing list telegram --json` |
| Telegram Pairing freigeben | `openclaw pairing approve telegram <CODE>` |
| Device-Pairing-Requests listen | `openclaw devices list --json` |
| Device-Pairing freigeben | `openclaw devices approve <ID>` |

Empirisch (Sandbox 2026-08-06): `pairing list telegram --json` →
`{"channel": "telegram", "requests": []}` (RC=0; Feld `requests`, kein Fehler –
F10 beantwortet). `devices list --json` → `{"pending": [...], "paired": [...]}`.

### ID-Formate (kalibriert an realen Test-IDs)

| Test-ID | Format | Typ | Länge |
|---------|--------|-----|-------|
| `QVDCXJEM` | `^[A-Z0-9]{6,12}$` | telegram | 8 Zeichen |
| `9df47d697653fb4069407734e06849b342738ed3e9ec4b172402aca911925392` | `^[0-9a-fA-F-]{36,128}$` | device | 64 Zeichen |
| `b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5` | `^[0-9a-fA-F-]{36,128}$` | device | 36 Zeichen (UUID-Stil) |
| `2e68bca9-4965-4e29-9a9d-d1a12644d644` | `^[0-9a-fA-F-]{36,128}$` | device | 36 Zeichen (UUID-Stil) |

### Whitelist

- Telegram User ID: `7145674995` (Harald)
- Auth: `auth_check.sh` (Nicht-Leer + numerisch + Whitelist-Grep) – nur für
  `repository_dispatch` mit `telegram_user_id`

## Sicherheits-Gates

| Gate | Mechanismus |
|------|-------------|
| Auth (Telegram) | Whitelist `TELEGRAM_APPROVE_USERS` + `auth_check.sh` |
| Auth (GH-UI) | GitHub Permission Model (Owner-only) |
| ID-Injection | Regex-Validierung pro Format (Kurzcode/Hex, disjunkt) + Python `subprocess.run` (kein Shell-Kontext) |
| Prod-Schutz | GH Environment `prod-approve` (Required Reviewer) + Zwei-Job-Design |
| SSH | Tailscale-only, `StrictHostKeyChecking=accept-new`, `ConnectTimeout=10` |
| Audit | GH Actions Run Log (Jede Freigabe = Run) |

## Workflow-Struktur (05 v2.2)

- **Trigger:** `workflow_dispatch` (Inputs: `id` Pflicht; `type` Choice
  [auto, telegram, device, both] default auto; `target` Choice [both, dev, prod]
  default both; `instance` String default all) + `repository_dispatch`
  (client_payload: id, type?, target?, instance?, telegram_user_id)
- **Jobs:** `discover` → `approve` (Zwei-Job für Environment-Gate;
  `needs.discover.outputs.request_id` etc.)
- **Scripts:** `tools/device-approve/discovery.py` (Discovery-Kern, getrennte
  Quellen, `--validate-id`), `approve.py` (CLI-Fassade discovery-only,
  `--discover-only`, `--summary`, lokaler Modus), `approve_step.py`
  (approve-only, typ-spezifisch), `summary.py` (Markdown)
- **Summary:** `$GITHUB_STEP_SUMMARY` (Markdown-Tabelle mit WAS/WO/Status;
  `--summary` schreibt per File-Open, kein Redirect)

## Migrationsplan (v2.2)

| Schritt | Änderung | Risiko | Abhängigkeit |
|---------|----------|--------|--------------|
| **M1** | `tools/device-approve/` v2.2 (discovery.py, approve_step.py, approve.py, summary.py) + Tests | Niedrig | V0c (pairing-Schema) |
| **M2** | `05-device-approve.yml` → v2.2 (ersetzt 05 v1 + 06 v1); CI-Update; deploy-stages.md bereinigt; Issue/PR | Mittel | M1, F7 |
| **M3** | `06-device-approve-telegram.yml` entfernt (in 05 v2.2 integriert – im M2-PR umgesetzt) | Niedrig | M2 |
| **M4** | Telegram-Bot deployen (Hosting-Entscheidung F2) – Payload um type/target/instance erweitern | Mittel | M2 stabil |
| **M5** | VPS-Combi-Unterstützung (target als Instanz-Attribut) | Hoch | M2 stabil |

## Offene Fragen (vor M2-Deployment zu klären)

- **F1a** `pairing list --json` Eintragsschema: Felder eines pending Pairing-Eintrags
  (Hypothese: `code`, `userId`, `channel`, `createdAtMs`) – empirisch auf vps-dev/oc1
  mit Telegram-Kanal prüfen (V0c). Sandbox-Beleg: Top-Level-Schema
  `{"channel": "telegram", "requests": []}`.
- **F1b** Idempotenz `openclaw pairing approve` bei bereits genehmigtem Code –
  Harmlos (Exit 0) oder Fehler?
- **F5** Idempotenz `openclaw devices approve` bei bereits genehmigter ID (V0)
- **F7** GH Environments `prod-approve` (Required Reviewer) + `dev-approve`
  (ohne Protection) bereits angelegt? → Deployment-Blocker
- **F10** `pairing list telegram` ohne konfigurierten Kanal → leere Liste oder
  Fehler? **Belegt (Sandbox):** mit explizitem Kanal RC=0 + `requests: []`;
  ohne Kanal Fehler "No chat DM pairing channels are configured" → Discovery
  überspringt fail-safe.

## Akzeptanzkriterien (Test-IDs)

- [ ] **Telegram-Pairing:** `id = QVDCXJEM` (Kurzcode) → Typ-Ableitung
      `telegram`, Discovery über `pairing list telegram --json`, Approve
      `openclaw pairing approve telegram QVDCXJEM`
- [ ] **Device-Approve (64-Hex):** `id = 9df47d697653fb4069407734e06849b342738ed3e9ec4b172402aca911925392`
      → Typ-Ableitung `device`, Discovery über `devices list --json`, Approve
      `openclaw devices approve <ID>`
- [ ] **Device-Approve (UUID-Stil):** `id = b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5`
      und `id = 2e68bca9-4965-4e29-9a9d-d1a12644d644` → Typ-Ableitung `device`
- [ ] **Lokal testbar (Testbarkeits-Beleg):** `APPROVE_LOCAL=1 python3
      tools/device-approve/approve.py --discover-only` liefert für alle vier
      Test-IDs `not_found` mit korrekter `filters_applied.type`
      (QVDCXJEM → telegram, restliche → device)
- [ ] Approve via Telegram funktioniert auch dann, wenn die Request-ID nicht auf
      dem lokalen/aufrufenden Gateway pendet (instanzübergreifend, D1)
- [ ] Nur autorisierte Telegram-User-IDs (Whitelist-Secret) kommen durch; leere
      User-ID wird abgelehnt (auth_check.sh)
- [ ] IDs mit Shell-Metazeichen werden abgelehnt (Zwei-Format-Regex, Bot + Workflow)
- [ ] prod-Approve läuft durch das Environment `prod-approve` (Required Reviewer);
      dev ohne Protection
- [ ] Discovery findet die ID über alle enabled Instanzen (SSoT-dynamisch,
      `glob('vps-*.yml')`, kein Hardcoding)
- [ ] VPS-down wird als `UNREACHABLE` in der Fehlermeldung ausgewiesen
- [ ] Typ-Filter wirkt: `type=telegram` durchsucht NUR `pairing list`,
      `type=device` NUR `devices list`, `both` beide (sequentiell)
- [ ] Doppelter Approve derselben ID ist definiert (F1b/F5-Ergebnis dokumentiert)
- [ ] Alle Statik-/Unit-Checks grün (actionlint, shellcheck, bash -n, pytest)

## Test-Strategie

1. **Unit/Statik (automatisiert, ohne Tailscale/SSH):** `ci-device-approve.yml`
   mit actionlint + shellcheck + pytest + `bash -n`; pytest für discovery
   (pairing/device-Pfade, Typ-Filter, GITHUB_OUTPUT), approve_step (Mock-SSH,
   typ-spezifische Kommandos), approve.py CLI (--discover-only, --summary,
   lokaler Modus), Bot-Regex und SSoT-Parser.
2. **Dry-Run (vor Deployment):** Dispatch mit Dummy-ID → `discover` durchläuft
   die ganze Kette (Validierung, Mapping, Tailscale, SSH, List), meldet
   „nicht gefunden"; `approve` startet nie.
3. **Smoke-Test (nach M2):** echte Request-ID aus der Control-UI per Dispatch,
   Run in GH Actions verfolgen; Idempotenz-V0 (F1b/F5) auf vps-dev/oc1.
4. **Keine echten Tailscale-/SSH-Produktions-Calls in Tests.**

## Referenzen

- Konzept: `iac4-design/05-workflow-erweiterung-v2.2.md` (aktuelle Wahrheit)
- Reviewed v2.1: `konzepte/05-workflow-v2-reviewed.md` (3 Major in v2.2 adressiert)
- V2-Draft: `architect/iac4-design/05-workflow-erweiterung-v2.md`
- Workflows: `05-device-approve.yml` (v2.2), `06-device-approve-telegram.yml`
  (gelöscht – in 05 v2.2 integriert)
- Doku: <https://docs.openclaw.ai/cli/pairing>
