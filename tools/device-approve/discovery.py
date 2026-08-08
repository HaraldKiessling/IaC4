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

v3.1 (Listen-Modus, Design 05-workflow-listen-modus.md, Review R01-R09):
  - build_list_remote_cmd(): wie build_ein_job_remote_cmd, aber NUR
    JSON-Blöcke (kein ID-Match, kein Approve, kein FOUND) – gemeinsame
    Block-Generierung _build_json_collection_block (R01).
  - parse_list_output() / run_list_discovery(): aggregieren ALLE pending
    Eintraege ueber alle VPS (PendingEntry/ListDiscoveryResult); leere Liste
    ist ein gueltiges Ergebnis (Exit 0, gruen).

v3.2 (Reject-Modus, 2026-08-07):
  - build_ein_job_remote_cmd(action=...)/parse_ein_job_output(action=...):
    dieselbe Ein-Job-Remote-Schleife fuehrt je `action` Approve ODER Reject
    aus (REJECT-BEGIN/END/FAILED-Marker analog APPROVE-*, B2-Semantik).
  - REJECT_CMD_TEMPLATES: NUR device (`openclaw devices reject <ID>`) – die
    openclaw CLI hat KEIN 'pairing reject' (empirisch 2026-08-07);
    Telegram-Codes sind CLI-seitig nicht reject-bar (Hard-Gate).
  - run_discovery(action=...), discovery-CLI --reject.

v3.3 (Listen-Modus + requestId, 2026-08-07 – Owner-Auftrag „GUID soll in der
Liste stehen", e2e-Beleg aee3a00/Run 31156554728):
  - PendingEntry.request_id: pro pending Eintrag wird AUCH das Feld
    `requestId` (UUID-36) extrahiert – das ist die ID, die
    `openclaw devices approve/reject` erwartet (pending[].deviceId ist der
    64er-PublicKey-Hash, NICHT die Approve-ID). Telegram: "" wenn das
    pairing-request kein requestId-Feld hat (ID-Feld dort bleibt `code`).
  - pending_entry_to_dict()/build_list_result_json(): JSON-Feld
    `entries[].requestId` ("" = nicht vorhanden, konsistent zu R04).

v3.4 (Remove-Modus, 2026-08-07 – Owner-Auftrag 12:14 „mode=remove als
  Follow-up-Feature in Workflow 05“, Antwort „2 b“):
  - build_ein_job_remote_cmd(action=...)/parse_ein_job_output(action=...):
    action "remove" analog approve/reject – REMOVE-BEGIN/END/FAILED-Marker,
    B2-Semantik (FOUND=1 erst nach Exit-Code 0).
  - REMOVE_CMD_TEMPLATES: NUR device (`openclaw devices remove <ID>`) – die
    openclaw CLI hat KEIN 'pairing remove' (empirisch 2026-08-07: `openclaw
    pairing` kennt nur approve|list|help) → device-only-Hard-Gate wie reject.
  - WICHTIGER ID-Unterschied zu approve/reject: remove matcht GEPAARTE
    Eintraege – das Array ist `paired` (NICHT `pending`) und das ID-Feld ist
    `deviceId` (64-hex Public-Key-Hash; paired-Eintraege haben KEINE
    requestId). CLI-Fakt: `openclaw devices remove <deviceId>` (2026.7.1),
    e2e-Beleg: 'Removed 587758f1…' nach `devices remove <deviceId>`.

v3.3.1 (Approve/Reject-Match auf requestId, 2026-08-07 – Bugfix nach
  Workflow-Befund: 7 approve/reject-Runs lieferten not_found obwohl pending,
  z.B. 31165552730/31165829570):
  - Der Approve-/Reject-Pfad matchte `"deviceId": "<UUID>"` – aber die
    UUID-36 steht in pending[] im Feld `requestId` (deviceId = 64er-Key-Hash).
    - _SOURCE_ID_FIELD device: deviceId → requestId (kanonisches Feld).
    - Remote-grep (build_ein_job_remote_cmd): matcht requestId ODER deviceId
      (defensiv, "(requestId|deviceId)" – Fund zählt, wenn EINES der Felder
      die Request-ID trägt; Telegram unveraendert: code).
    - entry_matches_id: device → requestId zuerst, deviceId als Fallback.
  - Listen-Pfad (parse_list_output) unveraendert – extrahiert requestId
    bereits korrekt (v3.3). Validierung/Typ-Ableitung unveraendert
    (UUID-36 = device).

v3.6 (Instanz-Remove, scope=instance, 2026-08-08 – Owner-Entscheidungen
  „Instanz leeren“: entfernt ALLE gepaarten Geraete der gefilterten Instanzen,
  NICHT „neuestes je Instanz“):
  - build_instance_remove_remote_cmd(): Remote-Schleife je VPS – sammelt
    devices list --json (JSON-Blöcke, gemeinsame
    _build_json_collection_block), extrahiert ALLE deviceIds aus paired[]
    (Array-Key via _action_array_key, KEIN jq – R08) und entfernt JEDE
    deviceId per REMOVE_CMD_TEMPLATES[device] (`openclaw devices remove
    <deviceId>`); je Geraet DEV-REMOVE-BEGIN/END/FAILED-Marker (B2-Semantik:
    FOUND=1 erst nach Exit-Code 0).
  - Sicherheits-Limit max_devices=50 (MAX_REMOVE_DEVICES): Shell-seitiger
    Hard-Cap (COUNT, DEV-REMOVE-LIMIT-Marker) als Defense-in-Depth; der
    eigentliche Abbruch (Exit 2 VOR jedem Remove) macht approve.py anhand
    des Phasen-1-Plans (collect_paired_devices + parse_paired_output).
  - parse_paired_output(): liest paired[]-Eintraege (deviceId/platform/
    clientId) aus den JSON-Blöcken – Basis des Remove-Plans.
  - parse_instance_remove_output(): parst DEV-REMOVE-*-Marker → removed/-
    failed-Listen (instanz, deviceId, Output) + limit_hit + scanned.
  - run_instance_remove()/collect_paired_devices(): VPS-Gruppierung wie
    run_discovery (1 SSH pro VPS); UNREACHABLE-Semantik unveraendert.
  - build_instance_remove_result_json(): Schema erweitert (scope, removed_count,
    per_instance, failed, limit_hit, unreachable) – bestehende Felder
    (status, id, found, scanned) bleiben fuer scope=device unveraendert.
  - Der ID-basierte Remove-Pfad (action="remove", v3.5) bleibt unangetastet.

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
# v3.4: zulaessige Aktionen der Ein-Job-Remote-Schleife (approve|reject|remove)
VALID_ACTIONS = ("approve", "reject", "remove")

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
# Δ3 (v3.2, Reject-Modus): Reject-Kommando je Typ. NUR device – die openclaw
# CLI hat KEIN 'pairing reject' (empirisch 2026-08-07: `openclaw pairing` kennt
# nur approve|list|help). Telegram-Pairing-Codes sind CLI-seitig nicht
# reject-bar → der Reject-Modus erlaubt ausschliesslich device-Requests
# (Hard-Gate in build_ein_job_remote_cmd + approve.py).
REJECT_CMD_TEMPLATES = {
    "device": "sudo docker exec openclaw-{instance} openclaw devices reject {request_id}",
}
# Δ4 (v3.4, Remove-Modus): Remove-Kommando je Typ. NUR device – die openclaw
# CLI hat KEIN 'pairing remove' (empirisch 2026-08-07: `openclaw pairing` kennt
# nur approve|list|help). Remove adressiert GEPAARTE Geraete per deviceId
# (64-hex Public-Key-Hash) – `openclaw devices remove <deviceId>`
# (CLI-Fakt 2026.7.1, e2e-Beleg 'Removed 587758f1…'). Kein pairing-Counterpart
# → Remove erlaubt ausschliesslich device-Eintraege (Hard-Gate wie reject).
REMOVE_CMD_TEMPLATES = {
    "device": "sudo docker exec openclaw-{instance} openclaw devices remove {request_id}",
}

# v3.6 (Instanz-Remove, scope=instance): Sicherheits-Limit – max. 50 Geraete
# pro Lauf (Owner-Entscheidung 2026-08-08: „max 50 Geräte pro Lauf, darüber
# Abbruch mit klarer Fehlermeldung (Exit 2) statt Massen-Remove“). Wird in
# approve.py (Phase-1-Plan) UND als Shell-Hard-Cap im Remote-Skript
# (build_instance_remove_remote_cmd, Defense-in-Depth) durchgesetzt.
MAX_REMOVE_DEVICES = 50

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
# v3.2 (Reject-Modus): Marker analog zu APPROVE-* – der Reject laeuft in
# derselben Remote-Schleife (REJECT-BEGIN/END + REJECT-FAILED bei Exit-Code
# != 0; FOUND=1 erst NACH Exit-Code 0 – kein falscher Erfolg, B2-Semantik).
REJECT_BLOCK_RE = re.compile(
    rf"---REJECT-BEGIN:(?P<label>{_LABEL_RE})---\n(?P<body>.*?)---REJECT-END:(?P=label)---",
    re.DOTALL,
)
REJECT_FAILED_RE = re.compile(rf"---REJECT-FAILED:(?P<label>{_LABEL_RE})---")
# v3.4 (Remove-Modus): Marker analog zu APPROVE-/REJECT-* – der Remove laeuft
# in derselben Remote-Schleife (REMOVE-BEGIN/END + REMOVE-FAILED bei
# Exit-Code != 0; FOUND=1 erst NACH Exit-Code 0 – kein falscher Erfolg,
# B2-Semantik).
REMOVE_BLOCK_RE = re.compile(
    rf"---REMOVE-BEGIN:(?P<label>{_LABEL_RE})---\n(?P<body>.*?)---REMOVE-END:(?P=label)---",
    re.DOTALL,
)
REMOVE_FAILED_RE = re.compile(rf"---REMOVE-FAILED:(?P<label>{_LABEL_RE})---")
# v3.6 (Instanz-Remove): Geraete-Marker mit deviceId-Suffix im Label
# (`<inst>:<deviceId>` – ein Block je Geraet in der Instanz-Remove-Schleife).
# Disjunkt zu den Einzel-REMOVE-* (die ein `<inst>:device`-Label tragen).
_DEV_LABEL_RE = r"oc[1-9][0-9]*:[0-9a-fA-F-]{36,128}"
DEV_REMOVE_BLOCK_RE = re.compile(
    rf"---DEV-REMOVE-BEGIN:(?P<label>{_DEV_LABEL_RE})---\n(?P<body>.*?)---DEV-REMOVE-END:(?P=label)---",
    re.DOTALL,
)
DEV_REMOVE_FAILED_RE = re.compile(rf"---DEV-REMOVE-FAILED:(?P<label>{_DEV_LABEL_RE})---")
DEV_REMOVE_LIMIT_RE = re.compile(rf"---DEV-REMOVE-LIMIT:(?P<label>{_LABEL_RE})---")
FOUND_RE = re.compile(r"---FOUND:(?P<found>[01])---")

API_TIMEOUT = 30
# Remote-Loop über alle Instanzen eines VPS (bei type=both 2 Quellen pro
# Instanz) – grosszuegiger Timeout als der alte Pro-Instanz-Call.
SSH_TIMEOUT = 60

# Array-Key + ID-Feld je Quelle (für den Remote-Match ohne jq, R08)
_SOURCE_ARRAY_KEY = {"telegram": "requests", "device": "pending"}
# v3.3.1: kanonisches ID-Feld je Quelle – device ist jetzt `requestId`
# (UUID-36, die ID, die `openclaw devices approve/reject` erwartet;
# pending[].deviceId ist der 64er-PublicKey-Hash, NICHT die Approve-ID).
# v3.4 (Remove): fuer action="remove" gilt das Array `paired` und das
# ID-Feld `deviceId` (64-hex) – gepaarte Eintraege haben KEINE requestId.
_SOURCE_ID_FIELD = {"telegram": "code", "device": "requestId"}
# v3.3.1: ID-Felder je Quelle für den Remote-grep (defensiv: requestId ODER
# deviceId) – der Fund zählt, wenn EINES der Felder die Request-ID trägt.
_SOURCE_ID_FIELDS = {"telegram": ("code",), "device": ("requestId", "deviceId")}


def _action_array_key(typ: str, action: str) -> str:
    """Array-Key je Quelle + Aktion.

    approve/reject wirken auf OFFENE Eintraege (telegram: requests,
    device: pending); remove wirkt auf GEPAARTE Eintraege (device: paired)
    – CLI-Fakt: `openclaw devices remove <deviceId>` loescht den paired-
    Eintrag (e2e-Beleg 'Removed 587758f1…'), approve/reject nur pending
    (v3.2/v3.3.1). Telegram hat kein paired-Array → remove ist device-only
    (Hard-Gate in build_ein_job_remote_cmd).
    """
    if action == "remove":
        return "paired"
    return _SOURCE_ARRAY_KEY[typ]


def _action_id_fields(typ: str, action: str) -> Tuple[str, ...]:
    """ID-Felder je Quelle + Aktion für den Remote-grep + Python-Match.

    approve/reject (device): requestId (UUID-36) ODER deviceId (defensiv,
    v3.3.1). remove (device): NUR deviceId – paired-Eintraege fuehren die
    64-hex deviceId, aber KEINE requestId (CLI-Fakt 2026.7.1, e2e-Beleg
    aee3a00: paired[] hat deviceId/publicKey/platform/clientId, keine
    requestId). Telegram: unveraendert `code` (kein remove).
    """
    if action == "remove":
        return ("deviceId",)
    return _SOURCE_ID_FIELDS[typ]


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
    # v3.2/v3.4: Feldname historisch 'approved' – gilt auch fuer den Reject-/
    # Remove-Modus (action='reject': REJECT-Marker + FOUND=1; action='remove':
    # REMOVE-Marker + FOUND=1 → Aktion in der Session ok);
    # approve_output = Session-Text der jeweiligen Aktion.
    approved: bool = False
    approve_output: str = ""
    action: str = "approve"  # v3.4: "approve" | "reject" | "remove"


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


def entry_matches_id(entry: dict, request_id: str, typ: str, action: str = "approve") -> bool:
    """Exakter ID-Match auf dem typ-spezifischen ID-Feld (Δ3, v3.3.1, v3.4).

    telegram → Feld `code` (Kurzcode).
    device → Feld `requestId` (UUID-36 – die ID, die `openclaw devices
    approve/reject` erwartet; e2e-Beleg: pending[].requestId=UUID-36,
    deviceId=64er-PublicKey-Hash), Fallback auf `deviceId` (defensiv für
    Quellen ohne requestId-Feld).
    v3.4 (remove): NUR Feld `deviceId` – remove adressiert GEPAARTE Geraete
    (paired[]), die keine requestId fuehren (CLI-Fakt: `openclaw devices
    remove <deviceId>`, 64-hex).
    """
    if typ == "telegram":
        return entry.get("code") == request_id
    if action == "remove":
        return entry.get("deviceId") == request_id
    if typ == "device":
        return entry.get("requestId") == request_id or entry.get("deviceId") == request_id
    return False


def _action_entries(data: dict, typ: str, action: str) -> list:
    """Eintraege je Quelle + Aktion aus dem Discovery-JSON.

    approve/reject → offene Eintraege (telegram: requests/pending-Fallback,
    device: pending). remove → GEPAARTE Eintraege (device: paired) –
    v3.4: der Parser muss fuer remove das paired[]-Array lesen (der
    Remote-Grep matcht ebenfalls "paired", siehe _action_array_key).
    """
    if action == "remove":
        return data.get("paired") or []
    return parse_entries(data, typ)


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


def _source_var(typ: str, src_typ: str) -> str:
    """Variablenname der JSON-Ausgabe je Quelle im Remote-Skript.

    Eine Quelle → RESULT; mehrere (type=both) → RESULT_TG / RESULT_DEV
    (disjunkt, damit beide JSON-Bloecke in derselben Session erhalten bleiben).
    """
    if len(_source_specs(typ)) == 1:
        return "RESULT"
    return "RESULT_TG" if src_typ == "telegram" else "RESULT_DEV"


def _build_json_collection_block(src_typ: str, list_tmpl: str, var: str) -> List[str]:
    """JSON-Block-Zeilen (Marker + List-Cmd + printf) fuer EINE Quelle.

    Gemeinsame Basis von build_ein_job_remote_cmd (Approve-Modus) und
    build_list_remote_cmd (Listen-Modus) – R01 (Review Listen-Modus):
    Marker-Format, List-Cmd-Escaping und printf-Ausgabe existieren NUR hier
    (keine ~60%-Duplikation; Aenderungen/Bugfixes an EINER Stelle).

    Die Zeilen laufen innerhalb der `for inst in ...`-Remote-Schleife;
    ${inst} setzt die Remote-Shell. `|| true` = fail-safe bei Instanz-Down.
    """
    list_cmd = list_tmpl.format(instance="${inst}")
    return [
        f'  echo "---JSON-BEGIN:${{inst}}:{src_typ}---"',
        f"  {var}=$({list_cmd} || true)",
        f"  printf '%s\\n' \"${var}\"",
        f'  echo "---JSON-END:${{inst}}:{src_typ}---"',
    ]


def build_ein_job_remote_cmd(
    typ: str,
    instances: List[str],
    request_id: str,
    *,
    approve: bool = True,
    action: str = "approve",
) -> str:
    """Baut das Ein-Job-Remote-Shell-Template (1 SSH pro VPS).

    Pro Instanz:
      - JSON-Block je Quelle (telegram → pairing list, device → devices list;
        type=both → beide Quellen in derselben Session, R02) – gemeinsame
        Block-Generierung via _build_json_collection_block (R01)
      - bei approve: ID-Match im Textpfad (grep auf das JSON-Feld des
        relevanten Arrays, KEIN jq – R08) → Aktion direkt in der Session
        (---APPROVE-/---REJECT-BEGIN/END-Marker), break-Semantik (erster Fund
        stoppt)
    `|| true` = fail-safe bei Instanz-Down (leere Ausgabe → kein Match).
    Am Ende: `---FOUND:${FOUND}---`.

    v3.2 (Reject-Modus): `action` waehlt die Aktion – "approve" (Default,
    APPROVE_CMD_TEMPLATES + APPROVE-Marker) oder "reject"
    (REJECT_CMD_TEMPLATES + REJECT-Marker). Reject ist NUR fuer device-
    Requests zulaessig (die openclaw CLI hat kein 'pairing reject') →
    typ != "device" ⇒ ValueError (Hard-Gate, defense in depth).
    v3.4 (Remove-Modus): "remove" analog – REMOVE_CMD_TEMPLATES +
    REMOVE-Marker, matcht GEPAARTE Eintraege (Array "paired", ID-Feld
    "deviceId" 64-hex). Remove ist NUR fuer device zulaessig (kein
    'pairing remove' in der openclaw CLI) → typ != "device" ⇒ ValueError.

    Raises:
        ValueError: unbekannter Typ, leere Instanzliste, ungueltige Instanz
                    oder ID (Format-Sperre, defense in depth), Reject/Remove
                    mit Nicht-Device-Typ.
    """
    if action not in VALID_ACTIONS:
        raise ValueError(
            f"Unbekannte Aktion: '{action}'. Erlaubt: {', '.join(VALID_ACTIONS)}."
        )
    if action in ("reject", "remove") and typ != "device":
        # v3.2/v3.4: reject UND remove sind device-only – die openclaw CLI
        # hat weder 'pairing reject' noch 'pairing remove' (empirisch
        # 2026-08-07: `openclaw pairing` kennt nur approve|list|help).
        aktion_name = "Reject" if action == "reject" else "Remove"
        raise ValueError(
            f"{aktion_name}-Modus unterstuetzt nur device-Requests – die openclaw CLI "
            f"hat kein 'pairing {action}' (nur `openclaw devices {action} <ID>`)."
        )
    if typ not in REMOTE_TYPES:
        raise ValueError(
            f"Ungueltiger Typ fuer Remote-Schleife: '{typ}'. Erlaubt: {', '.join(REMOTE_TYPES)}."
        )
    if not instances:
        raise ValueError("Keine Instanzen fuer die Remote-Schleife uebergeben.")
    for inst in instances:
        validate_instance(inst)
    validate_request_id(request_id, typ)

    lines = ["FOUND=0", "for inst in " + " ".join(instances) + "; do"]
    # v3.2/v3.4: Aktion waehlt Kommando-Templates + Marker-Praefix
    # (APPROVE|REJECT|REMOVE) – approve/reject wirken auf pending/requests,
    # remove auf paired (deviceId; _action_array_key/_action_id_fields).
    if action == "approve":
        cmd_templates = APPROVE_CMD_TEMPLATES
    elif action == "reject":
        cmd_templates = REJECT_CMD_TEMPLATES
    else:
        cmd_templates = REMOVE_CMD_TEMPLATES
    marker = {"approve": "APPROVE", "reject": "REJECT", "remove": "REMOVE"}[action]
    for src_typ, list_tmpl, _approve_tmpl in _source_specs(typ):
        var = _source_var(typ, src_typ)
        # v3.4: Array-Key + ID-Felder aktionsabhaengig – remove matcht
        # "paired" + "deviceId" (64-hex), approve/reject "pending"/"requests"
        # + requestId/deviceId (v3.3.1).
        array_key = _action_array_key(src_typ, action)
        id_fields = "|".join(_action_id_fields(src_typ, action))

        lines.extend(_build_json_collection_block(src_typ, list_tmpl, var))

        if approve:
            action_cmd = cmd_templates[src_typ].format(
                instance="${inst}", request_id=request_id
            )
            # Array-Inhalt extrahieren (nur pending/requests, nicht paired) und
            # ID-Feld matchen – kein jq, nur POSIX-Tools (R08).
            lines.append(
                f"  ENTRIES=$(printf '%s' \"${var}\" | tr -d '\\n' | "
                f"sed -n 's/.*\"{array_key}\"[[:space:]]*:[[:space:]]*\\[\\([^]]*\\)\\].*/\\1/p')"
            )
            lines.append(
                f"  if printf '%s' \"$ENTRIES\" | grep -qE '\"({id_fields})\"[[:space:]]*:[[:space:]]*\"{request_id}\"'; then"
            )
            lines.append(f'    echo "---{marker}-BEGIN:${{inst}}:{src_typ}---"')
            # B2 (2. Review, Blocker): Aktion-Erfolg MUSS geprueft werden –
            # KEIN `|| true` um den Aktion-Befehl; FOUND=1 erst NACH Exit-Code
            # 0. Bei Fehler: {marker}-FAILED-Marker + break (laut scheitern,
            # kein falscher Erfolg im Workflow).
            lines.append(f"    if {action_cmd} 2>&1; then")
            lines.append(f'      echo "---{marker}-END:${{inst}}:{src_typ}---"')
            lines.append("      FOUND=1")
            lines.append("      break")
            lines.append("    else")
            lines.append(f'      echo "---{marker}-END:${{inst}}:{src_typ}---"')
            lines.append(f'      echo "---{marker}-FAILED:${{inst}}:{src_typ}---"')
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


def build_list_remote_cmd(
    typ: str,
    instances: List[str],
) -> str:
    """Baut das Listen-Remote-Shell-Template (1 SSH pro VPS, KEIN Approve).

    Sammelt pro Instanz+Quelle die JSON-Bloecke ALLER pending-Eintraege
    (`openclaw pairing list telegram --json` + `openclaw devices list --json`).
    Die JSON-Block-Generierung (Marker + List-Cmd + printf) ist identisch zum
    Approve-Modus – gemeinsame Funktion _build_json_collection_block (R01).
    Kein ID-Match, kein Approve-Befehl, kein break, kein FOUND-Marker:
    der Listen-Modus approvt NIE (Hard-Gate).

    Marker: `---LIST-BEGIN---` … `---LIST-END---`; pro Block
    `---JSON-BEGIN:<inst>:<typ>---` … `---JSON-END:<inst>:<typ>---`
    (Typ-Suffix wie im Approve-Modus – parsebar auch bei type=both).

    Raises:
        ValueError: unbekannter Typ, leere Instanzliste, ungueltige Instanz
                    (R05: Defense-in-Depth, identisch zu
                    build_ein_job_remote_cmd).
    """
    if typ not in REMOTE_TYPES:
        raise ValueError(
            f"Ungueltiger Typ fuer Remote-Schleife: '{typ}'. Erlaubt: {', '.join(REMOTE_TYPES)}."
        )
    if not instances:
        raise ValueError("Keine Instanzen fuer die Remote-Schleife uebergeben.")
    for inst in instances:  # R05: Defense-in-Depth (Injection-Sperre)
        validate_instance(inst)

    lines = ["echo '---LIST-BEGIN---'", "for inst in " + " ".join(instances) + "; do"]
    for src_typ, list_tmpl, _approve_tmpl in _source_specs(typ):
        var = _source_var(typ, src_typ)
        lines.extend(_build_json_collection_block(src_typ, list_tmpl, var))
    lines.append("done")
    lines.append('echo "---LIST-END---"')
    return "\n".join(lines) + "\n"


# ── Listen-Modus (v3.1): pending-Eintraege ueber alle Instanzen ──


@dataclass
class PendingEntry:
    """Ein einzelner pending-Eintrag aus der Listen-Discovery."""

    instance: str  # oc1, oc2, ...
    target: str  # dev, prod
    vps_ip: Optional[str]
    entry_type: str  # "telegram" | "device"
    entry_id: str  # code (Telegram) oder deviceId
    # v3.3: requestId (UUID-36) des pending-Eintrags – die ID, die
    # approve/reject erwartet (e2e-Beleg aee3a00: pending[].requestId=UUID-36,
    # deviceId=64er-PublicKey-Hash). Telegram: "" wenn kein requestId-Feld.
    request_id: str = ""
    # R04-Konvention: platform "" = Wahrheit (Telegram hat kein platform-Feld,
    # O7); die Markdown-Tabelle rendert "" → "—" (Darstellung).
    platform: str = ""
    created_at_ms: int = 0  # 0 = nicht vorhanden


@dataclass
class ListDiscoveryResult:
    """Ergebnis der Listen-Discovery: alle pending-Eintraege pro Instanz."""

    entries: List[PendingEntry] = field(default_factory=list)
    scanned: List[str] = field(default_factory=list)  # "target/instance"
    unreachable: List[str] = field(default_factory=list)  # VPS-Hostnames


def parse_list_output(
    stdout: str,
    target: str,
) -> List[PendingEntry]:
    """Parst ---LIST-BEGIN/END--- + JSON-Blöcke → Liste aller pending-Eintraege.

    Nutzt dieselben JSON_BLOCK_RE-Marker wie der Approve-Modus (R01): pro
    Eintrag werden type (aus dem Label-Suffix), id (code|deviceId), platform
    (device; "" bei telegram, R04) und createdAtMs (0 wenn fehlt) extrahiert.
    v3.3: zusaetzlich requestId (UUID-36) – das Feld, das approve/reject
    erwartet (pending[].deviceId ist der 64er-PublicKey-Hash, e2e-Beleg
    aee3a00). Telegram: "" wenn das pairing-request kein requestId-Feld hat
    (konsistent: ID-Feld dort bleibt `code`, approve matcht `code`).
    Defensiv (R07): leere/defekte Bloecke und kaputtes JSON werden uebersprungen
    – der Rest der Liste bleibt erhalten.
    """
    entries: List[PendingEntry] = []
    for blk in JSON_BLOCK_RE.finditer(stdout or ""):
        label = blk.group("label")
        instance, block_typ = _split_label(label)
        body = blk.group("body").strip()
        if not body:
            continue  # fail-safe: Instanz down / leere Quelle
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            continue  # fail-safe: defekte Ausgabe ueberspringen
        for entry in parse_entries(data, block_typ):
            entries.append(PendingEntry(
                instance=instance,
                target=target,
                vps_ip=None,  # wird vom Aufrufer (run_list_discovery) gesetzt
                entry_type=block_typ,
                entry_id=entry.get("code") or entry.get("deviceId") or "?",
                # v3.3: requestId (UUID-36) der Approve-/Reject-ID; "" wenn
                # die Quelle kein Feld liefert (Telegram ohne requestId).
                request_id=entry.get("requestId") or "",
                platform=entry.get("platform", "") or "",
                created_at_ms=entry.get("createdAtMs", 0) or 0,
            ))
    return entries


def pending_entry_to_dict(entry: PendingEntry) -> dict:
    """PendingEntry → JSON-Dict (Listen-Schema, Design §11).

    v3.3: Feld `requestId` (UUID-36, approve/reject-ID) – "" = nicht
    vorhanden (Telegram ohne requestId-Feld, konsistent zu R04-""-Konvention).
    """
    return {
        "instance": entry.instance,
        "target": entry.target,
        "type": entry.entry_type,
        "id": entry.entry_id,
        "requestId": entry.request_id,
        "platform": entry.platform,  # "" = Wahrheit (R04)
        "createdAtMs": entry.created_at_ms,
        "vps_ip": entry.vps_ip,
    }


def run_list_discovery(
    instance_map: List[Tuple[str, str]],
    derived_type: str = "both",
    *,
    resolve_ip: Optional[Callable[[str], Optional[str]]] = None,
    run_remote: Optional[Callable[[str, str], str]] = None,
    log: Optional[Callable[[str], None]] = None,
) -> ListDiscoveryResult:
    """Listen-Discovery ueber alle VPS: sammelt ALLE pending-Eintraege.

    Gleiche VPS-Gruppierung (group_by_vps) und 1-SSH-pro-VPS-Optimierung wie
    run_discovery, aber:
    - build_list_remote_cmd statt build_ein_job_remote_cmd (kein ID-Match,
      kein Approve)
    - parse_list_output statt parse_ein_job_output (extrahiert ALLE Eintraege)
    - Keine RequestNotFoundError – eine leere Liste ist ein gueltiges Ergebnis
      (Exit 0, gruen; Owner-Vereinbarung not_found-Semantik)

    Args:
        instance_map: gefilterte [(instance_name, target), ...]
        derived_type: telegram|device|both (auto ist vom Aufrufer aufgeloest;
                      Listen-Modus hat keine ID zum Ableiten, O3)
        resolve_ip(node) -> ip|None  (None = VPS down → unreachable)
        run_remote(vps_ip, remote_cmd) -> stdout der SSH-Session
        log: optionaler Logger (stderr im CLI)
    """
    log = log or (lambda _msg: None)
    all_entries: List[PendingEntry] = []
    scanned: List[str] = []
    unreachable: List[str] = []

    for target, instances in group_by_vps(instance_map).items():
        node = node_for_target(target)
        ip = resolve_ip(node) if resolve_ip else None
        if not ip:
            unreachable.append(node)
            log(f"⚠️  VPS {node} nicht erreichbar, ueberspringe")
            continue

        remote_cmd = build_list_remote_cmd(derived_type, instances)
        log(f"🔍 SSH {node} ({target}): {', '.join(instances)} – Sammle pending-Eintraege")
        stdout = run_remote(ip, remote_cmd) if run_remote else ""

        entries = parse_list_output(stdout, target)
        for e in entries:
            e.vps_ip = ip
        all_entries.extend(entries)
        scanned.extend(f"{target}/{inst}" for inst in instances)

    return ListDiscoveryResult(
        entries=all_entries,
        scanned=scanned,
        unreachable=unreachable,
    )


# ── Instanz-Remove (v3.6, scope=instance): ALLE gepaarten Geraete ──


@dataclass
class PairedDevice:
    """Ein einzelner gepaarter Eintrag aus der Listen-Discovery (v3.6).

    Basis des Remove-Plans fuer scope=instance: `openclaw devices list --json`
    → paired[] (Feld `deviceId` = 64-hex Public-Key-Hash; CLI-Fakt
    OpenClaw 2026.7.1).
    """

    instance: str  # oc1, oc2, ...
    target: str  # dev, prod
    vps_ip: Optional[str]
    device_id: str  # 64-hex deviceId aus paired[]
    platform: str = ""  # R04-Konvention: "" = Wahrheit
    client_id: str = ""


@dataclass
class InstanceRemoveResult:
    """Ergebnis der Instanz-Remove-Schleife (v3.6).

    removed: (instance, device_id) je erfolgreich entferntem Geraet.
    failed: (instance, device_id, output) je fehlgeschlagenem Geraet
            (DEV-REMOVE-FAILED-Marker, B2-Semantik).
    limit_hit: Shell-Hard-Cap (MAX_REMOVE_DEVICES) hat gegriffen
               (Defense-in-Depth; der geplante Abbruch passiert vorher in
               approve.py anhand des Phase-1-Plans).
    """

    removed: List[Tuple[str, str]] = field(default_factory=list)
    failed: List[Tuple[str, str, str]] = field(default_factory=list)
    limit_hit: bool = False
    scanned: List[str] = field(default_factory=list)  # "target/instance"
    unreachable: List[str] = field(default_factory=list)  # VPS-Hostnames


def parse_paired_output(stdout: str, target: str) -> List[PairedDevice]:
    """Parst JSON-Blöcke → Liste ALLER gepaarten Geraete (paired[]).

    v3.6 (scope=instance): Basis des Remove-Plans – nutzt dieselben
    JSON_BLOCK_RE-Marker wie der Listen-/Approve-Modus (R01). Nur
    device-Blöcke tragen ein paired[] (Telegram hat kein paired-Array,
    CLI-Fakt 2026.7.1) → telegram-Blöcke werden uebersprungen. Defensiv
    (R07): leere/defekte Blöcke und kaputtes JSON werden uebersprungen.
    """
    devices: List[PairedDevice] = []
    for blk in JSON_BLOCK_RE.finditer(stdout or ""):
        label = blk.group("label")
        instance, block_typ = _split_label(label)
        if block_typ != "device":
            continue  # nur devices haben paired[] (kein telegram paired)
        body = blk.group("body").strip()
        if not body:
            continue  # fail-safe: Instanz down / leere Quelle
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            continue  # fail-safe: defekte Ausgabe ueberspringen
        for entry in data.get("paired") or []:
            devices.append(PairedDevice(
                instance=instance,
                target=target,
                vps_ip=None,  # wird vom Aufrufer (collect_paired_devices) gesetzt
                device_id=entry.get("deviceId") or "",
                platform=entry.get("platform", "") or "",
                client_id=entry.get("clientId", "") or "",
            ))
    return devices


def build_instance_remove_remote_cmd(
    instances: List[str],
    max_devices: int = MAX_REMOVE_DEVICES,
) -> str:
    """Baut das Instanz-Remove-Remote-Shell-Template (1 SSH pro VPS, v3.6).

    Pro Instanz:
      - JSON-Block der Device-Quelle (devices list --json, gemeinsame
        Block-Generierung _build_json_collection_block – R01)
      - ALLE deviceIds aus dem paired[]-Array extrahieren (Array-Key via
        _action_array_key("device", "remove"), KEIN jq – R08)
      - JEDE deviceId per REMOVE_CMD_TEMPLATES[device]
        (`openclaw devices remove <deviceId>`) entfernen – je Geraet
        DEV-REMOVE-BEGIN/END/FAILED-Marker; B2-Semantik: FOUND=1 erst nach
        Exit-Code 0, FAILED-Marker bei Fehler (kein `|| true` um den Remove).
      - Shell-Hard-Cap max_devices (Defense-in-Depth): COUNTER, bei
        Ueberschreitung DEV-REMOVE-LIMIT-Marker + break.

    Raises:
        ValueError: leere Instanzliste oder ungueltige Instanz (R05:
                    Defense-in-Depth, identisch zu build_ein_job_remote_cmd).
    """
    if not instances:
        raise ValueError("Keine Instanzen fuer die Remote-Schleife uebergeben.")
    for inst in instances:
        validate_instance(inst)

    array_key = _action_array_key("device", "remove")  # "paired"
    remove_tmpl = REMOVE_CMD_TEMPLATES["device"]
    lines = ["FOUND=0", "COUNT=0", "for inst in " + " ".join(instances) + "; do"]
    for src_typ, list_tmpl, _approve_tmpl in _source_specs("device"):
        var = _source_var("device", src_typ)
        lines.extend(_build_json_collection_block(src_typ, list_tmpl, var))
    # paired[]-Array extrahieren (wie Einzel-Remove, aber OHNE ID-Filter –
    # ALLE Eintraege) und jede deviceId einzeln entfernen (kein jq, R08).
    lines.append(
        f"  PAIRED=$(printf '%s' \"${{{var}}}\" | tr -d '\\n' | "
        f"sed -n 's/.*\"{array_key}\"[[:space:]]*:[[:space:]]*\\[\\([^]]*\\)\\].*/\\1/p')"
    )
    lines.append(
        "  for did in $(printf '%s' \"$PAIRED\" | "
        "grep -oE '\"deviceId\"[[:space:]]*:[[:space:]]*\"[0-9a-fA-F-]+\"' | "
        "sed -E 's/.*\"([0-9a-fA-F-]+)\"/\\1/'); do"
    )
    lines.append("    COUNT=$((COUNT+1))")
    lines.append(f'    if [ "$COUNT" -gt {max_devices} ]; then')
    lines.append('      echo "---DEV-REMOVE-LIMIT:${inst}:device---"')
    lines.append("      break")
    lines.append("    fi")
    action_cmd = remove_tmpl.format(instance="${inst}", request_id="$did")
    lines.append('    echo "---DEV-REMOVE-BEGIN:${inst}:$did---"')
    # B2-Semantik (wie Einzel-Remove): KEIN `|| true`; FOUND=1 erst nach
    # Exit-Code 0; DEV-REMOVE-FAILED-Marker bei Fehler (Geraet in failed).
    lines.append(f"    if {action_cmd} 2>&1; then")
    lines.append('      echo "---DEV-REMOVE-END:${inst}:$did---"')
    lines.append("      FOUND=1")
    lines.append("    else")
    lines.append('      echo "---DEV-REMOVE-END:${inst}:$did---"')
    lines.append('      echo "---DEV-REMOVE-FAILED:${inst}:$did---"')
    lines.append("    fi")
    lines.append("  done")
    lines.append("done")
    lines.append('echo "---FOUND:${FOUND}---"')
    return "\n".join(lines) + "\n"


def parse_instance_remove_output(
    stdout: str,
    target: str,
) -> InstanceRemoveResult:
    """Parst die Instanz-Remove-Ausgabe (JSON-Blöcke + DEV-REMOVE-Marker).

    v3.6 (scope=instance):
      - DEV-REMOVE-BEGIN/END-Marker (Label `<inst>:<deviceId>`) → removed;
        gefolgt vom DEV-REMOVE-FAILED-Marker gleichen Labels → failed
        (B2-Semantik, Output bleibt sichtbar)
      - DEV-REMOVE-LIMIT-Marker → limit_hit (Shell-Hard-Cap, Defense-in-Depth)
      - JSON-Blöcke → scanned (target/instance, dedupliziert)

    Returns:
        InstanceRemoveResult (leer = kein Geraet gefunden → not_found).
    """
    stdout = stdout or ""
    result = InstanceRemoveResult()
    for blk in JSON_BLOCK_RE.finditer(stdout):
        label = blk.group("label")
        instance, block_typ = _split_label(label)
        result.scanned.append(f"{target}/{instance}" if target else instance)
    failed_labels = {m.group("label") for m in DEV_REMOVE_FAILED_RE.finditer(stdout)}
    for blk in DEV_REMOVE_BLOCK_RE.finditer(stdout):
        label = blk.group("label")
        instance, _, device_id = label.partition(":")
        body = blk.group("body").strip()
        if label in failed_labels:
            result.failed.append((instance, device_id, body))
        else:
            result.removed.append((instance, device_id))
    result.limit_hit = bool(DEV_REMOVE_LIMIT_RE.search(stdout))
    result.scanned = _dedupe(result.scanned)
    return result


def collect_paired_devices(
    instance_map: List[Tuple[str, str]],
    derived_type: str = "device",
    *,
    resolve_ip: Optional[Callable[[str], Optional[str]]] = None,
    run_remote: Optional[Callable[[str, str], str]] = None,
    log: Optional[Callable[[str], None]] = None,
) -> Tuple[List[PairedDevice], List[str], List[str]]:
    """Phase 1 (v3.6): Remove-Plan – ALLE gepaarten Geraete sammeln.

    Gleiche VPS-Gruppierung (group_by_vps) und 1-SSH-pro-VPS-Optimierung wie
    run_discovery; baut nur den PLAN (KEIN Remove): build_list_remote_cmd +
    parse_paired_output. approve.py entscheidet anhand des Plans: leer →
    not_found (Exit 0), > MAX_REMOVE_DEVICES → Abbruch (Exit 2) VOR jedem
    Remove, sonst Phase 2 (run_instance_remove).

    Returns:
        (devices, scanned, unreachable)
    """
    log = log or (lambda _msg: None)
    devices: List[PairedDevice] = []
    scanned: List[str] = []
    unreachable: List[str] = []

    for target, instances in group_by_vps(instance_map).items():
        node = node_for_target(target)
        ip = resolve_ip(node) if resolve_ip else None
        if not ip:
            unreachable.append(node)
            log(f"⚠️  VPS {node} nicht erreichbar, ueberspringe")
            continue
        remote_cmd = build_list_remote_cmd(derived_type, instances)
        log(f"🔍 SSH {node} ({target}): {', '.join(instances)} – Sammle gepaarte Geraete")
        stdout = run_remote(ip, remote_cmd) if run_remote else ""
        for dev in parse_paired_output(stdout, target):
            dev.vps_ip = ip
            devices.append(dev)
        scanned.extend(f"{target}/{inst}" for inst in instances)

    return devices, scanned, unreachable


def run_instance_remove(
    instance_map: List[Tuple[str, str]],
    *,
    resolve_ip: Optional[Callable[[str], Optional[str]]] = None,
    run_remote: Optional[Callable[[str, str], str]] = None,
    log: Optional[Callable[[str], None]] = None,
    max_devices: int = MAX_REMOVE_DEVICES,
) -> InstanceRemoveResult:
    """Phase 2 (v3.6): Instanz-Remove ueber alle VPS (1 SSH pro VPS).

    Fuehrt build_instance_remove_remote_cmd je VPS-Gruppe aus und aggregiert
    removed/failed/limit_hit/scanned/unreachable. UNREACHABLE-Semantik wie
    run_discovery (VPS down → ueberspringen, unreachable-Liste).
    """
    log = log or (lambda _msg: None)
    result = InstanceRemoveResult()

    for target, instances in group_by_vps(instance_map).items():
        node = node_for_target(target)
        ip = resolve_ip(node) if resolve_ip else None
        if not ip:
            result.unreachable.append(node)
            log(f"⚠️  VPS {node} nicht erreichbar, ueberspringe")
            continue
        remote_cmd = build_instance_remove_remote_cmd(instances, max_devices=max_devices)
        log(f"🗑️  SSH {node} ({target}): {', '.join(instances)} – Entferne ALLE gepaarten Geraete")
        stdout = run_remote(ip, remote_cmd) if run_remote else ""
        parsed = parse_instance_remove_output(stdout, target)
        result.removed.extend(parsed.removed)
        result.failed.extend(parsed.failed)
        result.limit_hit = result.limit_hit or parsed.limit_hit
        result.scanned.extend(parsed.scanned)
    result.scanned = _dedupe(result.scanned)
    return result



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
    action: str = "approve",
) -> Optional[DiscoveryResult]:
    """Parst die Ein-Job-Remote-Ausgabe (JSON-Blöcke + Aktion-Blöcke + FOUND).

    Marker (v3.0, R02-Umsetzung): `---JSON-BEGIN:<inst>:<typ>---` …
    `---JSON-END:<inst>:<typ>---` (typ = telegram|device – auch bei type=both
    eindeutig), `---APPROVE-BEGIN:<inst>:<typ>---` … `---APPROVE-END:...---`,
    `---FOUND:1|0---`.

    v3.2 (Reject-Modus): `action` waehlt die Marker-Menge – "approve"
    (APPROVE-BEGIN/END/FAILED), "reject" (REJECT-BEGIN/END/FAILED) oder
    v3.4 "remove" (REMOVE-BEGIN/END/FAILED) – disjunkt, damit ein
    Reject-/Remove-Lauf nicht als Approve-Lauf gelesen wird und umgekehrt.
    approved=True gilt fuer die jeweilige Aktion (Reject → rejected,
    Remove → removed).

    Der ID-Match wird hier in Python verifiziert (_action_entries +
    entry_matches_id, R08); approved=True nur wenn zusätzlich Aktion-Marker +
    FOUND=1 vorliegen (Aktion wirklich in der Session gelaufen).

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
        for entry in _action_entries(data, block_typ, action):
            if request_id and entry_matches_id(entry, request_id, block_typ, action):
                # v3.3.1: requestId (UUID-36) vor deviceId (64er-Hash)
                # bevorzugen – konsistent zum kanonischen ID-Feld.
                matched = (
                    instance,
                    block_typ,
                    entry.get("code")
                    or entry.get("requestId")
                    or entry.get("deviceId")
                    or request_id,
                )
                break
        if matched:
            break

    # v3.2/v3.4: Marker-Menge je Aktion (approve|reject|remove) – disjunkt
    # geparst, damit ein Reject-/Remove-Lauf nicht als Approve-Lauf gelesen
    # wird und umgekehrt.
    if action == "reject":
        action_blocks_re = REJECT_BLOCK_RE
        action_failed_re = REJECT_FAILED_RE
    elif action == "remove":
        action_blocks_re = REMOVE_BLOCK_RE
        action_failed_re = REMOVE_FAILED_RE
    else:
        action_blocks_re = APPROVE_BLOCK_RE
        action_failed_re = APPROVE_FAILED_RE
    action_blocks = list(action_blocks_re.finditer(stdout))
    action_failed = [m.group("label") for m in action_failed_re.finditer(stdout)]
    # B2: approved nur wenn Aktion-Block vorhanden, FOUND=1 UND kein
    # <ACTION>-FAILED-Marker (Aktion-Exit-Code war 0).
    approved = bool(action_blocks) and found_flag and not action_failed

    if matched:
        instance, block_typ, matched_id = matched
        rid = request_id or matched_id
    elif approved:
        # Aktion-Marker sind autoritativ (Shell hat den Fund bestätigt) –
        # konsistent mit dem Python-Match, da beide dieselben Felder nutzen.
        instance, block_typ = _split_label(action_blocks[0].group("label"))
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
            b.group("body").strip() for b in action_blocks
        ),
        action=action,
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
    action: str = "approve",
) -> DiscoveryResult:
    """Ein-Job-Kern (v3.0): Discovery + Aktion in EINER SSH-Session pro VPS.

    Gruppiert die Instanz-Map nach VPS (group_by_vps), baut pro VPS das
    Remote-Template (build_ein_job_remote_cmd) und parst die Marker-Ausgabe
    (parse_ein_job_output). Die Aktion (Approve ODER Reject, v3.2) läuft
    direkt in der SSH-Session beim Fund – auch auf prod (Owner-Entscheidung:
    kein Environment-Gate).

    Args:
        instance_map: gefilterte [(instance_name, target), ...]
        request_id: zu suchende ID
        derived_type: telegram|device|both (auto wird aus dem ID-Format abgeleitet)
        resolve_ip(node) -> ip|None  (None = VPS down; wird als UNREACHABLE gesammelt)
        run_remote(vps_ip, remote_cmd) -> stdout der SSH-Session
        approve: True = Ein-Job (Aktion in der Session), False = nur Discovery
        github_output: Pfad für $GITHUB_OUTPUT (request_id, found_*, derived_type)
        action: "approve" (Default) | "reject" | "remove" – waehlt Marker +
                Kommando (v3.2/v3.4; reject/remove nur device-Requests)

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
            derived_type, instances, request_id, approve=approve, action=action
        )
        log(f"🔍 SSH {node} ({target}): {', '.join(instances)} – Quelle(n): {derived_type}")
        stdout = run_remote(ip, remote_cmd) if run_remote else ""

        result = parse_ein_job_output(
            stdout, derived_type, request_id, target, action=action
        )
        if result is None:
            continue  # kein Fund auf diesem VPS → nächster VPS

        result.vps_ip = ip
        result.scanned = _dedupe(scanned + result.scanned)
        result.unreachable = list(unreachable)
        if github_output:
            _write_github_output(github_output, result, derived_type)
        if result.approved:
            if action == "reject":
                aktion = "rejected"
            elif action == "remove":
                aktion = "entfernt"
            else:
                aktion = "freigegeben"
            log(f"✅ Request-ID in {target}/{result.instance} gefunden und {aktion} "
                f"(Typ: {result.found_type})!")
        else:
            log(f"🔎 Request-ID in {target}/{result.instance} gefunden "
                f"(Typ: {result.found_type}, ohne Aktion)")
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


def build_list_result_json(
    status: str,
    entries: List[PendingEntry],
    scanned: List[str],
    unreachable: List[str],
    filters_applied: dict,
) -> dict:
    """Rueckgabe-Schema des Listen-Modus (Design §11).

    status = "list_ok"; entries = Liste aller pending-Eintraege (auch leer –
    Exit 0, gruener Run). platform "" = Wahrheit (R04); requestId (UUID-36)
    = approve/reject-ID des pending Eintrags, "" wenn nicht vorhanden (v3.3).
    """
    return {
        "status": status,
        "entries": [pending_entry_to_dict(e) for e in entries],
        "scanned": scanned,
        "unreachable": unreachable,
        "filters_applied": filters_applied,
    }


def build_instance_remove_result_json(
    status: str,
    *,
    removed_count: int,
    per_instance: List[dict],
    failed: List[dict],
    scanned: List[str],
    filters_applied: dict,
    unreachable: Optional[List[str]] = None,
    limit_hit: bool = False,
    request_id: str = "",
) -> dict:
    """Rueckgabe-Schema des Instanz-Remove (v3.6, scope=instance).

    Erweiterung zum Minor-#7-Schema (Owner-Entscheidung 2026-08-08):
    removed_count (Anzahl entfernt), per_instance-Aufschluesselung
    ({"instance": …, "removed": n, "failed": n}), failed-Details
    ({"instance": …, "device_id": …, "output": …}) und limit_hit
    (Shell-Hard-Cap gegriffen). Die bestehenden Felder (status, id, found,
    scanned, filters_applied) bleiben erhalten – fuer scope=device unveraendert.

    status ∈ {removed, partial, error, not_found}:
      removed    = alle entfernt (Exit 0)
      partial    = einige entfernt, einige fehlgeschlagen (Exit 1)
      error      = keines entfernt + Fehler ODER limit_hit (Exit 1/2)
      not_found  = keine gepaarten Geraete gefunden (Exit 0)
    """
    return {
        "status": status,
        "id": request_id,
        "scope": "instance",
        "removed_count": removed_count,
        "per_instance": per_instance,
        "failed": failed,
        "limit_hit": limit_hit,
        "found": [],
        "scanned": scanned,
        "unreachable": unreachable or [],
        "filters_applied": filters_applied,
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
    parser.add_argument("--reject", action="store_true",
                        help="Ein-Job-Reject (v3.2): Request per `openclaw devices reject <ID>` "
                             "in der SSH-Session ablehnen (nur device-Requests)")
    parser.add_argument("--remove", action="store_true",
                        help="Ein-Job-Remove (v3.4): gepaartes Geraet per "
                             "`openclaw devices remove <deviceId>` in der SSH-Session "
                             "entfernen (nur device, matcht paired[].deviceId=64-hex)")
    # Validierungs-Modus (Workflow-Step "Eingaben validieren", DRY mit approve.py)
    parser.add_argument("--validate-id", help="Nur ID validieren + Typ ableiten (stdout), exit 0/2")
    opts = parser.parse_args(args)

    if opts.approve and (opts.reject or opts.remove):
        parser.error("--approve schliesst --reject/--remove aus")
    if opts.reject and opts.remove:
        parser.error("--reject und --remove schliessen sich aus")

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

    # v3.2/v3.4: Reject-/Remove-Modus nur fuer device-Requests (openclaw CLI
    # hat weder 'pairing reject' noch 'pairing remove', empirisch 2026-08-07)
    # – Fail-Fast vor dem SSH-Aufbau.
    action = "reject" if opts.reject else ("remove" if opts.remove else "approve")
    if action in ("reject", "remove") and derived_type != "device":
        aktion_name = "Reject" if action == "reject" else "Remove"
        print(f"❌ {aktion_name}-Modus unterstuetzt nur device-Requests – die openclaw CLI "
              f"hat kein 'pairing {action}' (nur `openclaw devices {action} <ID>`).",
              file=sys.stderr)
        return 2

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
            approve=opts.approve or opts.reject or opts.remove,
            github_output=os.environ.get("GITHUB_OUTPUT"),
            log=log,
            action=action,
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

    if (opts.approve or opts.reject or opts.remove) and not result.approved:
        if opts.remove:
            aktion, marker_name = "Remove", "REMOVE"
        elif opts.reject:
            aktion, marker_name = "Reject", "REJECT"
        else:
            aktion, marker_name = "Approve", "APPROVE"
        print(
            f"❌ ID '{opts.request_id}' gefunden, aber {aktion} wurde nicht in der "
            f"SSH-Session bestätigt ({marker_name}-Marker fehlen).",
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
