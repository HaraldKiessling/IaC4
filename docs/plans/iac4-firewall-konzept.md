# IaC4 Firewall-Konzept: Tailscale × UFW (Lockout-Prävention)

> **Rahmen:** Issue #42 (Done-Nachweis/Evidenz) – entstanden aus Haralds Review-Fragen (2026-07-31)
> **Status:** aktiv, review-pflichtig (Issue #37)
> **Evidenz-Typen:** `[I]` Ist verifiziert · `[V]` Vendor-Doku · `[A]` Annahme
> **Frage:** Wie lauten die korrekten Ziel-Firewall-Regeln für Tailscale auf Ubuntu, und in welchen Schritten erreichen wir sie ohne Lockout?

---

## 1. Fragestellungen

1. Ist die CGNAT-Allow-Regel (`allow from 100.64.0.0/10 to port 22`) exakt so notwendig?
2. Welches Netzwerk-Device ist für Tailscale essentiell?
3. Wie ist sichergestellt, dass es zu keinem Lockout kommt?
4. Wie ist das Lockout-Risiko dargestellt?

## 2. Netzwerk-Architektur (evidenzbasiert)

### 2.1 Paketpfad SSH via Tailscale (100.x → VPS)

```
ssh deploy-user@100.107.5.26
  │ 1. Routing: Ziel 100.x → tailscale0 (WireGuard-Interface)
  ▼
  │ 2. WireGuard verschlüsselt das TCP-Paket → UDP-Paket
  │    src = echte Quell-IP (z.B. GH-Runner) · dst = VPS-Public-IP:41641/udp
  │    Transport über das PHYSISCHEN Interface (eth0)          [V: WireGuard-Architektur]
  ▼
VPS eth0: UDP 41641
  │ 3. Zweifach abgedeckt:
  │    (a) conntrack: Tunnel ist vom VPS AUSGEHEND etabliert → ESTABLISHED,
  │        ufw-before-input akzeptiert ESTABLISHED/RELATED       [V: UFW before-Chain]
  │    (b) Tailscale installiert bei netfilter=on SELBST eine ACCEPT-Regel
  │        für UDP 41641 in ts-input (AddMagicsockPortRule) → auch NEW-Flows
  │        abgedeckt; DERP-Fallback läuft über ausgehende TCP      [V: Tailscale-Source]
  ▼
WireGuard-Entkapselung → TCP-Paket (src 100.x, dst 100.x:22)
  │ 4. Paket erscheint auf tailscale0 → netfilter INPUT (in-interface tailscale0)
  │ 5. netfilter-mode=on (Tailscale-Default): INPUT-Jump → ts-input steht AM ANFANG
  │    der INPUT-Chain, VOR den UFW-Chains → akzeptiert tailscale0-Verkehr   [V: netfilter-modes]
  ▼
sshd (lauscht 0.0.0.0:22, alle Interfaces) → Login
```

**Kernaussage:** SSH via Tailscale ist ein *zweistufiger* Paketfluss: verschlüsselter UDP-Tunnel über das physische Interface (Port 41641), entkapseltes TCP auf `tailscale0` mit virtueller 100.x-Quelle. Die Firewall muss beide Ebenen kennen.

### 2.2 Paketpfad SSH von außen (Angreifer auf Public-IP)

```
TCP-SYN auf Public-IP:22 → eth0 → netfilter INPUT
  │ ts-input matcht NICHT (kein tailscale0-Verkehr)             [V: ts-input = tailscale0-Accepts]
  ▼
UFW first-match:
  ❌ Heute (Befund T2): generische Regel `22/tcp ALLOW IN Anywhere`
     (aus cloud-config `ufw allow ssh`) matcht ZUERST → ALLOW   [I: BDD-Lauf 2, Run 30638303706]
  ✅ Soll: generische Regel gelöscht → `deny in on eth0 to 22` → DROP
```

### 2.3 Essentielle Netzwerk-Devices

| Device | Rolle | Essentiell für | Berührt der Fix? |
|---|---|---|---|
| **`tailscale0`** (virtuell, WireGuard) | Entkapselter Verkehr (TCP/100.x) | den eigentlichen TS-Datenverkehr | ❌ – kein UFW-deny auf dieses Interface; ts-input akzeptiert |
| **`eth0`/`ens3`** (physisch) | WireGuard-Tunnel-UDP auf **41641** | die Tunnel-Ebene selbst (ausgehende Verbindung, Hole-Punching) | ❌ – kein deny auf 41641/udp; doppelt abgedeckt: conntrack ESTABLISHED + Tailscale-eigene ts-input-ACCEPT (Magicsock-Port) |
| `sshd` (0.0.0.0:22) | Zugang | – | Selektiert per Interface-Regel (deny eth0), nicht per sshd-Config |

**Antwort F2:** `tailscale0` **und** das physische Interface mit UDP 41641 sind beide essentiell — eine blockiert den Dienst, die andere den Tunnel. Keine der Ziel-Regeln berührt eines der beiden.

## 3. Firewall-Evidenzlage

### 3.1 Ist-Konfiguration `[I]`
- `cloud-config.yaml` Z. 16–19: `ufw default deny incoming` + `ufw default allow outgoing` + `ufw allow ssh` + `ufw --force enable` → **generische Allow-Regel für Bootstrap** (alle Interfaces!)
- `ansible/playbooks/02-ssh-restrict.yml` (Branch-Stand): CGNAT-Allow (100.64.0.0/10) → delete der generischen Regel → `deny in on <public_iface> to 22`
- **Befund BDD-Lauf 2** (Run 30638303706): T1 grün (TS-SSH funktioniert), T2 rot (Public-SSH weiter offen) → First-Match-Problem der generischen Allow-Regel empirisch belegt `[I]`

### 3.2 UFW-Verhalten `[V]`
- UFW = iptables-Frontend; Regeln werden in Reihenfolge ausgewertet (**first match wins**)
- `ufw enable` installiert `ufw-before-input` mit `ESTABLISHED,RELATED ACCEPT` → etablierte Verbindungen (inkl. WireGuard-Tunnel) werden nie gekappt
- Etablierte Verbindungen werden auch nicht abgebrochen → der laufende Ansible-SSH bricht durch Regeländerungen nicht ab

### 3.3 Tailscale netfilter-Interaktion `[V]`
Quellen: [netfilter-modes](https://tailscale.com/docs/reference/netfilter-modes), [UFW-Guide](https://tailscale.com/docs/how-to/secure-ubuntu-server-with-ufw)

| Mode | Verhalten |
|---|---|
| `on` (Default) | Tailscale legt `ts-input`/`ts-forward` an und **jumpt an den Anfang** von INPUT/FORWARD → akzeptiert tailscale0-Verkehr VOR UFW |
| `nodivert` | Chains existieren, aber keine Jumps → UFW ist der Gatekeeper → **UFW-Allow für TS zwingend** |
| `off` | Keine Tailscale-Regeln → alles manuell |

- Tailscale-UFW-Guide-Empfehlung: `default deny incoming` + `default allow outgoing` + **`ufw allow in on tailscale0`**
- Unsere CGNAT-Regel (`from 100.64.0.0/10 to 22`) ist das quellenbasierte Äquivalent zur Vendor-Empfehlung (interface-basiert): Bei `netfilter=on` **redundant** (ts-input gewinnt), bei `nodivert`/`off` **zwingend** (sonst droppt default deny incoming).

**Antwort F1 (korrigiert gegenüber früherer Darstellung):** Die CGNAT-Allow-Regel ist **nicht „exakt so notwendig"** unter netfilter=on — sie ist **Defense-in-Depth** und schützt die Fälle nodivert/off/Tailscale-Regeln-fehlen. Sie wird **behalten** (billig, klar, dokumentiert), aber ihre Begründung ist die Redundanz, nicht die Allein-Wirkung. Anmerkung: `100.64.0.0/10` ist der gesamte RFC-6598-CGNAT-Raum, nicht Tailscale-exklusiv — praktisch nur via Tailscale erreichbar (Restrisiko minimal); die Vendor-Empfehlung `allow in on tailscale0` wäre strikter (Entscheidung in §8.4).

### 3.4 Lockout-Vorfall 2026-07-31 früh `[I/A]`
- Belegt: VPS nach Restrict unerreichbar → nur Neuinstallation half `[I]`
- Damalige Lesson: „Restrict MUSS CGNAT-Allow enthalten" `[I]`
- **Offene Frage (Rekonstruktion):** Unter netfilter=on hätte ts-input TS-SSH auch ohne UFW-Allow erlaubt — die Vorfall-Ursache war vermutlich ein **nicht-funktionierender Tunnel** (parallel: Node-Delete-Vorfall), nicht primär die UFW-Regel `[A]`. Rekonstruktion aus den Logs von 2026-07-31 früh steht aus (Task).

## 4. Abgeleitete Ziel-Firewall-Regeln (Soll-Zustand nach Workflow 02)

| # | Regel | Zweck | Evidenz |
|---|---|---|---|
| R1 | `ufw default deny incoming` / `allow outgoing` | Basis-Policy (cloud-config) | `[I]` cloud-config Z. 16–17 |
| R2 | **keine** generische `allow 22` (aus cloud-config gelöscht) | Erstzugang nur für Bootstrap; nach 02 entfernt, sonst first-match-Gewinner | `[I]` BDD-Lauf 2 T2 |
| – | IPv6 | UFW erzeugt automatisch v6-Pendants (z. B. `22/tcp (v6) DENY IN on eth0`); `ts-input` existiert für v4+v6 analog — alle Ziel-Regeln gelten für beide Stacks | `[V]` ufw/Tailscale-Source |
| R3 | `ufw deny in on <public_iface> to any port 22 proto tcp` | Öffentliches SSH dicht (interface-gebunden, NICHT global → TS bleibt offen) | `[I/V]` §2.2, §3.2 |
| R4 | `ufw allow from 100.64.0.0/10 to any port 22 proto tcp` | TS-SSH: Defense-in-Depth für netfilter nodivert/off; bei `on` redundant | `[V]` netfilter-modes |
| R5 | **keine** Regel auf UDP 41641 | WireGuard-Tunnel doppelt abgedeckt: conntrack ESTABLISHED (ufw-before-input) **und** Tailscale-eigene ts-input-ACCEPT für 41641 (AddMagicsockPortRule); DERP = ausgehende TCP | `[V]` §2.1/3.2/3.3 |
| R6 | **keine** Regel auf `tailscale0` | Entkapselter Verkehr (ts-input akzeptiert bei netfilter=on) | `[V]` §3.3 |

## 5. Schritte zum Ziel – ohne Lockout

Reihenfolge mit Sicherheitsbegründung (Workflow 02, Phase 2a → 2b):

1. **Phase 2a – Tailscale-Join ZUERST** (via Public-IP-SSH): Der Rückweg über Tailscale muss existieren, BEVOR irgendeine Regel den Public-Weg schließt. Join-Fehler → Workflow bricht ab, Restrict startet nicht. `[I]` Workflow-Logik
2. **Phase 2b – Regel-Reihenfolge im Playbook:** (a) CGNAT-Allow (R4) zuerst anlegen → nie ein Zustand ohne TS-Allow; (b) generische Allow-Regel löschen (R2); (c) Deny auf öffentlichem Interface (R3). `[I]` Playbook
3. **Während des Laufs:** UFW kappt etablierte Verbindungen nicht → der ausführende SSH (Public-IP) bricht nicht ab, der Lauf kommt durch. `[V]` §3.2
4. **Nach dem Lauf – Verifikation:** Post-Bootstrap-Check via Tailscale-IP mit `exit 1` (seit PR #36) → Workflow ist erst grün, wenn SSH über den NEUEN Weg nachweislich funktioniert. `[I]` Workflow 02
5. **Dauerhaft:** BDD-T1 (TS-SSH), T2 (Public dicht), B5 (Regelreihenfolge), B6 (TS-Infrastruktur) überwachen die Ziel-Regeln. `[I]` qa/bdd-testkonzept.md

**Rollback-Pfad:** Fehlschlag vor Abschluss von 02 → Workflow rot, VPS bleibt via Public-SSH erreichbar (Bootstrap-Zugang noch offen) → Fehlerkorrektur im Repo, Re-Run. Nach erfolgreichem Restrict: VPS nur via TS (gewollt); TS-Ausfall → Provider-Konsole/Neuinstallation (R-001, Restrisiko).

## 6. Lockout-Risiko-Profil (R-001 – zur Übernahme in arc42/11)

| Dimension | Wert | Begründung |
|---|---|---|
| Schwere | **hoch** | Lockout = nur Provider-Konsole/Neuinstallation (Vorfall 2026-07-31) |
| Wahrscheinlichkeit | **niedrig** | Mehrfach-Schutz: Join-vor-Restrict, R4 vor R3, Interface-Deny statt global, Post-Bootstrap-Verifikation, ts-input (netfilter=on) |
| Restrisiko | **Tailscale-Ausfall direkt nach Restrict** | Tunnel down + Public dicht = kein Zugang; Node-Fehler (Lesson: Nodes nie löschen) |
| Gegenmaßnahmen | R1–R6, BDD-T1/T2/B5/B6, Node-Cleanup-Regel (Rename statt Delete) | §4, §5, §7 |
| Monitoring | BDD-Workflow 04 (manuell/nach Deploy; aktuell kein cron-Schedule) | qa/bdd-testkonzept.md |

## 7. BDD-Abdeckung (Szenarien ↔ Ziel-Regeln)

| Szenario | prüft | Regel |
|---|---|---|
| T1 SSH via Tailscale | TS-SSH funktioniert (Paketpfad §2.1 intakt) | R4 + ts-input |
| T2 Public-SSH dicht | Negativtest von außen | R3 |
| B5 UFW-Regelreihenfolge | Status active, keine generische Allow-22 (v4+v6), Deny auf iface, **CGNAT-Allow vorhanden** | R1+R2+R3+R4 |
| **B6 (neu)** TS-Infrastruktur | netfilter-mode on, WireGuard-UDP-41641 lauscht, tailscale0 existiert | R5+R6 |

## 8. Offene Punkte

1. **netfilter-mode auf dem VPS verifizieren** → wird via B6 maschinell beantwortet (`NetfilterMode` = 2)
2. **Lockout-Vorfall-Rekonstruktion** (Logs 2026-07-31 früh): Tunnel-Down vs. UFW-Regel — Ursachenkette der damaligen Lesson absichern
3. **arc42/11:** R-001-Eintrag übernehmen
4. **Vendor-Empfehlung vs. eigene Regel:** `allow in on tailscale0` (interface-basiert) vs. CGNAT-Allow (quellenbasiert, RFC-6598-Raum) — Entscheidung dokumentieren, aktuell: CGNAT-Allow (funktional äquivalent; nicht Tailscale-exklusiv, praktisch aber nur via TS erreichbar)
5. **Tailscale-Version auf dem VPS + Vorhandensein der ts-input-41641-Regel (AddMagicsockPortRule) verifizieren** — stützt R5-Evidenzlage

## 9. Tag-Design & Provisionierung (Option A – IaC3-Muster mit tag:ia4)

### 9.1 Evidenzlage

- **Original-ACL (Commit `0d3d1de`):** IaC4-Port sah **`tag:ia4`** für VPS-Nodes vor — `tagOwners: { tag:ia4: [admin], tag:ci: [admin] }`, `ssh: src [tag:ci] → dst [tag:ia4]` (deploy-user/root/ubuntu). Die ACL wurde später aus Terraform entfernt (geteilte Konsole-ACL, `tailscale-acl.mdc`: nie überschreiben, ia3+ia4+ha koordiniert). `[I]` Git-Historie
- **IaC3-Referenz:** `terraform/oauth-client.tf` = `tags ["tag:ci", "tag:ia3"]`; Auth-Keys mit `["tag:ia3","tag:ci"]`; Runner-Joins mit `tag:ci,tag:ia3` → **ein Client mit beiden Tags**, VPS joint direkt mit Ziel-Tag. `[I]` IaC3-Repo
- **IaC4-Ist (vor diesem PR):** Client nur `["tag:ci"]`, Auth-Key nur `tag:ci` → frischer VPS startet als tag:ci → **Re-Tag-Workaround auf tag:ia3** (Migration-Kompromiss „SSH-ACL-Kompatibilität"). `[I]` Migrationsplan + Workflows

### 9.2 Diagnose

1. `tag:ia3` auf dem IaC4-VPS ist ein **Fremd-Tag aus dem IaC3-Projekt** — das designierte IaC4-Tag ist `tag:ia4` (Original-ACL).
2. Der Re-Tag-Workaround entstand, weil die **Tag-Ownership** (ACL) bestimmt, welche Tags ein Client vergeben darf: Ein tag:ci-Client kann nur tag:ci-Auth-Keys erzeugen → der VPS startet falsch getaggt und muss umgetaggt werden (funktioniert nur, weil die geteilte ACL es implizit erlaubt — empirisch HTTP 200, nicht dokumentiert).
3. IaC3-Praxis bestätigt: **Ein Client mit beiden Tags** (nicht zwei Clients) — damit kann der Auth-Key das Ziel-Tag direkt setzen, kein Workaround.
4. **Exact-Match vs. Ownership-Mode (Tailscale-Doku):** Ein Auth-Key, dessen Tags ein **Subset** der Client-Tags sind (z. B. nur `["tag:ia4"]` bei Client `[tag:ci, tag:ia4]`), erfordert **tag-basierte Ownership** in der ACL (`tagOwners: tag:ia4 → [tag:ci]` oder Selbst-Ownership). IaC3 nutzt **Exact-Match** (Key-Tags = alle Client-Tags `["tag:ia3","tag:ci"]`) — das funktioniert ohne Ownership-Abhängigkeit. Option A übernimmt Exact-Match: Key-Tags `["tag:ci", "tag:ia4"]`.

### 9.3 Ziel-Zustand (dieser PR)

| Element | Vorher | Nachher (Option A) |
|---|---|---|
| OAuth-Client-Tags | `["tag:ci"]` | `["tag:ci", "tag:ia4"]` |
| Auth-Key-Tags (02) | `["tag:ci"]` | `["tag:ci", "tag:ia4"]` (Exact-Match, IaC3-Muster) → VPS joint direkt mit beiden Tags |
| Re-Tag-Step (02) | Workaround auf ia3 | Korrektur auf ia4 (frische Nodes: no-op) |
| VPS-Dauertag | `tag:ia3` | `tag:ia4` |
| BDD-T3 | erwartet tag:ia3 | erwartet tag:ia4 |

### 9.4 Schrittfolge ohne Lockout/Breakage (operativ, NACH diesem PR)

1. **ACL-Verifikation VOR allem** (Checkliste, `GET /api/v2/tailnet/{t}/acl` mit temporärem API-Key):
   - `tagOwners` enthält `tag:ia4` mit **tag-basiertem** Owner (`tag:ia4` oder `tag:ci` — nicht nur User/Group-Einträge, sonst schlägt die Key-Erzeugung im Ownership-Mode fehl)
   - `ssh`-Sektion enthält `src: [tag:ci] → dst: [tag:ia4]` für deploy-user/root/ubuntu
   - Fehlt etwas → koordinierte ACL-Ergänzung (Konsole, ia3+ia4+ha zusammen) — **kein Re-Tag ohne ACL-Nachweis** (Lockout-Klasse: SSH via Tailscale würde brechen).
   - **Zwischenzustand (2026-07-31 durchgeführt):** BDD-T3 war zwischen PR-Merge und Schritt 3 erwartungsgemäß rot (vps-dev noch tag:ia3); nach dem Re-Tag: BDD-Lauf 4 komplett grün inkl. T3 `tag:ia4`.
2. **Client neu erzeugen:** Workflow 01 (force=true) mit dem temporären API-Key → Client mit `["tag:ci", "tag:ia4"]`, Secrets werden aktualisiert.
3. **Bestands-VPS re-taggen:** `vps-dev` von tag:ia3 auf tag:ia4 (via API mit temporärem Key oder nach 01 via OAuth-Token) — erst NACH Schritt 1.
4. **Verifikation:** BDD-Lauf 4 → T1 (SSH via TS bleibt), T2 (Public dicht bleibt), T3 (tag:ia4), T4 unverändert.
5. **Rollback:** Re-Tag zurück auf ia3 (falls Schritt-1-Nachweis doch fehlerhaft war).

### 9.5 Risiko

R-002: Tag-Umbruch bricht TS-SSH (wenn ACL ia4 nicht kennt) — Schwere hoch (Lockout-Klasse), W'keit niedrig (Original-ACL hatte ia4; Schritt 1 verifiziert vor dem Umbau). Monitoring: BDD-T1/T3.

## 10. ACL-Policy-Erweiterung (idempotent, Workflow 01)

### 10.1 Problem
Die Tailscale-ACL ist **geteilt** (IaC3 `tag:ia3` + IaC4 `tag:ia4` + Home-Assistant `tag:ha`), im HUPL-Format mit Kommentaren, und darf **nie überschrieben** werden (Regel `tailscale-acl.mdc`; historisch: `terraform/acl.tf` mit `overwrite_existing_content = true` wurde deshalb entfernt). IaC4 braucht aber die ia4-Regeln (tagOwners + acls + ssh).

### 10.2 Lösung: `scripts/ensure-acl-ia4.py` (in Workflow 01, nach Terraform Apply)
Idempotenter, **rein additiver** Ablauf:
1. `GET /acl` → aktuelle Policy (HUPL)
2. **Idempotenz-Guard:** enthält die Policy bereits `tag:ia4` → no-op (exit 0)
3. **Backup** der aktuellen Policy (`/tmp/acl-backup.json`, Log-Hinweis)
4. **Additive Einfügung** an exakten Ankern (tagOwners-Zeile nach ia3, acl-Blöcke nach dem ci→ia3-Block, ssh-Eintrag nach dem ia3-Eintrag) — Anker müssen exakt 1× existieren, sonst Abbruch OHNE Änderung
5. `POST /acl` (Content-Type hujson)
6. **Verifikation:** ia4-Einträge vorhanden (4 Checks) + **ia3/ha-Bestand unverändert** (Zähler) + **Additivitäts-Diff** (keine bestehende Zeile entfernt/geändert — normalisierter Zeilenvergleich)
7. **Auto-Rollback** bei jedem Fehler: POST des Backups + exit 1

### 10.3 Sicherheits-Nachweise ("100 %")
- **Rein additiv:** Der normalisierte Diff Backup→Neu enthält nur `>`-Zeilen (bewiesen bei der manuellen Erst-Erweiterung 2026-07-31: POST 200, Verifikation bestanden, Backup `/tmp/acl-backup-20260731.hujson`)
- **Idempotent:** Wiederholte Läufe sind no-op (Guard); der erste Workflow-Lauf nach der manuellen Erweiterung ist der Idempotenz-Test
- **Fail-safe:** Mehrdeutige Anker → Abbruch vor Änderung; Verifikationsfehler → Rollback
- **Koordination:** ia3/ha-Blöcke werden nie angefasst (Zähler-Checks)

### 10.4 Abgrenzung
Kein Terraform-ACL-Management (kein `overwrite_existing_content`); das Skript ist ein eigenständiger, transparenter Schritt mit dokumentiertem Backup-/Rollback-Pfad.

## 11. Quellen

- Tailscale: [netfilter modes](https://tailscale.com/docs/reference/netfilter-modes) (on/nodivert/off, ts-input-Jumps)
- Tailscale: [Secure Ubuntu Server with UFW](https://tailscale.com/docs/how-to/secure-ubuntu-server-with-ufw)
- WireGuard-Architektur (UDP-Tunnel, virtuelles Interface)
- `cloud-config.yaml` Z. 14–19 (Ist) · `ansible/playbooks/02-ssh-restrict.yml` (Ist, Branch)
- BDD-Lauf 2: Run 30638303706 (T1 grün / T2 rot) · Lockout-Vorfall 2026-07-31 (Memory-Lesson)
