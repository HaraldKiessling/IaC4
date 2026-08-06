#!/usr/bin/env python3
"""Discovery-Kern v3.0 – Ein-Job-Fast-Path (Workflow-05-Performance-Optimierung).

Korrigiert/erweitert nach CLI-Fakten + Review-Befunden R01-R08 (2026-08-06):
  Δ1: Telegram-Pairing via `openclaw pairing list <channel> --json` (ID-Feld:
      code), Device via `openclaw devices list --json` (ID-Feld: deviceId).
  Δ2: ZWEI Approve-Kommandos: `openclaw pairing approve telegram <CODE>` vs.
      `openclaw devices approve <ID>` – Templates liegen HIER (approve_step.py
      re-exportiert sie, DRY ohne Zirkularimport).
  v3.0 (Ein-Job-Design, R02/R08-Umsetzung):
    - group_by_vps(): Instanz-Map nach target gruppieren → 1 SSH pro VPS
      statt pro Instanz (Design §4).
    - build_ein_job_remote_cmd(): Remote-Schleife mit JSON-/APPROVE-/FOUND-
      Markern; type=both fragt pairing UND devices in DERSELBEN Session ab;
      Approve-Befehl typabhängig; `|| true` fail-safe; break beim ersten Fund.
    - parse_ein_job_output(): parst die Marker-Ausgabe und verifiziert den
      ID-Match in Python (R08: KEIN jq auf den VPS – Remote-Entscheidung via
      grep auf das JSON-Textfeld, autoritative Verifikation hier).
    - run_discovery(): VPS-Gruppen-Loop; Approve direkt in der SSH-Session
      beim Fund – auch auf prod (Owner-Entscheidung: kein Environment-Gate).
    - B2 (2. Review, Blocker): Approve-Erfolg wird geprüft – KEIN `|| true`
      um den Approve; FOUND=1 erst nach Exit-Code 0; APPROVE-FAILED-Marker
      bei Fehler → Workflow meldet status=error statt falschem Erfolg.
  Bausteine aus v2.2 (behalten): Zwei-Format-ID-Validierung + Typ-Ableitung
  (--validate-id), UNREACHABLE-Liste, Break-Semantik, injizierbare
  Netzwerk-/SSH-Calls (unit-testbar ohne echte Tailscale-/SSH-Zugriffe).

Empirisch (Sandbox, OpenClaw 2026.7.1, 2026-08-06):
  - `openclaw pairing list telegram --json` → {"channel": "telegram", "requests": []}
  - `openclaw devices list --json` → {"pending": [...], "paired": [...]}
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

# ── ID-Formate v2.2 (disjunkte Regex-Mengen, Δ3/Δ5) ──
# Telegram-Pairing-Kurzcode: 6-12 Zeichen A-Z0-9 (kalibriert an QVDCXJEM, 8 Zeichen)
TELEGRAM_CODE_RE = re.compile(r"^[A-Z0-9]{6,12}$")
# Device-ID: 36-128 Zeichen Hex (mit optionalen Bindestrichen für UUIDs);
# kalibriert an 9df47d697653fb4069407734e06849b342738ed3e9ec4b172402aca911925392
# (64 Hex, kein Dash) und b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5 (UUID-Stil)
DEVICE_ID_RE = re.compile(r"^[0-9a-fA-F-]{36,128}$")
# Instanz: oc1…ocN, kein oc0 (Review Minor #4)
INSTANCE_RE = re.compile(r"^oc[1-9][0-9]*$")

VALID_TYPES = ("auto", "telegram", "device", "both")
# Typen, die als Remote-Schleifen-Quelle zulässig sind (auto ist aufgelöst)
REMOTE_TYPES = ("telegram", "device", "both")

SSH_OPTS = [
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "ConnectTimeout=10",
    "-o", "LogLevel=ERROR",
]
# Δ1: getrennte Discovery-Quellen je Typ (werden in der Remote-Schleife
# pro Instanz ausgeführt; 2>/dev/null + `|| true` = fail-safe bei Instanz-Down)
PAIRING_LIST_CMD = (
    "sudo docker exec openclaw-{instance} openclaw pairing list telegram --json 2>/dev/null"
)
DEVICES_LIST_CMD = (
    "sudo docker exec openclaw-{instance} openclaw devices list --json 2>/dev/null"
)
# Δ2: Approve-Kommandos je Typ (Templates HIER; approve_step.py re-exportiert)
APPROVE_CMD_TEMPLATES = {
    "telegram": "sudo docker exec openclaw-{instance} openclaw pairing approve telegram {request_id}",
    "device": "sudo docker exec openclaw-{instance} openclaw devices approve {request_id}",
}

# Remote-Marker (v3.0): Label = Instanz [:Typ] – der Typ-Suffix macht type=both
# in einer SSH-Session eindeutig parsebar (R02).
_LABEL_RE = r"oc[1-9][0-9]*(?::(?:telegram|device))?"
JSON_BLOCK_RE = re.compile(
    rf"---JSON-BEGIN:(?P<label>{_LABEL_RE})---\n(?P<body>.*?)---JSON-END:(?P=label)---",
    re.DOTALL,
)
APPROVE_BLOCK_RE = re.compile(
    rf"---APPROVE-BEGIN:(?P<label>{_LABEL_RE})---\n(?P<body>.*?)---APPROVE-END:(?P=label)---",
    re.DOTALL,
)
# B2 (2. Review, Blocker): Approve-Fehler werden explizit markiert – FOUND=1
# wird erst NACH Exit-Code 0 des Approve-Befehls gesetzt (kein falscher Erfolg).
APPROVE_FAILED_RE = re.compile(rf"---APPROVE-FAILED:(?P<label>{_LABEL_RE})---")
FOUND_RE = re.compile(r"---FOUND:(?P<found>[01])---")

API_TIMEOUT = 30
# Remote-Loop über alle Instanzen eines VPS (bei type=both 2 Quellen pro
# Instanz) – grosszuegiger Timeout als der alte Pro-Instanz-Call.
SSH_TIMEOUT = 60

# Array-Key + ID-Feld je Quelle (für den Remote-Match ohne jq, R08)
_SOURCE_ARRAY_KEY = {"telegram": "requests", "device": "pending"}
_SOURCE_ID_FIELD = {"telegram": "code", "device": "deviceId"}


def node_for_target(target: str) -> str:
    """NODE-Konvention M1a: 1:1 target<->VPS-Hostname (VPS-Combi erst M5)."""
    return f"vps-{target}"


# ── Validierung + Typ-Ableitung (v2.2, Δ3/Δ4/Δ5) ──


def derive_type(id_str: str) -> str:
    """Typ-Ableitung aus ID-Format (ohne Validierung): telegram|device|unknown."""
    if TELEGRAM_CODE_RE.match(id_str):
        return "telegram"
    if DEVICE_ID_RE.match(id_str):
        return "device"
    return "unknown"


def validate_and_classify_id(id_str: str, explicit_type: str = "auto") -> Tuple[bool, str, str]:
    """Validiert und klassifiziert eine Request-ID.

    Returns: (is_valid, derived_type, error_message)
    explicit_type: auto (aus Format ableiten) | telegram | device | both
    """
    if explicit_type == "telegram":
        if TELEGRAM_CODE_RE.match(id_str):
            return (True, "telegram", "")
        return (False, "", f"ID '{id_str}' entspricht nicht dem Telegram-Kurzcode-Format ^[A-Z0-9]{{6,12}}$")

    if explicit_type == "device":
        if DEVICE_ID_RE.match(id_str):
            return (True, "device", "")
        return (False, "", f"ID '{id_str}' entspricht nicht dem Device-ID-Format ^[0-9a-fA-F-]{{36,128}}$")

    if explicit_type == "both":
        if TELEGRAM_CODE_RE.match(id_str) or DEVICE_ID_RE.match(id_str):
            return (True, "both", "")
        return (False, "", f"ID '{id_str}' passt weder zu Telegram-Kurzcode noch Device-ID")

    # auto: aus Format ableiten
    if TELEGRAM_CODE_RE.match(id_str):
        return (True, "telegram", "")
    if DEVICE_ID_RE.match(id_str):
        return (True, "device", "")
    return (False, "", f"ID '{id_str}' passt zu keinem bekannten Format "
                       f"(Telegram: ^[A-Z0-9]{{6,12}}, Device: ^[0-9a-fA-F-]{{36,128}})")


def validate_type(type_str: str) -> None:
    """Typ-Filter validieren (auto|telegram|device|both), sonst ValueError."""
    if type_str not in VALID_TYPES:
        raise ValueError(
            f"Ungueltiger Typ-Filter: '{type_str}'. Erlaubt: {', '.join(VALID_TYPES)}."
        )


def validate_request_id(request_id: str, explicit_type: str = "auto") -> None:
    """ID-Format validieren (v2.2 Zwei-Format-Regex), sonst ValueError."""
    valid, _, err = validate_and_classify_id(request_id, explicit_type)
    if not valid:
        raise ValueError(err)


def validate_instance(instance: str) -> None:
    """Instanz-Name validieren (^oc[1-9][0-9]*$), sonst ValueError (Minor #4)."""
    if not INSTANCE_RE.fullmatch(instance):
        raise ValueError(
            f"Ungueltige Instanz: '{instance}'. Erlaubt: oc1, oc2, ... (kein oc0)."
        )


def filter_instance_map(
    instance_map: List[Tuple[str, str]],
    *,
    target_filter: str = "both",
    instance_filter: str = "all",
) -> List[Tuple[str, str]]:
    """SSoT-Filter: schraenkt die Map auf passende target/instance ein."""
    result: List[Tuple[str, str]] = []
    for name, target in instance_map:
        if target_filter not in ("both", target):
            continue
        if instance_filter not in ("all", name):
            continue
        result.append((name, target))
    return result


# ── Discovery-Result (einheitliches Teilschema, Minor #7; v3.0: +approved) ──


@dataclass
class DiscoveryResult:
    request_id: str
    instance: str
    target: str
    vps_ip: Optional[str]
    found_type: str = "unknown"  # telegram|device (über welchen Pfad gefunden)
    scanned: List[str] = field(default_factory=list)
    unreachable: List[str] = field(default_factory=list)
    # v3.0 (Ein-Job): approved=True wenn der Approve direkt in der SSH-Session
    # bestätigt wurde (APPROVE-Marker + FOUND=1); approve_output = Session-Text
    approved: bool = False
    approve_output: str = ""


class RequestNotFoundError(Exception):
    """Request-ID auf keiner enabled Instanz gefunden."""

    def __init__(self, request_id: str, unreachable: List[str]):
        self.request_id = request_id
        self.unreachable = unreachable
        lines = [f"Request-ID '{request_id}' auf keiner enabled Instanz gefunden"]
        lines.append(
            f"Uebersprungen (VPS down): {' '.join(unreachable) if unreachable else 'keine'}"
        )
        super().__init__("\n".join(lines))


# ── Tailscale / SSH / Netzwerk (injizierbar, wie v1) ──


def fetch_tailscale_token(
    client_id: str, client_secret: str, timeout: int = API_TIMEOUT
) -> str:
    """OAuth-Token von der Tailscale-API (stdlib-only)."""
    data = urllib.parse.urlencode(
        {"client_id": client_id, "client_secret": client_secret}
    ).encode("ascii")
    req = urllib.request.Request(
        "https://api.tailscale.com/api/v2/oauth/token",
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 – Tailscale-API
        payload = json.load(resp)
    return payload["access_token"]


def resolve_vps_ip(
    tailnet: str, token: str, node: str, timeout: int = API_TIMEOUT
) -> Optional[str]:
    """VPS-IP via Tailscale-API; -1-Suffix-Fallback (Major #6)."""
    url = (
        f"https://api.tailscale.com/api/v2/tailnet/{tailnet}/devices"
        "?fields=hostname,addresses,lastSeen"
    )
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        devices = json.load(resp).get("devices", [])
    for device in devices:
        if device.get("hostname") in (node, f"{node}-1"):
            addresses = device.get("addresses") or []
            return addresses[0] if addresses else None
    return None


def run_remote_ssh(
    vps_ip: str,
    vps_user: str,
    ssh_key: str,
    remote_cmd: str,
    *,
    runner=None,
    timeout: int = SSH_TIMEOUT,
) -> str:
    """SSH: führt das Ein-Job-Remote-Skript auf dem VPS aus (1 Call pro VPS).

    Das Remote-Skript (build_ein_job_remote_cmd) wird als EIN Argument an ssh
    übergeben und von der Remote-Shell ausgeführt – Argument-Liste, keine
    lokale Shell, kein Injection-Vektor.
    """
    cmd = (
        ["ssh", "-i", ssh_key]
        + SSH_OPTS
        + [f"{vps_user}@{vps_ip}", remote_cmd]
    )
    proc = (runner or subprocess.run)(  # noqa: S603 – Befehle fix/parametrisiert, keine Shell
        cmd, capture_output=True, text=True, timeout=timeout
    )
    return proc.stdout or ""


def parse_entries(data: dict, typ: str) -> list:
    """Pending-Einträge aus dem JSON-Schema der Discovery-Quelle extrahieren.

    Empirisch (Sandbox 2026-08-06): pairing list liefert
    {"channel": "telegram", "requests": [...]}; devices list liefert
    {"pending": [...], "paired": [...]}. Defensiv: requests mit Fallback auf
    pending (F1a – Eintragsfelder des pairing-Schemas noch offen).
    """
    if typ == "telegram":
        if "requests" in data:
            return data.get("requests") or []
        return data.get("pending") or []
    return data.get("pending") or []


def entry_matches_id(entry: dict, request_id: str, typ: str) -> bool:
    """Exakter ID-Match auf dem typ-spezifischen ID-Feld (Δ3).

    telegram → Feld `code` (Kurzcode), device → Feld `deviceId` (Hex).
    """
    if typ == "telegram":
        return entry.get("code") == request_id
    if typ == "device":
        return entry.get("deviceId") == request_id
    return False


# ── Ein-Job-Remote-Loop (v3.0: 1 SSH pro VPS, Discovery + Approve) ──


def group_by_vps(instance_map: List[Tuple[str, str]]) -> "OrderedDict[str, List[str]]":
    """Gruppiert die Instanz-Map nach VPS (target) in Map-Reihenfolge.

    Eine Gruppe = eine SSH-Session (1 SSH pro VPS, Design §4 / R02).
    """
    groups: "OrderedDict[str, List[str]]" = OrderedDict()
    for name, target in instance_map:
        groups.setdefault(target, []).append(name)
    return groups


def _source_specs(typ: str) -> List[Tuple[str, str, str]]:
    """(source_typ, list_cmd_template, approve_cmd_template) je Remote-Quelle."""
    if typ == "telegram":
        return [("telegram", PAIRING_LIST_CMD, APPROVE_CMD_TEMPLATES["telegram"])]
    if typ == "device":
        return [("device", DEVICES_LIST_CMD, APPROVE_CMD_TEMPLATES["device"])]
    # both: beide Quellen in DERSELBEN Session (R02)
    return [
        ("telegram", PAIRING_LIST_CMD, APPROVE_CMD_TEMPLATES["telegram"]),
        ("device", DEVICES_LIST_CMD, APPROVE_CMD_TEMPLATES["device"]),
    ]


def build_ein_job_remote_cmd(
    typ: str,
    instances: List[str],
    request_id: str,
    *,
    approve: bool = True,
) -> str:
    """Baut das Ein-Job-Remote-Shell-Template (1 SSH pro VPS).

    Pro Instanz:
      - JSON-Block je Quelle (telegram → pairing list, device → devices list;
        type=both → beide Quellen in derselben Session, R02)
      - bei approve: ID-Match im Textpfad (grep auf das JSON-Feld des
        relevanten Arrays, KEIN jq – R08) → Approve direkt in der Session
        (---APPROVE-BEGIN/END-Marker), break-Semantik (erster Fund stoppt)
    `|| true` = fail-safe bei Instanz-Down (leere Ausgabe → kein Match).
    Am Ende: `---FOUND:${FOUND}---`.

    Raises:
        ValueError: unbekannter Typ, leere Instanzliste, ungueltige Instanz
                    oder ID (Format-Sperre, defense in depth).
    """
    if typ not in REMOTE_TYPES:
        raise ValueError(
            f"Ungueltiger Typ fuer Remote-Schleife: '{typ}'. Erlaubt: {', '.join(REMOTE_TYPES)}."
        )
    if not instances:
        raise ValueError("Keine Instanzen fuer die Remote-Schleife uebergeben.")
    for inst in instances:
        validate_instance(inst)
    validate_request_id(request_id, typ)

    single_source = len(_source_specs(typ)) == 1
    lines = ["FOUND=0", "for inst in " + " ".join(instances) + "; do"]
    for src_typ, list_tmpl, approve_tmpl in _source_specs(typ):
        var = "RESULT" if single_source else ("RESULT_TG" if src_typ == "telegram" else "RESULT_DEV")
        array_key = _SOURCE_ARRAY_KEY[src_typ]
        id_field = _SOURCE_ID_FIELD[src_typ]
        list_cmd = list_tmpl.format(instance="${inst}")

        lines.append(f'  echo "---JSON-BEGIN:${{inst}}:{src_typ}---"')
        lines.append(f"  {var}=$({list_cmd} || true)")
        lines.append(f"  printf '%s\\n' \"${var}\"")
        lines.append(f'  echo "---JSON-END:${{inst}}:{src_typ}---"')

        if approve:
            approve_cmd = approve_tmpl.format(instance="${inst}", request_id=request_id)
            # Array-Inhalt extrahieren (nur pending/requests, nicht paired) und
            # ID-Feld matchen – kein jq, nur POSIX-Tools (R08).
            lines.append(
                f"  ENTRIES=$(printf '%s' \"${var}\" | tr -d '\\n' | "
                f"sed -n 's/.*\"{array_key}\"[[:space:]]*:[[:space:]]*\\[\\([^]]*\\)\\].*/\\1/p')"
            )
            lines.append(
                f"  if printf '%s' \"$ENTRIES\" | grep -qE '\"{id_field}\"[[:space:]]*:[[:space:]]*\"{request_id}\"'; then"
            )
            lines.append(f'    echo "---APPROVE-BEGIN:${{inst}}:{src_typ}---"')
            # B2 (2. Review, Blocker): Approve-Erfolg MUSS geprüft werden –
            # KEIN `|| true` um den Approve; FOUND=1 erst NACH Exit-Code 0.
            # Bei Fehler: APPROVE-FAILED-Marker + break (laut scheitern, kein
            # falscher Erfolg im Workflow).
            lines.append(f"    if {approve_cmd} 2>&1; then")
            lines.append(f'      echo "---APPROVE-END:${{inst}}:{src_typ}---"')
            lines.append("      FOUND=1")
            lines.append("      break")
            lines.append("    else")
            lines.append(f'      echo "---APPROVE-END:${{inst}}:{src_typ}---"')
            lines.append(f'      echo "---APPROVE-FAILED:${{inst}}:{src_typ}---"')
            lines.append("      break")
            lines.append("    fi")
            lines.append("  fi")
    lines.append("done")
    lines.append('echo "---FOUND:${FOUND}---"')
    return "\n".join(lines) + "\n"


def _split_label(label: str) -> Tuple[str, str]:
    """Marker-Label → (instance, typ); typ leer wenn ohne Suffix."""
    parts = label.split(":")
    return parts[0], (parts[1] if len(parts) > 1 else "")


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def parse_ein_job_output(
    stdout: str,
    typ: str,
    request_id: str = "",
    target: str = "",
) -> Optional[DiscoveryResult]:
    """Parst die Ein-Job-Remote-Ausgabe (JSON-Blöcke + Approve-Blöcke + FOUND).

    Marker (v3.0, R02-Umsetzung): `---JSON-BEGIN:<inst>:<typ>---` …
    `---JSON-END:<inst>:<typ>---` (typ = telegram|device – auch bei type=both
    eindeutig), `---APPROVE-BEGIN:<inst>:<typ>---` … `---APPROVE-END:...---`,
    `---FOUND:1|0---`.

    Der ID-Match wird hier in Python verifiziert (parse_entries +
    entry_matches_id, R08); approved=True nur wenn zusätzlich APPROVE-Marker +
    FOUND=1 vorliegen (Approve wirklich in der Session gelaufen).

    Returns:
        DiscoveryResult wenn die ID gefunden wurde (approved je nach Markern),
        sonst None (kein Fund / fail-safe bei Instanz-Down / defekter JSON).
    """
    stdout = stdout or ""
    found_m = FOUND_RE.search(stdout)
    found_flag = bool(found_m and found_m.group("found") == "1")

    scanned: List[str] = []
    matched: Optional[Tuple[str, str, str]] = None  # (instance, typ, id)
    for blk in JSON_BLOCK_RE.finditer(stdout):
        label = blk.group("label")
        instance, block_typ = _split_label(label)
        scanned.append(f"{target}/{instance}" if target else instance)
        body = blk.group("body").strip()
        if not body:
            continue  # fail-safe: Instanz down / leere Liste
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            continue  # fail-safe: defekte Ausgabe ueberspringen
        for entry in parse_entries(data, block_typ):
            if request_id and entry_matches_id(entry, request_id, block_typ):
                matched = (
                    instance,
                    block_typ,
                    entry.get("code") or entry.get("deviceId") or request_id,
                )
                break
        if matched:
            break

    approve_blocks = list(APPROVE_BLOCK_RE.finditer(stdout))
    approve_failed = [m.group("label") for m in APPROVE_FAILED_RE.finditer(stdout)]
    # B2: approved nur wenn Approve-Block vorhanden, FOUND=1 UND kein
    # APPROVE-FAILED-Marker (Approve-Exit-Code war 0).
    approved = bool(approve_blocks) and found_flag and not approve_failed

    if matched:
        instance, block_typ, matched_id = matched
        rid = request_id or matched_id
    elif approved:
        # Approve-Marker sind autoritativ (Shell hat den Fund bestätigt) –
        # konsistent mit dem Python-Match, da beide dieselben Felder nutzen.
        instance, block_typ = _split_label(approve_blocks[0].group("label"))
        rid = request_id
    else:
        return None

    return DiscoveryResult(
        request_id=rid,
        instance=instance,
        target=target,
        vps_ip=None,  # wird von run_discovery gesetzt
        found_type=block_typ,
        scanned=_dedupe(scanned),
        unreachable=[],
        approved=approved,
        approve_output="\n".join(
            b.group("body").strip() for b in approve_blocks
        ),
    )


# ── Ein-Job-Kern (v3.0: VPS-Gruppierung + Remote-Loop mit Approve) ──


def _write_github_output(path: str, result: DiscoveryResult, derived_type: str) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(
            f"request_id={result.request_id}\n"
            f"found_target={result.target}\n"
            f"found_instance={result.instance}\n"
            f"found_vps_ip={result.vps_ip}\n"
            f"found_type={result.found_type}\n"
            f"derived_type={derived_type}\n"
        )


def run_discovery(
    instance_map: List[Tuple[str, str]],
    request_id: str,
    derived_type: str = "auto",
    *,
    resolve_ip: Optional[Callable[[str], Optional[str]]] = None,
    run_remote: Optional[Callable[[str, str], str]] = None,
    approve: bool = True,
    github_output: Optional[str] = None,
    log: Optional[Callable[[str], None]] = None,
) -> DiscoveryResult:
    """Ein-Job-Kern (v3.0): Discovery + Approve in EINER SSH-Session pro VPS.

    Gruppiert die Instanz-Map nach VPS (group_by_vps), baut pro VPS das
    Remote-Template (build_ein_job_remote_cmd) und parst die Marker-Ausgabe
    (parse_ein_job_output). Der Approve läuft direkt in der SSH-Session beim
    Fund – auch auf prod (Owner-Entscheidung: kein Environment-Gate).

    Args:
        instance_map: gefilterte [(instance_name, target), ...]
        request_id: zu suchende ID
        derived_type: telegram|device|both (auto wird aus dem ID-Format abgeleitet)
        resolve_ip(node) -> ip|None  (None = VPS down; wird als UNREACHABLE gesammelt)
        run_remote(vps_ip, remote_cmd) -> stdout der SSH-Session
        approve: True = Ein-Job (Approve in der Session), False = nur Discovery
        github_output: Pfad für $GITHUB_OUTPUT (request_id, found_*, derived_type)

    Raises:
        RequestNotFoundError: ID auf keiner Instanz gefunden (unreachable-Liste)
    """
    log = log or (lambda _msg: None)

    if derived_type == "auto":
        derived_type = derive_type(request_id)
        if derived_type == "unknown":
            raise ValueError(
                f"ID '{request_id}' passt zu keinem bekannten Format "
                f"(Telegram: ^[A-Z0-9]{{6,12}}, Device: ^[0-9a-fA-F-]{{36,128}})"
            )

    scanned: List[str] = []
    unreachable: List[str] = []

    for target, instances in group_by_vps(instance_map).items():
        node = node_for_target(target)
        ip = resolve_ip(node) if resolve_ip else None
        if not ip:
            unreachable.append(node)
            log(f"⚠️  VPS {node} nicht erreichbar, ueberspringe")
            continue

        remote_cmd = build_ein_job_remote_cmd(
            derived_type, instances, request_id, approve=approve
        )
        log(f"🔍 SSH {node} ({target}): {', '.join(instances)} – Quelle(n): {derived_type}")
        stdout = run_remote(ip, remote_cmd) if run_remote else ""

        result = parse_ein_job_output(stdout, derived_type, request_id, target)
        if result is None:
            continue  # kein Fund auf diesem VPS → nächster VPS

        result.vps_ip = ip
        result.scanned = _dedupe(scanned + result.scanned)
        result.unreachable = list(unreachable)
        if github_output:
            _write_github_output(github_output, result, derived_type)
        if result.approved:
            log(f"✅ Request-ID in {target}/{result.instance} gefunden und freigegeben "
                f"(Typ: {result.found_type})!")
        else:
            log(f"🔎 Request-ID in {target}/{result.instance} gefunden "
                f"(Typ: {result.found_type}, ohne Approve)")
        return result

    raise RequestNotFoundError(request_id, unreachable)


# ── Result-JSON-Building (einheitlich, Minor #7) ──


def build_result_json(
    status: str,
    request_id: str,
    found: Optional[List[dict]] = None,
    scanned: Optional[List[str]] = None,
    filters_applied: Optional[dict] = None,
) -> dict:
    """Einheitliches Rueckgabe-Schema (Minor #7).

    status ∈ {found, not_found, error}; approve.py setzt bei Vollausfuehrung
    status="approved".
    """
    return {
        "status": status,
        "id": request_id,
        "found": found or [],
        "scanned": scanned or [],
        "filters_applied": filters_applied or {},
    }


# ── CLI ──


def _load_instance_map(path: str) -> List[Tuple[str, str]]:
    result: List[Tuple[str, str]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            name, _, target = line.partition("|")
            if name:
                result.append((name, target))
    return result


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:]) if argv is None else argv
    parser = argparse.ArgumentParser(
        description="D1-Discovery-Scan v3.0 (Ein-Job: 1 SSH pro VPS, optional Approve in der Session)"
    )
    parser.add_argument("--instance-map", help="Datei mit 'name|target'-Zeilen")
    parser.add_argument("--request-id", help="Request-ID (Kurzcode ODER Device-ID)")
    parser.add_argument("--type-filter", default="auto", help="auto|telegram|device|both (default: auto)")
    parser.add_argument("--target-filter", default="both", help="dev|prod|both (default: both)")
    parser.add_argument("--instance-filter", default="all", help="all|oc1|oc2|... (default: all)")
    parser.add_argument("--vps-user")
    parser.add_argument("--ssh-key")
    parser.add_argument("--ts-tailnet")
    parser.add_argument("--ts-client-id")
    parser.add_argument("--ts-client-secret")
    parser.add_argument("--result-json", help="Ergebnis-JSON in Datei schreiben (optional)")
    parser.add_argument("--approve", action="store_true",
                        help="Ein-Job: Approve direkt in der SSH-Session beim Fund (v3.0)")
    # Validierungs-Modus (Workflow-Step "Eingaben validieren", DRY mit approve.py)
    parser.add_argument("--validate-id", help="Nur ID validieren + Typ ableiten (stdout), exit 0/2")
    opts = parser.parse_args(args)

    # ── Validierungs-Modus ──
    if opts.validate_id is not None:
        typ = opts.type_filter
        try:
            validate_type(typ)
        except ValueError as exc:
            print(f"❌ {exc}", file=sys.stderr)
            return 2
        valid, derived, err = validate_and_classify_id(opts.validate_id, typ)
        if not valid:
            print(f"❌ {err}", file=sys.stderr)
            return 2
        print(derived)
        return 0

    # ── Discovery-Modus ──
    if not all([opts.instance_map, opts.request_id, opts.vps_user, opts.ssh_key,
                opts.ts_tailnet, opts.ts_client_id, opts.ts_client_secret]):
        parser.error("Discovery-Modus benoetigt --instance-map, --request-id, "
                     "--vps-user, --ssh-key, --ts-tailnet, --ts-client-id, --ts-client-secret")
    try:
        validate_type(opts.type_filter)
        validate_request_id(opts.request_id, opts.type_filter)
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2
    if opts.instance_filter != "all":
        try:
            validate_instance(opts.instance_filter)
        except ValueError as exc:
            print(f"❌ {exc}", file=sys.stderr)
            return 2

    # auto → konkreter Typ aus Format ableiten (für Filter-Anzeige)
    derived_type = opts.type_filter
    if derived_type == "auto":
        derived_type = derive_type(opts.request_id)

    instance_map = _load_instance_map(opts.instance_map)
    filtered_map = filter_instance_map(
        instance_map,
        target_filter=opts.target_filter,
        instance_filter=opts.instance_filter,
    )

    filters = {
        "type": derived_type,
        "target": opts.target_filter,
        "instance": opts.instance_filter,
    }

    def log(msg: str) -> None:
        print(msg, file=sys.stderr)

    token = fetch_tailscale_token(opts.ts_client_id, opts.ts_client_secret)

    def resolve_ip(node: str) -> Optional[str]:
        return resolve_vps_ip(opts.ts_tailnet, token, node)

    def run_remote(ip: str, remote_cmd: str) -> str:
        return run_remote_ssh(ip, opts.vps_user, opts.ssh_key, remote_cmd)

    try:
        result = run_discovery(
            filtered_map,
            opts.request_id,
            derived_type=derived_type,
            resolve_ip=resolve_ip,
            run_remote=run_remote,
            approve=opts.approve,
            github_output=os.environ.get("GITHUB_OUTPUT"),
            log=log,
        )
    except RequestNotFoundError as err:
        print(f"❌ {err}", file=sys.stderr)
        if opts.result_json:
            result_obj = build_result_json(
                status="not_found",
                request_id=opts.request_id,
                scanned=[f"{n}|{t}" for n, t in filtered_map],
                filters_applied=filters,
            )
            with open(opts.result_json, "w", encoding="utf-8") as fh:
                json.dump(result_obj, fh, ensure_ascii=False)
        return 1

    if opts.approve and not result.approved:
        print(
            f"❌ ID '{opts.request_id}' gefunden, aber Approve wurde nicht in der "
            "SSH-Session bestätigt (APPROVE-Marker fehlen).",
            file=sys.stderr,
        )
        return 1

    if opts.result_json:
        result_obj = build_result_json(
            status="found",
            request_id=result.request_id,
            found=[{
                "target": result.target,
                "instance": result.instance,
                "type": result.found_type,
                "vps_ip": result.vps_ip,
            }],
            scanned=result.scanned,
            filters_applied=filters,
        )
        with open(opts.result_json, "w", encoding="utf-8") as fh:
            json.dump(result_obj, fh, ensure_ascii=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
