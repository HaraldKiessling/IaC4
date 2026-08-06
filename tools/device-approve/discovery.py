#!/usr/bin/env python3
"""Discovery-Kern v2.2 – Unified ID-basierte Freigabe (Design 05 v2.2).

Korrigiert nach CLI-Fakten (v2.1-Annahme widerlegt, 2026-08-06):
  Δ1: Telegram-Pairing erscheint NICHT in `devices list --json`, sondern in
      `openclaw pairing list <channel> --json` – separater Befehlspfad.
  Δ2: ZWEI Approve-Kommandos: `openclaw pairing approve telegram <CODE>` (Telegram)
      vs. `openclaw devices approve <ID>` (Device).
  Δ3/Δ5: ZWEI ID-Formate: Telegram-Kurzcode ^[A-Z0-9]{6,12}$ (z.B. QVDCXJEM)
      und Device-ID ^[0-9a-fA-F-]{36,128}$ (64-Hex wie 9df47d69… oder UUID-Stil).
  Δ4: Typ-Ableitung aus ID-Format (kein clientId/clientMode); expliziter
      type-Input (telegram|device|both) überschreibt.
  Δ6: Discovery ist strikt getrennt vom Approve (approve_step.py).
      GITHUB_OUTPUT: request_id, found_target, found_instance, found_vps_ip,
      found_type, derived_type.

Empirisch (Sandbox, OpenClaw 2026.7.1, 2026-08-06):
  - `openclaw pairing list telegram --json` → {"channel": "telegram", "requests": []}
    (F10 beantwortet: kein Fehler, Schema-Feld ist "requests"; der Parser liest
    defensiv "requests" mit Fallback auf "pending" – F1a bleibt für Eintragsfelder offen)
  - `openclaw devices list --json` → {"pending": [...], "paired": [...]}

Bausteine aus v1 (behalten): Tailscale-API fields=hostname,addresses,lastSeen mit
'-1'-Suffix-Fallback (Major #6), UNREACHABLE-Liste (Minor #15), Break-Semantik,
injizierbare Netzwerk-/SSH-Calls (unit-testbar ohne echte Tailscale-/SSH-Zugriffe).
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
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

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

SSH_OPTS = [
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "ConnectTimeout=10",
    "-o", "LogLevel=ERROR",
]
# Δ1: getrennte Discovery-Quellen je Typ
PAIRING_LIST_CMD = (
    "sudo docker exec openclaw-{instance} openclaw pairing list telegram --json 2>/dev/null"
)
DEVICES_LIST_CMD = (
    "sudo docker exec openclaw-{instance} openclaw devices list --json 2>/dev/null"
)

API_TIMEOUT = 30
SSH_TIMEOUT = 25


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


# ── Discovery-Result (einheitliches Teilschema, Minor #7) ──


@dataclass
class DiscoveryResult:
    request_id: str
    instance: str
    target: str
    vps_ip: Optional[str]
    found_type: str = "unknown"  # telegram|device (über welchen Pfad gefunden)
    scanned: List[str] = field(default_factory=list)
    unreachable: List[str] = field(default_factory=list)


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


def list_entries_ssh(
    instance: str, vps_ip: str, vps_user: str, ssh_key: str, typ: str
) -> str:
    """SSH: typ-spezifische Discovery-Quelle (Δ1).

    telegram → `openclaw pairing list telegram --json` (ID-Feld: code)
    device   → `openclaw devices list --json`            (ID-Feld: deviceId)

    Fehler (z.B. pairing list ohne konfigurierten Kanal, F10) werden durch
    stderr-Redirect + leerer stdout-Ausgabe gefangen → Discovery überspringt
    die Instanz (fail-safe, Design §8).
    """
    if typ == "telegram":
        remote_cmd = PAIRING_LIST_CMD.format(instance=instance)
    elif typ == "device":
        remote_cmd = DEVICES_LIST_CMD.format(instance=instance)
    else:
        raise ValueError(f"Unbekannter Discovery-Typ: {typ}")
    cmd = (
        ["ssh", "-i", ssh_key]
        + SSH_OPTS
        + [f"{vps_user}@{vps_ip}", remote_cmd]
    )
    proc = subprocess.run(  # noqa: S603 – Befehle fix/parametrisiert, keine Shell
        cmd, capture_output=True, text=True, timeout=SSH_TIMEOUT
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


# ── Discovery-Kern (v2.2: typ-spezifischer Pfad, types-outer) ──


def _types_to_try(derived_type: str) -> List[str]:
    """Discovery-Pfade aus dem (bereits validierten) Typ ableiten."""
    if derived_type == "both":
        return ["telegram", "device"]
    if derived_type in ("telegram", "device"):
        return [derived_type]
    raise ValueError(
        f"Ungueltiger Discovery-Typ: '{derived_type}'. Erlaubt: telegram, device, both."
    )


def run_discovery(
    instance_map: List[Tuple[str, str]],
    request_id: str,
    derived_type: str = "auto",
    resolve_ip: Optional[Callable[[str], Optional[str]]] = None,
    list_entries: Optional[Callable[[str, str, str, str], str]] = None,
    github_output: Optional[str] = None,
    log: Optional[Callable[[str], None]] = None,
) -> DiscoveryResult:
    """Kernlogik: findet (instance, target, vps_ip, found_type) oder wirft
    RequestNotFoundError.

    Scan-Reihenfolge (Design §3c): types outer (telegram vor device bei 'both'),
    Instanzen inner in Map-Reihenfolge; erster Fund stoppt den Scan (Break).
    VPS-IPs werden pro Node gecacht (kein doppelter Tailscale-Call bei 'both').

    Args:
        instance_map: gefilterte [(instance_name, target), ...]
        request_id: zu suchende ID
        derived_type: telegram|device|both (auto wird aus dem ID-Format abgeleitet)
        resolve_ip(node) -> ip|None  (None = VPS down; wird als UNREACHABLE gesammelt)
        list_entries(instance, target, vps_ip, typ) -> JSON-Ausgabe der Quelle
        github_output: Pfad für $GITHUB_OUTPUT (request_id, found_*, derived_type)
    """
    log = log or (lambda _msg: None)

    if derived_type == "auto":
        derived_type = derive_type(request_id)
        if derived_type == "unknown":
            raise ValueError(
                f"ID '{request_id}' passt zu keinem bekannten Format "
                f"(Telegram: ^[A-Z0-9]{{6,12}}, Device: ^[0-9a-fA-F-]{{36,128}})"
            )
    types_to_try = _types_to_try(derived_type)

    scanned: List[str] = []
    unreachable: List[str] = []
    ip_cache: dict = {}

    for typ in types_to_try:
        for instance, target in instance_map:
            node = node_for_target(target)
            if node not in ip_cache:
                ip_cache[node] = resolve_ip(node) if resolve_ip else None
            ip = ip_cache[node]
            if not ip:
                unreachable.append(node)
                log(f"⚠️  VPS {node} nicht erreichbar, ueberspringe")
                continue

            log(f"🔍 Suche in {target}/{instance} (VPS {node}, Quelle: {typ})...")
            output = list_entries(instance, target, ip, typ) if list_entries else ""
            entry_label = f"{target}/{instance}"
            if entry_label not in scanned:
                scanned.append(entry_label)

            try:
                data = json.loads(output) if output.strip() else {}
            except (json.JSONDecodeError, TypeError) as exc:
                log(f"⚠️  {typ}-Liste auf {target}/{instance} nicht als JSON parsebar – uebersprungen ({exc})")
                continue

            for entry in parse_entries(data, typ):
                if entry_matches_id(entry, request_id, typ):
                    result = DiscoveryResult(
                        request_id=request_id,
                        instance=instance,
                        target=target,
                        vps_ip=ip,
                        found_type=typ,
                        scanned=scanned,
                        unreachable=unreachable,
                    )
                    if github_output:
                        with open(github_output, "a", encoding="utf-8") as fh:
                            fh.write(
                                f"request_id={result.request_id}\n"
                                f"found_target={result.target}\n"
                                f"found_instance={result.instance}\n"
                                f"found_vps_ip={result.vps_ip}\n"
                                f"found_type={result.found_type}\n"
                                f"derived_type={derived_type}\n"
                            )
                    log(f"✅ Request-ID in {target}/{instance} gefunden (Typ: {typ})!")
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
        description="D1-Discovery-Scan v2.2 (typ-spezifische Quellen, GITHUB_OUTPUT)"
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

    def list_entries(instance: str, _target: str, ip: str, typ: str) -> str:
        return list_entries_ssh(instance, ip, opts.vps_user, opts.ssh_key, typ)

    try:
        result = run_discovery(
            filtered_map,
            opts.request_id,
            derived_type=derived_type,
            resolve_ip=resolve_ip,
            list_entries=list_entries,
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
