#!/usr/bin/env python3
"""SSoT-Parser: Instanz-Mapping aus ansible/group_vars/vps-*.yml (Design 05, Major #7).

Liest per dynamischem Globbing alle vps-*.yml-Dateien, filtert enabled Instanzen
und gibt je Instanz eine Zeile ``name|target`` aus (target = env der VPS-Datei;
Zukunft M5: target als Instanz-Attribut, ueberschreibt Datei-level env).

Wird vom Workflow 06-device-approve-telegram.yml UND von den Unit-Tests
(tests/device-approve/) genutzt – eine Implementierung, keine Duplikate.

CLI:  python3 sot_parser.py [root] [glob]
Beispiel: python3 sot_parser.py . 'ansible/group_vars/vps-*.yml'
"""

from __future__ import annotations

import glob
import os
import sys
from typing import List, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover - Workflow installiert pyyaml vorab
    sys.stderr.write("Fehler: PyYAML nicht installiert (python3 -m pip install pyyaml)\n")
    sys.exit(2)

DEFAULT_GLOB = "ansible/group_vars/vps-*.yml"


def iter_enabled_instances(
    root: str = ".", pattern: str = DEFAULT_GLOB
) -> List[Tuple[str, str]]:
    """Liefert [(name, target)] aller enabled Instanzen ueber alle VPS-Dateien."""
    result: List[Tuple[str, str]] = []
    for path in sorted(glob.glob(os.path.join(root, pattern))):
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        file_target = data.get("env", "unknown")
        for inst in data.get("openclaw_instances", []) or []:
            if not inst.get("enabled", False):
                continue
            name = inst.get("name")
            if not name:
                continue
            # M5: target als Instanz-Attribut ueberschreibt spaeter Datei-level env
            target = inst.get("target", file_target)
            result.append((name, str(target)))
    return result


def main(argv: List[str] | None = None) -> int:
    args = list(sys.argv[1:]) if argv is None else argv
    root = args[0] if len(args) > 0 else "."
    pattern = args[1] if len(args) > 1 else DEFAULT_GLOB
    for name, target in iter_enabled_instances(root, pattern):
        print(f"{name}|{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
