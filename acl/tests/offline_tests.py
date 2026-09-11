#!/usr/bin/env python3
"""Offline-Nachweis für die ACL-Single-Source-Migration (KEIN Netz, kein POST).

Prüft:
 1. SSoT-Datei parsebar + Modell-Gates (Tag-Referenzen, Marker).
 2. Null-Diff des Modells gegen den rekonstruierten Live-Snapshot (acl/tests/fixtures).
 3. Rein additive Einfügung der iac4-Gruppe in einen Snapshot OHNE iac4
    (0 Entfernungen, count==1-Gate, semantische Additivität).
 4. Negativ-Test: Erkennung einer entfernten Bestandsregel.
 5. Export-Modus liest offline (--file) und schreibt huJSON + SHA256.

Aufruf: python3 acl/tests/offline_tests.py
"""
import importlib.util
import json
import os
import sys
import tempfile
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL = os.path.join(ROOT, "acl", "tailscale-acl.hujson")
FIXTURE = os.path.join(ROOT, "acl", "tests", "fixtures", "live-reconstructed.hujson")

_failures = []


def check(name, cond, detail=""):
    mark = "✅" if cond else "❌"
    print("%s %s%s" % (mark, name, (" – " + detail) if detail and not cond else ""))
    if not cond:
        _failures.append(name)


def load_mod():
    spec = importlib.util.spec_from_file_location(
        "ensure_acl", os.path.join(ROOT, "scripts", "ensure-acl.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    m = load_mod()

    # 1) SSoT-Gates
    model, _ = m.parse_model(MODEL)
    gates = m.model_gates(model)
    check("SSoT-Gates (Tag-Referenzen, Marker)", gates == [], "; ".join(gates))
    n_entries = sum(len(model[s]) for s in m.SECTION_ORDER)
    print("   Modell: %d Einträge (%s)" % (
        n_entries, ", ".join("%s=%d" % (s, len(model[s])) for s in m.SECTION_ORDER)))

    # 2) Null-Diff gegen rekonstruierten Live-Snapshot
    with open(FIXTURE, encoding="utf-8") as f:
        live_text = f.read()
    live = m.parse_live(live_text)
    rep = m.diff_model_vs_live(model, live)
    check("Null-Diff Modell ↔ rekonstruierter Live-Snapshot", m.null_diff_ok(rep),
          "missing=%d changed=%d foreign=%d" % (
              len(rep["missing"]), len(rep["changed"]), len(rep["foreign"])))
    check("Pending-Regel 7 (Energie) ist im Snapshot nicht live",
          any(s == "acls" for s, _o, _msg in rep["pending_missing"]))
    check("Pending-Regel 6 (MQTT) als live erkannt (streitig → pending_live)",
          any(s == "acls" for s, _o, _msg in rep["pending_live"]))

    # 3) Additive Einfügung der iac4-Gruppe in Snapshot OHNE iac4
    raw = json.loads(live_text)
    del raw["tagOwners"]["tag:ia4"]
    raw["acls"] = [r for r in raw["acls"] if r.get("dst") != ["tag:ia4:*"]
                   and r.get("src") != ["tag:ia4"]]
    raw["ssh"] = [r for r in raw["ssh"] if r.get("dst") != ["tag:ia4"]]
    minus_text = json.dumps(raw, indent=2)

    minus_live = m.parse_live(minus_text)
    iac4 = [e for s in m.SECTION_ORDER for e in model[s] if e.group == "iac4"]
    check("iac4-Gruppe hat 4 Einträge (1 tagOwner + 2 acl + 1 ssh)", len(iac4) == 4,
          "gefunden: %d" % len(iac4))

    new_text = minus_text
    for section in m.SECTION_ORDER:
        ents = [e for e in iac4 if e.section == section]
        if ents:
            new_text = m.insert_entries(new_text, section, ents)

    # a) 0 Entfernungen (nur hinzugefügte Zeilen)
    old_lines = Counter(l.rstrip("\n") for l in minus_text.splitlines() if l.strip())
    new_lines = Counter(l.rstrip("\n") for l in new_text.splitlines() if l.strip())
    removed = sum(max(0, c - new_lines.get(t, 0)) for t, c in old_lines.items())
    check("Einfügung ist rein additiv (0 entfernte/geänderte Zeilen)", removed == 0,
          "entfernt=%d" % removed)

    # b) count==1-Gate je eingefügtem Eintrag
    vmodel = m.parse_live(new_text)
    gates_ok = True
    for section in m.SECTION_ORDER:
        vcnt = Counter(e.ident() for e in vmodel[section])
        bcnt = Counter(e.ident() for e in minus_live[section])
        for e in [x for x in iac4 if x.section == section]:
            if vcnt.get(e.ident(), 0) != bcnt.get(e.ident(), 0) + 1:
                gates_ok = False
                print("   count!=+1: %s" % e.rule_id())
    check("count==1-Gate: jeder iac4-Eintrag exakt +1", gates_ok)

    # c) semantische Additivität
    ok_add, details = m.semantic_additivity(minus_text, new_text, iac4)
    check("Semantische Additivität (keine Bestandsregel entfernt/geändert)", ok_add,
          "; ".join(details))

    # 4) Negativ-Test: entfernte Bestandsregel wird erkannt
    broken = json.loads(new_text)
    broken["acls"] = broken["acls"][1:]  # erste Regel (base ia3) entfernen
    ok_neg, det_neg = m.semantic_additivity(new_text, json.dumps(broken, indent=2), [])
    check("Negativ-Test: entfernte Bestandsregel wird erkannt", not ok_neg,
          "unerkannt")

    # 5) Export offline (--file) schreibt huJSON + SHA256
    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, "exp.hujson")
    rc = os.system("%s %s --file %s --export --out %s >/dev/null" % (
        sys.executable, os.path.join(ROOT, "scripts", "ensure-acl.py"),
        FIXTURE, out))
    check("Export offline: Datei + .sha256 geschrieben",
          rc == 0 and os.path.exists(out) and os.path.exists(out + ".sha256"))
    with open(out, encoding="utf-8") as f:
        check("Export ist byte-identisch zum Snapshot", f.read() == live_text)

    print("")
    if _failures:
        print("❌ %d Test(s) fehlgeschlagen: %s" % (len(_failures), ", ".join(_failures)))
        return 1
    print("🎉 Alle Offline-Nachweise bestanden")
    return 0


if __name__ == "__main__":
    sys.exit(main())
