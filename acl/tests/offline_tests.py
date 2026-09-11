#!/usr/bin/env python3
"""Offline-Nachweis für die ACL-Single-Source-Migration (KEIN Netz, kein POST).

Prüft:
 1. SSoT-Datei parsebar + Modell-Gates (Tag-Referenzen, Marker).
 2. Null-Diff des Modells gegen den rekonstruierten Live-Snapshot (acl/tests/
    fixtures) – semantisch, inkl. Regel-Reihenfolge (acls/ssh).
 3. Rein additive Einfügung der iac4-Gruppe in einen Snapshot OHNE iac4
    (0 Entfernungen, count==1-Gate, semantische Additivität, Reihenfolge erhalten).
 4. Negativ-Test: Erkennung einer entfernten Bestandsregel.
 4b. Negativ-Test A2: eine PERMUTIERTE acls-/ssh-Reihenfolge wird von `--verify`
     erkannt (exit 1) – die Regel-Reihenfolge wird wirklich erzwungen, nicht nur
     behauptet (Abweichung ist REIN die Reihenfolge: Fehlend/Geändert/Fremd = 0).
 4c. A3a: fehlt eine Regel, wird KEINE irreführende Reihenfolge-Abweichung
     gemeldet; die Ursache wird als 'Fehlend' benannt.
 5. Export-Modus liest offline (--file) und schreibt huJSON + SHA256.
 6. IaC4-Vorbedingung (aus HA-PR #54) semantisch inkl. Negativ-Fall.
 7. `--verify <export-datei>` (Positional) = reproduzierbarer Null-Diff.

Aufruf: python3 acl/tests/offline_tests.py

 8. Fremdbestand-Toleranz (`--tolerated-foreign`): verwalteter Teil exakt +
    dokumentierter Fremdbestand unverändert/an Live-Positionen; jeder
    unerwartete Fremdbestand (fehlt/verändert/neu/falsche Position) -> exit 1.
    Toleranzliste: acl/tolerated-foreign.json (nur IaC3 aktiv, 5 Einträge;
    die 4 Konsolen-Einträge sind seit 2026-09-11 19:52 UTC Teil des Modells).
    Befund: der reale Live-Aufbau ist nicht block-konform (IaC3-Selbstregel
    steht vor dem Konsolen-Block) -> Block-Positions-Check meldet Reihenfolge
    (bekannte Limitierung; siehe 8b).
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL = os.path.join(ROOT, "acl", "tailscale-acl.hujson")
FIXTURE = os.path.join(ROOT, "acl", "tests", "fixtures", "live-reconstructed.hujson")
TOLERATED = os.path.join(ROOT, "acl", "tolerated-foreign.json")
FIXTURE_FULL = os.path.join(ROOT, "acl", "tests", "fixtures", "live-with-foreign.hujson")
FIXTURE_TOL = os.path.join(ROOT, "acl", "tests", "fixtures", "live-with-tolerated-foreign.hujson")

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
    mqtt_mod = [e for e in model["acls"] if e.group == "mqtt-1883"]
    mqtt_live = {e.canon for e in live["acls"]}
    check("Regel 6 (MQTT) ist Live-Soll (nicht mehr pending)",
          len(mqtt_mod) == 1 and not mqtt_mod[0].pending,
          "mqtt-1883-Einträge=%d pending=%s"
          % (len(mqtt_mod), [e.pending for e in mqtt_mod]))
    check("Regel 6 (MQTT) im Live-Snapshot vorhanden (nicht mehr pending_live)",
          bool(mqtt_mod) and mqtt_mod[0].canon in mqtt_live
          and not any(s == "acls" for s, _o, _m in rep["pending_live"]))

    # 3) Additive Einfügung der iac4-Gruppe in Snapshot OHNE iac4
    #    Entfernt werden GENAU die iac4-Modell-Einträge (semantisch über canon),
    #    damit z. B. die MQTT-Regel (gleiche src wie ein iac4-Eintrag, aber
    #    dst tag:ha:1883) im Snapshot bleibt.
    iac4 = [e for s in m.SECTION_ORDER for e in model[s] if e.group == "iac4"]
    iac4_acls = {e.canon for e in iac4 if e.section == "acls"}
    iac4_ssh = {e.canon for e in iac4 if e.section == "ssh"}
    iac4_tags = {e.key for e in iac4 if e.section == "tagOwners"}

    raw = json.loads(live_text)
    for k in iac4_tags:
        raw["tagOwners"].pop(k, None)
    raw["acls"] = [r for r in raw["acls"] if m.canon(r) not in iac4_acls]
    raw["ssh"] = [r for r in raw["ssh"] if m.canon(r) not in iac4_ssh]
    minus_text = json.dumps(raw, indent=2)

    minus_live = m.parse_live(minus_text)
    check("iac4-Gruppe hat 4 Einträge (1 tagOwner + 2 acl + 1 ssh)", len(iac4) == 4,
          "gefunden: %d" % len(iac4))

    new_text = minus_text
    for section in m.SECTION_ORDER:
        ents = [e for e in iac4 if e.section == section]
        if ents:
            new_text = m.insert_entries(new_text, section, ents, model[section])

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

    # d) Regel-Reihenfolge nach Einfügung erhalten (Modell-Position je Eintrag)
    ord_problems = m.order_diff(model, m.parse_live(new_text))
    check("Regel-Reihenfolge nach Einfügung erhalten (acls/ssh)", ord_problems == [],
          "; ".join(ord_problems))

    # 4) Negativ-Test: entfernte Bestandsregel wird erkannt
    broken = json.loads(new_text)
    broken["acls"] = broken["acls"][1:]  # erste Regel (base ia3) entfernen
    ok_neg, det_neg = m.semantic_additivity(new_text, json.dumps(broken, indent=2), [])
    check("Negativ-Test: entfernte Bestandsregel wird erkannt", not ok_neg,
          "unerkannt")

    # 4b) Negativ-Test A2: PERMUTIERTE Regel-Reihenfolge (acls/ssh) → --verify exit 1
    #     Beweist, dass die Reihenfolge erzwungen und nicht nur behauptet wird:
    #     die Multimenge ist unverändert (Fehlend/Geändert/Fremd = 0), allein die
    #     Sequenz ist umgedreht.
    ptmp = tempfile.mkdtemp()

    def verify_permuted(section):
        raw_perm = json.loads(live_text)
        raw_perm[section] = list(reversed(raw_perm[section]))
        path = os.path.join(ptmp, "perm-%s.hujson" % section)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw_perm, f, indent=2)
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "ensure-acl.py"),
             "--verify", path], capture_output=True, text=True)
        return proc.returncode, proc.stdout

    rc_a, out_a = verify_permuted("acls")
    check("A2: permutierte acls-Reihenfolge → --verify exit 1", rc_a == 1,
          "rc=%d" % rc_a)
    check("A2: acls-Abweichung ist REIN die Reihenfolge (Fehlend=0, abweichend=1)",
          "Fehlend (Soll, nicht live): 0" in out_a
          and "Regel-Reihenfolge (acls/ssh) abweichend: 1" in out_a,
          "Fehlend!=0 oder Reihenfolge nicht gemeldet")

    rc_s, out_s = verify_permuted("ssh")
    check("A2: permutierte ssh-Reihenfolge → --verify exit 1", rc_s == 1,
          "rc=%d" % rc_s)
    check("A2: ssh-Abweichung ist REIN die Reihenfolge (Fehlend=0, abweichend=1)",
          "Fehlend (Soll, nicht live): 0" in out_s
          and "Regel-Reihenfolge (acls/ssh) abweichend: 1" in out_s,
          "Fehlend!=0 oder Reihenfolge nicht gemeldet")

    # 4c) A3a: fehlt eine Regel, gibt es KEINE irreführende Reihenfolge-Meldung;
    #     die Ursache wird (allein) als 'Fehlend' berichtet.
    raw_miss = json.loads(live_text)
    raw_miss["acls"] = raw_miss["acls"][1:]  # erste (base ia3) entfernen
    rep_miss = m.diff_model_vs_live(model, m.parse_live(json.dumps(raw_miss, indent=2)))
    check("A3a: fehlende Regel → KEINE Reihenfolge-Meldung (order=[])",
          rep_miss["order"] == [], "; ".join(rep_miss["order"]))
    check("A3a: fehlende Regel wird als 'Fehlend' benannt",
          len(rep_miss["missing"]) == 1, "missing=%d" % len(rep_miss["missing"]))

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

    # 6) IaC4-Vorbedingung (übernommen aus HA-PR #54) – semantisch, layout-tolerant
    pol = m.parse_policy(live_text)
    check("Vorbedingung ha-tagowners erfüllt (tag:ia4 -> autogroup:admin)",
          m.precondition_ok(pol, "ha-tagowners"))
    check("Vorbedingung ha-acl erfüllt (src tag:ia4 -> dst tag:ia4:*)",
          m.precondition_ok(pol, "ha-acl"))
    check("Vorbedingung ha-ssh erfüllt (dst tag:ia4)",
          m.precondition_ok(pol, "ha-ssh"))
    bare = {"tagOwners": {}, "acls": [], "ssh": []}
    check("Vorbedingung ha-acl fehlt ohne IaC4-Basis (Negativ-Fall)",
          not m.precondition_ok(bare, "ha-acl"))
    check("Gruppe 'iac4' hat keine Vorbedingung", m.precondition_ok(bare, "iac4"))

    # 7) --verify <export-datei> (Positional) = reproduzierbarer Null-Diff
    rc = os.system("%s %s --verify %s >/dev/null" % (
        sys.executable, os.path.join(ROOT, "scripts", "ensure-acl.py"), FIXTURE))
    check("--verify <export-datei>: Null-Diff gegen Snapshot (exit 0)", rc == 0)

    # ----------------------------------------------------------------------
    # 8) Fremdbestand-Toleranz (Owner-Entscheide 2026-09-11):
    #    - 19:41 UTC „IaC3 nicht übernehmen": IaC3 bleibt dokumentierter
    #      Fremdbestand (5 Einträge).
    #    - 19:52 UTC „Ja" zu den 4 Konsolen-Einträgen: sie sind INS MODELL
    #      übernommen (Gruppe console-owner, live) – kein Platzhalter mehr.
    #    Erfolgskriterium: verwalteter Teil exakt + dokumentierter Fremdbestand
    #    unverändert/an Live-Positionen; jede unerwartete Abweichung -> exit 1.
    #    BEFUND (bekannte Limitierung): der reale Live-Aufbau ist NICHT block-
    #    konform – die IaC3-Selbstregel steht VOR dem Konsolen-Block. Der
    #    Block-Positions-Check (start|end) meldet das als Reihenfolge-Abweichung
    #    (8b). Siehe acl/README.md „Bekannte Limitierung" / M2-Findings.
    # ----------------------------------------------------------------------
    tol = m.load_tolerated(TOLERATED)
    n_tol = sum(len(tol["sections"][s]["entries"]) for s in ("acls", "ssh"))
    check("Toleranzliste parst; 5 aktive IaC3-Einträge (4 acls + 1 ssh)",
          n_tol == 5 and len(tol["sections"]["acls"]["entries"]) == 4
          and len(tol["sections"]["ssh"]["entries"]) == 1, "n=%d" % n_tol)
    check("Toleranzliste: KEIN offener Platzhalter mehr (Konsolen ins Modell übernommen)",
          len(tol["pending"]) == 0, "pending=%d" % len(tol["pending"]))
    check("Toleranzliste: Block-Positionen (acls=end, ssh=start)",
          tol["sections"]["acls"]["position"] == "end"
          and tol["sections"]["ssh"]["position"] == "start")

    ttmp = tempfile.mkdtemp()

    def verify(path, tolerated=True):
        cmd = [sys.executable, os.path.join(ROOT, "scripts", "ensure-acl.py"),
               "--verify", path]
        if tolerated:
            cmd += ["--tolerated-foreign", TOLERATED]
        return subprocess.run(cmd, capture_output=True, text=True)

    def write_live(name, mutate, base=None):
        with open(base or FIXTURE_TOL, encoding="utf-8") as f:
            d = json.load(f)
        mutate(d)
        p = os.path.join(ttmp, name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
        return p

    # Kanon-Lage (kontiguierlicher Fremdbestand): acls = verwalteter Teil +
    # IaC3-Block geschlossen am Ende, in Toleranz-Reihenfolge (Selbstregel zuerst).
    _foreign = [
        {"action": "accept", "src": ["tag:ia3"], "dst": ["tag:ia3:*"]},
        {"action": "accept", "src": ["tag:ia3"], "dst": ["tag:ha:*"]},
        {"action": "accept", "src": ["tag:ia3"], "dst": ["192.168.0.0/24:*"]},
        {"action": "accept", "src": ["tag:ha"], "dst": ["tag:ia3:*"]},
    ]

    def _contiguous(d):
        d["acls"] = [r for r in d["acls"] if r not in _foreign] + list(_foreign)

    # 8a) Mechanik-Nachweis (Kanon-Lage): kontiguierlicher Fremdbestand-Block
    #     (IaC3 geschlossen NACH den verwalteten Einträgen) -> exit 0. Belegt,
    #     dass der verwaltete Teil exakt matcht UND der dokumentierte
    #     Fremdbestand an seinen Live-Positionen unverändert vorhanden ist.
    p_contig = write_live("tol-contiguous.hujson", _contiguous)
    p = verify(p_contig)
    check("Toleranz-Verify (kontiguierlicher Fremdbestand): exit 0",
          p.returncode == 0, "rc=%d" % p.returncode)
    check("Toleranz-Verify: verwalteter Teil exakt (Fehlend/Geändert/Fremd=0)",
          "Fehlend (Soll, nicht live): 0" in p.stdout
          and "Geändert (Soll != live): 0" in p.stdout
          and "Unerwartet fremd in live (Modell+Toleranz unbekannt): 0" in p.stdout)
    check("Toleranz-Verify: 5 tolerierte Einträge als vorhanden gemeldet",
          "Tolerierter Fremdbestand (vorhanden/unverändert): 5" in p.stdout)

    # 8b) REALER Live-Aufbau (eingefrorener Export): verwalteter Teil exakt +
    #     IaC3-Fremdbestand vorhanden/unverändert + kein unerwarteter Eintrag.
    #     BEFUND (bekannte Limitierung): In Live steht die IaC3-Selbstregel VOR
    #     dem Konsolen-Block (IaC3 nicht zusammenhängend). Der Block-Positions-
    #     Check (start|end) meldet das als Reihenfolge-Abweichung -> exit 1,
    #     obwohl der verwaltete Teil und der Fremdbestand selbst korrekt sind.
    p_real = verify(FIXTURE_TOL)
    check("Toleranz-Verify (realer Aufbau): verwalteter Teil exakt (Fehlend/Geändert/Fremd=0)",
          "Fehlend (Soll, nicht live): 0" in p_real.stdout
          and "Geändert (Soll != live): 0" in p_real.stdout
          and "Unerwartet fremd in live (Modell+Toleranz unbekannt): 0" in p_real.stdout)
    check("Toleranz-Verify (realer Aufbau): 5 IaC3-Einträge vorhanden/unverändert",
          "Tolerierter Fremdbestand (vorhanden/unverändert): 5" in p_real.stdout
          and "Tolerierter Fremdbestand fehlt/verändert: 0" in p_real.stdout)
    check("Toleranz-Verify (realer Aufbau): Interleaving -> Reihenfolge-Abweichung (bekannte Limitierung) -> exit 1",
          p_real.returncode == 1
          and "Regel-Reihenfolge (acls/ssh) abweichend: 1" in p_real.stdout,
          "rc=%d" % p_real.returncode)

    # 8c) Ohne Toleranz (strikt): derselbe reale Live-Zustand -> 5 IaC3-Fremd-Einträge = Drift
    p_strict = verify(FIXTURE_FULL, tolerated=False)
    check("Strikter Verify (ohne Toleranz): 5 Fremd-Einträge -> exit 1",
          p_strict.returncode == 1
          and "Unerwartet fremd in live (Modell+Toleranz unbekannt): 5" in p_strict.stdout,
          "rc=%d" % p_strict.returncode)

    # 8d) Tolerierter Fremdbestand FEHLT (gelöscht) -> exit 1
    p_miss = write_live("tol-missing.hujson", lambda d: d.__setitem__(
        "acls", [r for r in d["acls"]
                 if not (r.get("src") == ["tag:ia3"] and r.get("dst") == ["tag:ia3:*"])]))
    p = verify(p_miss)
    check("Toleranz-Verify: tolerierter Fremdbestand fehlt -> exit 1",
          p.returncode == 1
          and "Tolerierter Fremdbestand fehlt/verändert: 1" in p.stdout,
          "rc=%d" % p.returncode)

    # 8e) Tolerierter Fremdbestand VERÄNDERT -> exit 1
    def _mutate_changed(d):
        for r in d["acls"]:
            if r.get("src") == ["tag:ia3"] and r.get("dst") == ["tag:ha:*"]:
                r["dst"] = ["tag:ha:22"]
    p_chg = write_live("tol-changed.hujson", _mutate_changed)
    p = verify(p_chg)
    check("Toleranz-Verify: tolerierter Fremdbestand verändert -> exit 1",
          p.returncode == 1
          and "Tolerierter Fremdbestand fehlt/verändert: 1" in p.stdout,
          "rc=%d" % p.returncode)

    # 8f) UNERWARTETER neuer Fremdbestand -> exit 1
    p_new = write_live("tol-extra.hujson", lambda d: d["acls"].append(
        {"action": "accept", "src": ["autogroup:member"], "dst": ["tag:ia4:9999"]}))
    p = verify(p_new)
    check("Toleranz-Verify: unerwarteter neuer Eintrag -> exit 1",
          p.returncode == 1
          and "Unerwartet fremd in live (Modell+Toleranz unbekannt): 1" in p.stdout,
          "rc=%d" % p.returncode)

    # 8g) Fremdbestand an FALSCHER Live-Position (ssh?) -> exit 1 (Reihenfolge/Position)
    #     Basis = Kanon-Lage (p_contig), damit die Abweichung REIN die ssh-Position ist.
    def _mutate_moved(d):
        e = d["ssh"].pop(0)
        d["ssh"].append(e)
    p_moved = write_live("tol-moved.hujson", _mutate_moved, base=p_contig)
    p = verify(p_moved)
    check("Toleranz-Verify: Fremdbestand an falscher Position -> exit 1",
          p.returncode == 1
          and "Regel-Reihenfolge (acls/ssh) abweichend: 1" in p.stdout,
          "rc=%d" % p.returncode)

    print("")
    if _failures:
        print("❌ %d Test(s) fehlgeschlagen: %s" % (len(_failures), ", ".join(_failures)))
        return 1
    print("🎉 Alle Offline-Nachweise bestanden")
    return 0


if __name__ == "__main__":
    sys.exit(main())
