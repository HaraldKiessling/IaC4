# Device-Approve v3.6 – Workflow 05: Geräte-Freigabe und -Verwaltung

Package `tools/device-approve/` – das CLI-Herz des Workflows 05
(`.github/workflows/05-device-approve.yml`). Es findet Geräte-Requests und
gepaarte Geräte auf den OpenClaw-Instanzen (per SSH über Tailscale) und führt
die gewünschte Aktion aus. Das Package ist standalone lokal testbar.

## Was der Workflow tut

Workflow 05 verwaltet Geräte-Zugriff auf alle OC-Instanzen (dev/prod):

- **approve** – einen offenen Geräte-Request freigeben (pending → paired)
- **list** – alle offenen Requests anzeigen (Diagnose: „Was pendet gerade wo?“)
- **reject** – einen offenen Geräte-Request ablehnen (nur device)
- **remove** – ein gepaartes Gerät entfernen (nur device)
- **e2e** – kompletten Geräte-Lifecycle testen (Request → Approve → Nutzen → Löschen)

Ein Lauf läuft in **einem** Job und nutzt **eine SSH-Session pro VPS**
(1-SSH-pro-VPS-Optimierung). Die Aktion wird direkt in der Session beim Fund
ausgeführt – auch auf prod (Owner-Entscheidung: kein Environment-Gate).

## Modi

| Mode | CLI-Flags | ID nötig? | Wirkung |
|---|---|---|---|
| `approve` (Default) | `--full-run --request-id <ID>` | ja, validiert | pending-Request freigeben (`openclaw devices approve`) |
| `list` | `--list-only` | nein (wird ignoriert) | alle pending Requests als Tabelle + JSON anzeigen |
| `reject` | `--full-run --reject-only --request-id <ID>` | ja, validiert | pending-Request ablehnen (`openclaw devices reject`) |
| `remove` | `--full-run --remove-only --request-id <ID>` | ja, validiert | gepaartes Gerät entfernen (`openclaw devices remove`) |
| `remove` + `scope=instance` | `--full-run --remove-only --scope instance` | nein (muss leer sein) | ALLE gepaarten Geräte der gefilterten Instanzen entfernen |
| `e2e` | (Workflow-eigener Step) | nein | Lifecycle-Test mit frischem Client |

`reject` und `remove` wirken **nur auf device-Einträge** – die openclaw CLI hat
kein `pairing reject`/`pairing remove` (empirisch, OpenClaw 2026.7.1).
Telegram-Pairing-Codes sind daher nicht reject-/remove-bar.

## Inputs (Workflow 05)

| Input | Default | Bedeutung |
|---|---|---|
| `mode` | `approve` | `approve` \| `list` \| `reject` \| `remove` \| `e2e` |
| `scope` | `device` | `device` = ein Gerät per `id`; `instance` = alle gepaarten Geräte der gefilterten Instanzen (nur mit `mode=remove`) |
| `id` | — | Request-ID: Telegram-Kurzcode (`QVDCXJEM`) ODER Device-ID (`9df47d69…`, 64-hex) |
| `type` | `auto` | `auto` (aus ID-Format ableiten), `telegram`, `device`, `both` |
| `target` | `both` | `dev` \| `prod` \| `both` |
| `instance` | `all` | `all` oder `oc1`…`ocN` |

Es gibt **kein Confirm-Gate** – eine Aktion wird ohne weitere Rückfrage
ausgeführt (Owner-Entscheidung 2026-08-08).

## scope=device vs. scope=instance

**`scope=device` (Default, unverändertes Verhalten):** Die ID wird validiert
(Format + Typ), das Gerät in der Ein-Job-Remote-Schleife gesucht und die
Aktion (approve/reject/remove) direkt ausgeführt.

**`scope=instance` („Instanz leeren“):** Entfernt ALLE gepaarten Geräte der
gefilterten Instanzen (z. B. `target=prod`, `instance=all`). Zweiphasig:

1. **Plan:** alle gepaarten Geräte sammeln. Keine Geräte → `not_found`
   (Exit 0, Idempotenz – ein zweiter Lauf auf leerer Instanz ist grün).
   Mehr als 50 Geräte → Abbruch mit Fehlermeldung **vor** jedem Remove
   (Exit 2, kein Massen-Remove).
2. **Remove:** jedes Gerät einzeln per `openclaw devices remove <deviceId>`
   entfernen (B2-Semantik, Shell-Hard-Cap als zusätzliche Absicherung).

`scope=instance` ist nur mit `mode=remove` erlaubt; `id` muss leer sein
(Konflikt → Exit 2). `scope=device` bleibt zu 100 % der ID-basierte Pfad.

## Exit-Codes

| Exit | Bedeutung |
|---|---|
| 0 | Erfolg: Aktion ausgeführt (approved/rejected/removed) ODER nichts gefunden (`not_found` – grün, Idempotenz) ODER Liste erstellt (auch leer) |
| 1 | Teilerfolg (`partial`: bei scope=instance einige entfernt, einige fehlgeschlagen – Details im Summary/JSON) ODER Infrastruktur-/Auth-Fehler |
| 2 | Validierungs-/Config-/Limit-Fehler (falsche ID, Konflikt `id`+`scope=instance`, > 50 Geräte, Nicht-Device bei reject/remove) |

## Sicherheits-Limit und Concurrency

- **Max 50 Geräte pro Lauf** (`MAX_REMOVE_DEVICES=50`) bei `scope=instance` –
  darüber Abbruch vor jedem Remove.
- **Concurrency-Group `device-approve`** (cancel-in-progress: false): Runs
  laufen seriell – ein neuer Run wartet, bis der laufende fertig ist (kein
  Doppel-Approve, kein stale read).
- **Tokens nie loggen:** Secrets (SSH-Key, Tailscale-OAuth, Gateway-Token)
  werden nur als Env-Variablen genutzt und nie in Logs/Summaries ausgegeben.
- **Kein jq auf den VPS nötig** (R08): Der Remote-ID-Match läuft über `grep`,
  die Verifikation macht der Python-Parser.

## Beispiele

```bash
# Alle gepaarten Geräte von prod entfernen (Instanz leeren)
python3 tools/device-approve/approve.py --full-run --remove-only --scope instance \
  --type-filter device --target-filter prod --instance-filter all \
  --vps-user "$VPS_USER" --ssh-key ~/.ssh/id_ed25519 \
  --ts-tailnet "$TS_TAILNET" --ts-client-id "$TS_CLIENT_ID" \
  --ts-client-secret "$TS_CLIENT_SECRET" --summary

# Ein Gerät freigeben (ID aus mode=list entnehmen)
python3 tools/device-approve/approve.py --full-run \
  --request-id "$REQUEST_ID" \
  --vps-user "$VPS_USER" --ssh-key ~/.ssh/id_ed25519 \
  --ts-tailnet "$TS_TAILNET" --ts-client-id "$TS_CLIENT_ID" \
  --ts-client-secret "$TS_CLIENT_SECRET" --summary

# Alle pending Requests anzeigen
python3 tools/device-approve/approve.py --list-only --local

# Lokal testen (kein SSH nötig)
python3 tools/device-approve/approve.py --remove-only --scope instance --local
```

**Wichtig:** Zwischen Listen-Lesen und approve/reject kann sich die
`requestId` ändern (wird pro Pairing-Versuch neu vergeben) – vor einer Aktion
immer frisch listen und die aktuelle ID nehmen.

## Env-Vars

| Variable | Pflicht | Default | Beschreibung |
|---|---|---|---|
| `APPROVE_ID` | je nach Mode | — | Request-ID (Telegram-Kurzcode ODER Device-ID) |
| `APPROVE_TYPE` | — | `auto` | `auto`, `telegram`, `device`, `both` |
| `APPROVE_TARGET` | — | `both` | `dev`, `prod`, `both` |
| `APPROVE_INSTANCE` | — | `all` | `all` oder `oc1`…`ocN` |
| `APPROVE_SCOPE` | — | `device` | Remove-Scope: `device` oder `instance` |
| `APPROVE_LOCAL` | — | `0` | `1` = lokaler Modus ohne SSH |
| `VPS_USER` | SSH | — | SSH-User (z. B. `deploy-user`) |
| `SSH_KEY_PATH` | SSH | — | Pfad zum SSH-Key |
| `TS_TAILNET` | SSH | — | Tailscale-Tailnet |
| `TS_CLIENT_ID` | SSH | — | Tailscale-OAuth-Client-ID |
| `TS_CLIENT_SECRET` | SSH | — | Tailscale-OAuth-Client-Secret |
| `INSTANCE_MAP` | — | — | Pfad zur SSoT-Map (sonst sot_parser-Generierung) |
| `GITHUB_STEP_SUMMARY` | — | — | Pfad für `--summary` Markdown-Ausgabe |

## Discovery-Quellen

| Typ | SSH-Quelle (`docker exec`) | ID-Feld |
|---|---|---|
| telegram | `openclaw pairing list telegram --json` | `code` (Kurzcode) |
| device | `openclaw devices list --json` | pending: `requestId` (UUID-36); paired: `deviceId` (64-hex) |

| Aktion | Kommando |
|---|---|
| approve | `openclaw devices approve <requestId>` / `openclaw pairing approve telegram <CODE>` |
| reject | `openclaw devices reject <requestId>` (nur device) |
| remove | `openclaw devices remove <deviceId>` (nur device, nur paired) |

## Tests

```bash
python3 -m pytest tests/device-approve/ -v
```

## Module

| Modul | Zweck |
|---|---|
| `approve.py` | CLI-Fassade (`--full-run`, `--discover-only`, `--list-only`, `--reject-only`, `--remove-only`, `--scope device\|instance`, `--summary`, `--local`) |
| `discovery.py` | Ein-Job-Kern: VPS-Gruppierung, Remote-Kommando-Builder, Output-Parser, Validierung |
| `summary.py` | Markdown-Summary-Generator (alle Modi inkl. Instanz-Remove) |
| `approve_step.py` | Approve-only-Library (wird vom Workflow nicht mehr aufgerufen) |
