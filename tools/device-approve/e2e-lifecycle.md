# Device E2E Lifecycle – Request → List → Approve → Nutzbar → Delete → Nicht nutzbar

**Owner-Auftrag (2026-08-07 06:12):** Ein echter Geräte-Verbindungs-Request auf
einen OC pro dev/prod beantragen, die GUID in der Liste nachweisen, den Approval
herstellen UND nutzen, anschließend erfolgreich löschen und nachweisen, dass die
Verbindung danach nicht mehr genutzt werden kann.

**Frage des Owners:** „Wird die Approval-ID im UUID-Format (36 Zeichen) vom
Workflow/der Validierung gefunden?" – Offene Requests traten bisher in zwei
Formaten auf: UUID-36 (`21e6459c-…`, `840fc0f0-…`) und 64-Hex-deviceIds
(`5a3aecec-…`).

**Antwort (empirisch, siehe unten):** Pending Device-Requests haben IMMER eine
UUID-36-`requestId` (Gateway-vergeben). In `openclaw devices list --json`
steht diese UUID im Feld `requestId` des pending-Eintrags → die UUID **wird** in
der Liste gefunden, und `openclaw devices approve <requestId>` funktioniert. Das
Feld `deviceId` des pending-Eintrags ist dagegen der 64er-Public-Key-Hash des
anfragenden Clients (kein UUID-Format). Nach dem Approve ist die UUID-36
verbraucht; der gepaarte Eintrag wird über die 64-hex-`deviceId` adressiert.

## CLI-Fakten (empirisch, OpenClaw 2026.7.1)

| Kommando | Bedeutung | ID-Format |
|---|---|---|
| `openclaw devices list --json` | pending + paired | pending: `requestId` (UUID-36) + `deviceId` (64-hex Key-Hash); paired: `deviceId` (64-hex) |
| `openclaw devices approve <requestId>` | pending → paired | UUID-36 |
| `openclaw devices reject <requestId>` | pending ablehnen | UUID-36 |
| `openclaw devices remove <deviceId>` | **paired-Eintrag löschen** | 64-hex |
| `openclaw pairing list/approve` | Telegram-Pairing (Code) | Kurzcode 6-12 A-Z0-9 |

Wichtiger Unterschied (v3.2-Reject-Doku): `reject` wirkt NUR auf **pending**
Requests, `remove` NUR auf **paired** Geräte. Für den Owner-Lösch-Schritt
(eine *hergestellte* Verbindung löschen) ist **`remove`** der richtige Befehl.

## Harness

Reproduzierbarer Lauf: **Workflow 05, `mode: e2e`** (workflow_dispatch:
`target` dev|prod, `instance` oc1) – im selben Job wie die etablierten Muster
(Tailscale-Join, SSH docker exec, Tailscale-API-IP-Auflösung). Der frische
Client (neue Device-Identität) lebt im Runner-Volume (`/tmp/e2e-<target>-<inst>`)
und bleibt über alle Schritte identisch.

### Ablauf (je Umgebung, zuerst dev, dann prod)

| # | Schritt | Kommando | Erwartung |
|---|---|---|---|
| 1 | Request erzeugen | frischer Client: `openclaw gateway call health --url wss://vps-<t>.<tailnet>:<port> --token <GW_TOKEN>` | 1008 `pairing required … (requestId: <UUID-36>)`, pending Request entsteht |
| 2 | List-Nachweis | SSH: `sudo docker exec openclaw-<inst> openclaw devices list --json` | UUID im pending[]-Eintrag, Feld `requestId` (UUID-36) |
| 3 | Approve | SSH: `sudo docker exec openclaw-<inst> openclaw devices approve <requestId>` | pending → paired (64-hex deviceId, clientId `openclaw-cli`) |
| 4 | Nutzbar | derselbe Client reconnectet (`health`) | `"ok": true`, kein 1008 |
| 5 | Löschen | SSH: `sudo docker exec openclaw-<inst> openclaw devices remove <deviceId>` | paired-Eintrag weg |
| 6 | Nicht nutzbar | derselbe Client reconnectet | Fehler/1008 (neue requestId) |
| 7 | Cleanup | SSH: `… openclaw devices reject <neue-requestId>` | keine pending Reste |

### Fehlerabbruch (vermuteter Bug-Pfad)

Wird in Schritt 1/2 KEINE UUID-requestId gefunden oder erscheint die UUID
nicht im pending-Array → Lauf bricht mit Befund ab (kein Weiterraten). Seit
Review-Auflage H1 (PR #110) endet der Lauf dort ohne Diagnose-Payload – der
Transport-/Token-/Config-Check gehört vor den Run.

## Befunde

| Umgebung | Request-UUID | List-Feld | Approve | Nutzbar | Delete | Nicht nutzbar |
|---|---|---|---|---|---|---|
| dev/oc1 | [Run 31156870577](https://github.com/HaraldKiessling/IaC4/actions/runs/31156870577) | `requestId` = UUID | RC 0 | health ok | paired=0 | 1008 |
| prod/oc1 | [Run 31157287607](https://github.com/HaraldKiessling/IaC4/actions/runs/31157287607) | `requestId` = UUID | RC 0 | health ok | paired=0 | 1008 |

Details pro Lauf: Job-Summary des 05-Workflows mode=e2e (Run-URL) + Run-Log
(JSON-Auszüge, keine Secrets).

Weitere Nachweise (Approve/Reject/Listen-Pfad, ohne e2e-Lifecycle):

| Zweck | Run | Beleg |
|---|---|---|
| Reject-Validierung (device) | [Run 31156775179](https://github.com/HaraldKiessling/IaC4/actions/runs/31156775179) | Ein-Job-Reject-Pfad |
| Approve (Owner-ID 2daff7a2) | [Run 31168376348](https://github.com/HaraldKiessling/IaC4/actions/runs/31168376348) | Approve-Ergebnis |
| Approve (Owner-ID cb169e88) | [Run 31169341980](https://github.com/HaraldKiessling/IaC4/actions/runs/31169341980) | Approve-Ergebnis |
| Listen-Nachweis | [Run 31168469067](https://github.com/HaraldKiessling/IaC4/actions/runs/31168469067) / [Run 31169455208](https://github.com/HaraldKiessling/IaC4/actions/runs/31169455208) | pending[] mit requestId (UUID-36) |
| Remove (mode=remove, prod/oc1) | [Run 31179037313](https://github.com/HaraldKiessling/IaC4/actions/runs/31179037313) | status `removed`, found prod/oc1 (deviceId ea9b406a…), REMOVE-Marker |
| Remove-Idempotenz (2. Lauf) | [Run 31179068439](https://github.com/HaraldKiessling/IaC4/actions/runs/31179068439) | status `not_found` → Exit 0 (grün, Vertrag 0=removed|not_found) |
| Remove-List-Nachweis | [Run 31179182663](https://github.com/HaraldKiessling/IaC4/actions/runs/31179182663) | paired-Eintrag entfernt; Geraet hat danach erneut gepairt (neuer pending-Request 2086be70…, Gerät-seitig) |

*Tabelle aktualisiert im Rahmen der Review-Auflagen H3/H5 (PR #110, 2026-08-07)
und des Remove-Modus v3.5 (PR für session-20260807/device-remove, 2026-08-07).*

## Remove-Modus (v3.5, `mode: remove`) – Revoke gepaarter Geräte

**Owner-Auftrag (2026-08-07 12:14, Antwort „2 b“):** mode=remove als
Follow-up-Feature in Workflow 05 aufnehmen – der Revoke gepaarter Geräte läuft
über den etablierten Workflow-Pfad (statt manuellem SSH / standalone-Workflow
05-device-remove.yml).

**CLI-Fakt (OpenClaw 2026.7.1, empirisch):** `openclaw devices remove
<deviceId>` entfernt einen GEPAARTEN Eintrag – Argument ist die 64-hex
deviceId aus `paired[]` (Public-Key-Hash), KEINE requestId (UUID-36 wird mit
Exit 1 „unknown deviceId“ abgelehnt). `openclaw pairing` kennt KEIN remove
(nur approve|list|help) → remove ist device-only.

**Workflow-Mapping:** `mode: remove` → Validate-Step (device-only-Hard-Gate,
--validate-id) → `approve.py --full-run --remove-only --request-id
$APPROVE_ID` → Ein-Job-Remote-Schleife matcht Array `paired` + Feld
`deviceId` (nicht pending/requestId) und führt `openclaw devices remove
<deviceId>` in der SSH-Session aus (REMOVE-Marker, B2-Semantik).
Exit-Code-Vertrag: 0 = removed ODER not_found (grün), 1 = error, 2 = config.

## Instanz-Remove (v3.6, `mode: remove` + `scope: instance`) – „Instanz leeren“

**Owner-Entscheidungen (2026-08-08):** Entfernt ALLE gepaarten Geräte der
gefilterten Instanzen (z. B. `target=prod`, `instance=all`) – NICHT
„neuestes je Instanz“. **Kein Confirm-Gate** (bewusst keine confirm-Pflicht).
**Sicherheits-Limit:** max 50 Geräte pro Lauf (`MAX_REMOVE_DEVICES=50`),
darüber Abbruch mit klarer Fehlermeldung (Exit 2) VOR jedem Remove.

**Ablauf (Workflow 05, zweiphasig in approve.py):**

| Phase | Kommando | Ergebnis |
|---|---|---|
| 1 Plan | `collect_paired_devices` (build_list_remote_cmd + parse_paired_output) | Remove-Plan über ALLE paired[]-Einträge der gefilterten Instanzen; leer → `not_found` (Exit 0, Idempotenz); > 50 → Exit 2 VOR jedem Remove |
| 2 Remove | `run_instance_remove` (build_instance_remove_remote_cmd: pro Gerät `openclaw devices remove <deviceId>`, DEV-REMOVE-BEGIN/END/FAILED-Marker, B2-Semantik; Shell-Hard-Cap als Defense-in-Depth) | alle entfernt → Exit 0; Teilerfolg → Exit 1 (Fehlgeschlagene im Summary); Limit-Marker → Exit 2 |

**Exit-Code-Vertrag v3.6:** 0 = alle entfernt ODER not_found (grün),
1 = Teilerfolg (failed im Summary), 2 = Config/Limit. Konflikt
`id` + `scope=instance` → Fehler (Validate-Step exit 1 / approve.py exit 2).
scope=device (Default) = ID-basierter v3.5-Pfad, 100 % unverändert
(Rückwärtskompatibilität). Summary-JSON erweitert: `scope`, `removed_count`,
`per_instance`, `failed`, `limit_hit`.

**Live-Nachweis:** Ein nicht-destruktiver `mode=list`-Run auf dem Branch
verifiziert die Discovery (paired[]-Bestand); ein echter
`mode=remove scope=instance`-Lauf (destruktiv) wartet auf separate
Owner-Freigabe.
