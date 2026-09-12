# Entscheidungsvorlage: dauerhafte ACL-Lese-Regel für KSEM `192.168.0.31:502`

**Status:** VORLAGE — zur Owner-Sicht + Review; **NICHT angewendet** · **Autor:** engineer-pro (Subagent)
**Datum:** 2026-09-12 (UTC) · **Anlass-Input:** Owner 2026-09-12 14:06 UTC
**Governance:** ACL nur additiv · Autor ≠ Reviewer · kein Apply ohne Owner-Go · `confirm=APPLY-ACL`.
**Modus dieses Ergebnisses:** **ausschließlich offline/Modell + eingefrorener Live-Export**
(kein Live-GET/POST, kein Apply, keine Live-ACL-Änderung, keine Secrets).
**Repo/Branch:** `HaraldKiessling/IaC4` @ `main` (HEAD `b6ceaf1`, nach `git fetch`);
Arbeits-Branch der vorbereiteten Regel: **`feat/acl-ksem-read-durable`** (Draft-PR).
**Bezugsobjekt ACL (SSoT):** `acl/tailscale-acl.hujson`
**Eingefrorener Live-Anker (aktuell):** `acl-live-export-20260912-post-ksem.json`
(SHA256 `b7c7b2d4a47630dd32266e74cc423c777ebd2ec55cb41f78e21faab22f9c4b40`,
2026-09-12T12:48:34Z, Run 34694681107 – POST-APPLY nach `ksem-port-probe`).

> **Kernaussage vorab:** Es wird **nichts** umgesetzt. Diese Vorlage beschreibt
> eine **additive**, dauerhafte ACS-Lese-Regel (`ksem-read`, KSEM `:502`, nur lesend,
> deklariert als **`pending`**) und den Nachweis, dass der fremde Bestand dabei
> **positionsgenau unverändert** bleibt. Erst **nach** Owner-Sicht **und** Review
> (Autor ≠ Reviewer) folgt ein separater, manueller Dry-Run + Apply
> (`dry_run=false`, `confirm=APPLY-ACL`).

---

## 1) Anlass + Ziel

### 1.1 Befund (Anlass, belegt)
Die Port-Diagnose vom 2026-09-12 (`ksem-port-probe`, Live-Probe §G des
Umsetzungsberichts `iac4-ksem-testfreigabe-bericht-20260912.md`) hat ergeben:

| Ziel | Ergebnis | Deutung |
|---|---|---|
| KSEM `192.168.0.31:502` (Std-Modbus) | **OPEN** — Modbus **FC3, Unit 71** antwortet OK | **der funktionierende Modbus-Weg** |
| KSEM `192.168.0.31:80` (Web) | OPEN — HTTP `HEAD` → `200 OK`, `Server: nginx` | nur Geräte-Identifikation |
| KSEM `192.168.0.31:1502` | **REFUSED** (rc=111) | kein Listener (Service-Ebene, nicht ACL) |

⇒ Die `:1502`-REFUSED-Diagnose ist **abgeschlossen**: Das KSEM bietet Modbus auf
**`:502`** an, `:1502` ist tot. Die bestehende Regel `energie-read` (HA-Regel 7)
erlaubt `tag:ia4` auf `192.168.0.31:1502` (u. a.) — also auf einen **toten Port**.

### 1.2 Ziel (eng begrenzt)
- Eine **saubere, permanente** Lese-Regel für den **einzigen nötigen** KSEM-Port
  **`:502`** (Standard-Modbus TCP), NUR LESEND.
- **Ablösung** der **temporären/diagnostischen** Gruppe `ksem-port-probe`
  (`:80`+`:502`), die mit Owner-Go 2026-09-12 12:41 UTC nur zur Diagnose aktiviert
  wurde.
- **Kein** Schreibzugriff, **kein** `:80` (nur Diagnose-Web-Identität), **kein**
  Einbezug des toten `:1502`.

---

## 2) Design-Entscheid + Alternativen (mit Begründung)

### 2.1 Vorzugsvariante (b): eigene, permanente Regel `ksem-read`
**Neue, additive Regel `ksem-read`** — **bewusst NICHT** die bestehende Regel
`energie-read` erweitern.

| Kriterium | (b) neue Regel `ksem-read` **(empfohlen)** | (a) `energie-read` erweitern **(verworfen)** |
|---|---|---|
| Tool-Semantik | `ensure-acl.py` ist **rein additiv**: es fügt **ganze Regeln** ein | eine **bestehende Live-Regel** müsste **geändert** werden → nicht abbildbar |
| Nachweis „0 Änderungen“ | bleibt **wahr** (§3): +1 Einfügung / 0 Entfernungen / 0 Änderungen | **bricht**: Offline-`--verify` → **`Fehlend 1` + `Unerwartet fremd 1`** (Beleg E5) |
| Realer Effekt bei Apply | genau die gewollte **eine** neue Regel | der additve Applier **fügt eine 2. `energie-read`-Variante ein** und **lässt die alte stehen** → **Duplikat/Überlappung** (nicht „Erweiterung“) |
| „toter Port“ `:1502` | `energie-read` bleibt unangetastet; `:1502`-Bereinigung ist eine **eigene** Entscheidung | würde den toten `:1502`-Port **tiefer einzementieren** (enger an die Regel gebunden) |
| Semantik-Trennung | `energie-read` = eingefrorener **HA-Regel-7-Kanon** (Owner-Go 21:57) unangetastet | vermischt dauerhaften Regel-7-Kanon mit neuer KSEM-Port-Erkenntnis |
| Least Privilege / Rollback | eigene, **sauber separat entfernbare** Gruppe (Rollback = 1 Block) | Delete/Reset auf dem 3-Ziel-Kanon |
| Governance / `pending` | als **`pending`** deklarierbar → **kein Live-Soll ohne Freigabe** | nicht ausdrückbar |

**Entscheidung:** **`ksem-read` (dauerhaft), deklariert als `pending`.**
Die Regel ist im Modell dokumentiert, gehört aber **nicht** zum aktuellen Live-Soll
und wird **nur** bei ausdrücklicher Selektion (`--rule ksem-read` / `rules=ksem-read`)
eingeführt.

### 2.2 Exaktes SSoT-Snippet (huJSON)
Einfügen in `acl/tailscale-acl.hujson` **unmittelbar NACH** dem
`ksem-port-probe`-Block (dessen letzte Zeile `},` = Zeile **176**), **vor** dem
Schließen der `acls`-Liste `  ],` (Zeile **181**). Also als **letzter**
`acls`-Eintrag (Modell-Position **17** von `acls`).

```hujson
    // rule: ksem-read pending — DAUERHAFT (VORLAGE 2026-09-12, noch KEIN Owner-Go):
    // tag:ia4 (BEIDE VPS) → KSEM 192.168.0.31 NUR LESEND auf :502 (Standard-Modbus
    // TCP; Diagnose 2026-09-12: FC3 Unit 71 OK, :1502 REFUSED). Saubere, permanente
    // Lese-Regel, die die temporäre Diagnose-Gruppe `ksem-port-probe` (:80+:502)
    // ablöst — NICHT :80 (nur Diagnose-Web-Identität) und NICHT die tote :1502.
    // Aktivierung = eigener Owner-Go (confirm=APPLY-ACL); danach eigener
    // Entfernungs-Schritt für `ksem-port-probe`.
    {
      "action": "accept",
      "src": ["tag:ia4"],
      "dst": ["192.168.0.31:502"],
    },
```

**Einfügeposition (positionsgenau):** aktueller `acls`-Live-Aufbau =
`[verwaltet 0–6] [IaC3 7] [Konsole 8–11] [IaC3 12–14] [energie-read 15]
[ksem-port-probe 16]` (17 Positionen). Die neue Regel wird **Modell-Position 17**
(letzter Eintrag, nach `ksem-port-probe`, vor `]`). Das Werkzeug `insert_entries`
fügt sie über die **Modell-Reihenfolge** automatisch an dieser Position ein
(kein Hand-Edit an der Live-Policy).

> **Status:** Snippet **und** Beiwerk (`scripts/ensure-acl.py`,
> `acl/README.md`, Workflow `00-acl-apply.yml`) sind **im Draft-PR** dieser Vorlage
> vorbereitet; die Regel ist als **`pending`** deklariert. **Kein Merge, kein Apply.**

### 2.3 Minimal-Alternative (falls Owner nur `:80`-frei + `:502` will)
Falls doch **beide** Ports dauerhaft gewünscht sind (z. B. für künftiges
Web-Monitoring), wäre `"dst": ["192.168.0.31:502", "192.168.0.31:80"]` die
Erweiterung. **Empfehlung: nur `:502`** (Least Privilege; `:80` war rein
diagnostisch).

---

## 3) Betroffene Quellen/Ziele/Ports/Aktionen + Blast-Radius

| Feld | Wert | Anmerkung |
|---|---|---|
| Aktion | `accept` (nur diese) | keine `deny`-, keine Schreib-Rechenregel |
| Quelle (`src`) | `["tag:ia4"]` | **vps-dev UND vps-prod** — beide Knoten tragen `tag:ia4` (Owner-Entscheid 2026-09-09 18:47 UTC) |
| ⚠️ **Blast-Radius** | **Produktions-VPS betroffen** | die Regel gewährt damit auch **vps-prod** Lesezugriff auf KSEM `192.168.0.31:502` |
| Ziel (`dst`) | `["192.168.0.31:502"]` | nur **Einzelhost** KSEM, nur **1 Port** |
| Port `:502` | Modbus TCP (Standard) | **LESEND** (FC03/FC04 Read; Diagnose: FC3 Unit 71 OK) |
| Nicht betroffen | `tag:ha`, `tag:ia3`, `tag:ci`, `tag:ha-ci`, `autogroup:*`, `192.168.0.13:*`, `ksem-port-probe`, `energie-read` | **keine** Rechteänderung |
| Bestehende `energie-read`-Ziele | `192.168.0.31:1502`, `192.168.0.13:80`, `192.168.0.13:1502` | bleiben **semantisch identisch** (Regel unangetastet) |

### 3.1 Blast-Radius — Bewertung
- `tag:ia4` umfasst **beide VPS** (vps-dev **und** vps-prod). Die Lese-Regel trifft
  damit **auch den Produktions-VPS** — bewusst ausgewiesen.
- Die Oberfläche ist **minimal**: **ein** Zielhost, **ein** Port, **nur** `accept`
  (Netzfreigabe; keine Applikations-Schreiblogik). Bei Least-Privilege-Fokus könnte
  die Quelle später auf ein **dediziertes vps-dev-Tag** verengt werden — das wäre
  eine **Tag-/Node-Änderung außerhalb der ACL** (eigener Owner-Go).
- **Zu entscheiden (Owner):** *Soll vps-prod den dauerhaften KSEM-`:502`-Lesezugriff
  erhalten?* (Empfehlung: **ja** — der KSEM/Bilanz-Lesepfad ist produktionsrelevant;
  konsistent mit `energie-read`, das vps-prod bereits Lesezugriff auf die
  Energie-Ziele gibt.)

---

## 4) Nachweis: fremder Bestand bleibt unverändert (positionsgenau)

Alle Nachweise **offline** gegen den **eingefrorenen Anker-Export**
(`acl-live-export-20260912-post-ksem.json`, SHA256 `b7c7b2d4…4b40`) mit
`--tolerated-foreign acl/tolerated-foreign.json`; der **Provenienz-Anker**
(Export-SHA == `source_export_sha256`) wird mitgeprüft — **ok**.

### 4.1 Baseline (Referenz vor der Modell-Änderung) — Beleg E1 + E2
- `--check-model`: **20 Einträge**, Reihenfolge `tagOwners → acls → ssh`, Tag-Referenzen gültig (exit 0).
- `--verify <anker> --tolerated-foreign`: **exit 0 / grün**
  - `Fehlend 0 · Geändert 0 · Unerwartet fremd 0 · Zusatz/Duplikat 0`.
  - **Tolerierter Fremdbestand 5/5** vorhanden/unverändert (positionsgenau):
    `acls: 17 Positionen (managed=13, foreign=4, iac3=4)` + `ssh: 3 (managed=2, foreign=1, iac3=1)`.
  - **Regel-Reihenfolge abweichend: 0.**

### 4.2 Kandidat (empfohlen: neue Regel `ksem-read`) — Beleg E3 + E4
Modell-Kandidat = SSoT + `ksem-read` (**pending**), Modell-Position 17.
`--model <SSoT> --file <anker> --dry-run --rules ksem-read --tolerated-foreign <liste>`:

```
Fehlend (Soll, nicht live): 0
Geändert (Soll != live): 0
Unerwartet fremd in live: 0
Zusatz/Duplikat: 0
Tolerierter Fremdbestand (vorhanden/unverändert): 5   (5/5)
Tolerierter Fremdbestand fehlt/verändert: 0
Pending deklariert, live vorhanden: 0
Pending deklariert, nicht live: 1   ← die neue Regel (außerhalb des Live-Solls)
Regel-Reihenfolge (acls/ssh) abweichend: 0
--- Plan (selektiv) ---
   + [ksem-read] acls:{"action": "accept", "dst": ["192.168.0.31:502"], "src": ["tag:ia4"]}
   1 Einfügung(en), 0 Entfernung(en) – rein additiv
```
⇒ **Erwartung exakt erfüllt: +1 Einfügung, 0 Entfernungen, 0 Änderungen.**
Zusatz-Beleg E4: `--verify` mit dem Kandidaten bleibt **grün** (die `pending`-Regel
liegt außerhalb des Live-Solls) ⇒ die Vorlage verändert den **verifizierten
Null-Diff nicht**.

### 4.3 Gegenbeleg E5 (warum NICHT `energie-read` erweitern)
Modell-Kandidat B = `energie-read.dst` um `192.168.0.31:502` erweitert. Offline:
```
Fehlend (Soll, nicht live): 1
   - acls | {"dst": ["192.168.0.31:1502","192.168.0.31:502","192.168.0.13:80","192.168.0.13:1502"], "src": ["tag:ia4"]} | fehlt
Unerwartet fremd in live: 1
   - acls | {"dst": ["192.168.0.31:1502","192.168.0.13:80","192.168.0.13:1502"], "src": ["tag:ia4"]} | unbekannt
```
⇒ Eine Erweiterung des bestehenden Kanons **entfernt/ändert** die Live-Regel 7 und
verletzt die Additivitäts-/Null-Diff-Zusage. **Deshalb Vorzugsvariante (b).**

### 4.4 Offline-Test-Suite — Beleg E6
`python3 acl/tests/offline_tests.py` → **alle Nachweise grün** (`🎉 Alle
Offline-Nachweise bestanden`, exit 0), inkl. der positionsgenauen
Toleranz-Fälle (i)–(v), Duplikat-Erkennung (8h/8i) und Provenienz-Anker (8j).

### 4.5 Abgrenzung „verwaltet vs. toleriert“ (bleibt unberührt)
- **verwaltet:** IaC3-/pre-IaC4-`base` + IaC4 + HA-Regeln 1–7 + `console-owner`
  (inkl. `owner → 192.168.2.0/24:*`) + `ksem-port-probe` → exakt/positionsgenau,
  **keine** Änderung.
- **toleriert (Fremdbestand):** die **5 übrigen IaC3-Regeln** → unverändert.
- Die neue Regel ist **weder** verwalteter Bestand **noch** tolerierter
  Fremdbestand, sondern eine **`pending`-Deklaration** (nur bei expliziter Wahl
  anwendbar).

---

## 5) Rollback-Pfad

1. **Primär (Plan-/SSoT-Ebene):** Die Regel wird als **`pending`** geführt und ist
   **nicht Teil des Live-Solls**. Wird die Freigabe **nicht** erteilt, passiert
   **nichts** — der `pending`-Block wird einfach wieder aus der SSoT entfernt
   (kein Apply nötig; der Draft-PR wird geschlossen).
2. **Nach einem Apply (falls je ausgeführt):** Entfernung der Regel = **1 Block** löschen.
   `ensure-acl.py` ist **bewusst rein additiv** und hat **keine Delete-Funktion** ⇒
   die Wegnahme ist eine **eigene, bewusste** Aktion:
   - **a) Applier-Backup:** der Applier schreibt **vor** dem POST ein Backup
     (`/tmp/acl-backup.json` auf dem Runner-FS) und rollt bei **Verifikationsfehler**
     automatisch zurück (POST des Backups). Greift nur **automatisch beim Apply**.
   - **b) Rollback-Anker (empfohlen für den manuellen Rückweg):** **vor** dem Apply
     einen **rohen Export** ziehen (`ensure-acl.py --export`, read-only GET) und
     einfrieren; Rollback = dieses eingefrorene Policy-JSON **einmalig** per POST
     zurückschreiben (manuell, Owner-Go). Alternativ den Block im
     Admin-Console-Policy-Editor entfernen.
3. **Idempotenz:** `ensure-acl` ist additiv/idempotent — ein erneuter Lauf mit
   `--rule ksem-read` fügt **nicht** doppelt ein (`count==1`-Gate) und meldet
   „bereits vollständig vorhanden — no-op“.

---

## 6) Ablösung der temporären Gruppe `ksem-port-probe` (eigener Entfernungs-Schritt)

`ksem-port-probe` (`dst: ["192.168.0.31:80","192.168.0.31:502"]`, live seit Owner-Go
2026-09-12 12:41 UTC) ist **rein diagnostisch** und wird durch `ksem-read` abgelöst.

**Reihenfolge ist wichtig (First-add-then-remove):**
1. **Schritt 1 — dauerhafte Regel live bringen (dieser Vorlage-Gegenstand):**
   Owner-Apply-Go → Dry-Run → Apply `rules=ksem-read` (`confirm=APPLY-ACL`).
   Zwischenzustand: `:502` ist **doppelt** gewährt (`energie-read` deckt `:1502`
   nicht, aber `ksem-port-probe` **und** `ksem-read` decken `:502`) — **harmlos**
   (Tailscale = Mengen-Union von Freigaben; keine „deny“-Konflikte, da ausschließlich
   `accept`).
2. **Schritt 2 — Entfernung `ksem-port-probe` (separater, bewusster Vorgang):**
   - **Vorbereitung:** SSoT-Block `ksem-port-probe` aus `acl/tailscale-acl.hujson`
     entfernen (Modell-Änderung; `--check-model` → 20 Einträge) **und**
     `acl/tolerated-foreign.json`-Layout + Fixtures entsprechend nachziehen
     (Model-Token entfällt) sowie `docs/adr/ADR-026` + Runbook + README pflegen.
   - **Live-Entfernung:** Da `ensure-acl.py` **nicht löschen** kann, ist die
     Wegnahme eine **eigene** Aktion:
     - **a) Konsolen-Policy-Editor:** den einen `ksem-port-probe`-Eintrag manuell
       entfernen (Owner), **oder**
     - **b) Rollback-/Reset-POST:** die um `ksem-port-probe` **bereinigte**
       Live-Policy **einmalig** per POST zurückschreiben (Owner-Go) — gestützt auf
       den **vor** Schritt 2 gezogenen rohen Export (§5.2b).
   - **Verifikation:** `--verify <neuer post-Export> --tolerated-foreign` → **grün**
     (verwalteter Teil exakt; `ksem-port-probe` in Modell **und** Live weg;
     IaC3-Fremdbestand 5/5 positionsgenau). **Hinweis:** `:80` (Web) fällt mit der
     Entfernung **weg** — falls die Web-UI dauerhaft gebraucht wird, braucht sie
     eine **eigene** Regel (eigener Owner-Go).

> **Zwischenzustand ist ausdrücklich akzeptabel:** `:502` doppelt gewährt ist eine
> **Union**, kein Widerspruch. Es ist **kein** Big-Bang nötig; beide Schritte sind
> additiv bzw. einzeln reversibel.

---

## 7) Status — explizit

> **NICHT angewendet** (keine Live-ACL-Änderung). **Kein** ACL-Write (kein POST/PATCH),
> **kein** Apply, **kein** Workflow-Trigger, **keine** Tailscale-/ha1-/vps-dev-/
> vps-prod-Konfigänderung, **keine** Secrets. Ausschließlich **offline/Modell** gegen
> den **eingefrorenen Export**.
> Diese Vorlage wartet auf **Owner-Apply-Go** (`confirm=APPLY-ACL`) **nach** Sicht auf
> das Dokument **und** **Review (Autor ≠ Reviewer)**. Erst danach: manueller
> `--dry-run` (Wirkungs-Analyse) → `dry_run=false` + `confirm=APPLY-ACL` → Apply mit
> Backup + Verify + Auto-Rollback.
> **Draft-PR** (Branch `feat/acl-ksem-read-durable`) enthält **nur** die additive
> `pending`-Regel + Beiwerk — **offen, KEIN Merge, KEIN Apply**.

---

## 8) Offene Punkte (für Review/Freigabe)

1. **Owner-Apply-Go** für `ksem-read` (`rules=ksem-read`, `confirm=APPLY-ACL`) — und
   **expliziter Blast-Radius-Entscheid**: vps-prod erhält den KSEM-`:502`-Lesezugriff
   (§3.1). Alternative: engere Quelle über dediziertes vps-dev-Tag (eigener Go).
2. **Port-Umfang:** nur `:502` (empfohlen) vs. zusätzlich `:80` (§2.3).
3. **`energie-read` `:1502`:** die Regel führt weiter den **toten** KSEM-`:1502`-Port.
   Empfehlung: **separate** Aufräum-Entscheidung (nicht Teil dieser Vorlage).
4. **Ablösung `ksem-port-probe`:** Schritt 2 (§6) ist ein **eigener** Vorgang
   (Entfernung + Doku); Zeitpunkt nach Live von `ksem-read`.
5. **Alias-Hygiene:** In `scripts/ensure-acl.py` mappt `ksem`/`probe` aktuell auf
   `ksem-port-probe`, `ksem-read`/`ksemread`/`ksem-durable` auf `ksem-read`. Nach
   Entfernung von `ksem-port-probe` (Schritt 2) sollte `ksem` → `ksem-read` zeigen
   (eigene Kleinigkeit im Entfernungs-PR).
6. **Reviewer benennen** (Autor ≠ Reviewer) + Rollback-Anker (roher Export) vor Apply.

---

## 9) Belegübersicht (kompakt)

| # | Beleg | Ergebnis |
|---|---|---|
| E1 | `ensure-acl.py --check-model` | **21 Einträge** (nach `ksem-read`), Gates ok (exit 0) |
| E2 | `--verify <anker> --tolerated-foreign` (Baseline) | grün; Fremdbestand **5/5**; Fremd/Geändert/Fehlend/Reihenfolge = 0 |
| E3 | Kandidat Dry-Run (offline, `--rules ksem-read`) | **+1 Einfügung, 0 Entfernungen, 0 Änderungen**; pending |
| E4 | Kandidat `--verify` | grün (pending außerhalb Live-Soll) ⇒ Null-Diff unberührt |
| E5 | Kandidat B (`energie-read` erweitert) | **Fehlend 1 + Unerwartet fremd 1** ⇒ nicht additiv (verworfen) |
| E6 | `acl/tests/offline_tests.py` | **alle grün** (inkl. Toleranz-Fälle (i)–(v), Duplikate 8h/8i, Provenienz 8j) |
| E7 | `--check-model` / `--dry-run` Model | 20 → **21** Einträge; `acls` +1 (pending) |
| — | Provenienz-Anker | Export-SHA == `source_export_sha256` (`b7c7b2d4…4b40`) |

**Anker-Datei:** `/home/node/.openclaw/workspace/acl-live-export-20260912-post-ksem.json`
**SSoT:** `iaC4-cleanup/acl/tailscale-acl.hujson` — Basis `main` (HEAD `b6ceaf1`);
Kandidat-Regel + Beiwerk auf Branch `feat/acl-ksem-read-durable` (Draft-PR)
**Toleranzliste:** `iaC4-cleanup/acl/tolerated-foreign.json` (Schema v2, positionsgenau)

**Output-Contract (kompakt, für Orchestrator):**
```json
{
  "status": "done",
  "ergebnis": "Vorlage + additive pending-Regel ksem-read (KSEM 192.168.0.31:502, nur lesend) + Draft-PR vorbereitet; NICHT angewendet.",
  "belege": [
    "acl/tailscale-acl.hujson: neuer pending-Block 'rule: ksem-read pending' als letzter acls-Eintrag (Modell-Position 17)",
    "offline --verify <anker> --tolerated-foreign: exit 0, Fremdbestand 5/5 positionsgenau, Reihenfolge 0",
    "offline --dry-run --rules ksem-read: +1 Einfügung / 0 Entfernungen / 0 Änderungen",
    "Kandidat B (energie-read erweitert): Fehlend 1 + Unerwartet fremd 1 -> verworfen",
    "acl/tests/offline_tests.py: alle Nachweise gruen (exit 0)"
  ],
  "offene_punkte": [
    "Owner-Apply-Go (confirm=APPLY-ACL) + Blast-Radius-Entscheid vps-prod",
    "Port-Umfang nur :502 (empfohlen) vs. :80",
    "energie-read :1502 (toter Port) separate Aufraeum-Entscheidung",
    "Abloesung ksem-port-probe = eigener Entfernungs-Schritt nach Live",
    "Reviewer (Autor != Reviewer) benennen"
  ]
}
```
