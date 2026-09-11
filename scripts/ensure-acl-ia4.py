#!/usr/bin/env python3
"""Kompatibilitäts-Shim (DEPRECATED) → scripts/ensure-acl.py.

Bisheriger Aufrufer: .github/workflows/01-tailscale-terraform.yml
(`python3 scripts/ensure-acl-ia4.py`). Bis 2026-09-11 enthielt dieses Skript die
byte-exakten Anker-Einfügungen für `tag:ia4`.

Seit der Konsolidierung (Owner-Entscheid 2026-09-11: „Tailscale-ACL ist
Infrastruktur und gehört zu IaC4") gibt es EINEN semantischen Mechanismus
(`scripts/ensure-acl.py`) mit der Single Source of Truth
`acl/tailscale-acl.hujson`. Dieser Shim hält den alten Aufrufer funktionsfähig
(Selektion der `iac4`-Gruppe, apply) und wird nach Umstellung des Aufrufers im
Rahmen des Schnitts (Runbook M4) entfernt.

Nutzung (unverändert für Aufrufer): env TS_TAILNET + (TS_TOKEN|TS_API_KEY).
    python3 scripts/ensure-acl-ia4.py            # apply iac4 (wie bisher)
    python3 scripts/ensure-acl-ia4.py --dry-run  # Analyse, kein POST
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "ensure-acl.py")

args = [sys.executable, TARGET, "--rule", "iac4", "--confirm", "APPLY-ACL"] + sys.argv[1:]
sys.exit(subprocess.call(args))
