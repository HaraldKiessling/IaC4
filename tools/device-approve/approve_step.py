#!/usr/bin/env python3
"""Approve-only-Step v2.2 – typ-spezifischer SSH-Approve (Rollen-Trennung, Major #2).

Korrigiert nach CLI-Fakten (Δ2, 2026-08-06):
  telegram → `sudo docker exec openclaw-<inst> openclaw pairing approve telegram <CODE>`
  device   → `sudo docker exec openclaw-<inst> openclaw devices approve <ID>`

Discovery laeuft im eigenen Job (discovery.py); dieses Script fuehrt NUR den
Approve aus. Das Environment-Gate im approve-Job bleibt damit wirksam.

Validation (defense in depth):
  - Request-ID typ-spezifisch: telegram ^[A-Z0-9]{6,12}$ / device ^[0-9a-fA-F-]{36,128}$
  - Instanz: ^oc[1-9][0-9]*$ (Minor #4, kein oc0)
  - subprocess.run ohne Shell (Argument-Liste); ID/Code sind regex-scharf
    (keine Shell-Metazeichen im Zeichensatz) → kein Injection-Vektor.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from typing import List, Optional

# Eindeutiger Modulname (Kollisionsschutz, s. approve.py – v1-Tests importieren
# tools/telegram-approve-bot/discovery.py unter "discovery").
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS_DIR)


def _load_sibling_module(filename: str, unique_name: str):
    spec = importlib.util.spec_from_file_location(
        unique_name, os.path.join(_THIS_DIR, filename)
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module  # dataclass/__module__-Aufloesung
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


discovery = _load_sibling_module("discovery.py", "device_approve.discovery")
validate_and_classify_id = discovery.validate_and_classify_id
validate_instance = discovery.validate_instance

SSH_OPTS = [
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "ConnectTimeout=10",
    "-o", "LogLevel=ERROR",
]
SSH_TIMEOUT = 30

# Δ2: zwei Approve-Befehlstemplates statt einem
APPROVE_CMD_TEMPLATES = {
    "telegram": "sudo docker exec openclaw-{instance} openclaw pairing approve telegram {request_id}",
    "device": "sudo docker exec openclaw-{instance} openclaw devices approve {request_id}",
}

VALID_TYPES = ("telegram", "device")


def build_approve_cmd(
    found_type: str,
    instance: str,
    request_id: str,
) -> str:
    """Baut das typ-spezifische Approve-Kommando (validiert VOR dem Bau).

    Raises:
        ValueError: unbekannter Typ / ID entspricht nicht dem Typ-Format /
                    Instanz ungueltig
    """
    if found_type not in VALID_TYPES:
        raise ValueError(f"Unbekannter Typ: '{found_type}'. Erlaubt: telegram, device.")
    valid, _, err = validate_and_classify_id(request_id, found_type)
    if not valid:
        raise ValueError(err)
    validate_instance(instance)
    return APPROVE_CMD_TEMPLATES[found_type].format(instance=instance, request_id=request_id)


def validate_and_build_cmd(
    found_type: str,
    instance: str,
    vps_ip: str,
    vps_user: str,
    ssh_key: str,
    request_id: str,
) -> List[str]:
    """Validiert und baut das SSH-Kommando (Argument-Liste, keine Shell)."""
    remote_cmd = build_approve_cmd(found_type, instance, request_id)
    return (
        ["ssh", "-i", ssh_key]
        + SSH_OPTS
        + [f"{vps_user}@{vps_ip}", remote_cmd]
    )


def run_approve_ssh(
    found_type: str,
    instance: str,
    vps_ip: str,
    vps_user: str,
    ssh_key: str,
    request_id: str,
    *,
    runner=None,
    timeout: int = SSH_TIMEOUT,
) -> subprocess.CompletedProcess:
    """SSH-Approve – subprocess.run auf dem Runner.

    Args:
        runner: Optional, injizierbar (default subprocess.run)
        timeout: SSH-Timeout in Sekunden
    Returns:
        subprocess.CompletedProcess mit returncode, stdout, stderr
    Raises:
        ValueError bei ungueltiger ID/Instanz/Typ
        subprocess.TimeoutExpired bei SSH-Timeout
    """
    cmd = validate_and_build_cmd(
        found_type, instance, vps_ip, vps_user, ssh_key, request_id
    )
    return (runner or subprocess.run)(  # noqa: S603 – keine Shell, Argument-Liste
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def build_approve_result(
    status: str,
    request_id: str,
    target: str = "",
    instance: str = "",
    found_type: str = "unknown",
    vps_ip: str = "",
) -> dict:
    """Einheitliches Approve-Result (Teilschema, Minor #7)."""
    found = []
    if target and instance:
        found.append({
            "target": target,
            "instance": instance,
            "type": found_type,
            "vps_ip": vps_ip,
        })
    return {
        "status": status,
        "id": request_id,
        "found": found,
        "scanned": [f"{target}/{instance}"] if target and instance else [],
        "filters_applied": {"type": found_type},
    }


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:]) if argv is None else argv
    parser = argparse.ArgumentParser(
        description="SSH-only Approve v2.2 (Major #2, Rollen-Trennung)"
    )
    parser.add_argument("--found-type", required=True, help="telegram|device (aus Discovery)")
    parser.add_argument("--found-instance", required=True, help="OC-Instanz (z.B. oc1)")
    parser.add_argument("--target", required=True, help="VPS-Target (dev|prod)")
    parser.add_argument("--vps-ip", required=True, help="Tailscale-IP des VPS")
    parser.add_argument("--vps-user", required=True)
    parser.add_argument("--ssh-key", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--result-json", help="Ergebnis-JSON in Datei schreiben (optional)")
    opts = parser.parse_args(args)

    try:
        proc = run_approve_ssh(
            found_type=opts.found_type,
            instance=opts.found_instance,
            vps_ip=opts.vps_ip,
            vps_user=opts.vps_user,
            ssh_key=opts.ssh_key,
            request_id=opts.request_id,
        )
    except ValueError as exc:
        print(f"❌ Validierungsfehler: {exc}", file=sys.stderr)
        if opts.result_json:
            result = build_approve_result(
                status="error",
                request_id=opts.request_id,
                target=opts.target,
                instance=opts.found_instance,
                found_type=opts.found_type,
                vps_ip=opts.vps_ip,
            )
            with open(opts.result_json, "w", encoding="utf-8") as fh:
                json.dump(result, fh, ensure_ascii=False)
        return 2
    except subprocess.TimeoutExpired as exc:
        print(f"❌ SSH-Timeout: {exc}", file=sys.stderr)
        if opts.result_json:
            result = build_approve_result(
                status="error",
                request_id=opts.request_id,
                target=opts.target,
                instance=opts.found_instance,
                found_type=opts.found_type,
                vps_ip=opts.vps_ip,
            )
            with open(opts.result_json, "w", encoding="utf-8") as fh:
                json.dump(result, fh, ensure_ascii=False)
        return 1

    rc = proc.returncode
    if rc != 0:
        print(f"❌ SSH-Approve fehlgeschlagen (rc={rc})", file=sys.stderr)
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)

    result = build_approve_result(
        status="approved" if rc == 0 else "error",
        request_id=opts.request_id,
        target=opts.target,
        instance=opts.found_instance,
        found_type=opts.found_type,
        vps_ip=opts.vps_ip,
    )

    if opts.result_json:
        with open(opts.result_json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False)

    print(json.dumps(result, ensure_ascii=False))
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
