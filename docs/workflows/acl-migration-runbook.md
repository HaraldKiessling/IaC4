# Runbook: Tailscale-ACL-Migration nach IaC4 (Single Source)

> **Status:** Vorbereitung (Draft). Kein Merge, kein Apply. Owner-Entscheid
> 2026-09-11: „Tailscale-ACL ist Infrastruktur und gehört zu IaC4."
> **Grundsatz:** nur die reine Migration + saubere Dokumentation — keine
> zusätzlichen Anforderungen (identifizierte Lücken werden separat als
> IaC4-Issues erfasst).

## Zweck

Migration der geteilten Tailscale-ACL von **zwei additiven Schreibpfaden**
(IaC4 `ensure-acl-ia4.py` + ha-repo `ensure-acl-ha.py`) auf **eine Quelle in
IaC4**: SSoT `acl/tailscale-acl.hujson`, ein semantischer Applier
(`scripts/ensure-acl.py`), ein manueller Apply-Weg
(`.github/workflows/00-acl-apply.yml`). Ergebnis: `tag:ia4` **und** `tag:ha`
(inkl. `tag:ha-ci`, Phase-2-/MQTT-/Energie-Regeln) aus einer Regelquelle.

## Voraussetzungen (blockierend, vor M1)

| # | Voraussetzung | Status |
|---|---------------|--------|
| V1 | **IaC4-Tailscale-API-Key** erneuern (401 seit 2026-07-31 15:36) → als Secret `TAILSCALE_API_KEY` | **OFFEN (Lücke)** |
| V2 | **Roher Live-Export** der ACL (`GET /api/v2/tailnet/{tailnet}/acl`) als versioniertes Artefakt + SHA256 (read-only `--export`) | **OFFEN (Lücke)** |
| V3 | Drift-Befund verbindlich einarbeiten (`acl-drift-analyse-20260911.md`) | teilweise (rekonstruiert) |

> **Hinweis:** V1/V2 sind **bekannte Lücken, kein Auftrag dieser Migration.**
> Ohne sie ist M3 (Null-Diff) **nicht ausführbar**. Sie werden hier als
> Voraussetzung markiert, nicht gelöst.

## Ablauf

### M1 — Inventar (verlustfrei, read-only)

1. Live-Policy roh exportieren und versionieren:
   `python3 scripts/ensure-acl.py --export --out acl/live-<ts>.hujson`
   (schreibt rohe huJSON + `.sha256`; reiner `GET`).
2. Semantic parsen und in die Struktur `tagOwners` / `acls` / `ssh` zerlegen.
3. Regel-für-Regel-Zuordnung erstellen: welche Live-Blöcke gehören zu `tag:ia4`
   (IaC4), welche zu `tag:ha`/`tag:ha-ci` (HA 1–5), was ist „fremder Bestand"
   (ia3, Owner-Konsole) → Letzteres bleibt **unverändert**.
4. **Ergebnis:** vollständiges semantisches Inventar = Ist-Referenz für M2.
   Kein Schreiben.

### M2 — Modell (verlustfrei überführen)

1. `acl/tailscale-acl.hujson` **aus dem Inventar** ableiten — 1:1 aus der
   Live-Policy (inkl. ia3/tag:ci/Owner-Konsole). Ziel: Modell ≡ Live
   (Zero-Delta-Ausgang).
2. Die `tag:ha`-Regeln (live) werden Teil des IaC4-Modells — ohne Änderung am
   Live-Zustand.
3. **Noch nicht angewandte Regeln** (Regel 7 Energie; Regel 6 MQTT mit
   **strittigem** Live-Stand) werden **nicht still mitmigriert**: sie bleiben als
   `pending` markiert (deklariert, nicht Teil des Live-Solls) und laufen als
   **separate Owner-Freigaben**.
4. Modell-Gates prüfen: `python3 scripts/ensure-acl.py --check-model`.

### M3 — Verifikation (Zero-Delta-Beweis)

1. `python3 scripts/ensure-acl.py --verify` gegen Live → **Diff muss leer sein**
   (kein Fehlend/Geändert/Fremd). Voraussetzung: V1 + V2.
2. Roundtrip: `--dry-run` zeigt „0 Einfügungen, 0 Entfernungen".
3. Erst bei bestätigtem Zero-Delta gilt „Stand synchronisiert"; ein
   Drift-Befund, der von der Annahme abweicht, wird hier eingearbeitet.
4. **Nachweis (offline, ohne Live):** `python3 acl/tests/offline_tests.py`.

### M4 — Schnitt & Schreib-Hoheit (Übergang)

| Phase | Schreibpfad IaC4 | Schreibpfad ha-repo | Bedingung |
|-------|------------------|----------------------|-----------|
| M0–M3 | nur `--dry-run` | **eingefroren** (kein Apply) | ab Owner-Go „Freeze" |
| M4 (Schnitt) | einziger Schreibpfad | deaktiviert | Zero-Delta + Owner-Go |

- **Reihenfolge im Schnitt:** zuerst ha-repo-Apply-Workflow deaktivieren →
  **dann** erster IaC4-Apply. Niemals beide gleichzeitig aktiv.
- Doppel-Schreiben verhindern: `concurrency`-Guard im IaC4-Workflow,
  Fremdbestands-Abbruch im Skript, ha-repo-Apply deaktiviert.

### M5 — Deprecate ha-repo-ACL-Pfad

1. **Deprecate (mit M4):** `00-acl-apply-ha.yml` deaktivieren (Trigger entfernen
   oder `if: false`-Guard) + Header-Hinweis; `scripts/ensure-acl-ha.py` behalten
   (nur-lesend/Referenz) mit Deprecated-Marker; README/AGENTS.md/TODO.md im
   ha-repo aktualisieren (siehe Grenz-Hinweis unten).
2. **Einfrieren (nach erster IaC4-Apply-Phase):** Skript + Workflow nur noch als
   Rollback-Referenz; kein Dispatch mehr möglich.
3. **Entfernen (nach stabiler IaC4-Phase, Owner-Go):** Workflow +
   `ensure-acl-ha.py` löschen; History bleibt in Git.

### M6 — Stilllegung IaC4-Altpfad

1. Workflow 01 (`01-tailscale-terraform.yml`) enthält einen **automatischen**
   ACL-Schritt (`ensure-acl-ia4.py` auf `push: main`). Dieser widerspricht der
   Governance „ACL nie automatisch" und wird beim Schnitt entfernt; der
   Kompatibilitäts-Shim `ensure-acl-ia4.py` wird dann gelöscht.
2. Verbleibend: ausschließlich `00-acl-apply.yml` (manuell) als ACL-Schreibweg.

## Rollback

- **Live-ACL:** durch die Backup-/Rollback-Mechanik des Appliers jederzeit auf
  den letzten guten Stand zurückführbar (`/tmp/acl-backup.json` des Laufs erneut
  `POST`; zusätzlich manueller Konsolen-Rollback im Tailscale-Admin).
- **IaC4-Seite:** `git revert` des Modell-/Skript-/Doku-PR stellt den Vorzustand
  wieder her.
- **ha-repo-Seite:** der eingefrorene Workflow/das Skript bleibt bis Stufe 3
  erhalten und kann per `git` reaktiviert werden — **nur nach erneutem Owner-Go**.

## Grenz-Hinweis für das ha-repo

Der Textbaustein für das ha-repo liegt in
[ha-repo-acl-boundary-note.md](ha-repo-acl-boundary-note.md) (dort separat
einzubringen, z. B. `docs/reference/tailscale-acl.md` + Header-Hinweis im
Apply-Workflow + `AGENTS.md`/`TODO.md`).

## Offene Lücken (separat als IaC4-Issues, nicht Teil dieser Migration)

1. IaC4-Tailscale-API-Key erneuern (V1) — Voraussetzung für echten Access.
2. Raw-huJSON-Export + SHA256 der Live-Policy als versionierter Ist-Stand (V2).
3. Tag→Node-Inventar (ha1/ha3, vps-dev/vps-prod) für den Blast-Radius.
4. Doku-Widerspruch „Regel 6 live?" per Live-GET klären.
5. `--accept-routes` in IaC verankern (separater Task, nicht hier).
