# ADR-027: Upload-Brücke — Host-verwalteter Tailscale-Serve-Transport (HTTPS aus HTTPS-Browser)

- **Status:** Vorgeschlagen (Proposed)
- **Datum:** 2026-10-03
- **Issue:** #167
- **Supersedes:** – (kein Vorgänger; neue Entscheidung)
- **Bezug:** ADR-018 (HTTPS via Tailscale Serve), ADR-025 (OpenClaw Multi-Instanz),
  ADR-026 (Tailscale-ACL SSoT in IaC4)

## Kontext

Die Upload-Brücke (`upload-bridge.js`, **extern** aus `steuer-automation`, nicht
Bestandteil des OpenClaw-Images) läuft **im OpenClaw-Container** und lauscht dort
auf **Port 8099** (`openclaw_upload_bridge_internal_port`, SSoT
`ansible/group_vars/all.yml` Z.60). Der Aufruf erfolgt aus einem **HTTPS-Browser**;
die Brücke muss daher **per HTTPS** erreichbar sein, sonst blockiert der Browser
den Aufruf als **Mixed Content** (HTTP-Inhalt in einer HTTPS-Seite).

Gleichzeitig gilt:

- **Keine hartkodierte Container-IP:** `172.18.0.7` (Issue-wörtlicher Vorschlag)
  ist bei jedem `docker compose`-Recreate instabil (neue IP-Zuordnung im
  `traefik-network`). Ein daran gebundener Serve-Befehl bricht beim nächsten
  Recreate still.
- **ADR-025-Muster:** Jede OpenClaw-Instanz (oc1/oc2/oc3) ist ein gepinnter
  Container, Ports werden nur an **localhost** gebunden, TLS terminiert
  **Tailscale Serve** host-seitig (`--https=<port>`, belegt in
  `ansible/roles/openclaw-gateway/tasks/instance.yml` Z.242–244).
- **ADR-026-Grundsatz:** ACL-Änderungen sind Infrastruktur und werden **ausschließlich
  in IaC4** verwaltet, rein additiv, nur manuell angewendet.
- **Abgrenzung:** IaC4 liefert **nur den Transport** (Port-Mapping + Serve +
  ACL). Die Brücke selbst ist extern und darf **keine Deploy-Voraussetzung** sein
  (Deploy muss auch ohne laufende Brücke grün bleiben).

**Eingefrorene Entscheidung (Owner-Freigabe 2026-10-03, bindend):** Host-
verwalteter Tailscale Serve pro OpenClaw-Instanz, generisch für alle OCs.

## Entscheidungsfrage

Wie wird die im OpenClaw-Container auf 8099 lauschende Upload-Brücke **stabil**,
**HTTPS-fähig** (Mixed-Content-frei) und **IaC4-verwaltet** für den Owner-Browser
erreichbar gemacht — ohne hartkodierte Container-IP und ohne die Brücke zur
Deploy-Voraussetzung zu machen?

## Entscheidung

**Host-verwalteter Tailscale Serve pro OpenClaw-Instanz** (Loopback-Publish +
Serve), generisch über die bestehende `openclaw_instances`-Schleife:

1. **Loopback-Publish (Container → Host):** Der Container-Port
   `openclaw_upload_bridge_internal_port` (**8099**, fest, externes Artefakt) wird
   je Instanz auf einen **eigenen Host-Loopback-Port** publiziert
   (`127.0.0.1:{{ oc.upload_bridge_host_port }}:{{ openclaw_upload_bridge_internal_port }}`)
   — analog zum bestehenden `127.0.0.1:{{ oc.port }}:{{ oc.port }}` in
   `ansible/roles/openclaw-gateway/templates/docker-compose.yml.j2` (Z.8), nur dass
   intern (8099) und extern (`upload_bridge_host_port`, je Instanz) **verschieden**
   sind. Die Compose-Zeile wird nur bei `oc.upload_bridge_enabled` gerendert
   (Z.9–13).
2. **Tailscale Serve (Host, HTTPS):** Je Instanz ein Serve-Eintrag
   `tailscale serve --bg --https={{ oc.upload_bridge_https }} http://localhost:{{ oc.upload_bridge_host_port }}`.
   Der HTTPS-Port (`upload_bridge_https`) ist der **Tailnet-Port** für den
   Owner-Browser; er zeigt auf den Loopback-Host-Port und damit auf den Container.
3. **Generisch für alle OCs:** Die Zuordnung wird als **explizite, gepinnte
   Konstante** in `group_vars` je Instanz geführt (kein Index-Arithmetik-Magic),
   identisch zum bestehenden `port:`-Muster (18789/18790/18791).

### Port-Zuordnung (bewusst gesetzte Konstanten)

| Instanz | Container intern (fest) | Host-Loopback (127.0.0.1) | Serve-HTTPS (`upload_bridge_https`, Tailnet) |
|---|---|---|---|
| oc1 | 8099 | 18099 | 8443 |
| oc2 | 8099 | 18100 | 8444 |
| oc3 | 8099 | 18101 | 8445 |

Serve-Befehl je Instanz (Muster):
`tailscale serve --bg --https={{ oc.upload_bridge_https }} http://localhost:{{ oc.upload_bridge_host_port }}`
z. B. oc1: `tailscale serve --bg --https=8443 http://localhost:18099`.

**Kollisions-Check (belegt):** Die Ports 18099/18100/18101, 8443/8444/8445 und
8099 sind im Repo **aktuell unbelegt** — `8443` erscheint nur als
**container-interner** Traefik-Service-Port des code-server
(`services/code-server/docker-compose.yml` Z.30, `loadbalancer.server.port=8443`,
**kein** Host-Publish, `ansible/roles/code-server/tasks/main.yml` Z.41 „kein
Host-Port-Mapping"). Host-seitig existieren derzeit nur die Serve-Ports
443 (traefik), 6333/6334 (qdrant) und 18789–18791 (openclaw) — keine Überschneidung.

### Aktivierungs-Gate (Code = Maßstab)

Die `upload_bridge_*`-Konstanten sind in `group_vars` **immer** definiert
(dev: `upload_bridge_enabled: true`; prod: Werte definiert, `upload_bridge_enabled: false`
→ Aktivierung erst nach separater Owner-Freigabe). Das Verhalten wird über das
explizite Boolean **`oc.upload_bridge_enabled`** gesteuert (keine
„leerer-Wert"-Implizitheit), konsistent in Compose-Template und Serve-Task:

- **`group_vars/vps-dev.yml`:** oc1/oc2/oc3 `upload_bridge_enabled: true`,
  `upload_bridge_host_port` 18099/18100/18101, `upload_bridge_https` 8443/8444/8445.
- **`group_vars/vps-prod.yml`:** identische Werte, `upload_bridge_enabled: false`.

### ACL-Bezug (additiv, manueller Apply)

Neue **eigene Regelgruppe `upload-bridge`** in `acl/tailscale-acl.hujson`
(Marker `// rule: upload-bridge`), rein additiv, **nur Owner**:

```hujson
{
  "action": "accept",
  "src": ["autogroup:owner"],
  "dst": ["tag:ia4:8443", "tag:ia4:8444", "tag:ia4:8445"],
},
```

- **`src: autogroup:owner`** bewusst **enger** als die üblichen
  `admin/member`-Muster: Der Mixed-Content-Anwendungsfall ist der **Owner-Browser**.
- **`dst: tag:ia4:8443,8444,8445`** = die drei Serve-HTTPS-Ports auf dem
  (mit `tag:ia4` getaggten) VPS.
- **Apply ausschließlich manuell** über `.github/workflows/00-acl-apply.yml`
  (ADR-026-Governance): `dry_run` → Owner-`confirm` → Apply; **kein**
  push-/PR-Trigger, kein Auto-Apply.

## Optionen

### A: Host-verwalteter Tailscale Serve pro Instanz (Loopback-Publish + Serve) — EMPFEHLUNG
- **Vorteile:**
  - **Stabil gegen Recreate:** Ziel ist `localhost:<host_port>`, keine
    Container-IP → übersteht jedes `docker compose`-Recreate.
  - **Mixed-Content-frei:** Tailscale Serve stellt ein gültiges
    Let's-Encrypt-Zertifikat für `*.ts.net` aus → HTTPS aus HTTPS-Browser
    (ADR-018-Muster, bereits im Betrieb verifiziert).
  - **IaC4-verwaltet + idempotent:** über die bestehende
    `openclaw_instances`-Schleife; Serve-State-Check wie in `instance.yml`
    (Z.237–244) → kein Duplikat, Reproduzierbarkeit (QZ1).
  - **Abgrenzung gewahrt:** nur Transport (Port-Map + Serve + ACL); die Brücke
    selbst bleibt extern.
  - **Multi-Instanz-generisch:** identischer Mechanismus für oc1/oc2/oc3,
    Benchmark-Parität (alle Arme können die Brücke gleichberechtigt testen).
- **Nachteile:**
  - Zwei Port-Ebenen (8099 → 18099+ → 8443+) = etwas mehr kognitiver Aufwand.
  - Ein zusätzlicher `tailscale serve`-Eintrag je Instanz (Serve-Konfig wächst).
  - Loopback-Port-Mapping im Compose existiert auch, wenn die Brücke (noch)
    nicht läuft — harmlos, aber „toter" gemappter Port (Akzeptiert).

### B (a): Manueller Host-Befehl mit Container-IP (Issue-wörtlich) — VERWORFEN
- **Vorteile:** minimaler Aufwand (ein `tailscale serve`-Einzeiler).
- **Nachteile (entscheidend):** hartkodierte Container-IP `172.18.0.7` ist bei
  Recreate **instabil** (Docker-DNS/IP-Zuordnung ändert sich) → Serve zeigt ins
  Leere; nicht idempotent, nicht IaC-verwaltet, widerspricht Reproduzierbarkeit
  (QZ1) und dem ADR-025-Loopback-Muster.

### C (b): Traefik-Pfadrouting über das bestehende :443-Serve — VERWORFEN
- **Vorteile:** nutzt den vorhandenen Traefik-Root-Mount (`tailscale serve
  http://localhost:80`, HTTPS:443) ohne neuen Serve-Port.
- **Nachteile (entscheidend):** würde `PathPrefix`-Routing + `stripprefix`
  (code-server-Muster `/code`) erfordern; die externe `upload-bridge.js` ist
  **nicht** auf Pfad-Präfix-Routing zugeschnitten (erwartet Root-/eigene Routen)
  → hohe Bruchgefahr. Zusätzlich Kopplung des Transports an die Traefik-Konfig
  und an einen **geteilten** Host-weiten Serve-Mount (fragile
  `--set-path`-Konfiguration) — falsche Zuständigkeits-Trennung.

### D (c): Nur eine OC aktivieren — VERWORFEN
- **Vorteile:** ein Mapping, ein Serve, eine ACL-Zeile (Minimalfläche).
- **Nachteile (entscheidend):** widerspricht „generisch für alle OCs"; bricht die
  Benchmark-/Multi-Instanz-Parität (ADR-025) und die Anforderung, dass alle
  Instanzen die Brücke gleichberechtigt erreichen können.

## Evidenz

- `ansible/roles/openclaw-gateway/tasks/instance.yml` Z.237–244: bestehendes
  idempotentes Serve-Muster (`tailscale serve status` → `--bg --https={{ oc.port }}
  http://localhost:{{ oc.port }}`).
- `ansible/roles/openclaw-gateway/tasks/instance.yml` Z.248–257: Bridge-Serve-Task
  (`upload_bridge_enabled`-Gate → `--bg --https={{ oc.upload_bridge_https }}
  http://localhost:{{ oc.upload_bridge_host_port }}`).
- `ansible/roles/openclaw-gateway/templates/docker-compose.yml.j2` Z.8–13:
  Loopback-Publish `127.0.0.1:{{ oc.port }}:{{ oc.port }}` +
  `upload_bridge_enabled`-Gate + `127.0.0.1:{{ oc.upload_bridge_host_port }}:{{ openclaw_upload_bridge_internal_port }}`
  (Beleg: Localhost-only, ADR-025).
- `ansible/group_vars/all.yml` Z.60: `openclaw_upload_bridge_internal_port: 8099`
  (SSoT; Fallback in `roles/openclaw-gateway/defaults/main.yml` Z.9).
- `ansible/group_vars/vps-dev.yml` / `vps-prod.yml`: `upload_bridge_enabled` +
  `upload_bridge_host_port` 18099/18100/18101 + `upload_bridge_https`
  8443/8444/8445 (Beleg für explizites Konstanten-Muster, analog `port:`).
- `services/code-server/docker-compose.yml` Z.30 + `ansible/roles/code-server/tasks/main.yml`
  Z.41: 8443 ist **nur container-intern** (kein Host-Publish) → kein Kollisions-Risiko.
- `acl/tailscale-acl.hujson` + `acl/README.md`: Regelgruppen-Konvention
  (`// rule: <gruppe>`), rein additiver Applier, manueller Apply
  (`00-acl-apply.yml`, `dry_run` → `confirm`).
- `docs/adr/ADR-018` (Tailscale Serve = tailnet-intern, LE-Zertifikate, Secure
  Context), `docs/adr/ADR-025` (Multi-Instanz, Localhost-only, Serve-TLS),
  `docs/adr/ADR-026` (ACL-SSoT, Governance).
- Tailscale-Doku: <https://tailscale.com/docs/features/tailscale-serve> (Serve
  pro Port, `--https=<port>`, `--bg`), <https://tailscale.com/docs/how-to/set-up-https-certificates>
  (Zertifikate für `*.ts.net`).

## Konsequenzen

- **Rolle `openclaw-gateway`:**
  - Compose-Template um **eine** zusätzliche Port-Zeile je Instanz erweitern:
    `- "127.0.0.1:{{ oc.upload_bridge_host_port }}:{{ openclaw_upload_bridge_internal_port }}"`
    (nur wenn `oc.upload_bridge_enabled`; Default `false` → keine Zeile, kein
    Verhalten, Brücke bleibt optionale Ergänzung).
  - `instance.yml` um **einen** Serve-Task je Instanz erweitern
    (State-Check → `--bg --https={{ oc.upload_bridge_https }}
    http://localhost:{{ oc.upload_bridge_host_port }}`), nur wenn
    `oc.upload_bridge_enabled` gesetzt/`true` ist.
  - **Kein Health-Gate auf 8099** im Deploy-Pfad: die Brücke darf nicht
    existieren müssen (Abgrenzung). Das Serve-Registrieren selbst ist unkritisch
    (liefert 502, wenn Backend fehlt — kein Deploy-Fehler).
- **`group_vars`** (dev + prod): je Instanz `upload_bridge_enabled` +
  `upload_bridge_host_port` + `upload_bridge_https` (Tabelle oben), explizit
  gepinnt; Container-Port zentral `openclaw_upload_bridge_internal_port` (8099).
- **ACL:** neue Gruppe `upload-bridge` (additiv, owner-only); Apply nur manuell.
- **Doku:** arc42 05/06/07/09 ergänzen (siehe Part 2 unten); Zugriffs-URL
  `https://vps-<target>.<tailnet>:<upload_bridge_https>/` (z. B. oc1:
  `https://vps-dev.tailcfea8a.ts.net:8443/`).
- **BDD (später):** Serve-Status + `--https={{ oc.upload_bridge_https }}`-Rückroute
  prüfen (analog bestehender Serve-Checks); **kein** 8099/`<host_port>`-Check von
  außen (Loopback-only, von außen dicht — wie 18789–18791).

## Worst-Case / Rollback (Pflicht: Netzwerk-/Expositions-Entscheidung)

- **Worst-Case 1 — Serve-Proxypfad defekt / Backend down:** `https://…:8443+`
  antwortet nicht (bzw. 502, wenn Brücke nicht läuft).
  - **Gegenmaßnahme:** idempotenter Serve-Task (State-Check); Brücke bleibt
    explizit außerhalb des Deploy-Gates.
  - **Rollback:** `tailscale serve --reset` + erneut setzen (Playbook-Task);
    Fallback: Brücke direkt im Container auf 8099 testen.
- **Worst-Case 2 — Recreate ändert IP-Zuordnung:** der Serve-Befehl zeigt ins
  Leere.
  - **Gegenmaßnahme:** hier strukturell ausgeschlossen (Ziel ist
    `localhost:<host_port>`, **keine** Container-IP).
- **Worst-Case 3 — falsche/überbreite ACL:** Expositions-Fehler (Ports für
  Nicht-Owner erreichbar oder gar nicht).
  - **Gegenmaßnahme:** rein additiv, `src: autogroup:owner` (eng),
    `dry_run`-Default, Owner-Go vor Apply (ADR-026-Governance), Backup +
    Auto-Rollback im Applier.
  - **Rollback:** den `upload-bridge`-Block aus dem Modell entfernen + Commit
    zurücknehmen — der Applier ist rein additiv, es ist **kein** Live-POST zum
    Entfernen nötig (gleiche Mechanik wie `goe-read`, ADR-026).
- **Worst-Case 4 — Serve-Port-Kollision** (8443+ mit künftigem Host-Service):
  - **Gegenmaßnahme:** Ports sind heute belegt-frei (s. Kollisions-Check);
    Konstanten zentral in `group_vars` → bei Kollision ein einziger
    Änderungsort.

## Offene Punkte (vor Akzeptanz)

1. **Owner-Entscheid:** Akzeptieren/Ändern der ADR (je ADR-Governance).
2. **Port-Konstanten bestätigen:** 18099–18101 / 8443–8445 als endgültige Werte
   (oder alternative freie Ports vom Owner).
3. **Brücken-Verfügbarkeit:** Ist `upload-bridge.js` in allen drei OCs eingeplant
   oder zunächst nur in einer (dann: Konstanten nur dort setzen — Mechanismus
   bleibt generisch)? Die Antwort bestimmt nur die `group_vars`-Werte, nicht das
   Design.
4. **Serve-Mount-Verhalten der Brücke:** Erwartet die Brücke Root-Mount `/`?
   Falls sie Pfad-Präfixe voraussetzt, wäre Option C (Traefik) doch zu prüfen —
   heute verworfen, da `--https=<port>` standardmäßig `/`-Mount liefert.
5. **ACL-src-Klarstellung:** Ist `autogroup:owner` (nur Owner) final gewünscht,
   oder soll zusätzlich `autogroup:admin`/`member` (IaC4-Muster) ergänzt werden?
   Empfehlung: nur `owner`.

## Referenzen

- <https://tailscale.com/docs/features/tailscale-serve>
- <https://tailscale.com/docs/how-to/set-up-https-certificates>
- <https://tailscale.com/kb/1018/acls>
- Repo: `docs/adr/ADR-018`, `docs/adr/ADR-025`, `docs/adr/ADR-026`,
  `ansible/roles/openclaw-gateway/`, `ansible/group_vars/vps-*.yml`,
  `acl/tailscale-acl.hujson`, `acl/README.md`
