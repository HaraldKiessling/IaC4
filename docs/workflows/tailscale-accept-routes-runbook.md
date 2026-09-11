# Runbook: Tailscale `--accept-routes` (Subnetz-/Exit-Routen annehmen)

> **Bezug:** IaC4-Issue **#135** („`--accept-routes` in der Tailscale-Rolle verankern").
> **Status:** verankert in IaC (Rolle + Mini-Playbook + Workflow **02**, `mode=accept-routes`).
> **Kein Apply** im Rahmen dieses PRs — Ausführung nur manuell/nach Owner-Go.
> **Einstieg (Ausführung):** `.github/workflows/02-tailscale-bootstrap.yml`
> mit `mode=accept-routes` — **kein** eigener Workflow.
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
| `.github/workflows/02-tailscale-bootstrap.yml` | Ausführungspfad `workflow_dispatch`, Input **`mode=accept-routes`** + Input **`accept_routes`** (true/false, Default true) (Dry-Run immer → Anwenden nur mit `confirm=APPLY-ACCEPT-ROUTES`) |

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

### Variante A — bestehender GitHub-Workflow `02` (Standard, Einstieg)

Einstieg ist **Workflow 02 – Tailscale Bootstrap / accept-routes**
(`.github/workflows/02-tailscale-bootstrap.yml`) mit dem Input **`mode`**:

1. **Dry-Run zuerst:** Workflow `02` starten mit `mode=accept-routes`,
   `target=dev|prod`, Input **`accept_routes`** (Default `true`; `false` = Rückweg)
   und **leerem** `confirm`. Der Lauf führt
   `ansible-playbook … --check --diff -e '{"tailscale_accept_routes": <accept_routes>}'`
   aus und zeigt Ist vs. Soll (Debug-Zeile
   `accept-routes: ist=… soll=… → DRIFT/keine Änderung`). Es wird **nichts**
   geschrieben.
2. **Anwenden:** denselben Workflow mit `mode=accept-routes` und
   `confirm=APPLY-ACCEPT-ROUTES` starten. Der Guard (Schritt 1) weist ein
   gesetztes, falsches Bestätigungswort ab; der Anwenden-Step ist zusätzlich an
   `confirm=APPLY-ACCEPT-ROUTES` gebunden. Der Input `accept_routes` wird als
   Extra-Var `-e tailscale_accept_routes=…` an das Mini-Playbook durchgereicht.
3. Ergebnis im Step „Verifikation“ (`tailscale get accept-routes`).

`mode=bootstrap` (Default) bleibt auf **Workflow-Ebene** der unveränderte
Public-IP-Pfad für einen frischen VPS (Phase 2a + 2b) — nicht für diesen
Wartungsschritt nutzen. Die **Tailscale-Rolle** ändert sich jedoch: der
Join (`ansible/roles/tailscale/tasks/main.yml`) und der Re-Join-Handler
(`handlers/main.yml`) setzen `tailscale up …` nun zusätzlich
`--accept-routes={{ tailscale_accept_routes | default(true) | bool | ternary('true','false') }}`
— ein künftiger Bootstrap aktiviert `--accept-routes` also **schon beim Join**
(gewollt für künftige VPS, Issue #135).

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

Bewusst und mit Owner-Go (Rückweg = Redeclare des Soll-Zustands auf `false`):

```shell
# Variante A (Workflow 02, mode=accept-routes) – der Rückweg ist derselbe Pfad
# mit Soll=false:
#   1) Dry-Run:  mode=accept-routes, target=dev|prod, accept_routes=false,
#      confirm leer → zeigt Ist (true) vs. Soll (false), ändert nichts.
#   2) Anwenden: derselbe Lauf mit confirm=APPLY-ACCEPT-ROUTES
#      → setzt `tailscale set --accept-routes=false` (kein Re-Join).
#   3) Kontrolle: Step „Verifikation“ (`tailscale get accept-routes` → false).

# Variante B (manuell via Tailscale-SSH):
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
- Der Dry-Run (`mode=accept-routes`, leerer `confirm`) ist immer unkritisch und
  darf vorab von jedem Berechtigten ausgeführt werden.

### Offener Punkt (Owner-Einstellung, B2 aus Review PR #144)

> **Prod ist aktuell nur markiert, nicht hart gegated.** Ein Apply auf
> `target=prod` verlangt denselben Confirm-String wie `dev`; es gibt **kein**
> GitHub Environment / Required Reviewer. **Vor dem ersten prod-Apply** muss der
> Owner im Repo ein Environment `prod` mit Required Reviewer (= Owner) anlegen
> und Step „(11) Anwenden“ für `target=prod` daran binden. Das ist eine
> Repo-/Owner-Einstellung und bewusst **nicht** Teil dieses PRs.

## Grenzen / Sicherheit

- **Kein Re-Join:** Die Task ruft **nie** `tailscale up` auf, übergibt **keinen**
  Auth-Key und startet `tailscaled` **nicht** neu. Bestehende Knoten bleiben
  verbunden; nur der Pref wird gesetzt.
- **Kein Workflow-Trigger** durch diesen PR: Workflow **02** (`mode=accept-routes`)
  hat ausschließlich `workflow_dispatch` (kein push/PR/schedule). Es wurde kein
  Lauf gestartet.
- **Secrets** werden nie ausgegeben (`::add-mask`).

## Migrations-Log

| Datum (UTC) | Schritt | Status | Ausführender |
|-------------|---------|--------|--------------|
| 2026-09-11 | IaC-Verankerung: Rolle (Default + idempotente Task), Mini-Playbook, Ausführungspfad in **Workflow 02** (`mode=accept-routes`, Dry-Run → Anwenden mit Confirm), Runbook; Draft-PR (kein Merge, kein Apply) | vorbereitet | Engineer |
| 2026-09-11 | Review-Auflagen PR #144 umgesetzt: Rollback-Input **`accept_routes`** (Default `true`) in Workflow 02 → als Extra-Var an Step 10/11; Doku präzisiert (B3 stale `02b`, B4 „bootstrap unverändert“); IPv4-Auswahl (B6); `bool`-Härtung der Join-/Handler-`ternary`. Kein Apply. | vorbereitet | Engineer |
| 2026-09-11 | Fix nach Dry-Run dev: Step (7) schreibt den SSH-Key mit Trailing-Newline (`printf '%s\n'`) — zuvor `printf '%s'` → OpenSSH `error in libcrypto`, Dry-Run nicht ausführbar. Kein VPS-Eingriff. | vorbereitet | Engineer |
| 2026-09-11 | Ausführung dev/prod (Dry-Run → Apply), Ist-Zustand live verifizieren | ausstehend — Owner-Go | Owner (prod) |
