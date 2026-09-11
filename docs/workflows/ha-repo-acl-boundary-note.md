# Grenz-Hinweis für das ha-repo (Textbaustein)

> **Zweck:** Fertiger Textbaustein, der im **ha-repo**
> (`HaraldKiessling/home-assistant-agent`) **separat** einzubringen ist. Er
> dokumentiert dort, dass die Tailscale-ACL künftig in **IaC4** verwaltet wird
> und der HA-eigene ACL-Pfad nach dem Übergang **gesperrt** wird.
> Dieses Dokument selbst liegt in IaC4 (Quelle der Migration).

## Vorschlag Ort im ha-repo

- **Primär:** neue Seite `docs/reference/tailscale-acl.md`.
- **Sekundär:** Hinweis-Block im Header von
  `.github/workflows/00-acl-apply-ha.yml` + Eintrag in `AGENTS.md` (Harte
  Regeln) + `TODO.md` (F14 als superseded markieren).

## Textbaustein `docs/reference/tailscale-acl.md`

```markdown
# Tailscale-ACL — Verwaltung in IaC4

> **Stand:** 2026-09-11 (Owner-Entscheide 07:27 UTC + F1–F6) · ersetzt F14 (2026-09-06)

## Grundsatz

Die **Tailscale-ACL ist Infrastruktur** und wird **zentral im IaC4-Repo**
verwaltet (eine Regelquelle für `tag:ia4` **und** `tag:ha` inkl. `tag:ha-ci`).

Dieses HA-Repo enthält **keinen eigenen ACL-Schreibpfad** mehr.

## Was das für dieses Repo bedeutet

- Der Workflow **`00-acl-apply-ha.yml`** und das Skript
  **`scripts/ensure-acl-ha.py`** werden nach der Migration **nicht mehr
  verwendet** (gesperrt → eingefroren → entfernt).
- ACL-Änderungen (z. B. Phase-2-Regeln `oc → ha1/ha3`, die Energie-Lese-Regel
  Kostal/KSEM) werden **ausschließlich über das IaC4-Repo** beantragt und dort
  reviewed/freigegeben.
- Jede ACL-Änderung bleibt an die **Owner-Governance** gebunden:
  Wirkungs-Analyse + Review (Autor ≠ Reviewer) + Owner-Go. Kein automatischer
  Apply.

## Übergangsregelung (bis der Schnitt abgeschlossen ist)

1. Der Übergang ist **IaC4-first**: ACL-Änderungen laufen bevorzugt über IaC4.
   Der HA-eigene Weg bleibt **bis zur Sperre als Rückfallweg offen**.
2. Nach dem Schnitt wird der HA-ACL-Weg **gesperrt**: `00-acl-apply-ha.yml`
   wird **deaktiviert** (Trigger entfernt / `if: false`) — **nicht gelöscht** —
   inkl. Kopfhinweis; die Reaktivierung ist **nur nach erneutem Owner-Go** zulässig.
3. Der IaC4-API-Key muss gültig sein (der alte Key war seit 31.07. ungültig).
4. Rollback-Referenz: `scripts/ensure-acl-ha.py` bleibt bis zum Entfernen als
   historischer Beleg erhalten, wird aber nicht mehr ausgeführt.

## Verwandtes

- IaC4: `acl/tailscale-acl.hujson` (SSoT), `scripts/ensure-acl.py`,
  `00-acl-apply.yml` (dry_run/confirm), `docs/workflows/acl-migration-runbook.md`.
- Governance: Owner-Regel Tailscale-ACL (IaC4 `AGENTS.md`,
  `.roo/rules/tailscale-acl.mdc`).
```

## Header-Hinweis für `00-acl-apply-ha.yml` (F6=(a))

```yaml
# =============================================================================
# ⛔ GESPERRT / DEPRECATED (2026-09-11, Owner-Entscheid F6):
#    Tailscale-ACL ist Infrastruktur und wird zentral im IaC4-Repo verwaltet
#    (eine Regelquelle für tag:ia4 UND tag:ha). Dieser Workflow wird nach der
#    Migration NICHT mehr verwendet – DEAKTIVIERT (Trigger entfernt / if:false),
#    NICHT gelöscht (Rückfallweg bis zur endgültigen Stilllegung).
#    Reaktivierung nur nach erneutem Owner-Go.
#    Details: docs/reference/tailscale-acl.md
# =============================================================================
```

## Zusatz in `AGENTS.md` (Harte Regeln)

```markdown
| **Tailscale-ACL wird in IaC4 verwaltet** (Infrastruktur, Owner-Entscheid 2026-09-11, ersetzt F14) — kein ACL-Apply aus diesem Repo; Änderungen über IaC4 beantragen (`docs/reference/tailscale-acl.md`) | Alle |
```

## Korrektur in `TODO.md` (F14)

F14-Zeile (Issue #24) ergänzen: **„superseded durch Owner-Entscheid 2026-09-11:
ACL-Konsolidierung nach IaC4."** Issue #7 (ACL-Konsolen-Teil) auf das IaC4-Repo
verweisen.
