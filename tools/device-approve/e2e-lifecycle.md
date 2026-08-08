# Device E2E Lifecycle – Request → List → Approve → Nutzbar → Remove

Dokumentation der Live-Nachweise für Workflow 05 (`tools/device-approve/`):
Wie ein Geräte-Request entsteht, freigegeben, genutzt und wieder entfernt
wird – und wie der Instanz-Remove (v3.6) auf den produktiven Instanzen
verifiziert wurde.

## CLI-Fakten (empirisch, OpenClaw 2026.7.1)

| Kommando | Bedeutung | ID-Format |
|---|---|---|
| `openclaw devices list --json` | pending + paired | pending: `requestId` (UUID-36) + `deviceId` (64-hex Key-Hash); paired: `deviceId` (64-hex) |
| `openclaw devices approve <requestId>` | pending → paired | UUID-36 |
| `openclaw devices reject <requestId>` | pending ablehnen | UUID-36 |
| `openclaw devices remove <deviceId>` | paired-Eintrag löschen | 64-hex |
| `openclaw pairing list/approve` | Telegram-Pairing (Code) | Kurzcode 6-12 A-Z0-9 |

Kern-Unterschied: `approve`/`reject` wirken auf **pending** (UUID-36),
`remove` nur auf **paired** (64-hex). Eine frisch vergebene `requestId` kann
sich zwischen Listen-Lesen und Aktion ändern – vor approve/reject immer
frisch listen.

## Telegram-Pairing – Nachweis & Grenzen (2026-08-08)

Telegram-Pairing (Kurzcode) funktioniert und wurde live belegt:
[Run 31111747440](https://github.com/HaraldKiessling/IaC4/actions/runs/31111747440)
(06.08.2026, 14:38 UTC, success, `id=TY522VMZ`, type=telegram, prod/oc2,
`status: approved` via `openclaw pairing approve telegram TY522VMZ`).

Grenze: Ein **bestehendes** Telegram-Pairing kann nicht gezielt entfernt
werden – `openclaw pairing` kennt nur `approve | list` (kein remove/revoke,
empirisch OpenClaw 2026.7.1); `reject`/`remove` in Workflow 05 sind strikt
Geräte-only (Hard-Gate `05-device-approve.yml:198-201`). Approved Sender
liegen in SQLite (`channel_pairing_allow_entries`); `openclaw channels remove
--channel telegram` würde den ganzen Bot-Account löschen. Für die Abnahme
eines frischen Telegram-Pairings ist daher ein neuer, frischer OC nötig
(evtl. genügt ein OC Clean – prüfen):
[Issue #119](https://github.com/HaraldKiessling/IaC4/issues/119).

## Harness

Reproduzierbarer Lauf: **Workflow 05, `mode: e2e`** (workflow_dispatch:
`target` dev|prod, `instance` oc1). Ein frischer Client (neue
Device-Identität) lebt im Runner-Volume (`/tmp/e2e-<target>-<inst>`) und
bleibt über alle Schritte identisch:

| # | Schritt | Erwartung |
|---|---|---|
| 1 | Request erzeugen (Client-Connect, 1008 `pairing required` + UUID-36-requestId) | pending Request entsteht |
| 2 | List-Nachweis (`devices list --json`): UUID im `pending[]`, Feld `requestId` | UUID gefunden |
| 3 | Approve (`devices approve <requestId>`) | pending → paired |
| 4 | Nutzbar (Client-Reconnect, `health`) | `"ok": true`, kein 1008 |
| 5 | Löschen (`devices remove <deviceId>`, 64-hex aus `paired[]`) | paired-Eintrag weg |
| 6 | Nicht mehr nutzbar (Client-Reconnect) | Fehler/1008 (neue requestId) |
| 7 | Cleanup (`devices reject <neue-requestId>`) | keine pending Reste |

Abbruch mit Befund (Exit 1), wenn die UUID nicht gefunden wird.

## Lifecycle-Nachweise (dev + prod)

| Umgebung | Request-UUID | Ergebnis |
|---|---|---|
| dev/oc1 | [Run 31156870577](https://github.com/HaraldKiessling/IaC4/actions/runs/31156870577) | requestId im pending[], approve RC 0, health ok, paired=0 nach remove, 1008 danach |
| prod/oc1 | [Run 31157287607](https://github.com/HaraldKiessling/IaC4/actions/runs/31157287607) | dito (kompletter Lifecycle auf prod) |

## Instanz-Remove v3.6 – Live-Nachweis (prod, 2026-08-08)

`mode=remove` + `scope=instance` auf `main` (HEAD 824bb295): alle gepaarten
Geräte von prod/oc1 + prod/oc2 entfernen.

| Run | Zweck | Ergebnis (Summary-JSON) |
|---|---|---|
| [31246321993](https://github.com/HaraldKiessling/IaC4/actions/runs/31246321993) | Instanz-Remove prod (oc1+oc2) | `status: removed`, `removed_count: 2` (oc1: 1, oc2: 1), `failed: []`, Exit 0 |
| [31246375875](https://github.com/HaraldKiessling/IaC4/actions/runs/31246375875) | 2. Lauf (Idempotenz) | `removed_count: 1` (nur oc1 – Gerät hat sich automatisch neu gepairt), Exit 0 |
| [31246433582](https://github.com/HaraldKiessling/IaC4/actions/runs/31246433582) | 3. Lauf | `removed_count: 1` (oc1 – Auto-Re-Pairing reproduzierbar), Exit 0 |
| [31246480093](https://github.com/HaraldKiessling/IaC4/actions/runs/31246480093) | Post-Check `mode=list` | `entries: []` (0 pending Requests auf prod) |

Einordnung: oc2 war nach dem 1. Lauf durchgehend leer. Auf oc1 paart sich
das Win32-Control-UI-Gerät nach jeder Entfernung automatisch neu – der
Workflow verarbeitet den Ist-Zustand korrekt (Idempotenz: leerer Bestand ist
Exit 0, kein Fehler). Geräte-IDs werden aus Sicherheitsgründen nie im
Workflow-Log ausgegeben; belegt wird über `removed_count` je Instanz.

## Approve-Nachweise (UUID-Freigaben, 2026-08-08)

| Run | Request-ID | Ergebnis |
|---|---|---|
| [31246830424](https://github.com/HaraldKiessling/IaC4/actions/runs/31246830424) | `11064631-2e37-4638-b958-c8d38db71ebc` (prod/oc1) | `status: approved`, found prod/oc1, Exit 0 |
| [31246797154](https://github.com/HaraldKiessling/IaC4/actions/runs/31246797154) | `82922601-66e0-4d59-a831-9949cb11ff17` (prod/oc2) | `status: approved`, Exit 0 |

Nachweis-Check nach beiden Approves: `mode=list`-Run
[31246881439](https://github.com/HaraldKiessling/IaC4/actions/runs/31246881439)
→ `entries: []` (beide UUIDs nicht mehr pending).

## Weitere Nachweise (Approve/Reject/Remove-Einzelpfad)

| Zweck | Run | Beleg |
|---|---|---|
| Reject-Validierung (device) | [Run 31156775179](https://github.com/HaraldKiessling/IaC4/actions/runs/31156775179) | Ein-Job-Reject-Pfad |
| Approve (Owner-ID 2daff7a2) | [Run 31168376348](https://github.com/HaraldKiessling/IaC4/actions/runs/31168376348) | Approve-Ergebnis |
| Approve (Owner-ID cb169e88) | [Run 31169341980](https://github.com/HaraldKiessling/IaC4/actions/runs/31169341980) | Approve-Ergebnis |
| Listen-Nachweis | [Run 31168469067](https://github.com/HaraldKiessling/IaC4/actions/runs/31168469067) / [Run 31169455208](https://github.com/HaraldKiessling/IaC4/actions/runs/31169455208) | pending[] mit requestId (UUID-36) |
| Remove (mode=remove, prod/oc1) | [Run 31179037313](https://github.com/HaraldKiessling/IaC4/actions/runs/31179037313) | status `removed`, found prod/oc1 (deviceId ea9b406a…), REMOVE-Marker |
| Remove-Idempotenz (2. Lauf) | [Run 31179068439](https://github.com/HaraldKiessling/IaC4/actions/runs/31179068439) | status `not_found` → Exit 0 (Vertrag 0=removed\|not_found) |
| Remove-List-Nachweis | [Run 31179182663](https://github.com/HaraldKiessling/IaC4/actions/runs/31179182663) | paired-Eintrag entfernt; Gerät hat danach erneut gepairt |

Details pro Lauf: Job-Summary des 05-Workflows (Run-URL) + Run-Log
(JSON-Auszüge, keine Secrets).
