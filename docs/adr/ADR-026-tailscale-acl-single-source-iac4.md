# ADR-026: Tailscale-ACL — Single Source of Truth in IaC4

- **Status:** Vorgeschlagen (Proposed)
- **Datum:** 2026-09-11
- **Kontext:** Die Tailscale-ACL wurde bislang von **zwei unabhängigen
  Schreibpfaden** additiv verändert: IaC4 (`scripts/ensure-acl-ia4.py` für
  `tag:ia4`, Workflow 01, byte-exakte Anker) und ha-repo
  (`scripts/ensure-acl-ha.py` für `tag:ha`/`tag:ha-ci`, manueller Workflow).
  Beide schreiben per `POST /api/v2/tailnet/{tailnet}/acl` auf **dieselbe**
  Policy. Es gab **keine gemeinsame Regelquelle**, keine Schreib-Koordination
  und keine gemeinsame Verifikation; die IaC4-Gewähr endet am 31.07.2026
  (API-Key seither 401). Owner-Entscheid 2026-09-11 (07:27 UTC): „Tailscale-ACL
  ist Infrastruktur und gehört zu IaC4."
- **Supersedes:** F14 (ha-repo, 2026-09-06, „ACL-Pflege im HA-Repo", Issue #24)
  wird mit der Migration abgelöst. ADR-010 (IaC4, „ACL nicht mehr in
  IaC4-Terraform") bleibt für *Terraform* gültig — die ACL wird weiterhin
  **nicht** über eine Terraform-Resource verwaltet, sondern deklarativ über die
  SSoT-Datei + semantisches, additives Skript.

## Entscheidungsfrage

In welchem Repo und mit welchem Mechanismus wird die geteilte Tailscale-ACL für
beide Tag-Welten (`tag:ia4` und `tag:ha`/`tag:ha-ci`) **eindeutig** verwaltet?

## Entscheidung

**IaC4 ist die einzige Regelquelle.** Konkret:

1. **Eine SSoT-Datei:** `acl/tailscale-acl.hujson` hält die **gesamte** Policy
   (beide Tag-Welten, inkl. Phase-2-/Energie-/MQTT-Regeln), in fester
   Reihenfolge `tagOwners` → `acls` → `ssh`.
2. **Ein Mechanismus:** `scripts/ensure-acl.py` liest die SSoT, vergleicht sie
   **semantisch** (huJSON→JSON, layout-tolerant) mit der Live-Policy und wendet
   nur die fehlende Differenz **rein additiv** an (bestehende Zeilen werden nie
   verändert oder entfernt). Neue Einträge werden an ihrer **Modell-Position**
   eingefügt, sodass die Regel-Reihenfolge erhalten bleibt.
3. **Erfolgskriterium (Owner-Entscheid F4=(a), präzisiert 2026-09-11 19:41 UTC;
   positionsgenau 2026-09-11 20:24 UTC):**
   Der Abgleich `--verify <export-datei> --tolerated-foreign <liste>` gilt als
   bestanden, wenn der **verwaltete Teil** (Modelleinträge, **inkl. der
   `base`-Einträge** — IaC3-/pre-IaC4-Basis: `tagOwners` `tag:ia3`/`tag:ci` +
   Basis-Regel `ci/member/admin → tag:ia3`) **semantisch exakt**
   matcht **inkl. Regel-Reihenfolge** (`acls`/`ssh`) **und** der **dokumentierte
   Fremdbestand** **positionsgenau** unverändert vorhanden ist (jeder Eintrag an
   **seiner** dokumentierten Position, in **genau der** dokumentierten
   Reihenfolge). Tags (`tagOwners`) werden als Zuordnung verglichen; Formatierung,
   Kommentare und Trailing-Kommas bleiben unberücksichtigt. **Byte**-Gleichheit
   ist **nicht** das Kriterium (die Tailscale-API reserialisiert die Policy).
   Der frühere strikte **Null-Diff** („Modell ≡ Live, kein fremder Eintrag“) gilt
   damit **nur noch für den verwalteten Teil**; er wird hier als „Zero-Delta des
   verwalteten Teils“ verstanden, nicht als Deckungsgleichheit der gesamten Policy.
3b. **Nicht übernommener Fremdbestand (Owner-Entscheid 2026-09-11 „IaC3 nicht
   übernehmen“):** Die IaC3-Einträge (`tag:ia3`-Regeln + SSH admin/member/ci →
   `tag:ia3`) werden **nicht** ins IaC4-Modell aufgenommen. Sie sind eine **eigene
   Zuständigkeit** (IaC3) und bleiben als **dokumentierter Fremdbestand** in
   `acl/tolerated-foreign.json` erfasst (Gruppe `iac3`, 5 Einträge): Sie müssen
   vollständig und **positionsgenau** an ihren **Live-Positionen** erhalten
   bleiben, unterliegen aber **nicht** der IaC4-Modellierung.

   **Abgrenzung (präzise):** **verwaltet** = IaC3-/pre-IaC4-`base` (`tagOwners`
   `tag:ia3`, `tag:ci` + Basis-`acl` `ci/member/admin → tag:ia3`) **+** IaC4 **+**
   HA-Regeln 1–7 **+** die Konsolen-Einträge; **toleriert** = die **5 übrigen
   IaC3-*Regeln*** (4 `acls` + 1 `ssh`). Damit ist **nicht** der *gesamte*
   IaC3-Altbestand toleriert: die `base`-Einträge sind verwaltet und werden
   **strenger** geprüft (`missing`/`changed`, nicht „toleriert").

   Die **vier Konsolen-Einträge** (Regel-1-Cluster `owner` ↔ `tag:ha`, aus der
   Owner-Konsole) wurden mit dem **Owner-Entscheid 2026-09-11 (19:52 UTC, „Ja“)**
   **ins IaC4-Modell übernommen** (Gruppe `console-owner`, live) und sind damit
   **verwalteter Bestand** (nicht mehr Fremdbestand). Der Eintrag
   `owner → 192.168.2.0/24:*` (zweites Heimnetz) bleibt **ausdrücklich gewollt**;
   eine spätere Entfernung wäre eine eigene, bewusste Änderung. Der frühere
   Platzhalter (`owner-decision-pending`) ist damit entfallen (Backlog-Issue #141
   abgeschlossen/geschlossen).
4. **Ein Apply-Weg:** `.github/workflows/00-acl-apply.yml` — ausschließlich
   manuell (`workflow_dispatch`), Inputs `export`/`confirm`/`dry_run`/`rules`,
   **kein** push-/PR-Trigger (Governance: ACL nie automatisch). Secrets-Namen
   unverändert (`TAILSCALE_TAILNET`, `TAILSCALE_API_KEY`). Der Input `export`
   liefert den rohen Live-Stand als **Artefakt** (read-only, nicht versioniert) —
   Grundlage für M3. Der Legacy-Aufruf in Workflow 01 wurde mit dem Owner-Entscheid
   2026-09-11 (Entscheid 1) **entfernt**: Workflow 01 löst keinen `tag:ia4`-Apply
   mehr aus.
5. **Übergang IaC4-first (Owner-Entscheid F3=(b)):** Der IaC4-Apply führt; der
   HA-Apply-Weg bleibt während des Übergangs als **Rückfallweg offen** und wird
   **danach** gesperrt (deaktivieren statt löschen, F6=(a)).
6. **Kein Terraform-ACL-Resource:** ADR-010 bleibt gewahrt (Overwrite-Gefahr).
7. **Der Applier schreibt NIE das Modell als Gesamtdatei über die Live-Policy:**
   Er liest die **Live-Policy** (GET), fügt **rein additiv** ein und schreibt
   zurück. Basis ist ausnahmslos die gelesene Live-Policy; das Modell liefert nur
   die **einzufügenden** Einträge. Andernfalls würden nicht übernommene Einträge
   (Fremdbestand: IaC3/Konsolen) **gelöscht**. Abgesichert durch den Pre-POST-Guard
   (`semantic_additivity` vor dem POST) und den Post-POST-Verify (count==1 +
   Additivität); bei Fehler Backup-Rollback.

Der bisherige IaC4-Pfad (`ensure-acl-ia4.py`) wird auf einen dünnen
Kompatibilitäts-Shim reduziert (leitet auf `ensure-acl.py --rule iac4`); er wird
von **keinem** Workflow mehr aufgerufen (Workflow 01 entkoppelt, Entscheid 1) und
bleibt nur als Migrations-/Rollback-Referenz erhalten.

### Fremdbestand-Toleranz (Owner-Entscheid 2026-09-11 „IaC3 nicht übernehmen“)

**Begründung:** IaC3 ist eine **eigene Zuständigkeit**. Die IaC3-Regeln wurden
bewusst **nicht** übernommen (kein Mitverwalten). Damit ist ein strikter Null-Diff
der **gesamten** Policy nicht mehr das Ziel; das Erfolgskriterium ist der
**verwaltete Teil exakt + dokumentierter Fremdbestand unverändert**.

**Mechanik (positionsgenau, Schema v2):** `acl/tolerated-foreign.json`
modelliert je Abschnitt (`acls`/`ssh`) eine **geordnete Erwartung** (`layout`):
jeder Live-Eintrag ist als `managed` (Wert aus dem Modell, in Modell-Reihenfolge
konsumiert) oder `foreign` (eingefrorener Soll-Eintrag) klassifiziert, in genau
dieser Reihenfolge. **Verschränkung (Interleaving) ist damit zulässig.**
`--verify <export> --tolerated-foreign <liste>` prüft: (a) jeder `managed`-Eintrag
≡ Modell (Wert + Position), (b) jeder `foreign`-Eintrag ≡ Soll-Wert + steht an
seiner Position, (c) **kein unerwarteter** Live-Eintrag (Modell ∪ Toleranzliste)
und keine Umsortierung. Jede Abweichung → **exit 1** mit Nennung des betroffenen
Eintrags (+ Position). Der strikte Modus bleibt ohne `--tolerated-foreign` erhalten.

**Aufgelöste Limitierung (M2-Finding 2026-09-11, behoben 20:24 UTC):** Das frühere
Block-Positions-Modell (`position` `start`/`end`) setzte einen **zusammenhängenden**
Fremdbestand-Block voraus. In der realen Live-Policy ist der IaC3-`acls`-Block
jedoch durch den (jetzt verwalteten) Konsolen-Block **unterbrochen**
(IaC3-Selbstregel steht davor). Der `--verify` meldete daher fälschlich eine
Reihenfolge-Abweichung (exit 1), obwohl das **Erfolgskriterium** erfüllt war. Mit
dem Owner-Entscheid 2026-09-11 (20:24 UTC, „1“) ist der Fremdbestand
**positionsgenau** modelliert; Verschränkung ist erlaubt. Der `--verify` gegen den
eingefrorenen Export ist damit **grün** (exit 0). Siehe Runbook „M2-Finding“.

### Übernahme aus HA-PR #54 (F5=(a))

Die semantische **IaC4-Vorbedingung** (HA-Gruppen setzen auf die `tag:ia4`-Basis
auf; layout-tolerante, scope-gekoppelte Prüfung) aus `home-assistant-agent`
PR **#54** (Branch `fix/acl-precondition-semantisch`) ist **1:1** in
`scripts/ensure-acl.py` enthalten (`precondition_ok()`/`PRECOND_DESC`, im Apply nur
für die tatsächlich eingefügten Gruppen geprüft) und offline getestet
(`acl/tests/offline_tests.py`). **#54** wird als **überholt** geschlossen
(Referenz auf PR #140 + Branch/Commit).

## Optionen

### A: Konsolidierung in IaC4 (SSoT + semantischer Applier) — EMPFEHLUNG
- **Fachliche Auswirkungen:** Eine Regelquelle, ein Governance-Ort, deckt den
  Owner-Entscheid ab. Beseitigt doppelte Wartung und die geteilte-Skript-SSoT.
  Die robustere Mechanik des HA-Skripts (semantischer Vergleich) wird zum einzigen
  Mechanismus, ergänzt um die **Reihenfolge-Prüfung** (F4); die byte-exakten
  IaC4-Anker (brittle gegen API-Re-Serialisierung) entfallen.

### B: Konsolidierung in ha-repo
- **Verworfen:** ACL ist Infrastruktur → falsche Zuordnung; widerspricht dem
  Owner-Entscheid und dem IaC4-ADR-010-Kontext (koordinierter Prozess).

### C: Terraform-ACL-Resource wieder einführen
- **Verworfen:** ADR-010 — ein früher Overwrite löschte ia3+ha-Regeln; der
  Tailscale-Provider hat schwache Diff-/Rollback-Semantik für die Policy.

### D: Beide Pfade parallel weiterbetreiben
- **Verworfen:** kein Umbau, aber Drift-/Doppel-Schreib-Risiko bleibt — genau
  das Problem, das gelöst werden soll.

## Evidenz

- `acl-drift-analyse-20260911.md` (live zum Analyse-Zeitpunkt: Regeln 1–6 —
  Regel 6 belegt per Run-Log 2026-09-09; 7 damals nicht live, inzwischen
  aktiviert; IaC4-Byte-Anker vermutlich nicht mehr matchfähig nach
  API-Re-Serialisierung).
- `acl-konsolidierung-iac4-20260911.md` (Zielarchitektur, Migrationsplan M1–M7).
- ha-repo `scripts/ensure-acl-ha.py` (semantischer Multimengen-Vergleich,
  Precondition-Kette, `count==1`-Gates — als Mechanik-Vorbild).
- IaC4 `docs/arc42/09_architekturentscheidungen.md` ADR-008/010/014.

## Empfehlung

**Option A.** Umsetzung erfolgt schrittweise über das Runbook
[docs/workflows/acl-migration-runbook.md](../workflows/acl-migration-runbook.md)
(M1 Export → M2 Modell 1:1 → M3 semantischer Null-Diff → M4 IaC4-Apply
(HA parallel offen) → M5 Sperre HA-Weg → M6 Doku). Erste PR-Stufe (dieser Stand):
Modell + Skript + Workflow + Doku, **Draft, kein Merge, kein Apply**.

## Worst-Case / Rollback (Pflicht: ACL-Änderung)

- **Worst-Case 1 — Lockout:** eine falsche/leere ACL sperrt Tailnet-Zugriffe
  (SSH/8123) aus.
  - **Gegenmaßnahme:** nie Overwrite; nur additiv; Backup + Auto-Rollback im
    Skript; `dry_run`-Default; Owner-Go vor jedem Apply.
  - **Rollback:** automatischer POST des Backups bei Verifikationsfehler;
    zusätzlich Konsolen-Rollback (`GET`-Backup `/tmp/acl-backup.json` des Laufs
    erneut `POST`). Manueller Konsolenpfad im Runbook dokumentiert.
- **Worst-Case 2 — Überschreiben fremder Einträge** (IaC3/Owner-Konsole).
  - **Gegenmaßnahme:** Der Applier liest die Live-Policy und fügt **rein additiv**
    ein – das Modell wird **nie** als Gesamtdatei über die Live-Policy geschrieben
    (Pre-POST-Guard `semantic_additivity` + Post-POST-Verify). Der dokumentierte
    Fremdbestand ist in `acl/tolerated-foreign.json` erfasst; das Toleranz-Verify
    (M3) prüft ihn als vollständig/unverändert an seinen Live-Positionen und
    meldet jeden unerwarteten Eintrag mit exit 1.
- **Worst-Case 3 — Doppel-Schreiben** während des Übergangs.
  - **Gegenmaßnahme:** `concurrency`-Guard im Apply-Workflow; **IaC4-first** (der
    Applier erzwingt die IaC4-Baseline als Vorbedingung für HA-Gruppen); der
    HA-Pfad bleibt bis zur **Sperre nach** dem IaC4-Apply offen (F3=(b)) und wird
    danach deaktiviert (F6=(a)); Fremdbestands-/Additivitäts-Abbruch.

## Konsequenzen

- Neue SSoT `acl/tailscale-acl.hujson` + Konventionen (`acl/README.md`).
- **Fremdbestand-Toleranzliste** `acl/tolerated-foreign.json` (nur IaC3 aktiv,
  5 Einträge) + `--tolerated-foreign` im Verifier; die **vier Konsolen-Einträge**
  sind seit 2026-09-11 (19:52 UTC) **Teil des Modells** (Gruppe `console-owner`).
- `scripts/ensure-acl.py` ersetzt `ensure-acl-ia4.py` (Shim bleibt für Workflow 01).
- Neuer manueller Workflow `.github/workflows/00-acl-apply.yml`.
- ha-repo erhält einen Grenz-Hinweis (ACL wird in IaC4 verwaltet); sein ACL-Pfad
  wird nach dem Übergang **gesperrt** (deaktivieren statt löschen, F6=(a); → später
  entfernen).
- **Voraussetzung (Lücke, nicht Auftrag):** gültiger IaC4-`TAILSCALE_API_KEY`
  sowie ein roher Live-Export sind für M3 (Null-Diff) erforderlich; heute nicht vorhanden.
- **Folge-Entscheidungen (separat):** Zeitpunkt des Schnitts, Prod-Ausführung,
  `--accept-routes` (nicht Teil dieser ADR). **Regel 7 (Energie)** ist mit dem
  **Owner-Go 2026-09-11 21:57 UTC** aktiviert (Gruppe `energie-read`, rein
  lesend; s. Migrations-Log im Runbook).

## Referenzen

- <https://tailscale.com/kb/1018/acls>
- <https://tailscale.com/kb/1236/ts-acl-ssh>
