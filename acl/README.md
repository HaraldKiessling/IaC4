# Tailscale-ACL — Single Source of Truth (IaC4)

Diese Verzeichnis enthält die **kanonische Tailscale-ACL** für das gesamte
Tailnet. Sie ist die **eine Regelquelle für beide Tag-Welten** (`tag:ia3` /
`tag:ia4` / `tag:ci` **und** `tag:ha` / `tag:ha-ci`).

> **Grundsatz (Owner-Entscheid 2026-09-11):** „Tailscale-ACL ist Infrastruktur
> und gehört zu IaC4." Siehe [ADR-026](../docs/adr/ADR-026-tailscale-acl-single-source-iac4.md)
> und das Migrations-Runbook [docs/workflows/acl-migration-runbook.md](../docs/workflows/acl-migration-runbook.md).

## Dateien

| Datei | Zweck |
|-------|-------|
| `tailscale-acl.hujson` | **SSoT**: kanonische Policy (tagOwners → acls → ssh) |
| `tests/fixtures/live-reconstructed.hujson` | Offline-Testfixture (rekonstruierter Live-Stand) |
| `tests/offline_tests.py` | Offline-Nachweise (kein Netz, kein POST) |

## Konventionen der SSoT-Datei

1. **Feste Block-Reihenfolge:** `tagOwners` → `acls` → `ssh`.
   `tagOwners` **vor** `acls`/`ssh` ist zwingend, da die Regeln auf die Tags
   verweisen (sonst Policy-invalid / Tag unbenannt).
2. **Marker-Zeile pro Eintrag** (huJSON-Kommentar unmittelbar darüber):
   - `// rule: <gruppe>` — Regel einer Teilmenge; bei selektivem Apply über
     `--rule <gruppe>` (bzw. Workflow-Input `rules`) einfügbar.
   - `// rule: <gruppe> pending` — Regel ist **deklariert**, aber **nicht Teil
     des aktuellen Live-Solls** (eigene, ausstehende Owner-Freigabe). Wird nur
     bei ausdrücklicher Selektion berücksichtigt.
   - `// base` — Bestands-Eintrag (pre-IaC4 / Owner-Konsole). Wird **nie**
     eingefügt, nur erwartet/verifiziert.
3. **huJSON-Kommentare** (`//`, `/* */`) und Trailing-Kommas sind erlaubt.
4. **Live-Zustand strittiger Regeln** wird an der Regel selbst kommentiert
   (siehe `mqtt-1883` in der SSoT).

## Gruppen (Workflow-Input `rules`)

| Gruppe | Herkunft | Status |
|--------|----------|--------|
| `iac4` | IaC4 (tag:ia4) | live (letzter IaC4-Lauf 31.07.2026) |
| `ha-tagowners` (= HA-Regel 1) | tag:ha + tag:ha-ci | live |
| `ha-acl` (= HA-Regel 2) | oc/ci/ia4 → ha1/ha3 (22+8123) | live |
| `ha-ssh` (= HA-Regel 3) | ssh-Spiegel → tag:ha | live |
| `ha-runner` (= HA-Regel 4) | ha-ci → ia4 (22+8123) | live |
| `owner-8123` (= HA-Regel 5) | admin/member → ia4:8123 | live |
| `mqtt-1883` (= HA-Regel 6) | ia4 → ha:1883 | **pending / Live-Zustand strittig** |
| `energie-read` (= HA-Regel 7) | ia4 → 3 Energie-Ziele | **pending / nicht live** |

Numerische Aliase `1`..`7` der HA-Regeln sind aus Kontinuität weiter erlaubt.

## Bedienung

```bash
# Modell-Gates prüfen (offline)
python3 scripts/ensure-acl.py --check-model

# Semantischer Soll/Ist-Diff (read-only, kein POST)
TS_TAILNET=… TS_API_KEY=… python3 scripts/ensure-acl.py --dry-run

# Null-Diff-Verifikation (exit != 0 bei Drift)
TS_TAILNET=… TS_API_KEY=… python3 scripts/ensure-acl.py --verify

# Inventar: rohe Live-huJSON + SHA256 (read-only GET, gewinnt den fehlenden
# versionierten Ist-Stand)
TS_TAILNET=… TS_API_KEY=… python3 scripts/ensure-acl.py --export --out acl/live.hujson

# Selektiver, additiver Apply (nur nach Dry-Run + Review + Owner-Go)
TS_TAILNET=… TS_API_KEY=… python3 scripts/ensure-acl.py --rules iac4 --confirm APPLY-ACL

# Offline-Tests (kein Netz, kein POST)
python3 acl/tests/offline_tests.py
```

## Governance

- Ein ACL-Apply läuft **nie automatisch** — manuell über
  `.github/workflows/00-acl-apply.yml` (`confirm=APPLY-ACL`, `dry_run`, `rules`).
- Jeder Apply: Wirkungs-Analyse (`--dry-run`) + Review (Autor ≠ Reviewer) +
  ausdrückliche Owner-Zustimmung.
- Der Applier ist **rein additiv** (bestehende Zeilen werden nie verändert/entfernt)
  mit Backup + Auto-Rollback bei Verifikationsfehler.

## Bekannte Lücke (Voraussetzung, kein Auftrag)

Ohne gültigen `TAILSCALE_API_KEY` (IaC4-Key seit 2026-07-31 **401**) und ohne
rohen Live-Export ist die **Null-Diff-Verifikation** ([Runbook](../docs/workflows/acl-migration-runbook.md)
M3) nicht ausführbar. Diese Lücke gehört in den Runbook-Kopf, nicht in diese
Migration.
