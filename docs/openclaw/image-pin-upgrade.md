# Image-Pin- und Config-Schema-Upgrades (OpenClaw)

Gilt für jede Änderung von `openclaw_image_version` und jede Änderung an
`ansible/roles/openclaw-gateway/templates/openclaw.json.j2`.

## Warum diese Regel existiert

Vorfall 2026-11-18: Nach dem Pin-Wechsel auf `2026.11.4` liefen **frische**
Instanzen nicht mehr an. Symptome waren irreführend:

- `openclaw config validate`: `StateDatabaseAccessError … offline maintenance`
- npm-/Plugin-Installs brachen mit `rc=137` (SIGKILL) ab
- Container im Restart-Loop (100+ Restarts), `docker logs` leer
- Health-Check lief 6 Minuten in `Connection reset by peer`

Echte Ursache: Die Config-Vorlage erzeugte ein **veraltetes Schema**.
`2026.11.4` lehnt die Config komplett ab → Gateway beendet sich sofort →
Restart-Loop. Die DB-Maintenance- und SIGKILL-Meldungen waren Folgefehler.
Bestehende Instanzen liefen nur, weil sie zuvor per `openclaw doctor --fix`
migriert worden waren.

## Pflicht-Checkliste bei Pin-Änderungen

1. **Branch, nie direkt `main`.** Änderung nur auf Feature-Branch.
2. **Schema der Zielversion prüfen:**
   ```bash
   openclaw config schema > /tmp/schema.json
   ```
   Templates gegen die neuen Keys abgleichen (`agents.*`, `memory.*`,
   `plugins.*`). Besonders prüfen: umbenannte oder entfernte Keys.
3. **Gerenderte Config validieren** (isoliertes State-Dir, damit kein DB-Lock
   blockiert):
   ```bash
   docker compose run --rm \
     -e OPENCLAW_STATE_DIR=/tmp/ocv \
     -e OPENCLAW_CONFIG_PATH=/home/node/.openclaw/openclaw.json \
     openclaw openclaw config validate --json
   ```
   Ziel: `"valid": true`. Bei `issues` zuerst das Template korrigieren.
4. **Frisch-Install-Test auf EINER dev-OC** (niemals prod):
   - Instanz wipen (`Wipe – OC-Instanz`, `confirm=WIPE-OC`)
   - Deploy aus dem Branch mit `target=dev`, `instance=<eine OC>`
   - Erfolg = `PLAY RECAP failed=0` **und** Health grün **und**
     `provider`/Plugin im laufenden Gateway verifiziert
5. **Erst danach** weitere dev-Instanzen, dann prod – einzeln, wegen des
   15-Minuten-Joblimits.
6. **Kein Pin-Downgrade.** Die State-DB wird nur vorwärts migriert; ein
   älterer Build verweigert den Start (`schema version … this build supports …`).

## Schema-Änderungen 2026.9.8 → 2026.11.4 (aus dem Vorfall)

- `agents.list` → **`agents.entries`** (keyed by agent id, kein `id`-Feld im Objekt)
- `agents.defaults.memorySearch` → **`memory.search`** (Top-Level)
- `memory.backend` → **entfernt** (QMD ist kein Config-Key mehr)
- `agents.ownership: "explicit"` ist für Multi-Agent-Rosters **Pflicht**
- `agents.entries.<id>` darf leer sein (Defaults greifen)

## Diagnosewerkzeuge (alle über GitHub Actions)

| Workflow | Zweck |
|---|---|
| `diag-oc-state.yml` | Read-only: Container, Version, Update-Status, Logs, Config-Validität, Host-RAM |
| `oc-foreground.yml` | Start im Vordergrund inkl. `validate`-Modus mit isoliertem State |
| `oc-power.yml` | `stop`/`start` einer Instanz |
| `wipe-oc.yml` | Destruktiv: Container + `/srv/openclaw/<inst>` löschen (`confirm=WIPE-OC`) |
| `seed-tools.yml` | Tools/Plugins zwischen Instanzen kopieren (Reparatur, `confirm=SEED-TOOLS`) |
| `04-service-deploy.yml` | Deploy (`target`, `playbook`, `instance`) |

## Merksätze

- **Erst Dev, dann Prod** – immer aus einem Branch, immer eine Instanz zuerst.
- **Config-Validierung vor dem Deploy**, nicht danach.
- **Symptome sind nicht die Ursache**: `rc=137` und „offline maintenance"
  waren hier Folgen eines Config-Fehlers, nicht Speichermangel.
- Bei Restart-Loop mit leeren Logs: **Foreground-Start** und
  **`config validate`** mit isoliertem State-Dir.
