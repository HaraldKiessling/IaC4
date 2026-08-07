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
steht diese UUID im Feld `deviceId` des pending-Eintrags → die UUID **wird** in
der Liste gefunden, und `openclaw devices approve <UUID>` funktioniert. Die
64-Hex-Werte sind die `deviceId`s der **gepaarten** Geräte (nach dem Approve).

## CLI-Fakten (empirisch, OpenClaw 2026.7.1)

| Kommando | Bedeutung | ID-Format |
|---|---|---|
| `openclaw devices list --json` | pending + paired | `deviceId` (pending: UUID-36, paired: 64-hex) |
| `openclaw devices approve <requestId>` | pending → paired | UUID-36 |
| `openclaw devices reject <requestId>` | pending ablehnen | UUID-36 |
| `openclaw devices remove <deviceId>` | **paired-Eintrag löschen** | 64-hex |
| `openclaw pairing list/approve` | Telegram-Pairing (Code) | Kurzcode 6-12 A-Z0-9 |

Wichtiger Unterschied (v3.2-Reject-Doku): `reject` wirkt NUR auf **pending**
Requests, `remove` NUR auf **paired** Geräte. Für den Owner-Lösch-Schritt
(eine *hergestellte* Verbindung löschen) ist **`remove`** der richtige Befehl.

## Harness

Reproduzierbarer Lauf: `.github/workflows/06-device-e2e-lifecycle.yml`
(workflow_dispatch: `target` dev|prod, `instance` oc1). Der Lauf nutzt die
etablierten Muster aus Workflow 05 (Tailscale-Join, SSH docker exec,
Tailscale-API-IP-Auflösung) und führt den kompletten Lifecycle in EINEM Job
aus – der frische Client (neue Device-Identität) lebt im Runner-Volume
(`/tmp/e2e-<target>-<inst>`) und bleibt über alle Schritte identisch.

### Ablauf (je Umgebung, zuerst dev, dann prod)

| # | Schritt | Kommando | Erwartung |
|---|---|---|---|
| 1 | Request erzeugen | frischer Client: `openclaw gateway call health --url wss://vps-<t>.<tailnet>:<port> --token <GW_TOKEN>` | 1008 `pairing required … (requestId: <UUID-36>)`, pending Request entsteht |
| 2 | List-Nachweis | SSH: `sudo docker exec openclaw-<inst> openclaw devices list --json` | UUID im pending[]-Eintrag, Feld `deviceId` |
| 3 | Approve | SSH: `sudo docker exec openclaw-<inst> openclaw devices approve <UUID>` | pending → paired (64-hex deviceId, clientId `openclaw-cli`) |
| 4 | Nutzbar | derselbe Client reconnectet (`health`) | `"ok": true`, kein 1008 |
| 5 | Löschen | SSH: `sudo docker exec openclaw-<inst> openclaw devices remove <deviceId>` | paired-Eintrag weg |
| 6 | Nicht nutzbar | derselbe Client reconnectet | Fehler/1008 (neue requestId) |
| 7 | Cleanup | SSH: `… openclaw devices reject <neue-requestId>` | keine pending Reste |

### Fehlerabbruch (vermuteter Bug-Pfad)

Wird in Schritt 1/2 KEINE UUID-requestId gefunden oder erscheint die UUID
nicht im pending-Array → Lauf bricht mit Befund ab (kein Weiterraten).

## Befunde

| Umgebung | Request-UUID | List-Feld | Approve | Nutzbar | Delete | Nicht nutzbar |
|---|---|---|---|---|---|---|
| dev/oc1 | (Run-Beleg) | `deviceId` = UUID | RC 0 | health ok | paired=0 | 1008 |
| prod/oc1 | (Run-Beleg) | `deviceId` = UUID | RC 0 | health ok | paired=0 | 1008 |

Details pro Lauf: Job-Summary des 06-Workflows (Run-URL) + Run-Log
(JSON-Auszüge, keine Secrets).
