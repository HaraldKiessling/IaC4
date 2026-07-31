#!/usr/bin/env python3
"""Idempotente, rein additive Erweiterung der geteilten Tailscale-ACL um IaC4-Regeln (tag:ia4).

Prinzip (100%-Sicherheit):
- NUR additive Einfügungen an exakten Ankern; bestehende Zeilen werden NIE verändert
- Idempotenz: ist "tag:ia4" bereits enthalten -> no-op (exit 0)
- Backup der aktuellen Policy vor jeder Änderung (Datei + Log)
- Verifikation nach POST: ia4-Einträge vorhanden, ia3/ha-Bestand unverändert (Zähler),
  Additivitäts-Diff (keine entfernten/geänderten Zeilen)
- Bei Verifikationsfehler: automatisches Rollback (POST des Backups) + exit 1

Nutzung (Workflow 01): env TS_TAILNET + TS_API_KEY (oder TS_TOKEN) gesetzt.
"""
import json
import os
import sys
import urllib.request

API = "https://api.tailscale.com/api/v2/tailnet"
TAILNET = os.environ.get("TS_TAILNET", "")
TOKEN = os.environ.get("TS_TOKEN", "") or os.environ.get("TS_API_KEY", "")
if not TAILNET or not TOKEN:
    print("❌ TS_TAILNET + (TS_TOKEN|TS_API_KEY) erforderlich (env)")
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {TOKEN}"}
URL = f"{API}/{TAILNET}/acl"


def api(method, data=None):
    req = urllib.request.Request(URL, method=method, headers=HEADERS, data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def insert_once(pol, anchor, addition, label):
    n = pol.count(anchor)
    if n != 1:
        print(f"❌ {label}: Anker {n}x (erwartet 1) – Abbruch OHNE Änderung")
        sys.exit(1)
    return pol.replace(anchor, anchor + addition, 1), label


def main():
    code, pol = api("GET")
    if code != 200:
        print(f"❌ GET /acl: HTTP {code}\n{pol[:300]}")
        sys.exit(1)

    if '"tag:ia4"' in pol:
        print("✅ IaC4-Regeln (tag:ia4) bereits enthalten – no-op (idempotent)")
        return 0

    # Backup
    with open("/tmp/acl-backup.json", "w", encoding="utf-8") as f:
        f.write(pol)
    print("💾 Backup: /tmp/acl-backup.json")

    # Additive Einfügungen (exakte Anker)
    pol, _ = insert_once(
        pol,
        '\t\t"tag:ia3": ["autogroup:admin"],\n',
        '\t\t"tag:ia4": ["autogroup:admin"],\n',
        "tagOwners tag:ia4",
    )
    acl_anchor = (
        '\t\t{\n'
        '\t\t\t"action": "accept",\n'
        '\t\t\t"src":    ["autogroup:admin", "autogroup:member", "tag:ci"],\n'
        '\t\t\t"dst":    ["tag:ia3:*"],\n'
        '\t\t},'
    )
    acl_add = (
        '\n'
        '\t\t// =======================================================\n'
        '\t\t// IaC4 (Option A): CI-Zugriff auf ia4 + ia4 intern\n'
        '\t\t// =======================================================\n'
        '\t\t{\n'
        '\t\t\t"action": "accept",\n'
        '\t\t\t"src":    ["autogroup:admin", "autogroup:member", "tag:ci"],\n'
        '\t\t\t"dst":    ["tag:ia4:*"],\n'
        '\t\t},\n'
        '\t\t{\n'
        '\t\t\t"action": "accept",\n'
        '\t\t\t"src":    ["tag:ia4"],\n'
        '\t\t\t"dst":    ["tag:ia4:*"],\n'
        '\t\t},'
    )
    pol, _ = insert_once(pol, acl_anchor, acl_add, "acls ci→ia4 + ia4→ia4")
    ssh_anchor = '\t\t\t"users":  ["deploy-user", "root", "ubuntu"],\n\t\t},'
    ssh_add = (
        '\n'
        '\t\t{\n'
        '\t\t\t"action": "accept",\n'
        '\t\t\t"src":    ["autogroup:admin", "autogroup:member", "tag:ci"],\n'
        '\t\t\t"dst":    ["tag:ia4"],\n'
        '\t\t\t"users":  ["deploy-user", "root", "ubuntu"],\n'
        '\t\t},'
    )
    pol, _ = insert_once(pol, ssh_anchor, ssh_add, "ssh ci→ia4")

    code, resp = api("POST", pol.encode("utf-8"))
    if code != 200:
        print(f"❌ POST /acl: HTTP {code}\n{resp[:300]}")
        print("↩️ Rollback: POST des Backups…")
        api("POST", open("/tmp/acl-backup.json", encoding="utf-8").read().encode("utf-8"))
        sys.exit(1)

    # Verifikation
    code, verify = api("GET")
    if code != 200:
        print(f"❌ GET (Verify): HTTP {code} – Rollback nötig")
        api("POST", open("/tmp/acl-backup.json", encoding="utf-8").read().encode("utf-8"))
        sys.exit(1)
    with open("/tmp/acl-backup.json", encoding="utf-8") as f:
        backup = f.read()
    checks = {
        "tagOwners tag:ia4": '"tag:ia4": ["autogroup:admin"]' in verify,
        "acl ci→ia4": '"dst":    ["tag:ia4:*"]' in verify,
        "acl ia4→ia4": '"src":    ["tag:ia4"],' in verify,
        "ssh ci→ia4": '"dst":    ["tag:ia4"],' in verify,
        "ia3-Bestand unverändert": backup.count('"tag:ia3"') == verify.count('"tag:ia3"'),
        "ha-Bestand unverändert": backup.count('"tag:ha"') == verify.count('"tag:ha"'),
    }
    # Additivitäts-Diff (normalisiert): keine Zeile aus dem Backup darf fehlen/geändert sein
    norm = lambda t: sorted(l.strip() for l in t.splitlines() if l.strip() and not l.strip().startswith("//"))
    missing = set(norm(backup)) - set(norm(verify))
    checks["Additivität (keine bestehende Zeile entfernt)"] = len(missing) == 0
    if missing:
        print("  Fehlende/geänderte Zeilen:", sorted(missing)[:10])

    ok = all(checks.values())
    for name, result in checks.items():
        print(("✅" if result else "❌") + f" {name}")
    if not ok:
        print("↩️ Rollback: POST des Backups…")
        api("POST", open("/tmp/acl-backup.json", encoding="utf-8").read().encode("utf-8"))
        sys.exit(1)
    print("🎉 ACL-Erweiterung bestanden (additiv, verifiziert)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
