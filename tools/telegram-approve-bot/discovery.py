#!/usr/bin/env python3
"""Discovery-Kern fuer 06-device-approve-telegram.yml (Design 05, D1).

Such eine Request-ID ueber alle enabled Instanzen (SSoT-Map aus sot_parser.py):
pro Instanz VPS-IP via Tailscale-API (fields=hostname,addresses,lastSeen, mit
'-1'-Suffix-Fallback, Major #6) aufloesen, per SSH `openclaw devices list` holen,
Request-ID als Substring suchen. Erster Fund gewinnt (break-Semantik wie Konzept
§2.1). Nicht erreichbare VPS werden gesammelt und in der Fehlermeldung ausgegeben
(Minor #15).

Nachtrag 2026-08-06 (Orchestrator/Realfall): Eine Request-ID
(b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5) war auf dem lokalen Gateway nicht pending
(pending: []) – genau der D1-Anwendungsfall. Der Discovery-Scan findet die ID
instanzuebergreifend auf der richtigen Instanz, unabhaengig vom aufrufenden
Gateway. Netzwerk-/Prozess-Aufrufe sind injizierbar -> unit-testbar OHNE echte
Tailscale-/SSH-Calls (tools/tests: tests/device-approve/test_discovery.py).

CLI (Workflow-Step):
  python3 discovery.py --instance-map <name|target-zeilen> --request-id <id> \
    --vps-user <user> --ssh-key <pfad> --ts-tailnet <tailnet> \
    --ts-client-id <id> --ts-client-secret <secret>
  - schreibt found_instance/found_target/found_vps_ip in $GITHUB_OUTPUT (falls gesetzt)
  - exit 0 bei Fund, exit 1 mit klarer Fehlermeldung (inkl. UNREACHABLE) sonst
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from typing import Callable, List, Optional, Tuple

# SSH-Optionen identisch zum Konzept §2.1 / Workflows 04/05.
SSH_OPTS = [
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "ConnectTimeout=10",
    "-o", "LogLevel=ERROR",
]
DEVICES_LIST_CMD = "sudo docker exec openclaw-{instance} openclaw devices list 2>/dev/null"

# Timeouts (Konzept: --max-time 30 fuer API, ConnectTimeout=10 fuer SSH).
API_TIMEOUT = 30
SSH_TIMEOUT = 25

# NODE-Konvention M1a: 1:1 target<->VPS-Hostname (VPS-Combi erst M5).
def node_for_target(target: str) -> str:
    return f"vps-{target}"


class RequestNotFoundError(Exception):
    """Request-ID auf keiner enabled Instanz gefunden (inkl. unerreichbarer VPS)."""

    def __init__(self, request_id: str, unreachable: List[str]):
        self.request_id = request_id
        self.unreachable = unreachable
        lines = [f"Request-ID '{request_id}' auf keiner enabled Instanz gefunden"]
        lines.append(f"Übersprungen (VPS down): {' '.join(unreachable) if unreachable else 'keine'}")
        super().__init__("\n".join(lines))


def fetch_tailscale_token(client_id: str, client_secret: str, timeout: int = API_TIMEOUT) -> str:
    """OAuth-Token von der Tailscale-API (ersetzt curl|jq des Konzepts, stdlib-only)."""
    data = urllib.parse.urlencode(
        {"client_id": client_id, "client_secret": client_secret}
    ).encode("ascii")
    req = urllib.request.Request(
        "https://api.tailscale.com/api/v2/oauth/token", data=data, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 – Tailscale-API fest
        payload = json.load(resp)
    return payload["access_token"]


def resolve_vps_ip(tailnet: str, token: str, node: str, timeout: int = API_TIMEOUT) -> Optional[str]:
    """VPS-IP via Tailscale-API; -1-Suffix-Fallback (Major #6), wie Workflows 04/05."""
    url = (
        f"https://api.tailscale.com/api/v2/tailnet/{tailnet}/devices"
        "?fields=hostname,addresses,lastSeen"
    )
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        devices = json.load(resp).get("devices", [])
    for device in devices:
        # Reihenfolge wie jq-select: erster Treffer (exakt oder '-1') gewinnt.
        if device.get("hostname") in (node, f"{node}-1"):
            addresses = device.get("addresses") or []
            return addresses[0] if addresses else None
    return None


def list_devices_ssh(instance: str, vps_ip: str, vps_user: str, ssh_key: str) -> str:
    """SSH: openclaw devices list auf der Instanz (Fehler -> leerer String wie Bash '|| echo ""')."""
    cmd = (
        ["ssh", "-i", ssh_key] + SSH_OPTS +
        [f"{vps_user}@{vps_ip}", DEVICES_LIST_CMD.format(instance=instance)]
    )
    proc = subprocess.run(  # noqa: S603 – Aufruf auf GH-Runner, Befehle sind fix/parametrisiert
        cmd, capture_output=True, text=True, timeout=SSH_TIMEOUT
    )
    return proc.stdout or ""


def run_discovery(
    instance_map: List[Tuple[str, str]],
    request_id: str,
    resolve_ip: Callable[[str], Optional[str]],
    list_devices: Callable[[str, str, str], str],
    github_output: Optional[str] = None,
    log: Optional[Callable[[str], None]] = None,
) -> Tuple[str, str, str]:
    """Kernlogik (D1): findet (instance, target, vps_ip) oder wirft RequestNotFoundError.

    resolve_ip(node) -> ip|None (None = VPS unerreichbar, wird gesammelt);
    list_devices(instance, target, ip) -> Device-Liste als String.
    """
    log = log or (lambda _msg: None)
    unreachable: List[str] = []
    for instance, target in instance_map:
        node = node_for_target(target)
        ip = resolve_ip(node)
        if not ip:
            unreachable.append(node)
            log(f"⚠️  VPS {node} nicht erreichbar, überspringe")
            continue
        log(f"🔍 Suche in {target}/{instance} (VPS {node})...")
        output = list_devices(instance, target, ip)
        if request_id in output:  # Substring-Match wie 'grep -q' – aber literal (kein Regex-Overmatch)
            found = (instance, target, ip)
            if github_output:
                with open(github_output, "a", encoding="utf-8") as fh:
                    fh.write(
                        f"found_instance={found[0]}\n"
                        f"found_target={found[1]}\n"
                        f"found_vps_ip={found[2]}\n"
                    )
            log(f"✅ Request-ID in {target}/{instance} gefunden!")
            return found
    raise RequestNotFoundError(request_id, unreachable)


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:]) if argv is None else argv
    parser = argparse.ArgumentParser(description="D1-Discovery-Scan (Device-Approve)")
    parser.add_argument("--instance-map", required=True, help="Datei mit 'name|target'-Zeilen")
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--vps-user", required=True)
    parser.add_argument("--ssh-key", required=True)
    parser.add_argument("--ts-tailnet", required=True)
    parser.add_argument("--ts-client-id", required=True)
    parser.add_argument("--ts-client-secret", required=True)
    opts = parser.parse_args(args)

    instance_map: List[Tuple[str, str]] = []
    with open(opts.instance_map, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            name, _, target = line.partition("|")
            instance_map.append((name, target))

    def log(msg: str) -> None:
        print(msg, file=sys.stderr)

    token = fetch_tailscale_token(opts.ts_client_id, opts.ts_client_secret)

    def resolve_ip(node: str) -> Optional[str]:
        return resolve_vps_ip(opts.ts_tailnet, token, node)

    def list_devices(instance: str, _target: str, ip: str) -> str:
        return list_devices_ssh(instance, ip, opts.vps_user, opts.ssh_key)

    try:
        run_discovery(
            instance_map,
            opts.request_id,
            resolve_ip,
            list_devices,
            github_output=os.environ.get("GITHUB_OUTPUT"),
            log=log,
        )
    except RequestNotFoundError as err:
        print(f"❌ {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
