#!/usr/bin/env python3
"""Markdown-Summary-Generator aus einheitlichem JSON-Schema (Minor #7).

Mapping:
  scanned          → "Discovery-Scan"
  filters_applied  → "Filter"
  found            → Tabelle mit Instanz/Typ/VPS
  status           → Ueberschrift-Status (✅ Gefunden / ❌ Fehler / ❌ Nicht gefunden)

v3.1 (Listen-Modus): list_result_to_markdown() rendert das Listen-Schema
({"status": "list_ok", "entries": [...], "scanned": [...],
"unreachable": [...], "filters_applied": {...}}) als Job-Summary-Tabelle.
Konventionen (Review R03/R04): Sortierung createdAtMs DESC (Sekundaerschluessel
stabil), platform "" → "—" in der Tabelle (JSON = Wahrheit).
v3.3 (2026-08-07, Owner-Auftrag „GUID soll in der Liste stehen"):
Request-ID-Spalte – `entries[].requestId` (UUID-36, approve/reject-ID) wird
VOLL gerendert (bewusste Ausnahme zur ID-Kuerzung); Telegram ohne
requestId-Feld → "—" (Darstellung, JSON bleibt "").
v3.4 (2026-08-07): Remove-Modus – status "removed" → Header "✅ Device-
Remove — Erfolgreich" / Status-Label "✅ Entfernt (removed)".
v3.6 (2026-08-08): Instanz-Remove (scope=instance) –
instance_remove_to_markdown() rendert removed_count, per_instance-
Aufschluesselung und failed-Details (Owner-Entscheidung: Teilerfolg Exit 1,
Fehlgeschlagene im Summary listen); status "partial" → Header "⚠️ … —
Teilweise entfernt".

v2.2: Status-Ueberschrift typ-spezifisch – found[0].type == "telegram" →
"Telegram-Pairing-Freigabe", sonst "Device-Freigabe" (Δ7, Design §3e).

Nutzung:
  - CLI: cat result.json | python3 summary.py   # liest stdin, schreibt $GITHUB_STEP_SUMMARY
  - Import: from summary import result_to_markdown
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional


# Listen-Modus: Typ-Label mit Emoji (Design §5.2)
_LIST_TYPE_LABELS = {"telegram": "✈️ Telegram", "device": "📱 Device"}


def _fmt_created(created_at_ms: int) -> str:
    """createdAtMs (Millisekunden) → lesbares UTC-Datum (O2).

    0 / fehlend → "—" (Darstellung, kein Datenpunkt).
    """
    if not created_at_ms:
        return "—"
    return datetime.fromtimestamp(
        created_at_ms / 1000, tz=timezone.utc
    ).strftime("%Y-%m-%d %H:%M")


def _fmt_list_id(entry_id: str) -> str:
    """ID in der Tabelle: lang (>24 Zeichen, v.a. Device-UUIDs) gekuerzt.

    Darstellung nur – die Voll-ID steht im JSON-Output (Run-Log).
    """
    if len(entry_id) > 24:
        return f"`{entry_id[:24]}…`"
    return f"`{entry_id}`"


def _fmt_request_id(request_id: str) -> str:
    """Request-ID (UUID-36) in der Tabelle: VOLL (v3.3, Owner-Auftrag „GUID
    soll in der Liste stehen" – die requestId ist die approve/reject-ID, die
    Antwort auf „bei welchem OC liegt welche GUID" soll direkt ablesbar
    sein; bewusste Ausnahme zur ID-Kuerzung oben). Leer (Telegram ohne
    requestId-Feld) → "—" (Darstellung, JSON bleibt "").
    """
    if not request_id:
        return "—"
    return f"`{request_id}`"



def _found_type(result: dict) -> str:
    found = result.get("found") or []
    if found:
        return found[0].get("type", "unknown")
    return "unknown"


def _label_for_type(found_type: str) -> str:
    return "Telegram-Pairing" if found_type == "telegram" else "Device"


def status_header(status: str, result: Optional[dict] = None) -> str:
    """Status-Emoji + Ueberschrift (typ-spezifisch, v2.2)."""
    result = result or {}
    label = _label_for_type(_found_type(result))
    mapping = {
        "approved": f"## ✅ {label}-Freigabe — Erfolgreich",
        "rejected": f"## ✅ {label}-Reject — Erfolgreich",  # v3.2: Reject-Modus
        "removed": f"## ✅ {label}-Remove — Erfolgreich",  # v3.4: Remove-Modus
        "partial": f"## ⚠️ {label}-Remove — Teilweise entfernt",  # v3.6: Instanz-Remove Teilerfolg
        "found": f"## ✅ {label}-Freigabe — Gefunden (Discovery)",
        # not_found ist kein Fehler (Owner-Vereinbarung 15:06, gruener Run)
        "not_found": f"## 🔎 {label}-Freigabe — Kein Treffer",
        "error": f"## ❌ {label}-Freigabe — Fehler",
    }
    return mapping.get(status, f"## ℹ️ {label}-Freigabe — {status}")


def result_to_markdown(result: dict) -> str:
    """Einheitliches JSON-Result → Markdown (Minor #7)."""
    status = result.get("status", "unknown")
    rid = result.get("id", "")
    found = result.get("found") or []
    scanned = result.get("scanned") or []
    filters = result.get("filters_applied") or {}

    lines = [status_header(status, result), ""]
    lines.append("| Feld | Wert |")
    lines.append("|------|------|")
    lines.append(f"| **Request-ID** | `{rid}` |")

    # Status-Zeile
    status_label = {
        "approved": "✅ Freigegeben",
        "rejected": "✅ Abgelehnt (rejected)",  # v3.2: Reject-Modus
        "removed": "✅ Entfernt (removed)",  # v3.4: Remove-Modus
        "partial": "⚠️ Teilweise entfernt (partial)",  # v3.6: Instanz-Remove
        "found": "✅ Gefunden",
        "not_found": "🔎 Nicht gefunden",
        "error": "❌ Fehler",
    }.get(status, status)
    lines.append(f"| **Status** | {status_label} |")

    # Found-Eintraege
    if found:
        for fentry in found:
            inst_str = f"{fentry.get('target', '')}/{fentry.get('instance', '')}"
            lines.append(f"| **Instanz** | `{inst_str}` |")
            lines.append(f"| **Typ** | `{fentry.get('type', 'unknown')}` |")
            if fentry.get("vps_ip"):
                lines.append(f"| **VPS** | `{fentry['vps_ip']}` |")

    lines.append("")

    # Discovery-Scan (Minor #5: Count integriert)
    if scanned:
        count = len(scanned)
        scan_list = ", ".join(f"`{s}`" for s in sorted(set(scanned)))
        lines.append(f"**Discovery-Scan:** {count} Instanz(en) geprueft — {scan_list}")

    # Filter
    if filters:
        filter_parts = [f"{k}={v}" for k, v in filters.items()]
        lines.append(f"**Filter:** {' | '.join(filter_parts)}")

    lines.append("")
    return "\n".join(lines)


def _fmt_device_id(device_id: str) -> str:
    """deviceId in der Tabelle: lang (>24 Zeichen, 64-hex) gekuerzt.

    Darstellung nur – die Voll-ID steht im JSON-Output (Run-Log).
    """
    if len(device_id) > 24:
        return f"`{device_id[:24]}…`"
    return f"`{device_id}`"


def instance_remove_to_markdown(result: dict) -> str:
    """Instanz-Remove-Ergebnis (v3.6, scope=instance) → Markdown (Job-Summary).

    Erwartetes Eingabe-Schema (build_instance_remove_result_json):
    {
      "status": "removed|partial|error|not_found",
      "scope": "instance",
      "removed_count": n,
      "per_instance": [{"instance": "oc1", "removed": n, "failed": n}],
      "failed": [{"instance": "oc1", "device_id": "…", "output": "…"}],
      "limit_hit": false,
      "scanned": ["prod/oc1", ...],
      "unreachable": [...],
      "filters_applied": {...}
    }
    Owner-Entscheidungen (2026-08-08): Teilerfolg → Exit 1, Fehlgeschlagene
    werden VOLL im Summary gelistet (deviceId gekuerzt in der Tabelle, Voll-ID
    im JSON).
    """
    status = result.get("status", "unknown")
    removed_count = result.get("removed_count", 0)
    per_instance = result.get("per_instance") or []
    failed = result.get("failed") or []
    scanned = result.get("scanned") or []
    unreachable = result.get("unreachable") or []
    filters = result.get("filters_applied") or {}
    limit_hit = result.get("limit_hit", False)

    header = {
        "removed": "## 🗑️ Device-Remove (Instanz) — Alle entfernt",
        "partial": "## ⚠️ Device-Remove (Instanz) — Teilweise entfernt",
        "error": "## ❌ Device-Remove (Instanz) — Fehler",
        "not_found": "## 🔎 Device-Remove (Instanz) — Keine gepaarten Geraete",
    }.get(status, f"## ℹ️ Device-Remove (Instanz) — {status}")
    lines = [header, ""]

    lines.append("| Feld | Wert |")
    lines.append("|------|------|")
    lines.append(f"| **Scope** | `instance` |")
    lines.append(f"| **Entfernt** | {removed_count} |")
    lines.append(f"| **Fehlgeschlagen** | {len(failed)} |")
    if limit_hit:
        lines.append("| **Limit** | ⛔ Sicherheits-Limit (max 50) erreicht/ueberschritten |")
    lines.append("")

    if per_instance:
        lines.append("**Pro Instanz:**")
        lines.append("")
        lines.append("| Instanz | Entfernt | Fehlgeschlagen |")
        lines.append("|---------|----------|----------------|")
        for entry in per_instance:
            lines.append(
                f"| {entry.get('instance', '?')} | {entry.get('removed', 0)} "
                f"| {entry.get('failed', 0)} |"
            )
        lines.append("")

    if failed:
        lines.append("**Fehlgeschlagene Geraete:**")
        lines.append("")
        lines.append("| Instanz | Device-ID | Output |")
        lines.append("|---------|-----------|--------|")
        for entry in failed:
            output = (entry.get("output") or "").replace("|", "\\|")[:200]
            lines.append(
                f"| {entry.get('instance', '?')} "
                f"| {_fmt_device_id(entry.get('device_id', ''))} "
                f"| `{output}` |"
            )
        lines.append("")

    if scanned:
        count = len(scanned)
        scan_list = ", ".join(f"`{s}`" for s in sorted(set(scanned)))
        lines.append(f"**Discovery-Scan:** {count} Instanz(en) geprueft — {scan_list}")
    if unreachable:
        lines.append(f"**Nicht erreichbar:** {', '.join(unreachable)}")
    if filters:
        filter_parts = [f"{k}={v}" for k, v in filters.items()]
        lines.append(f"**Filter:** {' | '.join(filter_parts)}")

    lines.append("")
    return "\n".join(lines)


def list_result_to_markdown(result: dict) -> str:
    """Listen-Ergebnis → Markdown-Tabelle (Job-Summary, Listen-Modus v3.1).

    Erwartetes Eingabe-Schema (Design §11, build_list_result_json):
    {
      "status": "list_ok",
      "entries": [{"instance": "oc1", "target": "dev", "type": "telegram",
                    "id": "QVDCXJEM", "requestId": "", "platform": "",
                    "createdAtMs": …, "vps_ip": …}],
      "scanned": ["dev/oc1", ...],
      "unreachable": ["vps-prod"],
      "filters_applied": {"type": "both", "target": "both", "instance": "all"}
    }
    v3.3: requestId (UUID-36) = approve/reject-ID des pending Eintrags
    (device; Telegram ohne Feld → "", Tabelle rendert "—").

    Darstellungs-Konventionen (Review R03/R04, verbindlich):
    - R03 Sortierung: createdAtMs DESC (neueste zuerst); Sekundaerschluessel
      (target, instance, type, id) – deterministisch und stabil.
    - R04 platform: JSON "" ist die Wahrheit (Telegram hat kein platform-Feld,
      O7); die Tabelle rendert "" → "—" (Darstellung, JSON bleibt "").
    - v3.3 Request-ID-Spalte: `requestId` (UUID-36) der approve/reject-ID wird
      VOLL gerendert (Owner-Auftrag „GUID in der Liste", bewusste Ausnahme zur
      ID-Kuerzung); Telegram ohne requestId-Feld → "—". Voll-ID immer im JSON.
    - Erstellt: UTC (YYYY-MM-DD HH:MM, O2); fehlendes createdAtMs → "—".
    - Leere Liste: "Keine offenen Requests" + Platzhalterzeile – Exit 0 bleibt
      gruen (Owner-Vereinbarung: leere Liste ≠ Fehler).
    - Lange IDs (>24 Zeichen) werden in der Tabelle gekuerzt (Voll-ID im JSON).
    """
    entries = sorted(
        result.get("entries") or [],
        # R03: neueste zuerst; Sekundaerschluessel stabil
        key=lambda e: (
            -(e.get("createdAtMs") or 0),
            e.get("target", ""),
            e.get("instance", ""),
            e.get("type", ""),
            e.get("id", ""),
        ),
    )
    scanned = result.get("scanned") or []
    unreachable = result.get("unreachable") or []
    filters = result.get("filters_applied") or {}

    if entries:
        lines = ["## 📋 Pending-Requests — Übersicht", ""]
    else:
        lines = ["## 📋 Pending-Requests — Keine offenen Requests", ""]

    # v3.3: Request-ID-Spalte (UUID-36, voll) zwischen Typ und ID.
    lines.append("| # | Instanz | Typ | Request-ID | ID | Platform | Erstellt |")
    lines.append("|---|---------|-----|------------|----|----------|----------|")
    if not entries:
        lines.append("| — | — | — | — | — | — | — |")
    for i, e in enumerate(entries, start=1):
        inst_str = f"{e.get('target', '')}/{e.get('instance', '')}"
        typ_label = _LIST_TYPE_LABELS.get(e.get("type", ""), e.get("type", ""))
        platform = e.get("platform", "") or "—"  # R04: "" → "—" (Darstellung)
        lines.append(
            f"| {i} | {inst_str} | {typ_label} | {_fmt_request_id(e.get('requestId', ''))} "
            f"| {_fmt_list_id(e.get('id', ''))} "
            f"| {platform} | {_fmt_created(e.get('createdAtMs', 0))} |"
        )
    lines.append("")

    if scanned:
        count = len(scanned)
        scan_list = ", ".join(f"`{s}`" for s in sorted(set(scanned)))
        lines.append(f"**Discovery-Scan:** {count} Instanz(en) geprüft — {scan_list}")
    if unreachable:
        lines.append(f"**Nicht erreichbar:** {', '.join(unreachable)}")
    else:
        lines.append("**Nicht erreichbar:** keine")
    if filters:
        filter_parts = [f"{k}={v}" for k, v in filters.items()]
        lines.append(f"**Filter:** {' | '.join(filter_parts)}")

    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[list] = None) -> int:
    """CLI: liest JSON von stdin, schreibt Markdown nach $GITHUB_STEP_SUMMARY."""
    raw = sys.stdin.read().strip()
    if not raw:
        print("⚠️  Keine JSON-Eingabe auf stdin", file=sys.stderr)
        return 1

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"❌ JSON-Parse-Fehler: {exc}", file=sys.stderr)
        return 2

    md = result_to_markdown(result)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_path:
        # Major #3 / Δ7: File-Open, KEIN >>-Redirect
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(md)
            fh.write("\n")
    else:
        # Lokaler Fallback: Markdown auf stdout
        print(md)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
