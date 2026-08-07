# Device-Approve v3.5.0 – Ein-Job-Fast-Path (Lokale Testanleitung)

Package `tools/device-approve/` (Design 05 v3.0, Workflow-05-Performance-Optimierung)
– Unified ID-basierte Freigabe (Telegram-Pairing + Device-Approve) als
standalone, lokal testbare CLI.

**v3.0 (Ein-Job-Design, 2026-08-06):** Discovery + Approve laufen in EINEM
Workflow-Job und in EINER SSH-Session pro VPS (1-SSH-pro-VPS-Optimierung,
`group_by_vps` + `build_ein_job_remote_cmd`). Der Approve wird direkt beim
Fund in der Session ausgeführt – auch auf prod (Owner-Entscheidung: kein
Environment-Gate, kein Required Reviewer). `approve.py --full-run` ist der
Workflow-Standard; `approve_step.py` bleibt als Library erhalten, wird aber
vom Workflow nicht mehr aufgerufen.

**Kein jq auf den VPS (R08):** Der Remote-ID-Match läuft über `grep` auf das
JSON-Textfeld (POSIX-Tools), die autoritative Verifikation macht der
Python-Parser (`parse_ein_job_output`). jq ist NICHT erforderlich.

**v3.1 – Listen-Modus (`--list-only`, Design 05-workflow-listen-modus.md,
Review R01–R09):** Statt einer ID zu suchen/freizugeben werden ALLE pending
Requests über alle (gefilterten) Instanzen aggregiert (Telegram `requests[]`
+ Device `pending[]`, 1 SSH pro VPS via `build_list_remote_cmd`) und als
Markdown-Tabelle (Job-Summary) + JSON ausgegeben. KEIN Approve; Exit 0 auch
bei leerer Liste (grün). Die JSON-Block-Generierung ist mit dem Approve-Modus
geteilt (`_build_json_collection_block`, R01).
**v3.3 – Listen-Modus + requestId (2026-08-07, Owner-Auftrag „die GUID soll
in der Liste stehen“, e2e-Beleg aee3a00):** Pro pending Device-Eintrag wird
zusätzlich `requestId` (UUID-36) ausgegeben – die ID, die
`openclaw devices approve/reject` erwartet (pending[].deviceId ist der
64er-PublicKey-Hash, NICHT die Approve-ID). JSON: `entries[].requestId`
("" = nicht vorhanden, z.B. Telegram-pairing-requests ohne requestId-Feld;
ID-Feld dort bleibt `code`). Job-Summary: neue Spalte „Request-ID“ mit der
VOLLEN UUID (bewusste Ausnahme zur ID-Kürzung).
**v3.3.1 – Approve/Reject-Match auf requestId (2026-08-07, Bugfix, Beleg:
7 approve/reject-Runs not_found trotz pending, u.a. 31165552730/31165829570):**
Der Approve-/Reject-Pfad matchte `"deviceId": "<UUID>"` – aber die UUID-36
steht in pending[] im Feld `requestId` (deviceId ist der 64er-PublicKey-Hash).
Fix: `_SOURCE_ID_FIELD` device → `requestId`; der Remote-grep matcht defensiv
`"(requestId|deviceId)"`; `entry_matches_id` prüft requestId zuerst, deviceId
als Fallback. Listen-Pfad unveraendert (extrahiert requestId seit v3.3).
Validierung/Typ-Ableitung unveraendert (UUID-36 = device).
**Ephemerität (wichtig vor approve/reject):** Die requestId wird pro
Pairing-Versuch NEU vergeben (e2e-Beleg: nach jedem Client-Connect entsteht
eine frische UUID; ein wiederholt neu pairender Client erzeugt laufend neue
Requests). Zwischen Listen-Lesen und Approve kann sie sich also ändern – vor
einem approve/reject IMMER frisch listen und die aktuelle requestId nehmen.
**v3.2 – Reject-Modus (`--reject-only`, 2026-08-07, Diagnose-Folgeauftrag):**
Statt zu approven wird die ID in derselben Ein-Job-Remote-Schleife gesucht
und per `openclaw devices reject <ID>` abgelehnt (REJECT-BEGIN/END/FAILED-
Marker, B2-Semantik). **NUR device-Requests:** die openclaw CLI hat kein
`pairing reject` (empirisch 2026-08-07: `openclaw pairing` kennt nur
approve|list|help) → Telegram-Codes sind CLI-seitig nicht reject-bar
(Hard-Gate: `derived_type != device` ⇒ Exit 2 in approve.py, ValueError in
build_ein_job_remote_cmd, Abbruch im Workflow-Validate-Step).
**v3.5 – Remove-Modus (`--remove-only`, 2026-08-07, Owner-Auftrag 12:14
„mode=remove als Follow-up-Feature in Workflow 05“, Antwort „2 b“):**
Statt zu approven/abzulehnen wird ein GEPAARTES Geraet in derselben
Ein-Job-Remote-Schleife gesucht und per `openclaw devices remove <deviceId>`
entfernt (REMOVE-BEGIN/END/FAILED-Marker, B2-Semantik). **ID-Unterschied zu
approve/reject (CLI-Fakt OpenClaw 2026.7.1):** remove matcht GEPAARTE
Eintraege – Array `paired`, ID-Feld `deviceId` (64-hex Public-Key-Hash;
paired-Eintraege haben KEINE requestId; e2e-Beleg `devices remove
<deviceId>` → 'Removed 587758f1…'). approve/reject wirken weiterhin nur auf
pending (requestId=UUID-36). **NUR device:** kein `pairing remove` in der
CLI → `derived_type != device` ⇒ Exit 2 in approve.py, ValueError im
Remote-Builder, Abbruch im Workflow-Validate-Step. Exit-Code-Vertrag:
0 = removed ODER not_found (gruen), 1 = error, 2 = config.

## Schnellstart (lokaler Modus)

```bash
# Notwendig: openclaw CLI verfuegbar
cd IaC4
# Telegram-Kurzcode (Test-ID) → pairing-Pfad
export APPROVE_ID="QVDCXJEM"
export APPROVE_TYPE="auto"
export APPROVE_LOCAL=1
python3 tools/device-approve/approve.py --discover-only
# → {"status":"not_found","id":"QVDCXJEM","found":[],"scanned":["local/local"],
#    "filters_applied":{"type":"telegram","target":"both","instance":"all"}}

# Device-ID (Test-ID, UUID-Stil) → devices-Pfad
export APPROVE_ID="b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5"
python3 tools/device-approve/approve.py --discover-only
# → status=not_found (erwartet – lokal keine pending Eintraege)
```

## Env-Vars (alle Modi)

| Variable | Pflicht | Default | Beschreibung |
|---|---|---|---|
| `APPROVE_ID` | ✅ | — | Request-ID: Telegram-Kurzcode `^[A-Z0-9]{6,12}$` ODER Device-ID `^[0-9a-fA-F-]{36,128}$` |
| `APPROVE_TYPE` | — | `auto` | `auto` (aus Format ableiten), `telegram`, `device`, `both` |
| `APPROVE_TARGET` | — | `both` | Target-Filter: `dev`, `prod`, `both` |
| `APPROVE_INSTANCE` | — | `all` | Instanz-Filter: `all` oder `oc1`...`ocN` |
| `APPROVE_LOCAL` | — | `0` | `1` = lokaler Modus ohne SSH |
| `VPS_USER` | SSH | — | SSH-User (z.B. `deploy-user`) |
| `SSH_KEY_PATH` | SSH | — | Pfad zum SSH-Key |
| `TS_TAILNET` | SSH | — | Tailscale-Tailnet |
| `TS_CLIENT_ID` | SSH | — | Tailscale-OAuth-Client-ID |
| `TS_CLIENT_SECRET` | SSH | — | Tailscale-OAuth-Client-Secret |
| `INSTANCE_MAP` | — | — | Pfad zur SSoT-Map (sonst sot_parser-Generierung) |
| `GITHUB_STEP_SUMMARY` | — | — | Pfad fuer --summary Markdown-Ausgabe |

## CLI-Flags

```
python3 tools/device-approve/approve.py --help

  --request-id ID         Request-ID (oder env APPROVE_ID)
  --type-filter {auto,telegram,device,both}   (default: auto)
  --target-filter {dev,prod,both}
  --instance-filter {all,oc1,oc2,...}
  --instance-map PATH     SSoT-Instanz-Map (sonst sot_parser)
  --full-run              Ein-Job: Discovery + Approve in einem Aufruf
                          (Workflow-Standard v3.0; 1 SSH pro VPS)
  --discover-only         Nur Discovery, kein Approve
  --list-only             Listen-Modus (v3.1): ALLE pending Requests auflisten
                          (kein Approve, keine ID; schliesst --full-run/--discover-only
                          aus; --request-id wird ignoriert, type=auto → both)
  --reject-only           Reject-Modus (v3.2): ID suchen + per `openclaw devices
                          reject <ID>` ablehnen (REJECT-Marker, B2-Semantik). NUR
                          device-Requests (kein 'pairing reject' in der CLI);
                          schliesst --list-only/--discover-only aus
  --remove-only           Remove-Modus (v3.5): GEPAARTES Geraet suchen (Array
                          `paired`, Feld `deviceId` 64-hex) + per `openclaw devices
                          remove <deviceId>` entfernen (REMOVE-Marker, B2-Semantik).
                          NUR device (kein 'pairing remove' in der CLI); schliesst
                          --list-only/--discover-only/--reject-only aus
  --summary               Markdown-Summary in $GITHUB_STEP_SUMMARY
  --local                 Lokaler Modus ohne SSH (env APPROVE_LOCAL=1)
  --vps-user, --ssh-key, --ts-tailnet, --ts-client-id, --ts-client-secret
```

`--full-run`, `--discover-only`, `--list-only`, `--reject-only` und
`--remove-only` schließen sich teils gegenseitig aus: `--full-run` schließt
`--discover-only` aus; `--reject-only`/`--remove-only` schließen
`--list-only`/`--discover-only` (und sich gegenseitig) aus (mit `--full-run`
ist es der Ein-Job-Reject/-Remove). Ohne `--discover-only`/`--list-only` ist
der SSH-Modus immer Discovery + Aktion (Approve/Reject/Remove, Ein-Job).

## Listen-Modus (v3.1, `--list-only`)

Diagnose-Sicht „WAS pendet gerade WO?“ – vor einem Approve oder nach einem
`not_found`. Workflow-Input `mode: list` (Workflow 05) bzw. CLI:

```bash
# SSH: alle pending Requests ueber alle VPS (keine ID noetig; die Instanz-Map
# generiert approve.py selbst via sot_parser, v3.4/H2 – kein /tmp-Instance-Map noetig)
python3 tools/device-approve/approve.py --list-only \
  --type-filter both --target-filter both --instance-filter all \
  --vps-user "$VPS_USER" --ssh-key ~/.ssh/id_ed25519 \
  --ts-tailnet "$TS_TAILNET" --ts-client-id "$TS_CLIENT_ID" \
  --ts-client-secret "$TS_CLIENT_SECRET" --summary

# Lokal (Ergaenzung fuer Diagnose auf dem Gateway, kein TS-SSH noetig)
python3 tools/device-approve/approve.py --list-only --local
```

### Mapping mode → CLI-Flags (R02, verbindlich)

| Workflow-Input `mode` | CLI-Flags | `--request-id` |
|---|---|---|
| `approve` (default) | `--full-run --request-id $APPROVE_ID` | required, validiert (`--validate-id`) |
| `list` | `--list-only` | **NICHT übergeben** – wird ignoriert (Warning, keine Validierung) |
| `reject` (v3.2) | `--full-run --reject-only --request-id $APPROVE_ID` | required, validiert (`--validate-id`); nur device |
| `remove` (v3.5) | `--full-run --remove-only --request-id $APPROVE_ID` | required, validiert (`--validate-id`); nur device; matcht paired[].deviceId (64-hex) |

`--list-only` schließt `--full-run`/`--discover-only` aus (argparse-Fehler,
Exit 2). `--list-only` + `--request-id` → Warning auf stderr, ID wird nie
validiert/verwendet (R02). `type=auto` wird im Listen-Modus zu `both` (O3:
keine ID zum Ableiten – Diagnose will ALLES sehen).

### Darstellungs-Konventionen (R03/R04)

- **Sortierung (R03):** `createdAtMs` DESC (neueste zuerst); Sekundärschlüssel
  (target, instance, type, id) – deterministisch und stabil (in
  `summary.list_result_to_markdown` dokumentiert).
- **Platform (R04):** JSON `platform: ""` ist die Wahrheit (Telegram hat kein
  platform-Feld); die Tabelle rendert `""` → `—` (Darstellung).
- **Erstellt:** UTC (YYYY-MM-DD HH:MM); fehlendes `createdAtMs` → `—`.
- Lange IDs (>24 Zeichen) werden in der Tabelle gekürzt – die Voll-ID steht im
  JSON-Output (Run-Log).

### Exit-Code-Vertrag (Listen-Modus)

| Exit | Bedeutung |
|---|---|
| 0 | Liste erstellt – **auch leer** (grüner Run, „Keine offenen Requests“) |
| 1 | Infrastruktur-/Auth-Fehler (SSH/Tailscale down, roter Run) |
| 2 | Validierungs-/Config-Fehler (fehlende Credentials, CLI-Missbrauch) |

Listen-Modus hat NIE `not_found`-Status (es gibt keine Such-ID); leere Liste
ist ein gültiges Ergebnis.

### Concurrency + Timeout (R06/R09)

- **R06:** Der Listen-Modus teilt die Concurrency-Group `device-approve`
  (cancel-in-progress: false) → serielle Ausführung. Ein List-Run wartet
  hinter einem laufenden Approve-Run in der Queue – konservativ-korrekt (kein
  stale read), kann aber zu Wartezeiten führen.
- **R09:** Timeout identisch zum Approve-Modus (15 Min Workflow, 60s SSH).
  Worst-Case bei 5 unerreichbaren VPS: ~5×60s ≈ 5 Min.

### Listen-JSON-Schema (Design §11)

```json
{"status": "list_ok", "entries": [{"instance": "oc1", "target": "dev",
 "type": "telegram", "id": "QVDCXJEM", "platform": "",
 "createdAtMs": 1785900000000, "vps_ip": "100.64.0.1"}],
 "scanned": ["dev/oc1"], "unreachable": [],
 "filters_applied": {"type": "both", "target": "both", "instance": "all"}}
```

## Reject-Modus (v3.2, `--reject-only`)

Aufräumen eines konkreten offenen device-Requests (z.B. Test-Requests aus
Diagnosen): ID in der Ein-Job-Remote-Schleife suchen und per
`openclaw devices reject <ID>` ablehnen (docker exec im Instanz-Container,
REJECT-Marker, B2-Semantik). Workflow-Input `mode: reject` (Workflow 05) bzw.
CLI:

```bash
# SSH: Ein-Job-Reject (nur device-Requests; Instanz-Map via sot_parser, v3.4/H2)
python3 tools/device-approve/approve.py --full-run --reject-only \
  --request-id "$APPROVE_ID" \
  --type-filter device --target-filter prod --instance-filter all \
  --vps-user "$VPS_USER" --ssh-key ~/.ssh/id_ed25519 \
  --ts-tailnet "$TS_TAILNET" --ts-client-id "$TS_CLIENT_ID" \
  --ts-client-secret "$TS_CLIENT_SECRET" --summary

# Lokal (Gateway, kein TS-SSH noetig)
python3 tools/device-approve/approve.py --reject-only --local --request-id "$APPROVE_ID"
```

### Reject-Regeln (verbindlich)

- **NUR device-Requests:** die openclaw CLI hat kein `pairing reject`
  (empirisch 2026-08-07) – Telegram-Kurzcodes (6-12 A-Z0-9) werden mit
  Exit 2 abgelehnt (approve.py), der Remote-Builder wirft ValueError und der
  Workflow bricht im Validate-Step ab (defense in depth).
- **ID-Formate unverändert** (gleiche Regex wie approve): Pairing-Kurzcode
  `^[A-Z0-9]{6,12}$` / Device-ID `^[0-9a-fA-F-]{36,128}$` – UUID-36-Requests
  (z.B. `21e6459c-7323-43aa-bdb0-a3105e9d8255`) passen auf das Device-Format.
- **Exit-Code-Vertrag wie approve:** 0 = rejected ODER not_found (grüner
  Run; not_found: „kein offener Request“ statt Fehler), 1 = error,
  2 = Config/Validierungs-Fehler (inkl. Nicht-Device-Reject).

### Reject-Kommandos (Δ3, Templates in discovery.py – Single Source of Truth)

| Typ | Reject-Kommando |
|---|---|
| device | `openclaw devices reject <ID>` |
| telegram | — (CLI-seitig nicht reject-bar, kein `pairing reject`) |

## Remove-Modus (v3.5, `--remove-only`)

Entfernen eines konkreten GEPAARTEN Geraets (z.B. Revoke eines freigegebenen
Geräts per Owner-Auftrag): deviceId in der Ein-Job-Remote-Schleife im Array
`paired` suchen und per `openclaw devices remove <deviceId>` entfernen
(docker exec im Instanz-Container, REMOVE-Marker, B2-Semantik).
Workflow-Input `mode: remove` (Workflow 05) bzw. CLI:

```bash
# SSH: Ein-Job-Remove (nur device; Instanz-Map via sot_parser, v3.4/H2)
python3 tools/device-approve/approve.py --full-run --remove-only \
  --request-id "$DEVICE_ID" \
  --type-filter device --target-filter prod --instance-filter all \
  --vps-user "$VPS_USER" --ssh-key ~/.ssh/id_ed25519 \
  --ts-tailnet "$TS_TAILNET" --ts-client-id "$TS_CLIENT_ID" \
  --ts-client-secret "$TS_CLIENT_SECRET" --summary

# Lokal (Gateway, kein TS-SSH noetig)
python3 tools/device-approve/approve.py --remove-only --local --request-id "$DEVICE_ID"
```

### Remove-Regeln (verbindlich)

- **NUR device:** die openclaw CLI hat kein `pairing remove` (empirisch
  2026-08-07) – Telegram-Kurzcodes werden mit Exit 2 abgelehnt (approve.py),
  der Remote-Builder wirft ValueError und der Workflow bricht im
  Validate-Step ab (defense in depth).
- **ID-Format:** deviceId = 64-hex Public-Key-Hash des gepaarten Geraets
  (z.B. `9df47d69…925392`) – die ID aus `devices list --json` → `paired[].deviceId`.
  requestId (UUID-36) wird von remove NICHT akzeptiert (CLI-Fakt 2026.7.1:
  unbekannte ID → Exit 1 "unknown deviceId").
- **Array `paired`, nicht `pending`:** remove matcht nur gepaarte Eintraege
  (approve/reject wirken nur auf pending – requestId).
- **Exit-Code-Vertrag:** 0 = removed ODER not_found (grüner Run), 1 = error,
  2 = Config/Validierungs-Fehler (inkl. Nicht-Device-Remove).

### Remove-Kommandos (Δ4, Templates in discovery.py – Single Source of Truth)

| Typ | Remove-Kommando |
|---|---|
| device | `openclaw devices remove <deviceId>` |
| telegram | — (CLI-seitig kein paired-Array / kein `pairing remove`) |

## Discovery-Quellen (Δ1, empirisch verifiziert 2026-08-06)

| Typ | Quelle (SSH: docker exec) | Lokal (openclaw CLI) | ID-Feld |
|---|---|---|---|
| telegram | `openclaw pairing list telegram --json` | `openclaw pairing list telegram --json` | `code` |
| device | `openclaw devices list --json` | `openclaw devices list --json` | `deviceId` |

Empirisch (Sandbox): `pairing list telegram --json` → `{"channel": "telegram", "requests": []}`
(RC=0; F10 beantwortet – Feld ist `requests`). `devices list --json` → `{"pending": [...], "paired": [...]}`.
Der Parser liest `requests` mit Fallback auf `pending` (F1a: Eintragsfelder offen).

## Approve-Kommandos (Δ2, Templates in discovery.py – Single Source of Truth)

| Typ | Approve-Kommando |
|---|---|
| telegram | `openclaw pairing approve telegram <CODE>` |
| device | `openclaw devices approve <ID>` |

## Ein-Job-Remote-Loop (v3.0)

`run_discovery()` gruppiert die Instanz-Map nach VPS (`group_by_vps`) und führt
pro VPS EINEN SSH-Call mit dem Remote-Skript aus (`build_ein_job_remote_cmd`):

- Pro Instanz JSON-Block mit der Discovery-Quelle; bei `type=both` werden
  `pairing list` UND `devices list` in derselben Session abgefragt (R02).
- ID-Match im Textpfad (grep, kein jq – R08); bei Fund läuft der Approve
  direkt in der Session (APPROVE-BEGIN/END-Marker). **B2 (2. Review): Der
  Approve-Erfolg wird über den Exit-Code geprüft (KEIN `|| true` um den
  Approve) – erst nach Exit-Code 0 wird `FOUND=1` gesetzt; bei Fehler wird
  `---APPROVE-FAILED:<inst>:<typ>---` emittiert und der Workflow meldet
  status=error statt falschen Erfolgs.** Break-Semantik: erster Fund stoppt.
- Marker-Format: `---JSON-BEGIN:<inst>:<typ>---` … `---JSON-END:<inst>:<typ>---`,
  `---APPROVE-BEGIN:<inst>:<typ>---` … `---APPROVE-END:<inst>:<typ>---`,
  `---APPROVE-FAILED:<inst>:<typ>---`, `---FOUND:1|0---` (Typ-Suffix macht
  type=both eindeutig parsebar).
- `|| true` NUR an der Discovery-Quelle = fail-safe bei Instanz-Down (leere
  Ausgabe → kein Match, Scan geht zur nächsten Instanz weiter).

## Beispiele

### Lokale Discovery (Realfall-Test-IDs, alle erwartet: not_found)

```bash
# Test-ID 1: Telegram-Kurzcode (Realfall 2026-08-06)
APPROVE_ID="QVDCXJEM" APPROVE_TYPE="auto" APPROVE_LOCAL=1 \
  python3 tools/device-approve/approve.py --discover-only

# Test-ID 2: Device-ID (64-Hex, Realfall aus devices list paired)
APPROVE_ID="9df47d697653fb4069407734e06849b342738ed3e9ec4b172402aca911925392" APPROVE_LOCAL=1 \
  python3 tools/device-approve/approve.py --discover-only

# Test-ID 3: Device-ID (UUID-Stil, v2.1-Test-ID)
APPROVE_ID="b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5" APPROVE_LOCAL=1 \
  python3 tools/device-approve/approve.py --discover-only

# Test-ID 4: Device-ID (UUID-Stil, alternative)
APPROVE_ID="2e68bca9-4965-4e29-9a9d-d1a12644d644" APPROVE_LOCAL=1 \
  python3 tools/device-approve/approve.py --discover-only
```

### SSH-Modus (Workflow-Sim)

```bash
export VPS_USER="deploy-user"
export SSH_KEY_PATH="$HOME/.ssh/id_ed25519"
export TS_TAILNET="tailcfea8a.ts.net"
export TS_CLIENT_ID="..."
export TS_CLIENT_SECRET="..."
export APPROVE_ID="..."

# Ein-Job: Discovery + Approve in einem Aufruf (1 SSH pro VPS)
python3 tools/device-approve/approve.py --full-run

# Nur Discovery (Debug/Test)
python3 tools/device-approve/approve.py --discover-only
```

### Summary in Datei schreiben

```bash
export GITHUB_STEP_SUMMARY=/tmp/summary.md
python3 tools/device-approve/approve.py --discover-only --summary
# JSON auf stdout, Markdown direkt in $GITHUB_STEP_SUMMARY (File-Open, kein Redirect)
```

### ID-Validierung + Typ-Ableitung (Workflow-Step, DRY)

```bash
python3 tools/device-approve/discovery.py --validate-id QVDCXJEM --type auto
# → telegram (exit 0); bei ungueltiger ID exit 2 mit Meldung
```

## Tests

```bash
python3 -m pytest tests/device-approve/ -v
```

## Submodule

| Modul | Zweck |
|---|---|
| `discovery.py` | Ein-Job-Kern v3.0 (group_by_vps, build_ein_job_remote_cmd, parse_ein_job_output, run_remote_ssh, run_discovery, --validate-id, --approve) |
| `approve_step.py` | Approve-only-Library (typ-spezifisch; NICHT mehr vom Workflow aufgerufen, R03-E12) |
| `approve.py` | CLI-Fassade (--full-run Ein-Job, --discover-only, --list-only v3.1, --reject-only v3.2, --remove-only v3.5, --summary, --local) |
| `summary.py` | Markdown-Summary-Generator (Minor #7 + list_result_to_markdown v3.1) |

## Rueckgabe-Schema

```json
{
  "status": "approved|rejected|removed|found|not_found|error",
  "id": "QVDCXJEM",
  "found": [{"target": "dev", "instance": "oc1", "type": "telegram", "vps_ip": "100.64.0.1"}],
  "scanned": ["dev/oc1", "dev/oc2"],
  "filters_applied": {"type": "telegram", "target": "both", "instance": "all"}
}
```

## Import

```python
# Device-Approve v3.0 (Tests):
sys.path.insert(0, "tools/device-approve")
from discovery import run_discovery, validate_and_classify_id, derive_type
```
