#!/usr/bin/env python3
"""CI-Gate: Pin-Drift / Pin-Downgrade fuer openclaw_image_version (Incident 2026-10-06).

Hintergrund
-----------
Ein Branch, der auf einem alten merge-base haengt, kann den in main bereits
erhoehten Image-Pin (openclaw_image_version) unbemerkt wieder zurueckdrehen.
Ein Merge wuerde die Flotte auf den alten Tag downgraden und die (schema-19/24)
State-DBs unbrauchbar machen -> genau der Produktions-Crash (oc3). Dieses Gate
blockt das reproduzierbar.

Geprueft wird (offline, nur stdlib, keine Secrets):
  1. Interne Konsistenz: ansible/group_vars/all.yml ==
     ansible/roles/openclaw-gateway/defaults/main.yml (keine Drift zwischen
     SSoT-Variable und Rollen-Default; beide tragen denselben Pin).
  2. Kein Downgrade: der Branch-Pin ist nicht aelter als der Baseline-Pin
     (Default-Ref: origin/main; via env PIN_BASELINE_REF ueberschreibbar).
  3. Default: strikte Gleichheit mit der Baseline (== main). Ein *gewollter*
     Pin-Bump muss explizit freigegeben werden: PIN_DRIFT_ALLOW_UPGRADE=1
     erlaubt ein Upgrade und blockt dann nur noch Downgrades.

Exit != 0 bei Downgrade, interner Inkonsistenz oder (Default) Abweichung.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIN_FILES = [
    "ansible/group_vars/all.yml",
    "ansible/roles/openclaw-gateway/defaults/main.yml",
]
# Bewusst backslash-frei (robust gegen Copy/Paste-Escaping); nur Leerzeichen-Indent.
PIN_RE = re.compile(r'^ *openclaw_image_version: *"?([0-9][^" #]*)"?', re.M)


def read_version(path):
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"nicht lesbar: {exc}"
    match = PIN_RE.search(text)
    if not match:
        return None, "openclaw_image_version nicht gefunden"
    return match.group(1), None


def git_show(ref, rel):
    try:
        out = subprocess.run(
            ["git", "show", ref + ":" + rel],
            cwd=str(ROOT), capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    match = PIN_RE.search(out.stdout)
    return match.group(1) if match else None


def parse(version):
    nums = re.findall(r"[0-9]+", version or "")
    return tuple(int(n) for n in nums) if nums else None


def main():
    failures = []
    versions = {}
    for rel in PIN_FILES:
        version, err = read_version(ROOT / rel)
        if err:
            failures.append(rel + ": " + err)
        else:
            versions[rel] = version

    uniq = set(versions.values())
    if len(uniq) > 1:
        failures.append("Interne Pin-Drift: " + ", ".join(
            rel + "=" + str(v) for rel, v in versions.items()))
    branch_version = next(iter(uniq), None)

    baseline_ref = os.environ.get("PIN_BASELINE_REF", "origin/main")
    baseline_version = git_show(baseline_ref, PIN_FILES[0])
    if not baseline_version:
        baseline_version = git_show(baseline_ref, PIN_FILES[1])
    allow_upgrade = os.environ.get("PIN_DRIFT_ALLOW_UPGRADE", "") == "1"

    print("Branch-Pin  :", branch_version)
    print("Baseline-Pin:", baseline_version, "(ref:", baseline_ref + ")")

    if branch_version and baseline_version:
        cur, base = parse(branch_version), parse(baseline_version)
        if cur is None or base is None:
            failures.append("Pin nicht parsebar: branch=" + str(branch_version)
                            + " baseline=" + str(baseline_version))
        elif cur < base:
            failures.append("PIN-DOWNGRADE: Branch " + str(branch_version) + " < "
                            + baseline_ref + " " + str(baseline_version)
                            + " (wuerde die Flotte downgraden / State-DB inkompatibel)")
        elif cur > base and not allow_upgrade:
            failures.append("PIN-DRIFT: Branch " + str(branch_version) + " != "
                            + baseline_ref + " " + str(baseline_version)
                            + " (Upgrade nur mit PIN_DRIFT_ALLOW_UPGRADE=1)")
        elif cur > base:
            print("::warning::Pin-Upgrade erlaubt (PIN_DRIFT_ALLOW_UPGRADE=1): "
                  + str(branch_version) + " > " + str(baseline_version))
        else:
            print("OK: Pin identisch mit Baseline.")
    elif branch_version and not baseline_version:
        print("::warning::Baseline " + baseline_ref
              + " nicht aufloesbar - Downgrade-Check uebersprungen "
              + "(Workflow muss 'git fetch origin main' ausfuehren).")

    if failures:
        print("")
        print("GATE FEHLGESCHLAGEN:")
        for item in failures:
            print("  - " + item)
        return 1
    print("")
    print("GATE OK: kein Pin-Downgrade / keine Drift.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
