# Device-Approve v3.0 – Ein-Job-Fast-Path (Lokale Testanleitung)

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
  --summary               Markdown-Summary in $GITHUB_STEP_SUMMARY
  --local                 Lokaler Modus ohne SSH (env APPROVE_LOCAL=1)
  --vps-user, --ssh-key, --ts-tailnet, --ts-client-id, --ts-client-secret
```

`--full-run` und `--discover-only` schließen sich aus. Ohne `--discover-only`
ist der SSH-Modus immer Discovery + Approve (Ein-Job).

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
| `approve.py` | CLI-Fassade (--full-run Ein-Job, --discover-only, --summary, --local) |
| `summary.py` | Markdown-Summary-Generator (Minor #7) |

## Rueckgabe-Schema

```json
{
  "status": "approved|found|not_found|error",
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
