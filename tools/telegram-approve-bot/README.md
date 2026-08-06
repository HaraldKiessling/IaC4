# Telegram-Device-Approve-Bot (Design 05, M4)

Minimaler Bot als **reiner Trigger** (Minor #10): Er validiert Telegram-User
(Whitelist) und Request-ID und stoesst ein GitHub-`repository_dispatch`-Event
`device-approve` an. **Das Ergebnis des Approves laeuft im GH-Actions-Run**
(Workflow `06-device-approve-telegram.yml`) und ist dort zu pruefen – der Bot
bekommt nur das Dispatch-Bestaetigungs-204. Callback/Run-Polling als Folgeausbau.

## Dateien

| Datei | Zweck |
|---|---|
| `bot.py` | Bot-Logik: `parse_request_id()`, `is_authorized()`, `dispatch_request()`, `handle_message()` |
| `auth_check.sh` | Ausgelagerter Auth-Check (identische Logik wie Workflow 06, unit-testbar) |
| `sot_parser.py` | SSoT-Parser `ansible/group_vars/vps-*.yml` → `name\|target` (geteilt mit Workflow 06 + Tests) |
| `requirements.txt` | Python-Abhaengigkeiten (`requests`) |

## Sicherheits-Design (reviewed Konzept §2.3)

| Gate | Mechanismus |
|---|---|
| Telegram-Auth | Whitelist `TELEGRAM_APPROVE_USERS` (GH-Secret, kommagetrennte User-IDs); Fallback-Konstante = Harald `7145674995` |
| ID-Injection (Blocker #3) | Geankerte Regex `^/approve\s+([a-zA-Z0-9_-]{8,64})$` – keine Shell-Metazeichen, keine Mehrdeutigkeit |
| PAT | `GH_DEVICE_APPROVE_PAT` (GH-Secret, feingranular, `repo`-Scope) – nur Env-Referenz, nie committen |
| Timeout (Minor #12) | `requests.post(..., timeout=10)` + expliziter Timeout-Fehlerpfad |

## Secrets (M2, in GH-Settings anlegen – niemals committen)

- `TELEGRAM_APPROVE_USERS` – kommagetrennte Telegram-User-IDs, z.B. `7145674995`
- `GH_DEVICE_APPROVE_PAT` – Fine-Grained PAT mit `repo`-Scope auf `HaraldKiessling/IaC4`

## Deployment-Optionen (F1 – Entscheidung Harald)

1. **Cloudflare Worker** (kostenlos, kein VPS noetig): Webhook-Registrierung via
   Telegram `setWebhook`, Worker ruft `handle_message()`-Logik (Python-Port noetig
   oder Worker als schlanker HTTP-Handler, der `bot.py`-Regex/Dispatch-Logik 1:1
   uebernimmt).
2. **systemd-Service auf vps-dev**: `python3 bot.py` als Polling-Bot (getUpdates)
   oder Webhook; `TELEGRAM_APPROVE_USERS`/`GH_DEVICE_APPROVE_PAT` als
   systemd-Environment (Referenz auf GH-Secrets beim Deploy).
3. **OpenClaw-Skill**: Dogfooding, haengt an laufender OC-Instanz.

## Payload-Schema (Dispatch an GH)

```json
{
  "event_type": "device-approve",
  "client_payload": { "id": "req_abc123", "telegram_user_id": "7145674995" }
}
```

## Dry-Run in dev OHNE echte Approve (vor M3/M4)

Workflow 06 fuehrt im `approve`-Job den echten `openclaw devices approve` aus.
Fuer einen gefahrlosen Testlauf ohne echte Freigabe:

1. Dispatch mit Dummy-ID feuern (kein realer pending Request vorhanden)
   → `discover`-Job laeuft, meldet "Request-ID auf keiner enabled Instanz gefunden",
   `approve` wird nie gestartet. Damit ist die gesamte Discovery-Kette
   (Auth, SSoT-Mapping, Tailscale, SSH, Docker-Exec-List) getestet.
2. Smoke-Test (echter Approve) spaeter manuell: Request-ID aus der Control-UI
   nehmen, per `curl -X POST .../dispatches` mit `GH_DEVICE_APPROVE_PAT` senden,
   Run in GH Actions verfolgen. M3 setzt M2 voraus (Environments `dev-approve`/
   `prod-approve`, Secrets).

## Idempotenz (Major #5, V0 – VOR M3)

Empirisch auf vps-dev/oc1 pruefen, ob `openclaw devices approve <id>` bei bereits
bestaetigter ID **harmlos** ist (dann bleibt der Call ohne `|| true`) oder
**fehlschlaegt** (dann Pre-Check "bereits confirmed" bzw. `|| true` im Workflow 06
einbauen). Ergebnis im Workflow-Kommentar fixieren.

## Tests

```bash
python3 -m pip install --user pyyaml pytest requests
python3 -m pytest -v tests/device-approve/
bash -n tools/telegram-approve-bot/auth_check.sh tests/device-approve/test_auth_check.sh
bash tests/device-approve/test_auth_check.sh      # Shell-Auth-Checks
shellcheck tools/telegram-approve-bot/auth_check.sh tests/device-approve/test_auth_check.sh
```
