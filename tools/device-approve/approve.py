#!/usr/bin/env python3
"""CLI-Fassade v3.0 – Unified Freigabe (Ein-Job-Fast-Path, Workflow-05-Optimierung).

Modi:
  1. SSH-Modus (Default / --full-run): Discovery + Approve in EINEM Aufruf –
     pro VPS EINE SSH-Session (Remote-Loop mit JSON-/APPROVE-/FOUND-Markern,
     discovery.py v3.0). Der Approve läuft direkt in der Session beim Fund –
     auch auf prod (Owner-Entscheidung: kein Environment-Gate).
  2. Lokaler Modus (--local / APPROVE_LOCAL=1): openclaw CLI direkt auf dem
     Gateway (Owner-Testläufe ohne SSH/Tailscale).
  3. --discover-only: Discovery ohne Approve (Debug/Test).
  4. --list-only (NEU, v3.1): Listen-Modus – ALLE pending Requests ueber alle
     Instanzen auflisten (kein Approve, keine ID noetig). --request-id wird
     ignoriert (Warning, R02), type=auto → both (O3). Exit 0 auch bei leerer
     Liste (gruen); JSON auf stdout, --summary = Markdown-Tabelle in
     $GITHUB_STEP_SUMMARY.
  5. --reject-only (NEU, v3.2): Reject-Modus – ID in der Ein-Job-Remote-
     Schleife suchen und per `openclaw devices reject <ID>` ablehnen
     (REJECT-Marker, B2-Semantik). NUR device-Requests: die openclaw CLI hat
     kein 'pairing reject' (Telegram-Codes sind CLI-seitig nicht reject-bar)
     → derived_type != device ⇒ Exit 2. --full-run --reject-only = Ein-Job-
     Reject (Workflow mode=reject); --reject-only schliesst --list-only/
     --discover-only aus.
  6. --remove-only (NEU, v3.4): Remove-Modus – GEPAARTES Geraet in der
     Ein-Job-Remote-Schleife suchen (Array `paired`, ID-Feld `deviceId`
     64-hex) und per `openclaw devices remove <deviceId>` entfernen
     (REMOVE-Marker, B2-Semantik). NUR device (kein 'pairing remove' in der
     CLI) → derived_type != device ⇒ Exit 2. --full-run --remove-only =
     Ein-Job-Remove (Workflow mode=remove); schliesst --list-only/
     --discover-only/--reject-only aus. Exit-Code-Vertrag: 0 = removed ODER
     not_found (gruen), 1 = error, 2 = config.
  7. --scope device|instance (NEU, v3.6): Remove-Scope – mit
     --remove-only --scope instance werden ALLE gepaarten Geraete der
     gefilterten Instanzen entfernt („Instanz leeren“, gesteuert durch
     --target-filter/--instance-filter; Owner-Entscheidung 2026-08-08).
     ZWEIPHASIG: Phase 1 = Remove-Plan (collect_paired_devices +
     parse_paired_output), dann Max-Limit-Check (MAX_REMOVE_DEVICES=50,
     darueber Exit 2 VOR jedem Remove), Phase 2 = run_instance_remove
     (build_instance_remove_remote_cmd, DEV-REMOVE-Marker). Exit-Code-
     Vertrag v3.6: 0 = alle entfernt ODER not_found (gruen), 1 = Teilerfolg
     (einige fehlgeschlagen, failed im Summary), 2 = Config/Limit. scope=
     device (Default) = unveraenderter ID-basierter Pfad (v3.5-Verhalten
     100%% erhalten). --scope instance schliesst --request-id aus
     (Konflikt → Exit 2) und ist nur mit --remove-only zulaessig.

--summary: JSON auf stdout + Markdown direkt in $GITHUB_STEP_SUMMARY via
File-Open (Review Major #3, Δ7).

v3.0-Änderungen (Review R01-R08):
  - --full-run-Flag: Workflow-Standard (Ein-Job); Discovery + Approve in einem
    Call, 1 SSH pro VPS (group_by_vps), approve_step.py wird nicht mehr
    separat aufgerufen (R03-E12).
  - Input-Name bleibt `id` (Telegram-Bot-Payload client_payload.id, R01);
    instance-Filter bleibt erhalten (R04).
  - Auth: auth_check.sh im Workflow (R07), ID-Validierung via
    discovery.py --validate-id (unverändert).

Env-Vars (statt GH-Context, fuer lokale Owner-Testlaeufe):
  APPROVE_ID, APPROVE_TYPE, APPROVE_TARGET, APPROVE_INSTANCE,
  VPS_USER, SSH_KEY_PATH, TS_TAILNET, TS_CLIENT_ID, TS_CLIENT_SECRET,
  INSTANCE_MAP (optional: Pfad zur SSoT-Map; sonst sot_parser-Generierung),
  SSOT_ROOT (default: .), APPROVE_LOCAL (1 = lokaler Modus)

Rueckgabe-Schema (Minor #7):
  {"status": "approved|found|not_found|error", "id": "...", "found": [...],
   "scanned": [...], "filters_applied": {type, target, instance}}

Exit-Code-Vertrag (Owner-Vereinbarung 2026-08-06 15:06, Run-#6-Befund):
  - 0 = approved ODER rejected ODER removed ODER found ODER not_found  (not_found = gruener Run, kein Fehler)
  - 1 = error (Infrastruktur/Auth/Injection/Aktions-Fehler – bleibt rot)
  - 2 = Validierungs-/Config-Fehler (CLI-Missbrauch, fehlende Credentials,
        Reject/Remove mit Nicht-Device-Typ)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from typing import Callable, List, Optional, Tuple

# Self-Import (Minor #8: echtes Package, sys.path bei Script-Ausfuehrung).
# WICHTIG: discovery.py wird unter einem EINDEUTIGEN Modulnamen geladen
# (device_approve.discovery), damit sys.modules["discovery"] NICHT von
# tools/telegram-approve-bot/discovery.py (v1, gleicher Modulname)
# kollidiert – die v1-Tests (test_discovery.py) importieren das v1-Modul
# weiterhin unter "discovery".
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
from summary import (  # type: ignore[import-untyped]
    instance_remove_to_markdown,
    list_result_to_markdown,
    result_to_markdown,
)

DiscoveryResult = discovery.DiscoveryResult
InstanceRemoveResult = discovery.InstanceRemoveResult
PairedDevice = discovery.PairedDevice
RequestNotFoundError = discovery.RequestNotFoundError
PendingEntry = discovery.PendingEntry
MAX_REMOVE_DEVICES = discovery.MAX_REMOVE_DEVICES
build_instance_remove_result_json = discovery.build_instance_remove_result_json
build_list_result_json = discovery.build_list_result_json
build_result_json = discovery.build_result_json
collect_paired_devices = discovery.collect_paired_devices
derive_type = discovery.derive_type
fetch_tailscale_token = discovery.fetch_tailscale_token
filter_instance_map = discovery.filter_instance_map
parse_entries = discovery.parse_entries
parse_paired_output = discovery.parse_paired_output
resolve_vps_ip = discovery.resolve_vps_ip
run_discovery = discovery.run_discovery
run_instance_remove = discovery.run_instance_remove
run_list_discovery = discovery.run_list_discovery
run_remote_ssh = discovery.run_remote_ssh
validate_and_classify_id = discovery.validate_and_classify_id
validate_instance = discovery.validate_instance
validate_type = discovery.validate_type

SSH_TIMEOUT = 30
LOCAL_TIMEOUT = 15


def load_instance_map_from_file(path: str) -> List[Tuple[str, str]]:
    """Laedt SSoT-Instanz-Map aus 'name|target'-Textdatei."""
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


def load_instance_map_from_ssot(root: str) -> List[Tuple[str, str]]:
    """Generiert Instanz-Map via sot_parser (aus tools/telegram-approve-bot/)."""
    tel_bot_dir = os.path.join(
        os.path.dirname(_THIS_DIR), "telegram-approve-bot"
    )
    sys.path.insert(0, tel_bot_dir)
    try:
        from sot_parser import iter_enabled_instances  # type: ignore[import-untyped]
        return iter_enabled_instances(root)
    except ImportError:
        print(
            "❌ sot_parser nicht importierbar – bitte INSTANCE_MAP angeben.",
            file=sys.stderr,
        )
        sys.exit(2)


# ── Lokaler Modus (ohne SSH, ohne Tailscale) ──


def _local_list_cmd(typ: str) -> List[str]:
    """Δ1: lokale Discovery-Quelle je Typ (openclaw CLI auf dem Gateway)."""
    if typ == "telegram":
        return ["openclaw", "pairing", "list", "telegram", "--json"]
    return ["openclaw", "devices", "list", "--json"]


def _local_approve_cmd(typ: str, request_id: str) -> List[str]:
    """Δ2: lokales Approve-Kommando je Typ."""
    if typ == "telegram":
        return ["openclaw", "pairing", "approve", "telegram", request_id]
    return ["openclaw", "devices", "approve", request_id]


def run_local_discovery(
    request_id: str,
    derived_type: str,
    *,
    runner=None,
    log: Optional[Callable[[str], None]] = None,
    timeout: int = LOCAL_TIMEOUT,
    action: str = "approve",
) -> Tuple[Optional[DiscoveryResult], dict]:
    """Lokale Discovery ueber die openclaw CLI direkt auf dem Gateway.

    Telegram → `openclaw pairing list telegram --json` (Feld code, Schema
    {"channel": ..., "requests": [...]}, F10: Fehler/leer → fail-safe überspringen)
    Device   → `openclaw devices list --json` (Schema pending/paired; Match auf
    requestId (UUID-36, approve/reject-ID) ODER deviceId (64er-Hash) – v3.3.1).
    v3.4 (action="remove"): matcht GEPAARTE Eintraege (Array `paired`, Feld
    `deviceId` 64-hex) – remove adressiert paired, NICHT pending (CLI-Fakt
    `openclaw devices remove <deviceId>`, 2026.7.1).

    Returns:
        (DiscoveryResult | None, stats_dict)
    """
    log = log or (lambda _msg: None)
    stats = {"scanned": ["local/local"], "unreachable": []}

    types_to_try = ["telegram", "device"] if derived_type == "both" else [derived_type]

    for typ in types_to_try:
        cmd_list = _local_list_cmd(typ)
        log(f"🔍 Lokale Discovery ({typ}): {' '.join(cmd_list)}")
        try:
            proc = (runner or subprocess.run)(  # noqa: S603 – keine Shell
                cmd_list, capture_output=True, text=True, timeout=timeout
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            log(f"⚠️  openclaw CLI nicht verfuegbar/Timeout: {exc}")
            continue

        if proc.returncode != 0:
            # F10: pairing list ohne konfigurierten Kanal → Fehler; fail-safe
            log(f"⚠️  {typ}-Liste fehlgeschlagen (rc={proc.returncode}) – uebersprungen")
            continue

        try:
            data = json.loads(proc.stdout) if proc.stdout.strip() else {}
        except json.JSONDecodeError as exc:
            log(f"⚠️  JSON-Parse-Fehler lokal ({typ}): {exc}")
            continue

        # Empirisch (Sandbox 2026-08-06): pairing list → Feld "requests"
        if typ == "telegram":
            entries = data.get("requests") or data.get("pending") or []
            id_fields = ("code",)
        elif action == "remove":
            # v3.4: remove matcht GEPAARTE Eintraege (paired[]) per deviceId
            # (64-hex) – pending[] ist fuer remove irrelevant (CLI-Fakt:
            # `openclaw devices remove <deviceId>` loescht den paired-Eintrag).
            entries = data.get("paired") or []
            id_fields = ("deviceId",)
        else:
            entries = data.get("pending") or []
            # v3.3.1: pending[].requestId (UUID-36) ist die approve/reject-ID
            # (deviceId = 64er-PublicKey-Hash, e2e-Beleg aee3a00); deviceId
            # bleibt als defensiver Fallback für Quellen ohne requestId-Feld.
            id_fields = ("requestId", "deviceId")

        for entry in entries:
            if any(entry.get(f) == request_id for f in id_fields):
                result = DiscoveryResult(
                    request_id=request_id,
                    instance="local",
                    target="local",
                    vps_ip=None,
                    found_type=typ,
                    scanned=stats["scanned"],
                    unreachable=stats["unreachable"],
                )
                log(f"✅ Request-ID lokal gefunden (Typ: {typ})!")
                return result, stats

    return None, stats


def run_local_approve(
    request_id: str,
    found_type: str,
    *,
    runner=None,
    timeout: int = LOCAL_TIMEOUT,
) -> int:
    """Lokaler Approve: typ-spezifisches Kommando (Δ2)."""
    cmd = _local_approve_cmd(found_type, request_id)
    proc = (runner or subprocess.run)(  # noqa: S603 – keine Shell
        cmd, capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0 and proc.stderr:
        print(proc.stderr, file=sys.stderr)
    return proc.returncode


def _local_reject_cmd(typ: str, request_id: str) -> List[str]:
    """Δ3 (v3.2): lokales Reject-Kommando je Typ.

    NUR device – die openclaw CLI hat kein 'pairing reject' (empirisch
    2026-08-07: `openclaw pairing` kennt nur approve|list|help);
    Telegram-Codes sind CLI-seitig nicht reject-bar.
    """
    if typ != "device":
        raise ValueError(
            "Reject-Modus unterstuetzt nur device-Requests (kein 'pairing reject' "
            "in der openclaw CLI – nur `openclaw devices reject <ID>`)."
        )
    return ["openclaw", "devices", "reject", request_id]


def run_local_reject(
    request_id: str,
    found_type: str,
    *,
    runner=None,
    timeout: int = LOCAL_TIMEOUT,
) -> int:
    """Lokaler Reject (v3.2): `openclaw devices reject <ID>` (analog Δ2)."""
    cmd = _local_reject_cmd(found_type, request_id)
    proc = (runner or subprocess.run)(  # noqa: S603 – keine Shell
        cmd, capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0 and proc.stderr:
        print(proc.stderr, file=sys.stderr)
    return proc.returncode


def _local_remove_cmd(typ: str, request_id: str) -> List[str]:
    """Δ4 (v3.4): lokales Remove-Kommando je Typ.

    NUR device – die openclaw CLI hat kein 'pairing remove' (empirisch
    2026-08-07: `openclaw pairing` kennt nur approve|list|help); remove
    adressiert GEPAARTE Geraete per deviceId (64-hex Public-Key-Hash) –
    `openclaw devices remove <deviceId>` (CLI-Fakt 2026.7.1).
    """
    if typ != "device":
        raise ValueError(
            "Remove-Modus unterstuetzt nur device-Eintraege (kein 'pairing remove' "
            "in der openclaw CLI – nur `openclaw devices remove <deviceId>`)."
        )
    return ["openclaw", "devices", "remove", request_id]


def run_local_remove(
    request_id: str,
    found_type: str,
    *,
    runner=None,
    timeout: int = LOCAL_TIMEOUT,
) -> int:
    """Lokaler Remove (v3.4): `openclaw devices remove <deviceId>` (analog Δ2)."""
    cmd = _local_remove_cmd(found_type, request_id)
    proc = (runner or subprocess.run)(  # noqa: S603 – keine Shell
        cmd, capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0 and proc.stderr:
        print(proc.stderr, file=sys.stderr)
    return proc.returncode


def run_local_instance_remove(
    *,
    runner=None,
    log: Optional[Callable[[str], None]] = None,
    timeout: int = LOCAL_TIMEOUT,
    max_devices: int = MAX_REMOVE_DEVICES,
) -> Tuple[dict, int]:
    """Lokaler Instanz-Remove (v3.6, scope=instance) auf dem Gateway.

    Leert die gepaarten Geraete der Gateway-Instanz (`openclaw devices list
    --json` → paired[], dann je deviceId `openclaw devices remove
    <deviceId>`). Gleiche Exit-/Status-Semantik wie der SSH-Pfad:
      - keine gepaarten Geraete → status not_found, Exit 0 (Idempotenz)
      - Plan > max_devices → status error, Exit 2 (Abbruch VOR jedem Remove)
      - alle entfernt → status removed, Exit 0
      - Teilerfolg → status partial, Exit 1; alles fehlgeschlagen → error, 1

    Returns:
        (result_json, exit_code)
    """
    log = log or (lambda _msg: None)
    cmd_list = _local_list_cmd("device")
    log(f"🔍 Lokale Discovery (device): {' '.join(cmd_list)}")
    try:
        proc = (runner or subprocess.run)(  # noqa: S603 – keine Shell
            cmd_list, capture_output=True, text=True, timeout=timeout
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        log(f"⚠️  openclaw CLI nicht verfuegbar/Timeout: {exc}")
        return build_instance_remove_result_json(
            status="error",
            removed_count=0,
            per_instance=[],
            failed=[],
            scanned=[],
            filters_applied={},
            unreachable=["local"],
        ), 1
    if proc.returncode != 0:
        log(f"⚠️  devices list fehlgeschlagen (rc={proc.returncode}) – Abbruch")
        return build_instance_remove_result_json(
            status="error",
            removed_count=0,
            per_instance=[],
            failed=[],
            scanned=[],
            filters_applied={},
        ), 1
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        log(f"⚠️  JSON-Parse-Fehler lokal: {exc}")
        return build_instance_remove_result_json(
            status="error",
            removed_count=0,
            per_instance=[],
            failed=[],
            scanned=[],
            filters_applied={},
        ), 1

    devices = [
        {"device_id": e.get("deviceId") or "",
         "platform": e.get("platform", "") or ""}
        for e in (data.get("paired") or [])
        if e.get("deviceId")
    ]
    if not devices:
        # Idempotenz (Owner-Entscheidung 2026-08-08): 2. Lauf auf leerer
        # Instanz = not_found / 0 entfernt, Exit 0 (gruen).
        return build_instance_remove_result_json(
            status="not_found",
            removed_count=0,
            per_instance=[{"instance": "local", "removed": 0, "failed": 0}],
            failed=[],
            scanned=["local/local"],
            filters_applied={},
        ), 0
    if len(devices) > max_devices:
        # Sicherheits-Limit: Abbruch VOR jedem Remove (Owner-Entscheidung).
        return build_instance_remove_result_json(
            status="error",
            removed_count=0,
            per_instance=[{"instance": "local", "removed": 0, "failed": 0}],
            failed=[],
            scanned=["local/local"],
            filters_applied={},
            limit_hit=True,
        ), 2

    removed: List[Tuple[str, str]] = []
    failed: List[Tuple[str, str, str]] = []
    for dev in devices:
        did = dev["device_id"]
        log(f"🗑️  Lokaler Remove: openclaw devices remove {did[:12]}…")
        rc = run_local_remove(did, "device", runner=runner, timeout=timeout)
        if rc == 0:
            removed.append(("local", did))
        else:
            failed.append(("local", did, f"remove rc={rc}"))

    if failed and removed:
        status = "partial"
    elif failed:
        status = "error"
    else:
        status = "removed"
    per_instance = [{
        "instance": "local",
        "removed": len(removed),
        "failed": len(failed),
    }]
    return build_instance_remove_result_json(
        status=status,
        removed_count=len(removed),
        per_instance=per_instance,
        failed=[{"instance": i, "device_id": d, "output": o} for i, d, o in failed],
        scanned=["local/local"],
        filters_applied={},
    ), (0 if status == "removed" else 1)


def run_local_list_discovery(
    derived_type: str,
    *,
    runner=None,
    log: Optional[Callable[[str], None]] = None,
    timeout: int = LOCAL_TIMEOUT,
) -> Tuple[List[PendingEntry], dict]:
    """Lokale Listen-Discovery: ALLE pending Eintraege der Gateway-Instanz.

    Ergaenzung zum SSH-Pfad (Design §1/2c): `--local --list-only` diagnostiziert
    die Gateway-eigenen pending Requests (der Orchestrator hat kein TS-SSH).
    Telegram → `openclaw pairing list telegram --json` (Feld code),
    Device → `openclaw devices list --json` (Feld deviceId). Defensiv wie
    run_local_discovery: CLI nicht verfuegbar / Fehler / kaputtes JSON →
    Quelle wird uebersprungen (R07).

    Returns:
        (entries, stats) – stats: {"scanned": [...], "unreachable": [...]}
    """
    log = log or (lambda _msg: None)
    stats = {"scanned": ["local/local"], "unreachable": []}
    entries: List[PendingEntry] = []

    types_to_try = ["telegram", "device"] if derived_type == "both" else [derived_type]
    for typ in types_to_try:
        cmd_list = _local_list_cmd(typ)
        log(f"🔍 Lokale Discovery ({typ}): {' '.join(cmd_list)}")
        try:
            proc = (runner or subprocess.run)(  # noqa: S603 – keine Shell
                cmd_list, capture_output=True, text=True, timeout=timeout
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            log(f"⚠️  openclaw CLI nicht verfuegbar/Timeout: {exc}")
            continue
        if proc.returncode != 0:
            log(f"⚠️  {typ}-Liste fehlgeschlagen (rc={proc.returncode}) – uebersprungen")
            continue
        try:
            data = json.loads(proc.stdout) if proc.stdout.strip() else {}
        except json.JSONDecodeError as exc:
            log(f"⚠️  JSON-Parse-Fehler lokal ({typ}): {exc}")
            continue
        for entry in parse_entries(data, typ):
            entries.append(PendingEntry(
                instance="local",
                target="local",
                vps_ip=None,
                entry_type=typ,
                entry_id=entry.get("code") or entry.get("deviceId") or "?",
                # v3.3: requestId (UUID-36) konsistent zum Listen-Modus.
                request_id=entry.get("requestId") or "",
                platform=entry.get("platform", "") or "",
                created_at_ms=entry.get("createdAtMs", 0) or 0,
            ))
    return entries, stats


# ── Haupt-CLI ──


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(
        description="Unified Freigabe v3.0 – CLI-Fassade (--full-run Ein-Job, --discover-only, --summary, --local)"
    )
    ap.add_argument("--request-id", help="Request-ID (oder env APPROVE_ID)")
    ap.add_argument("--type-filter", default=None, help="auto|telegram|device|both")
    ap.add_argument("--target-filter", default=None, help="dev|prod|both")
    ap.add_argument("--instance-filter", default=None, help="all|oc1|oc2|...")
    ap.add_argument("--instance-map", help="Pfad zur SSoT-Map 'name|target' (optional)")
    ap.add_argument("--ssot-root", default=".", help="SSoT-Root (default: .)")
    ap.add_argument("--vps-user", help="VPS-SSH-User (env VPS_USER)")
    ap.add_argument("--ssh-key", help="SSH-Key-Pfad (env SSH_KEY_PATH)")
    ap.add_argument("--ts-tailnet", help="Tailscale-Tailnet (env TS_TAILNET)")
    ap.add_argument("--ts-client-id", help="Tailscale-OAuth-Client-ID (env TS_CLIENT_ID)")
    ap.add_argument("--ts-client-secret", help="Tailscale-OAuth-Client-Secret (env TS_CLIENT_SECRET)")
    ap.add_argument("--discover-only", action="store_true", help="Nur Discovery, kein Approve")
    ap.add_argument("--list-only", action="store_true",
                    help="Listen-Modus (v3.1): ALLE pending Requests auflisten (kein Approve, "
                         "keine ID noetig). Schliesst --full-run/--discover-only aus; "
                         "--request-id wird ignoriert (R02); type=auto → both (O3)")
    ap.add_argument("--reject-only", action="store_true",
                    help="Reject-Modus (v3.2): ID in der Ein-Job-Remote-Schleife suchen und per "
                         "`openclaw devices reject <ID>` ablehnen (REJECT-Marker, B2-Semantik). "
                         "NUR device-Requests – die openclaw CLI hat kein 'pairing reject'. "
                         "Schliesst --list-only/--discover-only aus; --full-run --reject-only = "
                         "Ein-Job-Reject (Workflow mode=reject)")
    ap.add_argument("--remove-only", action="store_true",
                    help="Remove-Modus (v3.4): GEPAARTES Geraet in der Ein-Job-Remote-Schleife "
                         "suchen (Array `paired`, Feld `deviceId` 64-hex) und per "
                         "`openclaw devices remove <deviceId>` entfernen (REMOVE-Marker, "
                         "B2-Semantik). NUR device – die openclaw CLI hat kein 'pairing remove'. "
                         "Schliesst --list-only/--discover-only/--reject-only aus; "
                         "--full-run --remove-only = Ein-Job-Remove (Workflow mode=remove)")
    ap.add_argument("--scope", default=None,
                    choices=["device", "instance"],
                    help="Remove-Scope (v3.6): device (Default) = genau ein Geraet per "
                         "--request-id (bisheriger Pfad); instance = ALLE gepaarten Geraete "
                         "der gefilterten Instanzen entfernen (nur mit --remove-only; "
                         "--request-id muss leer sein; Max-Limit "
                         f"{MAX_REMOVE_DEVICES} Geraete pro Lauf)")
    ap.add_argument("--full-run", action="store_true",
                    help="Ein-Job: Discovery + Approve in einem Aufruf (Workflow-Standard v3.0)")
    ap.add_argument("--summary", action="store_true", help="Markdown-Summary in $GITHUB_STEP_SUMMARY")
    ap.add_argument("--local", action="store_true", help="Lokaler Modus ohne SSH (env APPROVE_LOCAL=1)")

    opts = ap.parse_args(argv)

    if opts.full_run and opts.discover_only:
        ap.error("--full-run und --discover-only schliessen sich aus")
    if opts.reject_only and opts.discover_only:
        ap.error("--reject-only und --discover-only schliessen sich aus")
    if opts.reject_only and opts.list_only:
        ap.error("--reject-only und --list-only schliessen sich aus")
    if opts.remove_only and opts.discover_only:
        ap.error("--remove-only und --discover-only schliessen sich aus")
    if opts.remove_only and opts.list_only:
        ap.error("--remove-only und --list-only schliessen sich aus")
    if opts.remove_only and opts.reject_only:
        ap.error("--remove-only und --reject-only schliessen sich aus")

    # Env-Overrides
    rid = opts.request_id or os.environ.get("APPROVE_ID", "")
    type_f = opts.type_filter or os.environ.get("APPROVE_TYPE", "auto")
    target_f = opts.target_filter or os.environ.get("APPROVE_TARGET", "both")
    inst_f = opts.instance_filter or os.environ.get("APPROVE_INSTANCE", "all")
    scope = opts.scope or os.environ.get("APPROVE_SCOPE", "device")
    vps_user = opts.vps_user or os.environ.get("VPS_USER", "")
    ssh_key = opts.ssh_key or os.environ.get("SSH_KEY_PATH", "")
    ts_tailnet = opts.ts_tailnet or os.environ.get("TS_TAILNET", "")
    ts_cid = opts.ts_client_id or os.environ.get("TS_CLIENT_ID", "")
    ts_csec = opts.ts_client_secret or os.environ.get("TS_CLIENT_SECRET", "")
    inst_map_path = opts.instance_map or os.environ.get("INSTANCE_MAP", "")
    ssot_root = opts.ssot_root or os.environ.get("SSOT_ROOT", ".")
    is_local = opts.local or os.environ.get("APPROVE_LOCAL", "") == "1"

    # ── v3.6 (scope=instance): Validierung ──
    # Nur im Remove-Modus zulaessig; --request-id muss leer sein (Konflikt:
    # scope=instance entfernt ALLE gepaarten Geraete der gefilterten
    # Instanzen – Owner-Entscheidung 2026-08-08, KEINE id). scope=device
    # (Default) = bisheriger Pfad, 100%% unveraendert.
    if scope == "instance":
        if not opts.remove_only:
            print("❌ scope=instance ist nur im Remove-Modus (--remove-only) zulaessig.",
                  file=sys.stderr)
            return 2
        if rid:
            print("❌ Konflikt: scope=instance entfernt ALLE gepaarten Geraete der "
                  f"gefilterten Instanzen – --request-id '{rid}' darf NICHT gesetzt sein.",
                  file=sys.stderr)
            return 2

    # ── Listen-Modus (--list-only, v3.1): KEINE Request-ID noetig ──
    # R02 (Review Listen-Modus): Mapping mode=list → --list-only; eine evtl.
    # gesetzte ID wird weder validiert noch uebergeben (Warning statt Fehler).
    if opts.list_only:
        if opts.full_run:
            ap.error("--list-only und --full-run schliessen sich aus")
        if opts.discover_only:
            ap.error("--list-only und --discover-only schliessen sich aus")
        if rid:
            print(f"⚠️  --request-id '{rid}' wird im Listen-Modus ignoriert "
                  f"(keine Such-ID, keine Validierung – R02)", file=sys.stderr)
        # O3: type=auto hat im Listen-Modus keine ID zum Ableiten → both
        if type_f == "auto":
            type_f = "both"
        try:
            validate_type(type_f)
        except ValueError as exc:
            print(f"❌ {exc}", file=sys.stderr)
            return 2
        if inst_f != "all":
            try:
                validate_instance(inst_f)
            except ValueError as exc:
                print(f"❌ {exc}", file=sys.stderr)
                return 2
        derived_type = type_f
        filters = {"type": derived_type, "target": target_f, "instance": inst_f}
    else:
        if scope == "instance":
            # v3.6 (scope=instance): KEINE id noetig (leer erlaubt); der
            # Remove ist immer device-only (kein 'pairing remove' in der
            # openclaw CLI). Konflikt id+scope=instance wurde oben bereits
            # abgefangen (Exit 2).
            derived_type = "device"
            if inst_f != "all":
                try:
                    validate_instance(inst_f)
                except ValueError as exc:
                    print(f"❌ {exc}", file=sys.stderr)
                    return 2
            filters = {"type": derived_type, "target": target_f,
                       "instance": inst_f, "scope": scope}
        else:
            # ── Approve-/Reject-/Remove-Modus-Validierung (unverändert, v2.2: Fail-Fast) ──
            if not rid:
                print("❌ Keine Request-ID – --request-id oder APPROVE_ID setzen.", file=sys.stderr)
                return 2
            try:
                validate_type(type_f)
            except ValueError as exc:
                print(f"❌ {exc}", file=sys.stderr)
                return 2
            valid, derived_type, err = validate_and_classify_id(rid, type_f)
            if not valid:
                print(f"❌ {err}", file=sys.stderr)
                return 2

            # v3.2/v3.4 (Reject-/Remove-Modus): NUR device – die openclaw CLI hat
            # weder 'pairing reject' noch 'pairing remove' (empirisch 2026-08-07).
            # Fail-Fast VOR dem SSH-Aufbau.
            if (opts.reject_only or opts.remove_only) and derived_type != "device":
                aktion_name = "Reject" if opts.reject_only else "Remove"
                aktion_flag = "reject" if opts.reject_only else "remove"
                print(f"❌ {aktion_name}-Modus unterstuetzt nur device-Requests – die openclaw CLI "
                      f"hat kein 'pairing {aktion_flag}' (nur `openclaw devices {aktion_flag} <ID>`).",
                      file=sys.stderr)
                return 2

            if inst_f != "all":
                try:
                    validate_instance(inst_f)
                except ValueError as exc:
                    print(f"❌ {exc}", file=sys.stderr)
                    return 2

            filters = {"type": derived_type, "target": target_f, "instance": inst_f}

    def log(msg: str) -> None:
        print(msg, file=sys.stderr)

    def write_summary(result: dict) -> None:
        # v3.1: Listen-Modus → list_result_to_markdown (Tabellen-Schema),
        # Approve-/Discovery-Modus → result_to_markdown (Minor #7-Schema).
        # v3.6: scope=instance → instance_remove_to_markdown (removed_count /
        # per_instance / failed-Details).
        if result.get("scope") == "instance":
            md = instance_remove_to_markdown(result)
        elif result.get("status") == "list_ok":
            md = list_result_to_markdown(result)
        else:
            md = result_to_markdown(result)
        sm = os.environ.get("GITHUB_STEP_SUMMARY", "")
        if sm:
            # Δ7 / Major #3: File-Open, KEIN >>-Redirect
            with open(sm, "a", encoding="utf-8") as fh:
                fh.write(md + "\n")
        else:
            print(md, file=sys.stderr)

    def emit(result: dict, rc: int) -> int:
        print(json.dumps(result, ensure_ascii=False))
        if opts.summary:
            write_summary(result)
        return rc

    # ── Listen-Modus (--list-only): aggregiert pending ueber alle VPS ──
    if opts.list_only:
        if is_local:
            # Ergaenzung (Design §1/2c): Gateway-eigene pending Requests
            entries, stats = run_local_list_discovery(derived_type, log=log)
            result = build_list_result_json(
                status="list_ok",
                entries=entries,
                scanned=stats["scanned"],
                unreachable=stats["unreachable"],
                filters_applied=filters,
            )
            return emit(result, 0)

        if inst_map_path:
            instance_map = load_instance_map_from_file(inst_map_path)
        else:
            instance_map = load_instance_map_from_ssot(ssot_root)

        filtered_map = filter_instance_map(
            instance_map, target_filter=target_f, instance_filter=inst_f
        )
        if not filtered_map:
            print("❌ Keine Instanzen nach Filter (target/instance) uebrig.", file=sys.stderr)
            return 2

        if not all([vps_user, ssh_key, ts_tailnet, ts_cid, ts_csec]):
            print(
                "❌ SSH-Modus benoetigt VPS_USER, SSH_KEY_PATH, TS_TAILNET, "
                "TS_CLIENT_ID, TS_CLIENT_SECRET (env oder --flags).",
                file=sys.stderr,
            )
            return 2

        token = fetch_tailscale_token(ts_cid, ts_csec)

        def resolve_ip(node: str) -> Optional[str]:
            return resolve_vps_ip(ts_tailnet, token, node)

        def run_remote(ip: str, remote_cmd: str) -> str:
            return run_remote_ssh(ip, vps_user, ssh_key, remote_cmd)

        list_result = run_list_discovery(
            filtered_map,
            derived_type=derived_type,
            resolve_ip=resolve_ip,
            run_remote=run_remote,
            log=log,
        )
        result = build_list_result_json(
            status="list_ok",
            entries=list_result.entries,
            scanned=list_result.scanned,
            unreachable=list_result.unreachable,
            filters_applied=filters,
        )
        # Exit-Code-Vertrag Listen-Modus: 0 = Liste erstellt (auch leer), 1 =
        # Infrastruktur-Fehler, 2 = Config-Fehler – leere Liste ist gruen.
        return emit(result, 0)

    # ── Instanz-Remove (v3.6, --remove-only --scope instance) ──
    # „Instanz leeren“: entfernt ALLE gepaarten Geraete der gefilterten
    # Instanzen (target/instance) – ZWEIPHASIG:
    #   Phase 1: Remove-Plan sammeln (collect_paired_devices) → leer =
    #            not_found (Exit 0, Idempotenz); > MAX_REMOVE_DEVICES =
    #            Abbruch mit klarer Fehlermeldung (Exit 2) VOR jedem Remove.
    #   Phase 2: run_instance_remove (DEV-REMOVE-Marker, B2-Semantik).
    # Exit-Code-Vertrag: 0 = alle entfernt ODER not_found (gruen),
    # 1 = Teilerfolg/Fehler (failed im Summary), 2 = Config/Limit.
    if opts.remove_only and scope == "instance":
        if is_local:
            result, rc = run_local_instance_remove(log=log)
            result["filters_applied"] = filters
            return emit(result, rc)

        if inst_map_path:
            instance_map = load_instance_map_from_file(inst_map_path)
        else:
            instance_map = load_instance_map_from_ssot(ssot_root)

        filtered_map = filter_instance_map(
            instance_map, target_filter=target_f, instance_filter=inst_f
        )
        if not filtered_map:
            print("❌ Keine Instanzen nach Filter (target/instance) uebrig.", file=sys.stderr)
            return 2

        if not all([vps_user, ssh_key, ts_tailnet, ts_cid, ts_csec]):
            print(
                "❌ SSH-Modus benoetigt VPS_USER, SSH_KEY_PATH, TS_TAILNET, "
                "TS_CLIENT_ID, TS_CLIENT_SECRET (env oder --flags).",
                file=sys.stderr,
            )
            return 2

        token = fetch_tailscale_token(ts_cid, ts_csec)

        def resolve_ip(node: str) -> Optional[str]:
            return resolve_vps_ip(ts_tailnet, token, node)

        def run_remote(ip: str, remote_cmd: str) -> str:
            return run_remote_ssh(ip, vps_user, ssh_key, remote_cmd)

        # Phase 1: Remove-Plan (KEIN Remove)
        plan, scanned, unreachable = collect_paired_devices(
            filtered_map,
            derived_type="device",
            resolve_ip=resolve_ip,
            run_remote=run_remote,
            log=log,
        )
        if not plan:
            # Idempotenz: 2. Lauf auf leerer Instanz = not_found / 0 entfernt
            # (Exit 0, gruen – Owner-Entscheidung 2026-08-08).
            result = build_instance_remove_result_json(
                status="not_found",
                removed_count=0,
                per_instance=[
                    {"instance": name, "removed": 0, "failed": 0}
                    for name, _t in filtered_map
                ],
                failed=[],
                scanned=scanned,
                filters_applied=filters,
                unreachable=unreachable,
            )
            return emit(result, 0)

        if len(plan) > MAX_REMOVE_DEVICES:
            # Sicherheits-Limit (Owner-Entscheidung): max 50 Geraete pro Lauf,
            # darueber Abbruch VOR jedem Remove – kein Massen-Remove.
            per_inst = {name: 0 for name, _t in filtered_map}
            for dev in plan:
                per_inst[dev.instance] = per_inst.get(dev.instance, 0) + 1
            msg = (f"❌ Sicherheits-Limit erreicht: {len(plan)} gepaarte Geraete gefunden, "
                   f"max. {MAX_REMOVE_DEVICES} pro Lauf erlaubt. Abbruch VOR jedem Remove – "
                   f"Instanz(en) enger filtern (target/instance).")
            print(msg, file=sys.stderr)
            result = build_instance_remove_result_json(
                status="error",
                removed_count=0,
                per_instance=[
                    {"instance": name, "removed": 0, "failed": 0,
                     "geplant": per_inst.get(name, 0)}
                    for name, _t in filtered_map
                ],
                failed=[],
                scanned=scanned,
                filters_applied=filters,
                unreachable=unreachable,
                limit_hit=True,
            )
            return emit(result, 2)

        # Phase 2: Instanz-Remove (alle Geraete des Plans)
        res = run_instance_remove(
            filtered_map,
            resolve_ip=resolve_ip,
            run_remote=run_remote,
            log=log,
            max_devices=MAX_REMOVE_DEVICES,
        )

        removed_count = len(res.removed)
        failed_count = len(res.failed)
        per_instance = []
        for name, _t in filtered_map:
            per_instance.append({
                "instance": name,
                "removed": sum(1 for i, _d in res.removed if i == name),
                "failed": sum(1 for i, _d, _o in res.failed if i == name),
            })
        failed_details = [
            {"instance": i, "device_id": d, "output": o}
            for i, d, o in res.failed
        ]

        if res.limit_hit:
            # Defense-in-Depth: Shell-Hard-Cap gegriffen (zwischen Phase 1
            # und 2 nachgepaarte Geraete) – Teilerfolg melden, Exit 2.
            result = build_instance_remove_result_json(
                status="error",
                removed_count=removed_count,
                per_instance=per_instance,
                failed=failed_details,
                scanned=res.scanned or scanned,
                filters_applied=filters,
                unreachable=res.unreachable or unreachable,
                limit_hit=True,
            )
            print("❌ Sicherheits-Limit (max 50) waehrend des Laufs ueberschritten – "
                  "Remove-Schleife abgebrochen (siehe JSON).", file=sys.stderr)
            return emit(result, 2)

        if removed_count == 0 and failed_count == 0:
            # Zwischen Phase 1 und 2 entfernte Geraete (Race) – Ergebnis ist
            # idempotent: 0 entfernt, kein Fehler.
            status = "not_found"
            rc = 0
        elif removed_count > 0 and failed_count == 0:
            status = "removed"
            rc = 0
        elif removed_count > 0 and failed_count > 0:
            status = "partial"
            rc = 1
        else:  # removed_count == 0 and failed_count > 0
            status = "error"
            rc = 1

        result = build_instance_remove_result_json(
            status=status,
            removed_count=removed_count,
            per_instance=per_instance,
            failed=failed_details,
            scanned=res.scanned or scanned,
            filters_applied=filters,
            unreachable=res.unreachable or unreachable,
        )
        if rc == 1:
            print("❌ Teilerfolg/Fehler – fehlgeschlagene Geraete im Summary/JSON "
                  f"({failed_count} von {removed_count + failed_count}).", file=sys.stderr)
        return emit(result, rc)

    # ── Lokaler Modus ──
    if is_local:
        d_result, stats = run_local_discovery(
            rid, derived_type, log=log,
            action="remove" if opts.remove_only else "approve",
        )
        if d_result is None:
            result = build_result_json(
                status="not_found",
                request_id=rid,
                scanned=stats["scanned"],
                filters_applied=filters,
            )
            # Owner-Vereinbarung 15:06: not_found = gruener Run (Exit 0),
            # nur error bleibt rot (Exit 1).
            return emit(result, 0)

        if opts.discover_only:
            result = build_result_json(
                status="found",
                request_id=rid,
                found=[{
                    "target": d_result.target,
                    "instance": d_result.instance,
                    "type": d_result.found_type,
                    "vps_ip": None,
                }],
                scanned=d_result.scanned,
                filters_applied=filters,
            )
            return emit(result, 0)

        # v3.2: Lokaler Reject (nur device, Δ3) vor dem Approve-Pfad
        if opts.reject_only:
            rc = run_local_reject(rid, d_result.found_type)
            status = "rejected" if rc == 0 else "error"
            result = build_result_json(
                status=status,
                request_id=rid,
                found=[{
                    "target": "local",
                    "instance": "local",
                    "type": d_result.found_type,
                    "vps_ip": None,
                }],
                scanned=d_result.scanned,
                filters_applied=filters,
            )
            return emit(result, 0 if rc == 0 else 1)

        # v3.4: Lokaler Remove (nur device, Δ4) vor dem Approve-Pfad
        if opts.remove_only:
            rc = run_local_remove(rid, d_result.found_type)
            status = "removed" if rc == 0 else "error"
            result = build_result_json(
                status=status,
                request_id=rid,
                found=[{
                    "target": "local",
                    "instance": "local",
                    "type": d_result.found_type,
                    "vps_ip": None,
                }],
                scanned=d_result.scanned,
                filters_applied=filters,
            )
            return emit(result, 0 if rc == 0 else 1)

        # Lokaler Approve (typ-spezifisch, Δ2)
        rc = run_local_approve(rid, d_result.found_type)
        status = "approved" if rc == 0 else "error"
        result = build_result_json(
            status=status,
            request_id=rid,
            found=[{
                "target": "local",
                "instance": "local",
                "type": d_result.found_type,
                "vps_ip": None,
            }],
            scanned=d_result.scanned,
            filters_applied=filters,
        )
        return emit(result, 0 if rc == 0 else 1)

    # ── SSH-Modus ──
    if inst_map_path:
        instance_map = load_instance_map_from_file(inst_map_path)
    else:
        instance_map = load_instance_map_from_ssot(ssot_root)

    filtered_map = filter_instance_map(
        instance_map, target_filter=target_f, instance_filter=inst_f
    )

    if not filtered_map:
        print("❌ Keine Instanzen nach Filter (target/instance) uebrig.", file=sys.stderr)
        return 2

    if not all([vps_user, ssh_key, ts_tailnet, ts_cid, ts_csec]):
        print(
            "❌ SSH-Modus benoetigt VPS_USER, SSH_KEY_PATH, TS_TAILNET, "
            "TS_CLIENT_ID, TS_CLIENT_SECRET (env oder --flags).",
            file=sys.stderr,
        )
        return 2

    token = fetch_tailscale_token(ts_cid, ts_csec)

    def resolve_ip(node: str) -> Optional[str]:
        return resolve_vps_ip(ts_tailnet, token, node)

    def run_remote(ip: str, remote_cmd: str) -> str:
        # v3.0: Ein SSH-Call pro VPS mit dem Ein-Job-Remote-Skript
        # (Discovery + Approve in der Session, 1-SSH-pro-VPS-Optimierung)
        return run_remote_ssh(ip, vps_user, ssh_key, remote_cmd)

    try:
        result = run_discovery(
            filtered_map,
            rid,
            derived_type=derived_type,
            resolve_ip=resolve_ip,
            run_remote=run_remote,
            approve=not opts.discover_only,
            # v3.2/v3.4: Aktion approve|reject|remove (Reject-/Remove-Modus =
            # Ein-Job-Reject/-Remove)
            action=("remove" if opts.remove_only
                    else ("reject" if opts.reject_only else "approve")),
            # Run-#36-Fix: $GITHUB_OUTPUT nur im Workflow gesetzt; lokal (None)
            # bleibt der bisherige Bibliotheks-/CLI-Pfad unveraendert.
            github_output=os.environ.get("GITHUB_OUTPUT"),
            log=log,
        )
    except RequestNotFoundError as err:
        scanned = [f"{n}/{t}" for n, t in filtered_map]
        result = build_result_json(
            status="not_found",
            request_id=rid,
            scanned=scanned,
            filters_applied=filters,
        )
        # Owner-Vereinbarung 15:06: not_found = gruener Run (Exit 0) – gilt
        # fuer --full-run UND --discover-only (Run-#6-Befund: conclusion rot).
        return emit(result, 0)
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2

    if opts.discover_only:
        result_obj = build_result_json(
            status="found",
            request_id=rid,
            found=[{
                "target": result.target,
                "instance": result.instance,
                "type": result.found_type,
                "vps_ip": result.vps_ip,
            }],
            scanned=result.scanned,
            filters_applied=filters,
        )
        return emit(result_obj, 0)

    if not result.approved:
        # Ein-Job-Inkonsistenz/-Fehler: ID in der SSH-Session gefunden, aber die
        # Aktion (Approve/Reject/Remove) wurde nicht bestätigt (Aktions-Marker
        # fehlen ODER Aktion fehlgeschlagen, B2-2.Review) → laut scheitern.
        if opts.remove_only:
            aktion = "Remove"
        elif opts.reject_only:
            aktion = "Reject"
        else:
            aktion = "Approve"
        msg = (f"ID gefunden, aber {aktion} wurde nicht in der SSH-Session "
               f"bestätigt ({aktion}-Marker fehlen oder {aktion} fehlgeschlagen).")
        if result.approve_output:
            msg += f"\n{aktion}-Output:\n{result.approve_output}"
        print(f"❌ {msg}", file=sys.stderr)
        final = build_result_json(
            status="error",
            request_id=rid,
            found=[{
                "target": result.target,
                "instance": result.instance,
                "type": result.found_type,
                "vps_ip": result.vps_ip,
            }],
            scanned=result.scanned,
            filters_applied=filters,
        )
        return emit(final, 1)

    final = build_result_json(
        status=("removed" if opts.remove_only
                else ("rejected" if opts.reject_only else "approved")),
        request_id=rid,
        found=[{
            "target": result.target,
            "instance": result.instance,
            "type": result.found_type,
            "vps_ip": result.vps_ip,
        }],
        scanned=result.scanned,
        filters_applied=filters,
    )
    return emit(final, 0)


if __name__ == "__main__":
    raise SystemExit(main())
