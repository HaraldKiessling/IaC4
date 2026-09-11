# Runbook: Tailscale-ACL-Migration nach IaC4 (Single Source)

> **Status:** Vorbereitung (Draft). Kein Merge, kein Apply. Owner-Entscheide
> 2026-09-11 (07:27 UTC Grundsatz „ACL ist Infrastruktur → IaC4"; 07:56–11:08 UTC
> F1–F6; 19:41 UTC G1–G3; 19:52 UTC H1 – Konsolen-Einträge ins Modell; 20:24 UTC
> J1 – Fremdbestand positionsgenau, siehe unten).
> **M2-Finding (19:52 UTC) → behoben (20:24 UTC):** Das Block-Positions-Modell
> konnte den verschränkten IaC3-Fremdbestand nicht abbilden; mit **J1** ist er
> **positionsgenau** modelliert (Verschränkung zulässig), das M3-Gate gegen den
> eingefrorenen Export ist **grün** (Details unten).
> **Grundsatz:** **reiner, verhaltensneutraler Umzug** + saubere Dokumentation —
> keine zusätzlichen Anforderungen; identifizierte Lücken werden separat als
> IaC4-Issues erfasst.

## Zweck

Migration der geteilten Tailscale-ACL von **zwei additiven Schreibpfaden**
(IaC4 `ensure-acl-ia4.py` + ha-repo `ensure-acl-ha.py`) auf **eine Quelle in
IaC4**: SSoT `acl/tailscale-acl.hujson`, ein semantischer Applier
(`scripts/ensure-acl.py`), ein manueller Apply-Weg
(`.github/workflows/00-acl-apply.yml`). Ergebnis: `tag:ia4` **und** `tag:ha`
(inkl. `tag:ha-ci`, MQTT-/Energie-Regeln) aus einer Regelquelle.

## Abgestimmte Entscheide (2026-09-11, F1–F6)

| # | Gegenstand | Festlegung |
|---|------------|------------|
| **F1=(a)** | Umfang | **Reiner Umzug**, verhaltensneutral. Die neue **Lese-Regel (Kostal/KSEM = Energie-Regel 7)** bleibt `pending` und kommt erst **nach** dem Schnitt als eigener, freigegebener Schritt. |
| **F3=(b)** | Übergang | **IaC4-first**: der IaC4-Apply führt; der HA-Apply bleibt **bis danach** als **Rückfallweg offen**; **Sperre danach**. |
| **F4=(a)** | Erfolgskriterium | **Semantische Gleichheit** der geparsten Policy **inkl. Regel-Reihenfolge** (`acls`/`ssh`); Formatierung/Kommentare dürfen abweichen. **Byte**-Gleichheit ist **nicht** das Kriterium (Tailscale-API reserialisiert). → **Präzisiert 2026-09-11 (19:41 UTC):** gilt für den **verwalteten Teil**; nicht übernommener Fremdbestand wird **toleriert/dokumentiert** (siehe unten). |

### Zusätzliche Owner-Entscheide (2026-09-11, 19:41 UTC)

| # | Gegenstand | Festlegung |
|---|------------|------------|
| **G1** | IaC3-Übernahme | **„IaC3 nicht übernehmen"** – die IaC3-Einträge (`tag:ia3`-Regeln + SSH admin/member/ci → `tag:ia3`) werden **nicht** ins IaC4-Modell aufgenommen. Konsequenz: Der strikte Null-Diff entfällt; es gilt **„verwalteter Teil exakt + dokumentierter Fremdbestand unverändert"**. |
| **G2** | Konsolen-Einträge | Die **vier Konsolen-Einträge** (Regel-1-Cluster `owner` ↔ `tag:ha`) bleiben **offen**: klar markierter, konfigurierbarer Platzhalter in `acl/tolerated-foreign.json`; **nicht raten, nicht aufnehmen**. Backlog-Issue **#141** angelegt. **→ überholt durch H1 (19:52 UTC, unten).** |
| **G3** | Erfolgskriterium | „Zero-Delta" bezieht sich **nur** auf den **verwalteten Teil**. M3-Gate = Verify **mit Toleranz** (`--tolerated-foreign`). |
| **F5=(a)** | HA-PR #54 | Inhalt (semantische Precondition) wandert ins IaC4-Werkzeug; **#54** wird als **überholt** geschlossen (Referenz-Kommentar auf PR #140 + Branch/Commit). |
| **F6=(a)** | Sperre | HA-Workflow **deaktivieren** (nicht löschen) + **Kopfhinweis** + Doku-Eintrag; Ausführung durch den **Orchestrator nach Owner-Bestätigung**, im Migrations-Log festgehalten. |

### Zusätzliche Owner-Entscheide (2026-09-11, 19:52 UTC)

| # | Gegenstand | Festlegung |
|---|------------|------------|
| **H1** | Vier Konsolen-Einträge | **„Ja"** – die vier Einträge aus der Admin-Konsole (Regel-1-Cluster `owner` ↔ `tag:ha`) werden **ins Modell übernommen** (Gruppe `console-owner`, live), **nicht** nur toleriert. Der Eintrag `owner → 192.168.2.0/24:*` (zweites Heimnetz) bleibt **ausdrücklich** bestehen (kein Aufräumschritt; künftig modellverwaltet – spätere Entfernung = eigene, bewusste Änderung). **IaC3 bleibt weiterhin NICHT übernommen** (tolerierter, dokumentierter Fremdbestand). Damit enthält `acl/tolerated-foreign.json` nur noch die **5 IaC3-Einträge**; der frühere Platzhalter entfällt. |

### Zusätzliche Owner-Entscheide (2026-09-11, 20:24 UTC)

| # | Gegenstand | Festlegung |
|---|------------|------------|
| **J1** | Fremdbestand-Modell | **„1"** – Der Fremdbestand wird **positionsgenau modelliert** (Verschränkung/Interleaving **erlaubt**), **nicht** als zusammenhängender Block. Begründung: die **Reihenfolge-Überwachung bleibt scharf** (Umsortierungen/Einschübe rund um unsere Regeln fallen auf). Umsetzung: Toleranzliste **Schema v2** (`layout`: geordnete `managed`/`foreign`-Positionen) + `--verify` positionsgenau; **M2-Finding behoben** — M3-Gate gegen den eingefrorenen Export **grün**. |

### Zusätzliche Owner-Entscheide (2026-09-11, 17:52 UTC)

| # | Gegenstand | Festlegung | Umsetzung |
|---|------------|------------|-----------|
| **E1** | Legacy-Trigger Workflow 01 | Workflow `01-tailscale-terraform.yml` darf den `tag:ia4`-Apply **nicht mehr automatisch** auslösen (raus aus dem push-/`terraform/**`-Trigger). ACL-Apply **nur noch manuell** (`workflow_dispatch` + explizite Bestätigung). **Kein** eingebautes „Confirm“ in Workflow 01. | ACL-Schritt (Aufruf `ensure-acl-ia4.py`) **entfernt**; Kopfhinweis ergänzt; Terraform-Teil unverändert. Einziger Apply-Weg bleibt `00-acl-apply.yml` (`confirm=APPLY-ACL`). |
| **E2** | Merge-Grundlage | **Regel-6-live-Evidenz** (Run-Log-Rekonstruktion, Run 34398338512) wird für den **Merge** akzeptiert; der **rohe Export bestätigt später** (M3). | Merge von #140 ohne vorherigen Roh-Export; `--verify` gegen den Export erfolgt nachgelagert. |
| **E3** | Roh-Export | Roh-Export **nicht ins Repo**: `.gitignore` + Artefakt-Upload; Kopie im Workspace einfrieren. Doku-Notiz „Roh-Export wird nicht versioniert“. | `.gitignore` (`acl/live*.hujson`) + Artefakt-Upload in `00-acl-apply.yml` (`export=true`) + Hinweise in `acl/README.md`/Runbook (M1). |
| **E4** | Merge der Vorstufe | **Ja** — PR #140 (reine Migration + Doku, kein Apply) darf gemergt werden. | `gh pr merge 140 --merge` (kein Force, kein Branch-Delete). |

## Voraussetzungen (blockierend, vor M1)

| # | Voraussetzung | Status |
|---|---------------|--------|
| V1 | **IaC4-Tailscale-API-Key** erneuern (401 seit 2026-07-31 15:36) → als Secret `TAILSCALE_API_KEY` | **OFFEN (Lücke)** |
| V2 | **Roher Live-Export** der ACL (`GET /api/v2/tailnet/{tailnet}/acl`) als read-only `--export` + SHA256 — als **Artefakt** (nicht versioniert, Entscheid 3) | **OFFEN (Lücke)** |
| V3 | Drift-Befund verbindlich einarbeiten (`acl-drift-analyse-20260911.md`) | teilweise (Run-Log-rekonstruiert, siehe „Live-Bestand") |

> **Hinweis:** V1/V2 sind **bekannte Lücken, kein Auftrag dieser Migration.**
> Ohne sie ist M3 (Null-Diff) **nicht ausführbar**. Sie werden hier als
> Voraussetzung markiert, nicht gelöst.

## Live-Bestand (Run-Log-Rekonstruktion, Stand 2026-09-11)

Der aktuelle Live-Bestand ist **nicht** aus einem rohen huJSON-Export, sondern
aus **Run-Logs rekonstruiert** (Lücke V2). Modell-Soll und Offline-Fixture
(`acl/tests/fixtures/live-reconstructed.hujson`) bilden diesen Stand ab:
`base + iac4 + ha-tagowners + ha-acl + mqtt-1883 + ha-runner + owner-8123 + ha-ssh`
(HA-Regeln **1–6**; Regel 7 nicht live).

- **Regel 6 (MQTT 1883) = Live-Soll (belegt):** additiver POST am
  **2026-09-09T19:59:30Z** (HA-Repo-Run **34398338512**, `DRY_RUN=false`), Log
  „➕ …1883 MQTT eingefügt", „✅ count==1", **kein Rollback**.
- **Aufgelöster Widerspruch (Dry-Run vs. Apply):** Der kursierende „20:02Z-Apply"
  war **kein** Apply — Run **34398400415** (2026-09-09T20:00Z) lief mit
  `DRY_RUN=true`. Das erklärt die widersprüchlichen Aussagen („Regel 6 live" vs.
  „nur Branch-Stand"); beide sind hiermit geschlossen.
- **Ersetzen/Bestätigen nach der Lücke:** Sobald V2 (roher Export) geschlossen ist,
  wird diese Rekonstruktion durch den **rohen Export + `--verify`** ersetzt bzw.
  bestätigt (M3). Keine weitere Migration ohne diesen Abgleich.
- **Roher Export (V2) liegt vor:** `acl-live-export-20260911.json` (sha256
  `8cd58f88…`, 2026-09-11T17:58:11Z, read-only GET). Reale `acls`-Reihenfolge:
  verwalteter Teil (0–6), **IaC3-Selbstregel (7)**, **Konsolen-Block (8–11)**,
  restlicher IaC3-Block (12–14) — d. h. der **IaC3-Block ist unterbrochen**.
  Nach dem Owner-Entscheid H1 (19:52 UTC) sind die 4 Konsolen-Einträge Teil des
  Modells. Mit dem Owner-Entscheid **J1 (20:24 UTC)** ist der Fremdbestand
  **positionsgenau** modelliert; das Toleranz-Verify gegen diesen Export ist
  **grün (exit 0)**: **verwalteter Teil fehlend/geändert = 0**, **IaC3-Fremdbestand
  (5) positionsgenau vorhanden/unverändert**, **kein unerwarteter Eintrag**,
  **Reihenfolge ok** — also das **Erfolgskriterium** erfüllt. Ohne Toleranz wären
  alle **5** Fremd-Einträge Drift.

## M2-Finding (2026-09-11) → behoben durch J1 (20:24 UTC)

**Beobachtung (damals):** Der eingefrorene Live-Export zeigt für `acls` die
Reihenfolge `[verwaltet 0–6] [IaC3-Selbstregel 7] [Konsolen-Block 8–11]
[IaC3 12–14]`. Der IaC3-Fremdbestand ist also **nicht zusammenhängend** — er wird
durch den (mit H1 verwalteten) Konsolen-Block **unterbrochen**.

**Wirkung (damals):** Das Toleranz-Verify erfüllte das **Erfolgskriterium**
(verwalteter Teil exakt inkl. Reihenfolge, IaC3-Fremdbestand 5/5 vorhanden/
unverändert, kein unerwarteter Eintrag), meldete aber **eine
Reihenfolge-Abweichung** und lieferte **exit 1**, weil die Toleranzliste den
Fremdbestand nur als **zusammenhängenden Block** (`position` `start`/`end`)
abbilden konnte.

**Bewertung (damals):** Kein Datenfehler im Modell/Toleranz, sondern eine
**Limitierung des Block-Positions-Modells** — **nicht** durch „Zurechtbiegen“
von Modell/Toleranzliste aufzulösen.

**Lösung (Owner-Entscheid J1, 20:24 UTC, „1“): Option 1 — positionsgenaue
Modellierung.** Der Fremdbestand ist in `acl/tolerated-foreign.json` (Schema v2)
als **geordnetes `layout`** abgebildet: `managed`-Token (Wert aus dem Modell, in
Modell-Reihenfolge konsumiert) und `foreign`-Token (eingefrorener Soll-Eintrag)
in **exakt der Live-Reihenfolge**. Verschränkung ist damit zulässig; die
Reihenfolge-Überwachung bleibt **scharf** (Umsortierungen/Einschübe → exit 1).
Werkzeug: `ensure-acl.py` (`load_tolerated`, `expected_sequence`, `order_diff`).

**Status:** M3-Gate gegen den eingefrorenen Export **grün (exit 0)** — verwalteter
Teil exakt, Fremdbestand 5/5 **positionsgenau** vorhanden/unverändert, kein
unerwarteter Eintrag, Reihenfolge ok. Nachweis offline:
`acl/tests/offline_tests.py` (Fälle 8a–8g: verschränkt → grün; verschoben/
verändert/fehlend/Zusatz/Managed-verschoben → exit 1). **Kein Merge/kein Apply.**

## Ablauf

### M1 — Export (Inventar, verlustfrei, read-only)

1. Live-Policy roh exportieren (reiner `GET`, **kein Commit**):
   - über den Workflow (empfohlen, kein lokaler Key nötig):
     `.github/workflows/00-acl-apply.yml` per `workflow_dispatch` mit
     **`export=true`** (`dry_run=true`, **niemals** `apply`) starten; danach das
     Artefakt `acl-live-export-<run_id>` abrufen (`gh run download`).
   - oder lokal: `python3 scripts/ensure-acl.py --export --out acl/live-<ts>.hujson`
     (schreibt rohe huJSON + `.sha256`; reiner `GET`).
2. **Der Roh-Export wird NICHT versioniert** (Entscheid 3, 2026-09-11): Die
   Ablage erfolgt als **Workflow-Artefakt** plus eingefrorene Kopie im Workspace
   (`.gitignore`: `acl/live*.hujson`). Nur SHA256 + Zeitstempel sind der Beleg.
3. Semantisch parsen und in die Struktur `tagOwners` / `acls` / `ssh` zerlegen.
4. Regel-für-Regel-Zuordnung erstellen: welche Live-Blöcke gehören zu `tag:ia4`
   (IaC4), welche zu `tag:ha`/`tag:ha-ci` (HA), was ist „fremder Bestand"
   (ia3, Owner-Konsole) → Letzteres bleibt **unverändert**.
5. **Ergebnis:** vollständiges semantisches Inventar = Ist-Referenz für M2.
   Kein Schreiben.

### M2 — verwalteter Teil 1:1 + Fremdbestand toleriert/dokumentiert

Ziel ist **nicht** mehr „Modell ≡ Live (gesamte Policy)", sondern: **verwalteter
Teil 1:1** (Zero-Delta des verwalteten Teils) **+ dokumentierter Fremdbestand
unverändert**. Owner-Entscheid 2026-09-11 (19:41 UTC): „IaC3 nicht übernehmen" –
IaC3 ist eine **eigene Zuständigkeit** und wird **nicht mitverwaltet**.

> **Abgrenzung (präzise):** **verwaltet** = IaC3-/pre-IaC4-`base` (`tagOwners`
> `tag:ia3`, `tag:ci` + Basis-`acl` `ci/member/admin → tag:ia3`) **+** IaC4 **+**
> HA-Regeln 1–6 **+** die Konsolen-Einträge; **toleriert** = die **5 übrigen
> IaC3-*Regeln*** (4 `acls` + 1 `ssh`). Es ist **nicht** der *gesamte*
> IaC3-Altbestand toleriert — die `base`-Einträge sind verwaltet und werden
> **strenger** geprüft (`missing`/`changed`, nicht „toleriert").

1. `acl/tailscale-acl.hujson` für den **verwalteten Teil** 1:1 aus dem Inventar
   ableiten. Ziel: der verwaltete Teil matcht Live **exakt inkl. Reihenfolge**
   (Zero-Delta des verwalteten Teils).
2. **Nicht übernommener Fremdbestand** wird **nicht** ins Modell aufgenommen,
   sondern in `acl/tolerated-foreign.json` dokumentiert:
   - **IaC3** (Gruppe `iac3`, aktiv toleriert, **5 Einträge**): `tag:ia3`-Selbstregel,
     `tag:ia3 → tag:ha`, `tag:ia3 → 192.168.0.0/24`, `tag:ha → tag:ia3` sowie
     SSH admin/member/ci → `tag:ia3`.
   - Die früheren **vier Konsolen-Einträge** (Regel-1-Cluster `owner` ↔ `tag:ha`)
     sind mit **H1 (19:52 UTC)** **ins Modell übernommen** (Gruppe `console-owner`,
     live) — der Platzhalter (`owner-decision-pending`) ist entfallen. Der Eintrag
     `owner → 192.168.2.0/24:*` bleibt ausdrücklich bestehen (modellverwaltet).
   Die Liste modelliert je Abschnitt eine **geordnete, positionsgenaue Erwartung**
   (`layout`, Schema v2: `managed`/`foreign`-Positionen) — **Verschränkung
   (Interleaving) ist zulässig** (Owner-Entscheid J1, 20:24 UTC). Der reale
   `acls`-Block des IaC3-Fremdbestands ist **nicht zusammenhängend** (IaC3-
   Selbstregel vor dem Konsolen-Block); das positionsgenaue Layout bildet das
   exakt ab (M2-Finding behoben).
3. Die `tag:ha`-Regeln (live) **und die vier Konsolen-Einträge (H1)** werden Teil
   des IaC4-Modells — ohne Änderung am Live-Zustand.
4. **Noch nicht angewandte Regeln** werden **nicht still mitmigriert**, sondern
   bleiben `pending` (deklariert, nicht Teil des Live-Solls):
   - `energie-read` (Regel 7 — **die neue Kostal/KSEM-Lese-Regel**, F1=(a)).
   `energie-read` ist eine **separate Owner-Freigabe** und kommt erst **nach**
   dem Schnitt als eigener Schritt. `mqtt-1883` (Regel 6) ist dagegen **live**
   und damit Teil des Live-Solls (Beleg siehe „Live-Bestand").
5. Modell-Gates prüfen: `python3 scripts/ensure-acl.py --check-model`.

### M3 — Semantischer Verify **mit Toleranz** (Verifikation)

1. `python3 scripts/ensure-acl.py --verify <export-datei> --tolerated-foreign acl/tolerated-foreign.json`
   (Voraussetzung: V1 + V2). **Bestanden = verwalteter Teil exakt +
   Fremdbestand positionsgenau unverändert:**
   - **verwalteter Teil** (Modelleinträge) matchet **exakt inkl. Reihenfolge**
     (Zero-Delta **nur** des verwalteten Teils);
   - **Tags** (`tagOwners`) als **Zuordnung** — Reihenfolge irrelevant;
   - **dokumentierter Fremdbestand** (`acl/tolerated-foreign.json`, Schema v2)
     **positionsgenau** unverändert: jeder Eintrag an **seiner** dokumentierten
     Position, in **genau der** dokumentierten Reihenfolge; **Verschränkung
     (Interleaving) zulässig** (Owner-Entscheid J1, 20:24 UTC);
   - **Formatierung, Kommentare, Trailing-Kommas** und die Feld-/Listen-Reihenfolge
     *innerhalb* einer Regel bleiben **unberücksichtigt**.
   exit != 0 bei Fehlend/Geändert **oder** fehlendem/verändertem/verschobenem
   Fremdbestand **oder** unerwartetem Fremdbestand **oder** Positions-/Reihenfolge-
   Abweichung (mit Nennung des Eintrags). **Exakt-Zählung (PR-#142-Auflage):** jede
   **zusätzliche/doppelte Kopie** eines bekannten Eintrags (verwaltet **oder**
   fremd; `extra`) ist Drift → exit 1 — die Zusage „jeder Zusatz → Abbruch" gilt
   damit auch für Duplikate. **Provenienz-Anker:** Wird gegen eine Export-Datei
   verifiziert, prüft das Skript deren SHA256 gegen `source_export_sha256` der
   Toleranzliste; Mismatch → Abbruch (die Liste bestätigt sich nicht strukturell
   selbst).
   Hinweis: Der strikte Null-Diff (`--verify` **ohne** `--tolerated-foreign`)
   bleibt verfügbar; er fordert Modell ≡ Live ohne jeden Fremdbestand.
   ✅ **M3-Status (20:24 UTC, J1):** Mit der positionsgenauen Modellierung ist das
   Gate gegen den eingefrorenen Export **grün (exit 0)** — verwalteter Teil exakt,
   IaC3-Fremdbestand 5/5 positionsgenau vorhanden/unverändert, kein unerwarteter
   Eintrag, Reihenfolge ok. Details: Abschnitt „M2-Finding → behoben“.
2. **Reproduzierbar:** derselbe Export aus M1 (Datei + `.sha256`) ergibt denselben
   Null-Diff — der Abgleich ist wiederholbar und nicht byte-, sondern semantik-basiert
   (Tailscale-API reserialisiert).
3. Roundtrip: `--dry-run` zeigt „0 Einfügungen, 0 Entfernungen".
4. Erst bei bestätigtem Null-Diff gilt „Stand synchronisiert"; ein Drift-Befund, der
   von der Annahme abweicht, wird hier eingearbeitet.
5. **Nachweis (offline, ohne Live):** `python3 acl/tests/offline_tests.py`.

### M4 — IaC4-Apply (HA parallel offen) — F3=(b)

1. Erster IaC4-Apply über `.github/workflows/00-acl-apply.yml`
   (`confirm=APPLY-ACL`, `dry_run=false`, `rules` nach Freigabe) — rein additiv,
   Backup + Auto-Rollback, `count==1`-Gates.
2. **IaC4-first:** der IaC4-Apply führt. **Der HA-Apply-Weg bleibt während des
   Übergangs offen** (Rückfallweg) — bis zur Sperre (M5) ist bei Bedarf ein
   Rückgriff auf `00-acl-apply-ha.yml` möglich.
3. Doppel-Schreiben begrenzen: `concurrency`-Guard im IaC4-Workflow;
   Additivitäts-/Fremdbestands-Checks in beiden Skripten; der IaC4-Applier erzwingt
   die **IaC4-Baseline als Vorbedingung** für HA-Gruppen (Reihenfolge IaC4-first).

### M5 — Sperre HA-Weg — F6=(a)

**Checkliste — Ausführung durch den Orchestrator *nach* Owner-Bestätigung; jeder
Punkt wird im Migrations-Log festgehalten.**

- [ ] Owner-Bestätigung der Sperre liegt vor.
- [ ] `00-acl-apply-ha.yml` **deaktivieren** (nicht löschen): Trigger entfernen bzw.
      `if: false`-Guard setzen.
- [ ] **Kopfhinweis** im HA-Workflow setzen (Text = Block „Header-Hinweis" aus
      [ha-repo-acl-boundary-note.md](ha-repo-acl-boundary-note.md)).
- [ ] `scripts/ensure-acl-ha.py` als **Rollback-Referenz** erhalten (nur-lesend,
      Deprecated-Header-Marker).
- [ ] ha-repo-Doku aktualisieren: `docs/reference/tailscale-acl.md`,
      `AGENTS.md` (Harte Regeln), `TODO.md` (F14 als superseded) — Textbaustein aus
      [ha-repo-acl-boundary-note.md](ha-repo-acl-boundary-note.md).
- [ ] **Migrations-Log**-Eintrag ergänzen (Datum, Schritt, Ausführender).

> Deaktivieren statt löschen stellt den Rückfallweg bis zur endgültigen Stilllegung
> bereit; die Reaktivierung ist **nur nach erneutem Owner-Go** zulässig.

### M6 — Doku

- ADR-026, dieses Runbook und `acl/README.md` konsistent halten; Regel-Spiegelung in
  `.roo/rules/tailscale-acl.mdc` und `AGENTS.md`.
- Keine Platzhalter; Abweichungen von der Spezifikation sind zu melden.
- Übernahme aus HA-PR #54 dokumentieren (siehe Abschnitt unten).

## Übernahme aus HA-PR #54 (semantische Precondition) — F5=(a)

Die HA-seitige Vorab-Prüfung („IaC4-Voraussetzung `tag:ia4` vorhanden") wurde in
`HaraldKiessling/home-assistant-agent` von einem **byte-exakten Anker** auf eine
**semantische** Prüfung umgestellt (geparste huJSON, layout-tolerant, nur für die
tatsächlich eingefügten Regeln — PR **#54**, Branch `fix/acl-precondition-semantisch`).
Diese Semantik ist **1:1** in das IaC4-Werkzeug übernommen:

- `scripts/ensure-acl.py` → `precondition_ok()` + `PRECOND_DESC`; ausgeführt in
  `main()` nur für die Gruppen, die **dieser Lauf tatsächlich einfügt**
  (Scope-Kopplung), gegen Live + geplante Einfügungen;
- Nachweis: `acl/tests/offline_tests.py` — positiv (`ha-tagowners`/`ha-acl`/`ha-ssh`
  erfüllt) und negativ (ohne IaC4-Basis fehlt die Vorbedingung).

Damit ist der **Inhalt von #54 vollständig im IaC4-Checker enthalten**; **#54**
wurde als **überholt** geschlossen (Referenz auf PR #140 + Branch/Commit).

## Rollback

- **Live-ACL:** durch die Backup-/Rollback-Mechanik des Appliers jederzeit auf den
  letzten guten Stand zurückführbar (`/tmp/acl-backup.json` des Laufs erneut `POST`;
  zusätzlich manueller Konsolen-Rollback im Tailscale-Admin).
- **IaC4-Seite:** `git revert` des Modell-/Skript-/Doku-PR stellt den Vorzustand wieder her.
- **ha-repo-Seite:** der **deaktivierte** (nicht gelöschte) Workflow und das Skript
  bleiben bis zur endgültigen Stilllegung erhalten und können per `git` reaktiviert
  werden — **nur nach erneutem Owner-Go**.

## Grenz-Hinweis für das ha-repo

Der Textbaustein für das ha-repo liegt in
[ha-repo-acl-boundary-note.md](ha-repo-acl-boundary-note.md) (dort separat
einzubringen: `docs/reference/tailscale-acl.md` + Header-Hinweis im Apply-Workflow +
`AGENTS.md`/`TODO.md`).

## Migrations-Log

| Datum (UTC) | Schritt | Status | Ausführender |
|-------------|---------|--------|--------------|
| 2026-09-11 | M1–M3 vorbereitet: SSoT + semantischer Applier + Doku (Draft-PR #140) | vorbereitet | Engineer |
| 2026-09-11 | M4 IaC4-Apply | blockiert — V1 (Key 401) + V2 (roher Export) fehlen | Orchestrator (nach V1/V2) |
| 2026-09-11 | M5 Sperre HA-Weg | ausstehend — nach Owner-Bestätigung | Orchestrator |
| 2026-09-11 | Befund eingearbeitet: Regel 6 (mqtt-1883) = **Live-Soll** (Run-Log-Beleg 34398338512); Regel 7 bleibt `pending`; Live-Bestand als Rekonstruktion dokumentiert | erledigt | Engineer |
| 2026-09-11 | **E1** Workflow 01: automatischer `tag:ia4`-Apply entfernt (kein push-/PR-Auslöser mehr); ACL nur noch manuell | erledigt | Engineer |
| 2026-09-11 | **E3** Roh-Export nicht versioniert: `.gitignore` + Artefakt-Upload (`00-acl-apply.yml`, `export=true`); Doku-Notiz | erledigt | Engineer |
| 2026-09-11 | **E2/E4** Regel-6-live-Evidenz für Merge akzeptiert; Merge Vorstufe PR #140 freigegeben | erledigt | Engineer/Orchestrator |
| 2026-09-11 | **G1–G3** (19:41 UTC): „IaC3 nicht übernehmen" → Fremdbestand-Toleranz umgesetzt (`acl/tolerated-foreign.json` + `--verify --tolerated-foreign`); M2 = „verwalteter Teil 1:1 + Fremdbestand toleriert/dokumentiert"; M3-Gate = Verify **mit** Toleranz | umgesetzt (Draft-PR, kein Merge) | Engineer |
| 2026-09-11 | Verify gegen eingefrorenen Export: verwalteter Teil exakt, IaC3-Fremdbestand (5) toleriert/vorhanden, **4 Konsolen-Einträge undokumentiert → exit 1** (Owner-Entscheid G2 offen) | Befund | Engineer |
| 2026-09-11 | **H1 (19:52 UTC):** „Ja“ – die 4 Konsolen-Einträge (Regel-1-Cluster `owner` ↔ `tag:ha`) **ins Modell übernommen** (Gruppe `console-owner`); `owner → 192.168.2.0/24:*` ausdrücklich bestätigt (künftig modellverwaltet). `acl/tolerated-foreign.json` = nur noch 5 IaC3-Einträge; Platzhalter entfallen. Doku (ADR-026/Runbook/`acl/README.md`) aktualisiert. **Kein Merge/kein Apply.** | umgesetzt (Draft-PR, kein Merge) | Engineer |
| 2026-09-11 | Verify gegen eingefrorenen Export nach H1: verwalteter Teil exakt, IaC3-Fremdbestand (5) vorhanden/unverändert, kein Unerwarteter — **aber 1 Reihenfolge-Abweichung** (IaC3-Selbstregel vor Konsolen-Block, Block-Positions-Modell) → **exit 1**. **M2-Finding** dokumentiert; Owner-Entscheidung zu Option 1/2 offen. | Befund | Engineer |
| 2026-09-11 | **J1 (20:24 UTC):** „1“ – Fremdbestand **positionsgenau** modelliert (Verschränkung erlaubt). Toleranzliste auf Schema v2 (`layout`) umgestellt; `ensure-acl.py` (`load_tolerated`/`expected_sequence`/`order_diff`) positionsgenau; Offline-Tests 8a–8g erweitert (verschränkt → grün; verschoben/verändert/fehlend/Zusatz/Managed-verschoben → exit 1). **M2-Finding behoben.** | umgesetzt (Draft-PR, kein Merge) | Engineer |
| 2026-09-11 | Verify gegen eingefrorenen Export nach J1: verwalteter Teil exakt, IaC3-Fremdbestand (5) **positionsgenau** vorhanden/unverändert, kein Unerwarteter, Reihenfolge ok → **grün (exit 0)**. `--check-model` + `py_compile` + `offline_tests.py` grün. | erledigt | Engineer |

## Offene Lücken (separat als IaC4-Issues, nicht Teil dieser Migration)

1. IaC4-Tailscale-API-Key erneuern (V1) — Voraussetzung für echten Access.
2. Raw-huJSON-Export + SHA256 der Live-Policy als versionierter Ist-Stand (V2).
3. Tag→Node-Inventar (ha1/ha3, vps-dev/vps-prod) für den Blast-Radius.
4. ~~Doku-Widerspruch „Regel 6 live?" per Live-GET klären.~~ **aufgelöst 2026-09-11**
   (Regel 6 = Live-Soll, belegt per Run-Log; siehe „Live-Bestand").
5. ~~`--accept-routes` in IaC verankern (separater Task, nicht hier).~~ **verankert
   2026-09-11** (Issue #135): idempotente Rolle-Task + Mini-Playbook
   `ansible/playbooks/tailscale-accept-routes.yml` + Workflow
   `02b-tailscale-accept-routes.yml`; Runbook
   `docs/workflows/tailscale-accept-routes-runbook.md`. Kein Apply/Re-Join.
