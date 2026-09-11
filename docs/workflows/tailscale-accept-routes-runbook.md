# Runbook: Tailscale `--accept-routes` (Subnetz-/Exit-Routen annehmen)

> **Bezug:** IaC4-Issue **#135** („`--accept-routes` in der Tailscale-Rolle verankern").
> **Status:** verankert in IaC (Rolle + Mini-Playbook + Workflow 02b). **Kein Apply**
> im Rahmen dieses PRs — Ausführung nur manuell/nach Owner-Go.
> **Grundsatz:** reiner, additiver Flag-/Pref-Setzer — **kein Re-Join**, kein Auth-Key,
> kein Neustart des `tailscaled`-Dienstes.

## Zweck

`--accept-routes` (Pref **RouteAll**) legt fest, ob ein Knoten die **Subnetz-**
und **Exit-Routen** annimmt, die andere Tailnet-Knoten bewerben. `ha1` bewirbt
`192.168.0.0/24` (approved). `vps-dev`/`vps-prod` nahmen diese Subnetz-Route
bisher **nicht** an, weil die Ansible-Tailscale-Rolle beim Join nur Auth-Key +
Hostname setzte. Ohne `--accept-routes` ist die zugehörige **Energie-Regel
wirkungslos**.

## Wirkung

- **An:** Der Knoten installiert die beworbenen Subnetz-Routen in seine
  Routing-Tabelle → Ziele hinter `ha1` (z. B. `192.168.0.0/24`) sind über das
  Tailnet erreichbar.
- **Aus (`--accept-routes=false`):** Der Knoten ignoriert beworbene Routen.
- Betroffen sind **nur Client-Prefs** des Knotens. Andere Prefs
  (`--exit-node`, `--accept-dns`, `--shields-up`, `--advertise-*`) werden **nicht**
  angefasst.

## Soll-Zustand / IaC-Anker

| Ort | Inhalt |
|-----|--------|
| `ansible/group_vars/all.yml` | `tailscale_accept_routes: true` (Default; false = Rückweg) |
| `ansible/roles/tailscale/tasks/accept-routes.yml` | idempotenter Setzer (read → compare → set nur bei Drift) |
| `ansible/roles/tailscale/tasks/main.yml` | Join setzt `--accept-routes=…`; Include der accept-routes-Task (Tag `tailscale-accept-routes`) |
| `ansible/roles/tailscale/handlers/main.yml` | Re-Join-Handler setzt `--accept-routes=…` ebenfalls |
| `ansible/playbooks/tailscale-accept-routes.yml` | Mini-Playbook (nur dieser Schalter, kein Re-Join) |
| `.github/workflows/02b-tailscale-accept-routes.yml` | Ausführungspfad `workflow_dispatch` (`check` → `apply`) |

**Entscheidung – Soll-Zustand:** Nur `--accept-routes` ist Teil des
deklarativen Soll-Zustands der Rolle (Default `true`). Alle übrigen Prefs
bleiben bewusst unangetastet.

## Ist-Zustand prüfen (read-only)

Auf dem Knoten (via Tailscale-SSH):

```shell
tailscale get accept-routes          # true | false
tailscale get --json accept-routes   # {"accept-routes": true}
```

Fallback für ältere Clients (Feld `RouteAll`):

```shell
tailscale debug prefs | jq '.RouteAll'
```

Die Task liest genau diese Werte (kein Schreiben im Read-Schritt) und läuft mit
`check_mode: false`, damit der **Ist-Zustand auch im `--check`-Lauf** bekannt ist.

## Ausführung

### Variante A — GitHub-Workflow `02b` (Standard)

1. **Dry-Run zuerst:** Workflow `02b – Tailscale accept-routes` starten mit
   `target=dev|prod`, **`mode=check`**. Der Lauf führt
   `ansible-playbook … --check --diff` aus und zeigt Ist vs. Soll
   (Debug-Zeile `accept-routes: ist=… soll=… → DRIFT/keine Änderung`). Es wird
   **nichts** geschrieben.
2. **Apply:** denselben Workflow mit `mode=apply` und
   `confirm=APPLY-ACCEPT-ROUTES` starten. Der Guard (Schritt 1) weist ein Apply
   ohne exakte Bestätigung ab.
3. Ergebnis im Step „Verifikation" (`tailscale get accept-routes`).

Verwendete Secrets/Namespaces (unverändert zu Workflows 02/03): `SSH_KEY`,
`VPS_USER`, `TAILSCALE_OAUTH_CLIENT_ID`, `TAILSCALE_OAUTH_CLIENT_SECRET`,
`TAILSCALE_TAILNET`. Kein `VPS_*_PUBLIC_IP` nötig — der Weg läuft über die
Tailscale-IP (Public-IP ist nach Phase 2b geschlossen).

### Variante B — manuell via Tailscale-SSH (Runbook-Weg, Fallback)

Setzt voraus, dass der ausführende Rechner im Tailnet ist und SSH-Key +
SSH-Zugang hat:

```shell
# 1) Inventar (Knoten über MagicDNS erreichbar)
printf '[vps]\nvps-dev ansible_host=vps-dev.<TAILNET>.ts.net ansible_user=deploy-user\n' > /tmp/inventory

# 2) Dry-Run
cd ansible
ansible-playbook playbooks/tailscale-accept-routes.yml -i /tmp/inventory --check --diff

# 3) Apply (nur nach Owner-Go)
ansible-playbook playbooks/tailscale-accept-routes.yml -i /tmp/inventory

# 4) Kontrolle
ansible -i /tmp/inventory vps -m command -a 'tailscale get accept-routes'
```

## Idempotenz-Nachweis

Zweiter Lauf = erster Lauf:

- Read-Schritt ermittelt den Ist-Wert; die Set-Task ist über
  `when: ist != soll` gegated. Ohne Drift → Task **skipped**, `changed=0`.
- Der Dry-Run meldet `keine Änderung (idempotent)`; ein reales `tailscale set`
  passiert nur bei echtem Drift.

Nachweis: `ansible-playbook … -i /tmp/inventory` zweimal ausführen — der zweite
Lauf zeigt `changed=0`.

## Rollback

Bewusst und mit Owner-Go (Rückweg = Redeclare des Soll-Zustands):

```shell
# Variante A: Workflow 02b mit -e tailscale_accept_routes=false
# Variante B:
ansible-playbook playbooks/tailscale-accept-routes.yml -i /tmp/inventory \
  -e tailscale_accept_routes=false

# oder direkt auf dem Knoten:
tailscale set --accept-routes=false
```

Wirkung des Rollbacks: beworbene Subnetz-Routen (z. B. `192.168.0.0/24`) werden
nicht mehr angenommen; die zugehörige Energie-Regel ist dann wieder
wirkungslos. Rollback ist **kein** Re-Join.

## Prod-Regel

- **Prod (`target=prod`) führt der Owner aus** (Harald). Der Workflow erzwingt
  `confirm=APPLY-ACCEPT-ROUTES`; zusätzlich wird ein GitHub Environment mit
  Required Reviewer für prod empfohlen (Repo-Setting, nicht Teil dieses PRs).
- Der Dry-Run (`mode=check`) ist immer unkritisch und darf vorab von jedem
  Berechtigten ausgeführt werden.

## Grenzen / Sicherheit

- **Kein Re-Join:** Die Task ruft **nie** `tailscale up` auf, übergibt **keinen**
  Auth-Key und startet `tailscaled` **nicht** neu. Bestehende Knoten bleiben
  verbunden; nur der Pref wird gesetzt.
- **Kein Workflow-Trigger** durch diesen PR: `02b` hat ausschließlich
  `workflow_dispatch`. Es wurde kein Lauf gestartet.
- **Secrets** werden nie ausgegeben (`::add-mask`).

## Migrations-Log

| Datum (UTC) | Schritt | Status | Ausführender |
|-------------|---------|--------|--------------|
| 2026-09-11 | IaC-Verankerung: Rolle (Default + idempotente Task), Mini-Playbook, Workflow 02b (check/apply), Runbook; Draft-PR (kein Merge, kein Apply) | vorbereitet | Engineer |
| 2026-09-11 | Ausführung dev/prod (Dry-Run → Apply), Ist-Zustand live verifizieren | ausstehend — Owner-Go | Owner (prod) |
