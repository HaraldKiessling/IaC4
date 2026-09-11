#!/usr/bin/env python3
"""Einheitliches, rein additives ACL-Werkzeug für die Tailscale-ACL (SSoT in IaC4).

Ersetzt `scripts/ensure-acl-ia4.py` (byte-exakte Anker) durch EINEN semantischen
Mechanismus für BEIDE Tag-Welten (tag:ia4 + tag:ha/tag:ha-ci). Quelle der Regeln
ist die kanonische Datei `acl/tailscale-acl.hujson` (SSoT) – nicht der Skript-Code.

Prinzip (100% Sicherheit — additiv, idempotent, failsafe):
- Die Regelquelle ist `acl/tailscale-acl.hujson`; jede Regel trägt dort einen
  Marker (`// rule: <gruppe>` bzw. `// base`). Der Skript-Code enthält KEINE
  Regel-Inhalte mehr (Single Source of Truth).
- SEMANTISCHE Prüfung: Live-Policy und Modell werden als huJSON geparst und
  strukturell verglichen (kein Byte-Anker). Formatierung, Kommentare, Trailing-
  Kommas sowie die Feld-/Listen-Reihenfolge INNERHALB einer Regel sind
  irrelevant. Die REIHENFOLGE der Regeln (acls/ssh) ist dagegen Teil des
  Null-Diffs (Owner-Entscheid F4, 2026-09-11); tagOwners ist eine Zuordnung –
  dessen Key-Reihenfolge zählt nicht (JSON-Objekt).
- ADDITIV: neue Regeln werden als Text an ihrer Modell-Position in den
  jeweiligen Abschnitt eingefügt (Reihenfolge aus der SSoT) – bestehende Zeilen
  werden NIE verändert oder entfernt.
- Selektive Anwendung: `--rule/--rules <gruppe>` fügt NUR die gewählten Gruppen
  ein; ohne Auswahl wird im APPLY-Modus abgebrochen (kein POST).
  `pending`-Regeln (deklariert, nicht Teil des Live-Solls) nur bei expliziter Wahl.
- Verifikation nach POST: jede eingefügte Regel exakt um +1 (count==1-Gate),
  keine Bestands-Regel entfernt/geändert (semantische Multimengen-Prüfung).
- NIEMALS wird die Modell-Datei als Gesamtdatei über die Live-Policy geschrieben:
  Basis ist immer die frisch gelesene Live-Policy (GET); es werden nur neue
  Zeilen additiv eingefügt. So bleiben nicht übernommene Einträge erhalten
  (Fremdbestand: IaC3-/Konsolen-Regeln, `acl/tolerated-foreign.json`).
- Fremdbestand-Toleranz (Owner-Entscheid 2026-09-11 „IaC3 nicht übernehmen"):
  `--tolerated-foreign [DATEI]` erlaubt bei `--verify`/`--dry-run` den
  dokumentierten, NICHT von IaC4 verwalteten Live-Bestand. Geprüft wird:
  verwalteter Teil exakt (inkl. Reihenfolge) + Fremdbestand vollständig,
  unverändert und an seinen Live-Positionen; jede unerwartete Abweichung -> exit 1.
- IaC4-Vorbedingung (IaC4-first, übernommen aus HA-PR #54): die HA-Gruppen setzen
  auf die IaC4-Baseline (`tag:ia4`) auf; geprüft wird SEMANTISCH (geparst,
  layout-tolerant) und nur für Gruppen, die DIESER Lauf tatsächlich einfügt
  (Scope-Kopplung). Fehlt die Basis, Abbruch OHNE POST.
- Bei Verifikationsfehler: automatisches Rollback (POST des Backups) + exit 1.
- `--export`: read-only GET → rohe huJSON + SHA256 als versionierbares Inventar.

Governance (Owner 2026-09-06 / Owner-Entscheid 2026-09-11):
    ACLs sind zentral und produktionsrelevant. Ein ACL-Apply läuft NIE automatisch
    (kein push-/PR-/schedule-Trigger). Jeder Apply: Wirkungs-Analyse (--dry-run)
    + Review (Autor != Reviewer) + ausdrückliche Owner-Zustimmung.
    Ausführung ausschließlich manuell über .github/workflows/00-acl-apply.yml.

Nutzung:
    TS_TAILNET=... TS_API_KEY=... python3 scripts/ensure-acl.py --dry-run
    TS_TAILNET=... TS_API_KEY=... python3 scripts/ensure-acl.py --rule iac4
    TS_TAILNET=... TS_API_KEY=... python3 scripts/ensure-acl.py --export --out acl/live.hujson
    TS_TAILNET=... TS_API_KEY=... python3 scripts/ensure-acl.py --verify
    python3 scripts/ensure-acl.py --verify acl/live-export-<sha8>.hujson   # offline, reproduzierbar
    python3 scripts/ensure-acl.py --check-model
    python3 scripts/ensure-acl.py --file <snapshot.hujson> --dry-run      # offline
Python3, nur Standardbibliothek.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from collections import Counter

API = "https://api.tailscale.com/api/v2/tailnet"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(REPO_ROOT, "acl", "tailscale-acl.hujson")
DEFAULT_TOLERATED_PATH = os.path.join(REPO_ROOT, "acl", "tolerated-foreign.json")
SECTION_ORDER = ("tagOwners", "acls", "ssh")

TAILNET = os.environ.get("TS_TAILNET", "")
TOKEN = os.environ.get("TS_TOKEN", "") or os.environ.get("TS_API_KEY", "")

# Gruppen → Regel-Namen (Workflow-Input `rules`), inkl. numerischer Aliase der
# HA-Regeln 1–7 (Kontinuität zum bisherigen ha-repo-Workflow).
GROUP_NAMES = ("iac4", "ha-tagowners", "ha-acl", "ha-ssh", "ha-runner",
               "owner-8123", "console-owner", "mqtt-1883", "energie-read")
GROUP_ALIASES = {
    "iac4": "iac4",
    "1": "ha-tagowners", "ha-tagowners": "ha-tagowners", "tagowners": "ha-tagowners",
    "2": "ha-acl", "ha-acl": "ha-acl", "ha2": "ha-acl",
    "3": "ha-ssh", "ha-ssh": "ha-ssh", "ssh3": "ha-ssh",
    "4": "ha-runner", "ha-runner": "ha-runner", "ha-ia4": "ha-runner",
    "5": "owner-8123", "owner-8123": "owner-8123", "owner8123": "owner-8123",
    "console-owner": "console-owner", "console": "console-owner",
    "6": "mqtt-1883", "mqtt-1883": "mqtt-1883", "mqtt": "mqtt-1883",
    "7": "energie-read", "energie-read": "energie-read", "energie": "energie-read",
}


# ---------------------------------------------------------------------------
# huJSON-Primitive (übernommen/abgesichert aus scripts/ensure-acl-ha.py)
# ---------------------------------------------------------------------------
def hujson_to_json(text):
    """huJSON → JSON-Text: erst Kommentare (// und /* */) entfernen, dann
    Trailing-Kommas korrigieren – beide Schritte string-sicher (URLs wie
    "https://…" bleiben unberührt). Wirft ValueError bei ungültigem JSON."""
    def _strip_comments(src):
        out = []
        i, n = 0, len(src)
        in_str = False
        while i < n:
            c = src[i]
            if in_str:
                out.append(c)
                if c == "\\" and i + 1 < n:
                    out.append(src[i + 1])
                    i += 2
                    continue
                if c == '"':
                    in_str = False
                i += 1
                continue
            if c == '"':
                in_str = True
                out.append(c)
                i += 1
                continue
            if c == "/" and i + 1 < n and src[i + 1] == "/":
                while i < n and src[i] != "\n":
                    i += 1
                continue
            if c == "/" and i + 1 < n and src[i + 1] == "*":
                i += 2
                while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                    i += 1
                i = min(i + 2, n)
                continue
            out.append(c)
            i += 1
        return "".join(out)

    def _fix_trailing_commas(src):
        out = []
        i, n = 0, len(src)
        in_str = False
        while i < n:
            c = src[i]
            if in_str:
                out.append(c)
                if c == "\\" and i + 1 < n:
                    out.append(src[i + 1])
                    i += 2
                    continue
                if c == '"':
                    in_str = False
                i += 1
                continue
            if c == '"':
                in_str = True
                out.append(c)
                i += 1
                continue
            if c == ",":
                j = i + 1
                while j < n and src[j] in " \t\r\n":
                    j += 1
                if j < n and src[j] in "}]":
                    i = j
                    continue
            out.append(c)
            i += 1
        return "".join(out)

    return _fix_trailing_commas(_strip_comments(text))


def parse_policy(text):
    """huJSON-Text → Python-Struktur (ValueError bei Parse-Fehler)."""
    return json.loads(hujson_to_json(text))


def canon(v):
    """Kanonische Normalform für semantische Vergleiche:
    String-Listen → sortiertes, entdoppeltes Tupel (Reihenfolge irrelevant);
    Dicts → sortiert (Schlüsselreihenfolge irrelevant); übrige Listen → in Ordnung."""
    if isinstance(v, dict):
        return tuple(sorted((k, canon(x)) for k, x in v.items()))
    if isinstance(v, list):
        if all(isinstance(x, str) for x in v):
            return tuple(sorted(set(v)))
        return tuple(canon(x) for x in v)
    return v


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _short(obj):
    try:
        return json.dumps(obj, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(obj)


# ---------------------------------------------------------------------------
# Fremdbestand-Toleranzliste (nicht von IaC4 verwaltete Live-Einträge)
# ---------------------------------------------------------------------------
# Die Live-Tailscale-ACL enthält Einträge, die NICHT ins IaC4-Modell übernommen
# werden (Owner-Entscheid 2026-09-11: „IaC3 nicht übernehmen"). Sie bleiben
# „dokumentierter Fremdbestand": Der verwaltete Teil muss exakt matchen, der
# Fremdbestand vollständig/unverändert an seinen Live-Positionen vorhanden sein.
# Die Liste liegt in `acl/tolerated-foreign.json` (siehe `--tolerated-foreign`).
def load_tolerated(path):
    """Toleranzliste laden → strukturiertes Dict:
        { "tagOwners": [key, …],
          "sections": { section: {"position": "start"|"end",
                                  "entries": [{"group","obj","canon"}, …]} },
          "pending":  [{"section","group","reason"}, …] }
    Nur Einträge mit status == 'tolerated' sind aktiv. Platzhalter
    ('owner-decision-pending' o. Ä.) werden NICHT toleriert (nicht raten) und
    dienen nur der Dokumentation. Wirft ValueError bei ungültigem Schema."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    tol = {"tagOwners": [],
           "sections": {s: {"position": "end", "entries": []}
                        for s in ("acls", "ssh")},
           "pending": [],
           "source": path}
    for key in data.get("tagOwners", []) or []:
        tol["tagOwners"].append(key)
    for section in ("acls", "ssh"):
        blk = data.get(section) or {}
        pos = blk.get("position", "end")
        if pos not in ("start", "end"):
            raise ValueError("Abschnitt %s: position muss 'start' oder 'end' sein: %r"
                             % (section, pos))
        tol["sections"][section]["position"] = pos
        for item in blk.get("entries", []) or []:
            status = str(item.get("status", "tolerated")).strip().lower()
            if status != "tolerated":
                tol["pending"].append({"section": section,
                                       "group": item.get("group"),
                                       "reason": item.get("reason")})
                continue
            obj = item.get("obj")
            if not isinstance(obj, dict):
                raise ValueError("Abschnitt %s: tolerierter Eintrag ohne \"obj\""
                                 % section)
            tol["sections"][section]["entries"].append(
                {"group": item.get("group"), "obj": obj, "canon": canon(obj)})
    return tol


# ---------------------------------------------------------------------------
# SSoT-Parsing: Abschnitte + Marker (// rule: <gruppe> [pending] | // base)
# ---------------------------------------------------------------------------
_MARKER_RE = re.compile(r"^\s*(?P<kind>rule|base)\b\s*:?\s*(?P<grp>[A-Za-z0-9_-]+)?"
                        r"\s*(?P<pending>pending)?\b")


def strip_comments_with_markers(src):
    """Wie hujson_to_json (_strip_comments), sammelt aber Marker-Kommentare:
    liefert (clean_text, markers) mit markers = [(pos_in_clean, gruppe, pending)]."""
    out = []
    markers = []
    i, n = 0, len(src)
    in_str = False
    while i < n:
        c = src[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(src[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = i
            while j < n and src[j] != "\n":
                j += 1
            comment = src[i + 2:j]
            m = _MARKER_RE.match(comment)
            if m:
                if m.group("kind") == "base":
                    markers.append((len(out), "base", False))
                elif m.group("grp"):
                    markers.append((len(out), m.group("grp"),
                                    bool(m.group("pending"))))
            i = j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                i += 1
            i = min(i + 2, n)
            continue
        out.append(c)
        i += 1
    return "".join(out), markers


def _section_span(text, name):
    """(content_start, content_end) zwischen den Abschnitts-Klammern (exklusiv) oder None."""
    m = re.search(r'"%s"\s*:\s*([\{\[])' % re.escape(name), text)
    if not m:
        return None
    opener = m.group(1)
    closer = "}" if opener == "{" else "]"
    depth = 0
    i = m.end() - 1
    while i < len(text):
        if text[i] == opener:
            depth += 1
        elif text[i] == closer:
            depth -= 1
            if depth == 0:
                return (m.end(), i)
        i += 1
    return None


def _iter_objects(text, start, end):
    """Top-level {…}-Objekte im Bereich [start, end) → (obj_start, obj_end)."""
    i = start
    while i < end:
        if text[i] == "{":
            depth = 0
            j = i
            while j < end:
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            yield (i, j + 1)
            i = j + 1
        else:
            i += 1


def _iter_tagowners(text, start, end):
    """Top-level "key": [ … ]-Einträge im tagOwners-Bereich → (key, val_start, val_end, key_start)."""
    pat = re.compile(r'"([^"]+)"\s*:\s*\[', re.M)
    pos = start
    while True:
        m = pat.search(text, pos, end)
        if not m:
            return
        depth = 0
        j = m.end() - 1
        while j < end:
            if text[j] == "[":
                depth += 1
            elif text[j] == "]":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        yield (m.group(1), m.end() - 1, j + 1, m.start())
        pos = j + 1


def _group_for(entry_start, markers):
    """Gruppe eines Eintrags = jüngster Marker mit pos <= entry_start (Default base)."""
    grp, pending = "base", False
    for pos, g, p in markers:
        if pos <= entry_start:
            grp, pending = g, p
        else:
            break
    return grp, pending


class Entry:
    __slots__ = ("section", "key", "obj", "canon", "group", "pending", "text")

    def __init__(self, section, group, pending, text, key=None, obj=None):
        self.section = section
        self.group = group
        self.pending = pending
        self.text = text
        self.key = key
        self.obj = obj
        self.canon = canon(obj if obj is not None else key)

    def rule_id(self):
        if self.section == "tagOwners":
            return "tagOwners:%s" % self.key
        return "%s:%s" % (self.section, _short(self.obj))

    def ident(self):
        """Vergleichs-Identität: tagOwners über (key, wert) – zwei Tags können
        denselben Wert tragen und sind dennoch verschiedene Einträge."""
        if self.section == "tagOwners":
            return ("tagOwners", self.key, self.canon)
        return (self.section, self.canon)


def parse_model(path):
    """SSoT parsen → dict {section: [Entry, …]}. Validiert Parsebarkeit."""
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    clean, markers = strip_comments_with_markers(raw)
    parse_policy(raw)  # Validierung (wirft ValueError)
    entries = {s: [] for s in SECTION_ORDER}
    for section in SECTION_ORDER:
        span = _section_span(clean, section)
        if span is None:
            continue
        start, end = span
        if section == "tagOwners":
            for key, vs, ve, ks in _iter_tagowners(clean, start, end):
                grp, pend = _group_for(ks, markers)
                obj = parse_policy(clean[vs:ve])
                entries[section].append(Entry(section, grp, pend, clean[vs:ve],
                                              key=key, obj=obj))
        else:
            for os_, oe in _iter_objects(clean, start, end):
                grp, pend = _group_for(os_, markers)
                obj = parse_policy(clean[os_:oe])
                entries[section].append(Entry(section, grp, pend, clean[os_:oe],
                                              obj=obj))
    return entries, raw


def parse_live(text):
    """Live-Policy (huJSON, ggf. mit Kommentaren) → {section: [Entry, …]} (group='live')."""
    clean, _ = strip_comments_with_markers(text)
    parse_policy(text)
    entries = {s: [] for s in SECTION_ORDER}
    for section in SECTION_ORDER:
        span = _section_span(clean, section)
        if span is None:
            continue
        start, end = span
        if section == "tagOwners":
            for key, vs, ve, ks in _iter_tagowners(clean, start, end):
                obj = parse_policy(clean[vs:ve])
                entries[section].append(Entry(section, "live", False,
                                              clean[vs:ve], key=key, obj=obj))
        else:
            for os_, oe in _iter_objects(clean, start, end):
                obj = parse_policy(clean[os_:oe])
                entries[section].append(Entry(section, "live", False,
                                              clean[os_:oe], obj=obj))
    return entries


# ---------------------------------------------------------------------------
# Modell-Gates + Diff
# ---------------------------------------------------------------------------
def check_tag_references(model):
    """GATE: alle in acls/ssh referenzierten tag:* müssen in tagOwners deklariert
    sein (sonst Policy-invalid / Tag unbenannt). autogroup:*/user-* ausgenommen."""
    declared = {e.key for e in model["tagOwners"]}
    problems = []
    for section in ("acls", "ssh"):
        for e in model[section]:
            for field in ("src", "dst"):
                for item in e.obj.get(field, []):
                    if isinstance(item, str) and item.startswith("tag:"):
                        base = item.split(":", 2)
                        tagref = ":".join(base[:2])  # tag:<name> (ohne :port)
                        if tagref not in declared:
                            problems.append("%s: %s referenziert %s, das in "
                                            "tagOwners fehlt" % (section, field, tagref))
    return problems


def model_gates(model):
    """Definierte Modell-Gates (Reihenfolge/Referenzen/pending-Marker)."""
    problems = []
    problems += check_tag_references(model)
    for section in SECTION_ORDER:
        if not model[section] and section == "tagOwners":
            problems.append("tagOwners ist leer – Policy ohne Tags wäre unbrauchbar")
    # pending nur außerhalb von base erlaubt
    for section in SECTION_ORDER:
        for e in model[section]:
            if e.pending and e.group == "base":
                problems.append("%s: 'base' darf nicht 'pending' sein (%s)"
                                % (section, e.rule_id()))
    return problems


def _by_key(entries):
    d = {}
    for e in entries:
        d.setdefault(e.key, []).append(e)
    return d


def diff_model_vs_live(model, live, tolerated=None):
    """Semantischer Soll/Ist-Vergleich. Liefert ein Report-Dict.
    - expected: base + nicht-pending Regeln (Teil des Live-Solls)
    - pending:  deklariert, nicht Teil des Solls
    - foreign:  live vorhanden, im Modell UND in der Toleranzliste unbekannt
                (= unerwarteter Fremdbestand → Drift)
    - tolerated_present: dokumentierter Fremdbestand, live vorhanden/unverändert
    - tolerated_missing: dokumentierter Fremdbestand fehlt/verändert (Drift)
    Ist `tolerated` (aus `load_tolerated`) gesetzt, wird der dokumentierte
    Fremdbestand aus `foreign` herausgenommen und separat ausgewiesen.
    """
    rep = {"missing": [], "changed": [], "foreign": [],
           "tolerated_present": [], "tolerated_missing": [],
           "pending_live": [], "pending_missing": [], "order": [],
           "tolerance_active": bool(tolerated)}
    tol_to = set(tolerated["tagOwners"]) if tolerated else set()
    tol_sec = ({s: {t["canon"] for t in tolerated["sections"][s]["entries"]}
                for s in ("acls", "ssh")} if tolerated
               else {"acls": set(), "ssh": set()})

    # tagOwners (key→value, Reihenfolge irrelevant)
    mkeys = _by_key(model["tagOwners"])
    lkeys = {k: v for k, v in _by_key(live["tagOwners"]).items()}
    for key, es in mkeys.items():
        e = es[0]
        lval = lkeys.get(key)
        expected = not e.pending and e.group != "base"
        base = e.group == "base"
        if key not in lkeys:
            (rep["pending_missing"] if e.pending else rep["missing"]).append(
                ("tagOwners", key, e.canon))
        elif lval[0].canon != e.canon:
            if e.pending:
                rep["pending_live"].append(("tagOwners", key, "Wert abweichend (pending)"))
            else:
                rep["changed"].append(("tagOwners", key,
                                       "%s → %s" % (_short(e.canon), _short(lval[0].canon))))
        elif e.pending:
            rep["pending_live"].append(("tagOwners", key, "vorhanden (Wert ok)"))
        del expected, base
    for key in lkeys:
        if key not in mkeys:
            if key in tol_to:
                rep["tolerated_present"].append(("tagOwners", key, "toleriert"))
            else:
                rep["foreign"].append(("tagOwners", key, lkeys[key][0].canon))
    for key in tol_to:
        if key not in lkeys:
            rep["tolerated_missing"].append(("tagOwners", key, "fehlt"))

    # acls/ssh (Multimenge, Reihenfolge irrelevant)
    for section in ("acls", "ssh"):
        mcnt = Counter(e.canon for e in model[section])
        lcnt = Counter(e.canon for e in live[section])
        mobj = {e.canon: e for e in model[section]}
        for c, n in mcnt.items():
            e = mobj[c]
            have = lcnt.get(c, 0)
            if have < n:
                if e.pending:
                    rep["pending_missing"].append((section, _short(e.obj), "fehlt"))
                else:
                    rep["missing"].append((section, _short(e.obj), "fehlt"))
            elif e.pending and have >= n:
                rep["pending_live"].append((section, _short(e.obj), "vorhanden"))
        lobj = {e.canon: e for e in live[section]}
        found_tol = Counter()
        for c, n in lcnt.items():
            if c in mcnt:
                continue
            if c in tol_sec[section]:
                found_tol[c] += n
                rep["tolerated_present"].append((section, _short(lobj[c].obj), "toleriert"))
            else:
                rep["foreign"].append((section, _short(lobj[c].obj), "unbekannt"))
        if tolerated:
            for t in tolerated["sections"][section]["entries"]:
                if found_tol.get(t["canon"], 0) < 1:
                    rep["tolerated_missing"].append(
                        (section, _short(t["obj"]), "fehlt/verändert"))
    rep["order"] = order_diff(model, live, tolerated)
    return rep


def order_diff(model, live, tolerated=None):
    """Regel-Reihenfolge des Live-Solls gegen Live (Owner-Entscheid F4, 2026-09-11).
    Verglichen wird je Abschnitt die kanonische SEQUENZ der Einträge. `pending`-
    Einträge sind nicht Teil des Live-Solls und werden in der Live-Sequenz
    ausgelassen. Formatierung/Kommentare sowie Feld-/Listen-Reihenfolge innerhalb
    einer Regel sind irrelevant. `tagOwners` ist eine Zuordnung (JSON-Objekt) –
    dessen Key-Reihenfolge wird NICHT geprüft.
    Mit `tolerated` (aus `load_tolerated`) wird der ERWARTETE Fremdbestand-Block
    an seiner Live-Position (position='start'|'end') in die Soll-Sequenz
    eingefügt, sodass auch die Positionen des dokumentierten Fremdbestands
    erzwungen werden.
    Gemeldet wird NUR eine ECHTE Umsortierung: die kanonische Sequenz weicht ab,
    obwohl ALLE Soll-/Fremdbestand-Einträge vorhanden sind (Multimengen gleich).
    Fehlt dagegen ein Eintrag oder ist etwas unerwartet fremd (Multimenge !=
    Soll), ist die Ursache 'Fehlend'/'Fremd' – das wird bereits in
    rep["missing"]/rep["foreign"]/rep["tolerated_missing"] berichtet und hier
    NICHT zusätzlich irreführend als Reihenfolge-Abweichung.
    Liefert eine Liste von Abweichungs-Beschreibungen (leer = Reihenfolge ok)."""
    problems = []
    for section in ("acls", "ssh"):
        mseq = [e.canon for e in model[section] if not e.pending]
        fseq, pos = [], "end"
        if tolerated:
            fseq = [t["canon"] for t in tolerated["sections"][section]["entries"]]
            pos = tolerated["sections"][section].get("position", "end")
        exp_full = (fseq + mseq) if pos == "start" else (mseq + fseq)
        expected = Counter(exp_full)
        got = []
        for e in live[section]:
            if expected.get(e.canon, 0) > 0:
                got.append(e.canon)
                expected[e.canon] -= 1
        # Ursache-Trennung: weicht die Multimenge ab, fehlt/fremdelt ein Eintrag
        # (bereits als Fehlend/Fremd gemeldet) – KEINE Reihenfolge-Abweichung.
        if Counter(got) != Counter(exp_full):
            continue
        if got != exp_full:
            problems.append(
                "%s: Regel-Reihenfolge weicht ab (Soll: %d Einträge inkl. "
                "dokumentiertem Fremdbestand, in Live in dieser Reihenfolge "
                "gefunden: %d) – Formatierung ist irrelevant, die Reihenfolge nicht"
                % (section, len(exp_full), len(got)))
    return problems


def print_diff(rep):
    print("--- Semantischer Soll/Ist-Diff (Modell ↔ Live) ---")
    for label, rows in (("Fehlend (Soll, nicht live)", rep["missing"]),
                        ("Geändert (Soll != live)", rep["changed"]),
                        ("Unerwartet fremd in live (Modell+Toleranz unbekannt)", rep["foreign"]),
                        ("Tolerierter Fremdbestand (vorhanden/unverändert)", rep["tolerated_present"]),
                        ("Tolerierter Fremdbestand fehlt/verändert", rep["tolerated_missing"]),
                        ("Pending deklariert, live vorhanden", rep["pending_live"]),
                        ("Pending deklariert, nicht live", rep["pending_missing"])):
        print("%s: %d" % (label, len(rows)))
        for r in rows:
            print("   - %s" % " | ".join(str(x) for x in r))
    print("Regel-Reihenfolge (acls/ssh) abweichend: %d" % len(rep["order"]))
    for r in rep["order"]:
        print("   - %s" % r)


def null_diff_ok(rep):
    """STRENGER Null-Diff (Modell ≡ Live): kein Fehlend/Geändert/Fremd UND
    identische Regel-Reihenfolge (acls/ssh). Formatierung/Kommentare bleiben
    unberücksichtigt. Kein dokumentierter Fremdbestand toleriert."""
    return (not rep["missing"] and not rep["changed"] and not rep["foreign"]
            and not rep["order"])


def tolerant_diff_ok(rep):
    """Toleranz-Null-Diff (Owner-Entscheid 2026-09-11): Verwalteter Teil exakt
    (kein Fehlend/Geändert) + dokumentierter Fremdbestand vollständig/unverändert
    (kein tolerated_missing) + kein unerwarteter Fremdbestand (kein foreign) +
    Reihenfolge/Positionen (inkl. Fremdbestand-Block) eingehalten.
    Formatierung/Kommentare bleiben unberücksichtigt."""
    return (not rep["missing"] and not rep["changed"] and not rep["foreign"]
            and not rep["tolerated_missing"] and not rep["order"])


def print_tolerance_info(tol, path):
    """Kompakte Zusammenfassung der aktiven Toleranzliste (nur Doku)."""
    n_tol = sum(len(tol["sections"][s]["entries"]) for s in ("acls", "ssh")) \
        + len(tol["tagOwners"])
    print("--- Fremdbestand-Toleranzliste ---")
    print("Quelle: %s (aktive Einträge: %d)" % (path, n_tol))
    for section in ("acls", "ssh"):
        blk = tol["sections"][section]
        groups = {}
        for t in blk["entries"]:
            groups[t["group"]] = groups.get(t["group"], 0) + 1
        print("   %s: position=%s, %d Einträge (%s)"
              % (section, blk["position"], len(blk["entries"]),
                 ", ".join("%s=%d" % (g, n) for g, n in sorted(groups.items()))))
    if tol["pending"]:
        print("   ⚠️  %d offener Platzhalter (NICHT toleriert, Owner-Entscheid ausstehend):"
              % len(tol["pending"]))
        for p in tol["pending"]:
            print("      - [%s/%s] %s" % (p["section"], p["group"], p["reason"]))


# ---------------------------------------------------------------------------
# IaC4-Vorbedingungen (IaC4-first) – Migration aus HA-PR #54
# ---------------------------------------------------------------------------
# Die HA-Gruppen setzen auf die IaC4-Baseline (`tag:ia4`) auf. Die frühere
# Vorab-Prüfung verglich byte-exakte Textanker gegen die Live-Policy; die
# Tailscale-API RE-SERIALISIERT die Policy (Whitespace/Block-Layout/Trailing-
# Kommas), wodurch der Anker nicht mehr matchte (Live-Befund 2026-09-11). Der
# HA-PR #54 hat die Vorab-Prüfung deshalb auf die GEPARSTE Struktur (huJSON→JSON)
# umgestellt und die Prüfung an die tatsächlich eingefügten Regeln gekoppelt
# (Scope). Beides ist hier 1:1 auf die SSoT-Gruppen abgebildet.
PRECOND_DESC = {
    "ha-tagowners": "IaC4-tagOwners (tag:ia4 -> autogroup:admin)",
    "ha-ssh":       "IaC4-ssh-Block (dst tag:ia4)",
    "ha-acl":       "IaC4-acl-Block (src tag:ia4 -> dst tag:ia4:*)",
    "ha-runner":    "IaC4-acl-Block (src tag:ia4 -> dst tag:ia4:*)",
    "owner-8123":   "IaC4-acl-Block (src tag:ia4 -> dst tag:ia4:*)",
    "mqtt-1883":    "IaC4-acl-Block (src tag:ia4 -> dst tag:ia4:*)",
    "energie-read": "IaC4-acl-Block (src tag:ia4 -> dst tag:ia4:*)",
}


def _list_has(v, item):
    """True, wenn v eine Liste ist, die item enthält (None/kein-Liste = False)."""
    return isinstance(v, list) and item in v


def precondition_ok(pol, group):
    """Semantische IaC4-Vorbedingung der Gruppe gegen die GEPARSTE Policy
    (tolerant gegen Whitespace/Layout/Kommentare). Reihenfolge IaC4-first: die
    HA-Gruppen setzen auf die `iac4`-Baseline auf. Fehlt sie -> False (der
    Aufrufer meldet PRECOND_DESC[group] + bricht OHNE POST ab).
      ha-tagowners -> tagOwners: 'tag:ia4' enthält 'autogroup:admin'
      ha-ssh       -> ssh: eine Regel mit dst 'tag:ia4'
      übrige HA    -> acls: eine Regel src 'tag:ia4' -> dst 'tag:ia4:*'
    `iac4` (und Unbekanntes) hat keine Vorbedingung -> True."""
    if not isinstance(pol, dict):
        return False
    if group == "ha-tagowners":
        to = pol.get("tagOwners")
        return isinstance(to, dict) and _list_has(to.get("tag:ia4"),
                                                 "autogroup:admin")
    if group == "ha-ssh":
        return any(isinstance(r, dict) and _list_has(r.get("dst"), "tag:ia4")
                   for r in (pol.get("ssh") or []))
    if group in ("ha-acl", "ha-runner", "owner-8123", "mqtt-1883",
                 "energie-read"):
        return any(isinstance(r, dict) and _list_has(r.get("src"), "tag:ia4")
                   and _list_has(r.get("dst"), "tag:ia4:*")
                   for r in (pol.get("acls") or []))
    return True


def _policy_dict(entries_live, to_insert):
    """Live-Einträge (+ geplante Einfügungen) als einfaches Policy-Dict – für
    die Vorbedingungs-Prüfung (live + was dieser Lauf gleich einfügt)."""
    pol = {"tagOwners": {}, "acls": [], "ssh": []}
    for e in entries_live["tagOwners"]:
        pol["tagOwners"][e.key] = e.obj
    for s in ("acls", "ssh"):
        pol[s] = [e.obj for e in entries_live[s]]
    for e in to_insert:
        if e.section == "tagOwners":
            pol["tagOwners"][e.key] = e.obj
        else:
            pol[e.section].append(e.obj)
    return pol


# ---------------------------------------------------------------------------
# Additive Einfügung (Text in den Abschnitt, ohne Bestandszeilen zu verändern)
# ---------------------------------------------------------------------------
def _detect_indent(text, span):
    start, end = span
    m = re.search(r"\n([ \t]+)\S", text[start:end])
    return m.group(1) if m else "    "


def _render_tagowner(key, value, indent):
    return '\n%s"%s": %s,' % (indent, key, json.dumps(value, ensure_ascii=False))


def _render_rule(obj, indent):
    inner = ",\n".join(
        '%s  "%s": %s' % (indent, k, json.dumps(v, ensure_ascii=False))
        for k, v in obj.items())
    return "\n%s{\n%s\n%s}," % (indent, inner, indent)


def _entry_ident(e):
    """Vergleichs-Identität eines Eintrags für die Ordnungs-Zuordnung:
    tagOwners über den Key, acls/ssh über die kanonische Regel."""
    return e.key if e.section == "tagOwners" else e.canon


def _iter_section_entries(raw_text, section, start, end):
    """Top-level Einträge eines Abschnitts in Dokument-Reihenfolge →
    (span_start, span_end, ident). tagOwners: ident = Key; acls/ssh: ident = canon."""
    items = []
    if section == "tagOwners":
        for key, _vs, ve, ks in _iter_tagowners(raw_text, start, end):
            items.append((ks, ve, key))
    else:
        for os_, oe in _iter_objects(raw_text, start, end):
            items.append((os_, oe, canon(parse_policy(raw_text[os_:oe]))))
    return items


def _line_start_after_prev_nl(text, pos, lo):
    """Einfüge-Position VOR der Einrückung des Eintrags bei `pos`: der
    vorangehende Zeilenumbruch (pos wird über die Einrückung zurückgeführt).
    Liegt kein Umbruch davor (kompaktes JSON), bleibt `pos`. So bleiben alle
    bestehenden Zeilen byte-unverändert (nur neue Zeilen kommen hinzu)."""
    k = pos
    while k > lo and text[k - 1] in " \t":
        k -= 1
    if k > lo and text[k - 1] == "\n":
        return k - 1
    return pos


def insert_entries(raw_text, section, entries, model_entries=None):
    """Fügt die Einträge rein additiv in `raw_text` ein (bestehende Zeilen werden
    NIE verändert/entfernt; nur neue Zeilen kommen hinzu). Rückgabe: neuer Text.

    Ist das Modell (`model_entries` = ALLE Einträge des Abschnitts in
    SSoT-Reihenfolge) gegeben, wird jeder neue Eintrag an seiner MODELL-Position
    relativ zu den vorhandenen Einträgen eingefügt, sodass die Regel-Reihenfolge
    des Modells erhalten bleibt (Owner-Entscheid F4: Reihenfolge zählt). Ohne
    Modell wird direkt nach der öffnenden Klammer eingefügt (Alt-Verhalten)."""
    span = _section_span(raw_text, section)
    if span is None:
        raise ValueError("Abschnitt %s nicht in Live-Policy gefunden" % section)
    start, end = span
    indent = _detect_indent(raw_text, span)
    if section == "tagOwners":
        def render(e):
            return _render_tagowner(e.key, e.obj, indent)
    else:
        def render(e):
            return _render_rule(e.obj, indent)

    if model_entries is None:
        frag = "".join(render(e) for e in entries)
        return raw_text[:start] + frag + raw_text[start:]

    order = {}
    for i, e in enumerate(model_entries):
        order.setdefault(_entry_ident(e), i)
    existing = _iter_section_entries(raw_text, section, start, end)
    # Einfüge-Position je neuem Eintrag = unmittelbar vor den ersten vorhandenen
    # Eintrag, der im Modell NACH ihm steht; sonst ans Abschnitts-Ende. Jeweils
    # VOR der Einrückung (nach dem vorangehenden Zeilenumbruch), damit bestehende
    # Zeilen unverändert bleiben.
    buckets = {}
    for e in entries:
        mpos = order.get(_entry_ident(e), len(model_entries))
        anchor = end
        for ss, _se, ident in existing:
            if order.get(ident, -1) > mpos:
                anchor = ss
                break
        target = _line_start_after_prev_nl(raw_text, anchor, start)
        buckets.setdefault(target, []).append((mpos, e))
    out = raw_text
    for target in sorted(buckets, reverse=True):
        frag = "".join(render(e)
                       for _p, e in sorted(buckets[target], key=lambda t: t[0]))
        out = out[:target] + frag + out[target:]
    return out


# ---------------------------------------------------------------------------
# Semantische Additivitäts-Prüfung nach POST
# ---------------------------------------------------------------------------
def semantic_additivity(backup_text, verify_text, inserted_entries):
    """Multimengen-Vergleich: keine Bestands-Regel entfernt/geändert; nur die
    eingefügten Einträge dürfen hinzugekommen sein. Liefert (ok, details)."""
    details = []
    try:
        b = parse_live(backup_text)
        v = parse_live(verify_text)
    except ValueError as exc:
        return False, ["ACL-Policy nicht parsebar (huJSON→JSON): %s" % exc]

    bkeys = _by_key(b["tagOwners"])
    vkeys = _by_key(v["tagOwners"])
    for key, es in bkeys.items():
        if key not in vkeys:
            details.append("tagOwners: Bestands-Eintrag '%s' fehlt nach POST" % key)
        elif vkeys[key][0].canon != es[0].canon:
            details.append("tagOwners: Bestands-Eintrag '%s' geändert" % key)
    allowed_to = {(e.key, e.canon) for e in inserted_entries if e.section == "tagOwners"}
    for key in vkeys:
        if key not in bkeys and (key, vkeys[key][0].canon) not in allowed_to:
            details.append("tagOwners: fremder Eintrag '%s' hinzugekommen" % key)

    for section in ("acls", "ssh"):
        bcnt = Counter(e.canon for e in b[section])
        vcnt = Counter(e.canon for e in v[section])
        mobj = {e.canon: e for e in b[section]}
        for c, n in bcnt.items():
            if vcnt.get(c, 0) < n:
                details.append("%s: Bestands-Regel fehlt/geändert: %s"
                               % (section, _short(mobj[c].obj)))
        allowed = {e.canon for e in inserted_entries if e.section == section}
        lobj = {e.canon: e for e in v[section]}
        for c, n in vcnt.items():
            if n > bcnt.get(c, 0) and c not in allowed:
                details.append("%s: fremde Regel hinzugekommen: %s"
                               % (section, _short(lobj[c].obj)))
    return (not details), details


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(
        description="Einheitliches additives Tailscale-ACL-Werkzeug (SSoT: "
                    "acl/tailscale-acl.hujson). Governance: Apply nur manuell, "
                    "nach --dry-run + Review + Owner-Go.")
    p.add_argument("--model", default=MODEL_PATH,
                   help="SSoT-Datei (default: acl/tailscale-acl.hujson)")
    p.add_argument("--rule", action="append", metavar="GRUPPE", default=None,
                   help="Regel-Auswahl (repeatable): iac4 | 1..7 | ha-tagowners | "
                        "ha-acl | ha-ssh | ha-runner | owner-8123 | console-owner | "
                        "mqtt-1883 | energie-read | all.")
    p.add_argument("--rules", default=None,
                   help="Regel-Auswahl kommagetrennt (Workflow-Input), z. B. 'iac4' "
                        "oder '1,4'. Alternativ zu wiederholtem --rule.")
    p.add_argument("--dry-run", action="store_true",
                   help="Nur Analyse (GET/--file): semantischer Diff + geplante "
                        "Einfügungen, KEIN POST/Backup.")
    p.add_argument("--verify", action="store_true",
                   help="Null-Diff-Prüfung (semantisch, inkl. Regel-Reihenfolge): "
                        "exit != 0 bei Drift (Fehlend/Geändert/Fremd/Reihenfolge). "
                        "Mit Positional <export-datei> reproduzierbar offline. "
                        "Mit --tolerated-foreign wird dokumentierter Fremdbestand "
                        "toleriert (verwalteter Teil exakt + Fremdbestand unverändert).")
    p.add_argument("--tolerated-foreign", nargs="?", default=None,
                   const=DEFAULT_TOLERATED_PATH, metavar="DATEI",
                   help="Fremdbestand-Toleranzliste (JSON) für --verify/--dry-run; "
                        "ohne Wert: %s. Nur Einträge mit status='tolerated' werden "
                        "toleriert. Ohne dieses Flag bleibt der strikte Null-Diff "
                        "(jeder Fremdbestand = Drift)." % DEFAULT_TOLERATED_PATH)
    p.add_argument("--export", action="store_true",
                   help="Inventar: read-only GET → rohe huJSON + SHA256 nach --out.")
    p.add_argument("--out", default=None,
                   help="Zielpfad für --export (default: acl/live-export-<sha8>.hujson)")
    p.add_argument("--file", default=None,
                   help="Statt Live-GET eine lokale huJSON-Datei lesen (offline; "
                        "für --dry-run/--verify/--export-Test).")
    p.add_argument("snapshot", nargs="?", default=None,
                   help="Optionale Live-huJSON-Datei (Positional, wie --file); z. B. "
                        "`--verify acl/live-export-<sha8>.hujson` für den "
                        "reproduzierbaren Null-Diff gegen einen Export.")
    p.add_argument("--check-model", action="store_true",
                   help="Nur SSoT-Gates prüfen (Parsing, Tag-Referenzen, Marker); kein Netz.")
    p.add_argument("--confirm", default=None,
                   help="Governance-Token für den APPLY (muss 'APPLY-ACL' sein).")
    return p.parse_args()


def _resolve_groups(args):
    raw = []
    if args.rules:
        raw += [x for x in re.split(r"[,\s]+", args.rules) if x]
    if args.rule:
        raw += args.rule
    sel = set()
    for item in raw:
        key = item.strip().lower()
        if key == "all":
            sel.update(GROUP_NAMES)
            continue
        grp = GROUP_ALIASES.get(key)
        if grp is None:
            print("❌ unbekannte Gruppe %r – erlaubt: %s, 1..7 oder 'all'"
                  % (item, ", ".join(GROUP_NAMES)))
            sys.exit(2)
        sel.add(grp)
    return [g for g in GROUP_NAMES if g in sel]


def api(method, data=None):
    headers = {"Authorization": "Bearer %s" % TOKEN}
    if data is not None:
        headers["Content-Type"] = "application/hujson"
    req = urllib.request.Request("%s/%s/acl" % (API, TAILNET), method=method,
                                 headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        return -1, "Transportfehler: %s" % e.reason


def rollback(backup_text):
    code, resp = api("POST", backup_text.encode("utf-8"))
    if code == 200:
        print("✅ Rollback ok (HTTP 200)")
    else:
        print("❌ Rollback fehlgeschlagen (HTTP %s): %s" % (code, resp[:200]))


def _load_live(args):
    """Live-Policy-Text laden – via --file/Positional-<export> (offline) oder GET."""
    path = args.file or args.snapshot
    if path:
        with open(path, encoding="utf-8") as f:
            return f.read(), "file:%s" % path
    if not TAILNET or not TOKEN:
        print("❌ TS_TAILNET + (TS_TOKEN|TS_API_KEY) erforderlich (env) – "
              "oder --file für den Offline-Modus")
        sys.exit(1)
    code, text = api("GET")
    if code != 200:
        print("❌ GET /acl: HTTP %s\n%s" % (code, text[:300]))
        sys.exit(1)
    return text, "live"


def main():
    args = parse_args()
    try:
        model, _ = parse_model(args.model)
    except (OSError, ValueError) as exc:
        print("❌ SSoT %s nicht lesbar/parsebar: %s" % (args.model, exc))
        return 1
    gates = model_gates(model)
    if args.check_model:
        if gates:
            for g in gates:
                print("❌ " + g)
            return 1
        n = sum(len(model[s]) for s in SECTION_ORDER)
        print("✅ SSoT ok: %d Einträge, Reihenfolge %s, Tag-Referenzen gültig"
              % (n, " → ".join(SECTION_ORDER)))
        return 0
    if gates:
        print("❌ SSoT-Gates verletzt:")
        for g in gates:
            print("   - " + g)
        return 1

    live_text, source = _load_live(args)
    try:
        live = parse_live(live_text)
    except ValueError as exc:
        print("❌ Live-Policy nicht parsebar (huJSON→JSON): %s" % exc)
        return 1

    if args.export:
        out = args.out or os.path.join(
            REPO_ROOT, "acl", "live-export-%s.hujson" % _sha256(live_text)[:8])
        with open(out, "w", encoding="utf-8") as f:
            f.write(live_text)
        sha = _sha256(live_text)
        with open(out + ".sha256", "w", encoding="utf-8") as f:
            f.write("%s  %s\n" % (sha, os.path.basename(out)))
        print("📤 Export (%s): %s (%d Bytes)" % (source, out, len(live_text.encode())))
        print("🔑 SHA256: %s" % sha)
        return 0

    # Fremdbestand-Toleranzliste (optional): erlaubt --verify/--dry-run mit
    # dokumentiertem, nicht verwaltetem Live-Bestand (Owner-Entscheid 2026-09-11).
    tol = None
    if args.tolerated_foreign is not None:
        try:
            tol = load_tolerated(args.tolerated_foreign)
        except (OSError, ValueError) as exc:
            print("❌ Toleranzliste nicht lesbar/ungültig (%s): %s"
                  % (args.tolerated_foreign, exc))
            return 1

    rep = diff_model_vs_live(model, live, tol)
    if args.verify:
        print_diff(rep)
        if tol is not None:
            print_tolerance_info(tol, args.tolerated_foreign)
            if tolerant_diff_ok(rep):
                print("✅ Verify (mit Toleranz): verwalteter Teil ≡ Modell "
                      "(semantisch, inkl. Reihenfolge); dokumentierter Fremdbestand "
                      "vollständig/unverändert an seinen Live-Positionen; kein "
                      "unerwarteter Fremdbestand")
                return 0
            print("❌ Drift (mit Toleranz): verwalteter Teil und/oder dokumentierter "
                  "Fremdbestand weichen ab (siehe oben)")
            return 1
        if null_diff_ok(rep):
            print("✅ Null-Diff: Modell ≡ Live (semantisch, inkl. Regel-Reihenfolge; "
                  "Formatierung/Kommentare ignoriert)")
            return 0
        print("❌ Drift: Modell und Live weichen ab (siehe oben)")
        return 1

    # Selektion
    selected = _resolve_groups(args)
    pending_groups = {e.group for s in SECTION_ORDER for e in model[s] if e.pending}

    # Zu einfügende Einträge = fehlende Einträge der gewählten Gruppen
    to_insert = []

    def missing_entries(group):
        out = []
        for section in SECTION_ORDER:
            live_c = Counter(e.ident() for e in live[section])
            for e in model[section]:
                if e.group != group:
                    continue
                if live_c.get(e.ident(), 0) < 1:
                    out.append(e)
        return out

    if selected:
        for g in selected:
            for e in missing_entries(g):
                to_insert.append(e)

    # IaC4-Vorbedingung (IaC4-first, übernommen aus HA-PR #54): nur für Gruppen,
    # die DIESER Lauf tatsächlich einfügt (Scope-Kopplung); semantisch gegen
    # Live + geplante Einfügungen. Fehlt die IaC4-Baseline -> Abbruch OHNE POST.
    groups_to_insert = {e.group for e in to_insert}
    precond_missing = [g for g in GROUP_NAMES
                       if g in groups_to_insert
                       and not precondition_ok(_policy_dict(live, to_insert), g)]
    if precond_missing:
        for g in precond_missing:
            print("❌ Vorbedingung fehlt für Gruppe '%s': %s nicht gefunden – "
                  "Reihenfolge IaC4-first (zuerst 'iac4' anwenden); Abbruch OHNE POST"
                  % (g, PRECOND_DESC[g]))
        return 1

    if args.dry_run or not selected:
        print_diff(rep)
        if tol is not None:
            print_tolerance_info(tol, args.tolerated_foreign)
        print("--- Plan (selektiv) ---")
        if not selected:
            print("ℹ️ Keine Gruppe gewählt (--rule/--rules) – reine Analyse. "
                  "Apply erfordert eine Auswahl.")
        else:
            for e in to_insert:
                print("   + [%s] %s" % (e.group, e.rule_id()))
        for g in sorted(pending_groups & set(selected)):
            print("⚠️ Gruppe '%s' enthält pending-Regeln (streitig/ausstehend) – "
                  "nur bei bewusster Freigabe einführen" % g)
        removed = 0
        print("   %d Einfügung(en), %d Entfernung(en) – rein additiv"
              % (len(to_insert), removed))
        if not args.file and not args.snapshot:
            print("ℹ️ Kein POST ausgeführt (Dry-Run).")
        return 0

    # APPLY
    if args.confirm != "APPLY-ACL":
        print("❌ APPLY erfordert --confirm APPLY-ACL (Governance: nur manuell, "
              "nach --dry-run + Review + Owner-Go). Abbruch OHNE POST.")
        return 2
    if not to_insert:
        print("✅ Gewählte Gruppe(n) %s bereits vollständig vorhanden – no-op "
              "(idempotent), kein POST" % ", ".join(selected))
        return 0
    if args.file or args.snapshot:
        print("❌ APPLY ist mit --file/--verify-Datei deaktiviert (nur Dry-Run/"
              "Verify/Export offline).")
        return 2

    # SICHERHEITS-EIGENSCHAFT (bindend, nicht verhandelbar): Der Applier liest die
    # LIVE-Policy und fügt rein additiv ein – er schreibt NIE die Modell-Datei als
    # Gesamtdatei über die Live-Policy. Sonst würden nicht übernommene Einträge
    # (Fremdbestand: IaC3-/Konsolen-Regeln, siehe acl/tolerated-foreign.json) GELÖSCHT.
    # Basis ist ausschließlich `live_text` (GET); `new_text` entsteht daraus durch
    # additive Text-Einfügungen (insert_entries verändert keine Bestandszeilen).
    backup_text = live_text
    with open("/tmp/acl-backup.json", "w", encoding="utf-8") as f:
        f.write(backup_text)
    print("💾 Backup: /tmp/acl-backup.json")

    new_text = live_text
    # nach Abschnitt gruppieren, kanonische Einfüge-Reihenfolge; neue Einträge
    # werden an ihrer MODELL-Position eingefügt (Regel-Reihenfolge bleibt erhalten)
    for section in SECTION_ORDER:
        ents = [e for e in to_insert if e.section == section]
        if ents:
            new_text = insert_entries(new_text, section, ents, model[section])
            for e in ents:
                print("➕ [%s] eingefügt: %s" % (e.group, e.rule_id()))

    # Pre-POST-Guard (defensiv): beweist VOR dem POST, dass die Einfügung rein
    # additiv ist – kein Bestands-Eintrag (inkl. Fremdbestand) entfernt/geändert,
    # nur die gewählten Einträge hinzugefügt. Schlägt er fehl -> Abbruch OHNE POST.
    ok_pre, det_pre = semantic_additivity(live_text, new_text, to_insert)
    if not ok_pre:
        print("❌ Pre-POST-Guard: Einfügung wäre NICHT rein additiv "
              "(Bestands-Eintrag würde entfernt/geändert) – Abbruch OHNE POST")
        for d in det_pre:
            print("   - " + d)
        return 1
    print("✅ Pre-POST-Guard: rein additiv (kein Bestands-/Fremdbestand-Eintrag "
          "entfernt/geändert)")

    code, resp = api("POST", new_text.encode("utf-8"))
    if code != 200:
        print("❌ POST /acl: HTTP %s\n%s" % (code, resp[:300]))
        print("↩️ Rollback…")
        rollback(backup_text)
        return 1

    code, verify_text = api("GET")
    if code != 200:
        print("❌ GET (Verify): HTTP %s – Rollback nötig" % code)
        rollback(backup_text)
        return 1

    checks = {}
    vmodel = parse_live(verify_text)
    for section in SECTION_ORDER:
        vcnt = Counter(e.ident() for e in vmodel[section])
        bcnt = Counter(e.ident() for e in live[section])
        for e in to_insert:
            if e.section != section:
                continue
            got = vcnt.get(e.ident(), 0)
            exp = bcnt.get(e.ident(), 0) + 1
            checks["%s exakt +1 (count==1-Gate): %s" % (section, e.rule_id())] = (got == exp)
    ok_add, details = semantic_additivity(backup_text, verify_text, to_insert)
    checks["Additivität (semantisch: keine Bestands-Regel entfernt/geändert)"] = ok_add

    for d in details:
        print("  " + d)
    ok = all(checks.values())
    for name, res in checks.items():
        print(("✅" if res else "❌") + " " + name)
    if not ok:
        print("↩️ Rollback…")
        rollback(backup_text)
        return 1
    print("🎉 ACL-Erweiterung bestanden (additiv, verifiziert) – Gruppen: %s"
          % ", ".join(selected))
    print("ℹ️ Governance: kein weiterer Apply ohne erneute Freigabe.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
