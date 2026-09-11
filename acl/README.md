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
| `tolerated-foreign.json` | **Fremdbestand-Toleranzliste** (nur noch IaC3 aktiv, 5 Einträge; Konsolen-Einträge sind seit 2026-09-11 19:52 UTC **ins Modell** übernommen) |
| `tests/fixtures/live-reconstructed.hujson` | Offline-Testfixture (aktueller Live-Stand, verwalteter Teil inkl. Konsolen-Einträge) |
| `tests/fixtures/live-with-foreign.hujson` | Testfixture: Live-Stand **+ dokumentierter (IaC3) Fremdbestand** (realer Aufbau) |
| `tests/fixtures/live-with-tolerated-foreign.hujson` | Testfixture: Live-Stand **+ dokumentierter (IaC3) Fremdbestand** (realer Aufbau, inkl. Interleaving) |
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
4. **Live-Zustand** wird an der Regel selbst kommentiert (Beleg: Run-ID,
   Zeitstempel; z. B. `mqtt-1883`, Widerspruch aufgelöst 2026-09-11).

## Gruppen (Workflow-Input `rules`)

| Gruppe | Herkunft | Status |
|--------|----------|--------|
| `iac4` | IaC4 (tag:ia4) | live (letzter IaC4-Lauf 31.07.2026) |
| `ha-tagowners` (= HA-Regel 1) | tag:ha + tag:ha-ci | live |
| `ha-acl` (= HA-Regel 2) | oc/ci/ia4 → ha1/ha3 (22+8123) | live |
| `ha-ssh` (= HA-Regel 3) | ssh-Spiegel → tag:ha | live |
| `ha-runner` (= HA-Regel 4) | ha-ci → ia4 (22+8123) | live |
| `owner-8123` (= HA-Regel 5) | admin/member → ia4:8123 | live |
| `console-owner` | Regel-1-Cluster aus der Owner-Konsole: `owner` ↔ `tag:ha` + `owner` → LAN (`192.168.0.0/24`, `192.168.2.0/24`) | **live** (Owner-Entscheid 2026-09-11 19:52 UTC: ins Modell übernommen) |
| `mqtt-1883` (= HA-Regel 6) | ia4 → ha:1883 | **live** (Run-Log-rekonstruiert; Apply 2026-09-09) |
| `energie-read` (= HA-Regel 7) | ia4 → 3 Energie-Ziele | **pending / nicht live** |

Numerische Aliase `1`..`7` der HA-Regeln sind aus Kontinuität weiter erlaubt.

## Verify mit Toleranz (Erfolgskriterium, Owner-Entscheide F4 + G1–G3, 2026-09-11)

`--verify <export> --tolerated-foreign <liste>` gilt als bestanden, wenn

- der **verwaltete Teil** (Modelleinträge) **exakt** matcht **inkl. Reihenfolge**
  (`acls`/`ssh`) — Zero-Delta **nur** des verwalteten Teils;
- der **dokumentierte Fremdbestand** (siehe `tolerated-foreign.json`) vollständig,
  unverändert und an seinen **Live-Positionen** vorhanden ist;
- **kein unerwarteter** Live-Eintrag existiert (Modell ∪ Toleranzliste).

Tags (`tagOwners`) werden als **Zuordnung** verglichen (Reihenfolge irrelevant);
Formatierung, Kommentare und Trailing-Kommas bleiben unberücksichtigt. **Byte**-
Gleichheit ist **nicht** das Kriterium (die Tailscale-API reserialisiert die
Policy). Jede Abweichung → **exit 1** mit Benennung des Eintrags.

Der **strikte** Null-Diff (`--verify` **ohne** `--tolerated-foreign`, „Modell ≡
Live, kein Fremdbestand“) bleibt verfügbar.

### Bekannte Limitierung (Block-Position des Fremdbestands) — M2-Finding 2026-09-11

Die Toleranzliste pinnt den Fremdbestand je Abschnitt als **zusammenhängenden
Block** mit Position `start`/`end`. Der **reale** Live-Aufbau erfüllt das für
`acls` **nicht**: die IaC3-Selbstregel (`tag:ia3 → tag:ia3:*`) steht in Live
**vor** dem (jetzt verwalteten) Konsolen-Block, die übrigen drei IaC3-Einträge
danach — der IaC3-Block ist also durch verwaltete Einträge **unterbrochen**.

Folge: Für den eingefrorenen Export (`acl-live-export-20260911.json`) meldet
der `--verify`

- **verwalteter Teil exakt** (Fehlend/Geändert = 0), **Fremdbestand vollständig/
  unverändert** (5 vorhanden, 0 fehlend/verändert), **kein unerwarteter Eintrag**
  — also genau das **Erfolgskriterium** —,
- aber **eine** Reihenfolge-Abweichung, weil die IaC3-Selbstregel nicht im
  Block erwartet wird → **exit 1** (`Regel-Reihenfolge (acls/ssh) abweichend: 1`).

Das ist **kein** Datenfehler des Modells/Toleranz, sondern eine **Limitierung des
Block-Positions-Modells** gegenüber einem nicht-zusammenhängenden Fremdbestand.
Behebung erfordert eine **Owner-Entscheidung**: entweder den Fremdbestand
positions-genau (interleaving-fähig) modellieren oder die Block-Positionierung in
der Erfolgsdefinition präzisieren. Siehe Runbook „M2-Finding" + Migrations-Log.

## Fremdbestand (nicht von IaC4 verwaltet)

Owner-Entscheid 2026-09-11 (19:41 UTC): **„IaC3 nicht übernehmen“** — die
IaC3-Einträge (`tag:ia3`-Regeln + SSH admin/member/ci → `tag:ia3`) sind **eigene
Zuständigkeit** und werden **nicht** ins Modell aufgenommen; sie bleiben als
**dokumentierter Fremdbestand** in `tolerated-foreign.json` (Gruppe `iac3`,
aktiv toleriert, **5 Einträge**).

Owner-Entscheid 2026-09-11 (19:52 UTC): **„Ja“** — die **vier Konsolen-Einträge**
(Regel-1-Cluster `owner` ↔ `tag:ha`, aus der Admin-Konsole) wurden **ins Modell
übernommen** (Gruppe `console-owner`, live) und sind damit **verwalteter Bestand**.
Der Eintrag `owner → 192.168.2.0/24:*` (zweites Heimnetz) bleibt **ausdrücklich
bestehen** und ist künftig modellverwaltet — eine spätere Entfernung wäre eine
eigene, bewusste Änderung. Der frühere Platzhalter `owner-decision-pending` ist
entfallen.

> **Sicherheits-Eigenschaft:** Der Applier liest die **Live-Policy**, fügt **rein
> additiv** ein und schreibt zurück. Er schreibt **nie** das Modell als
> Gesamtdatei über die Live-Policy — sonst würden die nicht übernommenen
> Einträge **gelöscht** (Pre-POST-Guard `semantic_additivity` + Post-POST-Verify).
> **Risiko:** `tag:ia3 → 192.168.0.0/24` gewährt Zugriff ins Heimnetz (siehe
> Backlog-Issue #141).

## IaC4-first (Übergang, Owner-Entscheid F3/F6)

Der Applier erzwingt für die HA-Gruppen die **IaC4-Baseline** (`tag:ia4`) als
semantische Vorbedingung (aus HA-PR #54 übernommen). Neue Einträge werden an
ihrer **Modell-Position** eingefügt (Regel-Reihenfolge bleibt erhalten). Der
HA-Apply-Weg bleibt bis zur **Sperre nach** dem IaC4-Apply offen und wird danach
deaktiviert (nicht gelöscht).

## Bedienung

```bash
# Modell-Gates prüfen (offline)
python3 scripts/ensure-acl.py --check-model

# Semantischer Soll/Ist-Diff (read-only, kein POST)
TS_TAILNET=… TS_API_KEY=… python3 scripts/ensure-acl.py --dry-run

# Null-Diff-Verifikation (exit != 0 bei Drift; semantisch inkl. Regel-Reihenfolge)
TS_TAILNET=… TS_API_KEY=… python3 scripts/ensure-acl.py --verify

# Null-Diff reproduzierbar gegen einen exportierten Live-Stand (Datei + SHA256)
python3 scripts/ensure-acl.py --verify acl/live-export-<sha8>.hujson

# Verify MIT Fremdbestand-Toleranz (M3-Gate): verwalteter Teil exakt +
# dokumentierter Fremdbestand unverändert/an Live-Positionen
python3 scripts/ensure-acl.py --verify acl/live-export-<sha8>.hujson \
    --tolerated-foreign acl/tolerated-foreign.json

# Inventar: rohe Live-huJSON + SHA256 (read-only GET, gewinnt den fehlenden
# versionierten Ist-Stand)
TS_TAILNET=… TS_API_KEY=… python3 scripts/ensure-acl.py --export --out acl/live.hujson

# Selektiver, additiver Apply (nur nach Dry-Run + Review + Owner-Go)
TS_TAILNET=… TS_API_KEY=… python3 scripts/ensure-acl.py --rules iac4 --confirm APPLY-ACL

# Offline-Tests (kein Netz, kein POST)
python3 acl/tests/offline_tests.py
```

> **Roh-Export wird nicht versioniert** (Owner-Entscheid 2026-09-11, Entscheid 3):
> Der rohe Live-Export ist **kein** Repo-Artefakt. Er wird per Workflow
> `00-acl-apply.yml` (`export=true`) als **Artefakt** erzeugt/abgerufen und als
> Kopie im Workspace eingefroren; `.gitignore` schließt `acl/live*.hujson` aus.
> Beleg sind SHA256 + Zeitstempel (Artefakt `acl-export-info.txt`).

## Governance

- Ein ACL-Apply läuft **nie automatisch** — manuell über
  `.github/workflows/00-acl-apply.yml` (`confirm=APPLY-ACL`, `dry_run`, `rules`).
  Der Legacy-Trigger in Workflow 01 (`01-tailscale-terraform.yml`) ist **entfernt**
  (Entscheid 1): Workflow 01 löst **keinen** `tag:ia4`-Apply mehr aus.
- Jeder Apply: Wirkungs-Analyse (`--dry-run`) + Review (Autor ≠ Reviewer) +
  ausdrückliche Owner-Zustimmung.
- Der Applier ist **rein additiv** (bestehende Zeilen werden nie verändert/entfernt)
  mit Backup + Auto-Rollback bei Verifikationsfehler.

## Bekannte Lücke (Voraussetzung, kein Auftrag)

Ohne gültigen `TAILSCALE_API_KEY` (IaC4-Key seit 2026-07-31 **401**) und ohne
rohen Live-Export ist die **Null-Diff-Verifikation** ([Runbook](../docs/workflows/acl-migration-runbook.md)
M3) nicht ausführbar. Diese Lücke gehört in den Runbook-Kopf, nicht in diese
Migration.

Der Soll/Ist-Bestand (Modell-Soll + Fixture `tests/fixtures/live-reconstructed.hujson`)
ist derzeit eine **Run-Log-Rekonstruktion** (kein roher Export). Nach Schließen der
Lücke (V2) ist er durch den **rohen Export + `--verify`** zu ersetzen/bestätigen.
