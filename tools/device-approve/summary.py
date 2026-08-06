#!/usr/bin/env python3
"""Markdown-Summary-Generator aus einheitlichem JSON-Schema (Minor #7).

Mapping:
  scanned          → "Discovery-Scan"
  filters_applied  → "Filter"
  found            → Tabelle mit Instanz/Typ/VPS
  status           → Ueberschrift-Status (✅ Gefunden / ❌ Fehler / ❌ Nicht gefunden)

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
from typing import Optional


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
        "found": f"## ✅ {label}-Freigabe — Gefunden (Discovery)",
        "not_found": f"## ❌ {label}-Freigabe — Kein Treffer",
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
        "found": "✅ Gefunden",
        "not_found": "❌ Nicht gefunden",
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
