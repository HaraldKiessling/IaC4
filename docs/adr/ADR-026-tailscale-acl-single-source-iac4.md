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
   verändert oder entfernt).
3. **Ein Apply-Weg:** `.github/workflows/00-acl-apply.yml` — ausschließlich
   manuell (`workflow_dispatch`), Inputs `confirm`/`dry_run`/`rules`,
   **kein** push-/PR-Trigger (Governance: ACL nie automatisch). Secrets-Namen
   unverändert (`TAILSCALE_TAILNET`, `TAILSCALE_API_KEY`).
4. **Kein Terraform-ACL-Resource:** ADR-010 bleibt gewahrt (Overwrite-Gefahr).

Der bisherige IaC4-Pfad (`ensure-acl-ia4.py`) wird auf einen dünnen
Kompatibilitäts-Shim reduziert (leitet auf `ensure-acl.py --rule iac4`), damit
der bestehende Aufrufer (Workflow 01) nicht bricht.

## Optionen

### A: Konsolidierung in IaC4 (SSoT + semantischer Applier) — EMPFEHLUNG
- **Fachliche Auswirkungen:** Eine Regelquelle, ein Governance-Ort, deckt den
  Owner-Entscheid ab. Beseitigt doppelte Wartung und die geteilte-Skript-SSoT.
  Die robustere Mechanik des HA-Skripts (semantischer Multimengen-Vergleich)
  wird zum einzigen Mechanismus; die byte-exakten IaC4-Anker (brittle gegen
  API-Re-Serialisierung) entfallen.

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

- `acl-drift-analyse-20260911.md` (live: Regeln 1/2/3/4/5 + 6 strittig; 7 nicht
  live; IaC4-Byte-Anker vermutlich nicht mehr matchfähig nach API-Re-Serialisierung).
- `acl-konsolidierung-iac4-20260911.md` (Zielarchitektur, Migrationsplan M1–M7).
- ha-repo `scripts/ensure-acl-ha.py` (semantischer Multimengen-Vergleich,
  Precondition-Kette, `count==1`-Gates — als Mechanik-Vorbild).
- IaC4 `docs/arc42/09_architekturentscheidungen.md` ADR-008/010/014.

## Empfehlung

**Option A.** Umsetzung erfolgt schrittweise über das Runbook
[docs/workflows/acl-migration-runbook.md](../workflows/acl-migration-runbook.md)
(M1 Inventar/Export → M2 Modell 1:1 → M3 Null-Diff → M4 Schnitt → M5 Einfrieren
→ M6 Stilllegung). Erste PR-Stufe (dieser Stand): Modell + Skript + Workflow +
Doku, **Draft, kein Merge, kein Apply**.

## Worst-Case / Rollback (Pflicht: ACL-Änderung)

- **Worst-Case 1 — Lockout:** eine falsche/leere ACL sperrt Tailnet-Zugriffe
  (SSH/8123) aus.
  - **Gegenmaßnahme:** nie Overwrite; nur additiv; Backup + Auto-Rollback im
    Skript; `dry_run`-Default; Owner-Go vor jedem Apply.
  - **Rollback:** automatischer POST des Backups bei Verifikationsfehler;
    zusätzlich Konsolen-Rollback (`GET`-Backup `/tmp/acl-backup.json` des Laufs
    erneut `POST`). Manueller Konsolenpfad im Runbook dokumentiert.
- **Worst-Case 2 — Überschreiben fremder Einträge** (ia3/Owner-Konsole).
  - **Gegenmaßnahme:** semantische Additivitäts-/Multimengen-Prüfung
    (Fremdbestand unverändert); Null-Diff-Gate in M3.
- **Worst-Case 3 — Doppel-Schreiben** während des Übergangs.
  - **Gegenmaßnahme:** `concurrency`-Guard im Apply-Workflow; ha-repo-Pfad
    **vor** erstem IaC4-Apply deaktivieren (Runbook M4); Fremdbestands-Abbruch.

## Konsequenzen

- Neue SSoT `acl/tailscale-acl.hujson` + Konventionen (`acl/README.md`).
- `scripts/ensure-acl.py` ersetzt `ensure-acl-ia4.py` (Shim bleibt für Workflow 01).
- Neuer manueller Workflow `.github/workflows/00-acl-apply.yml`.
- ha-repo erhält einen Grenz-Hinweis (ACL wird in IaC4 verwaltet) und friert
  seinen ACL-Pfad ein (→ entfernen).
- **Voraussetzung (Lücke, nicht Auftrag):** gültiger IaC4-`TAILSCALE_API_KEY`
  sowie ein roher Live-Export sind für M3 (Null-Diff) erforderlich; heute nicht vorhanden.
- **Folge-Entscheidungen (separat):** Zeitpunkt des Schnitts, Prod-Ausführung,
  Aktivierungszeitpunkt von Regel 6/7, `--accept-routes` (nicht Teil dieser ADR).

## Referenzen

- <https://tailscale.com/kb/1018/acls>
- <https://tailscale.com/kb/1236/ts-acl-ssh>
