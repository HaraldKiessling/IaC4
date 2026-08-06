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
from summary import result_to_markdown  # type: ignore[import-untyped]

DiscoveryResult = discovery.DiscoveryResult
RequestNotFoundError = discovery.RequestNotFoundError
build_result_json = discovery.build_result_json
derive_type = discovery.derive_type
fetch_tailscale_token = discovery.fetch_tailscale_token
filter_instance_map = discovery.filter_instance_map
resolve_vps_ip = discovery.resolve_vps_ip
run_discovery = discovery.run_discovery
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
) -> Tuple[Optional[DiscoveryResult], dict]:
    """Lokale Discovery ueber die openclaw CLI direkt auf dem Gateway.

    Telegram → `openclaw pairing list telegram --json` (Feld code, Schema
    {"channel": ..., "requests": [...]}, F10: Fehler/leer → fail-safe überspringen)
    Device   → `openclaw devices list --json` (Feld deviceId, Schema pending/paired)

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
            id_field = "code"
        else:
            entries = data.get("pending") or []
            id_field = "deviceId"

        for entry in entries:
            if entry.get(id_field) == request_id:
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
    ap.add_argument("--full-run", action="store_true",
                    help="Ein-Job: Discovery + Approve in einem Aufruf (Workflow-Standard v3.0)")
    ap.add_argument("--summary", action="store_true", help="Markdown-Summary in $GITHUB_STEP_SUMMARY")
    ap.add_argument("--local", action="store_true", help="Lokaler Modus ohne SSH (env APPROVE_LOCAL=1)")

    opts = ap.parse_args(argv)

    if opts.full_run and opts.discover_only:
        ap.error("--full-run und --discover-only schliessen sich aus")

    # Env-Overrides
    rid = opts.request_id or os.environ.get("APPROVE_ID", "")
    type_f = opts.type_filter or os.environ.get("APPROVE_TYPE", "auto")
    target_f = opts.target_filter or os.environ.get("APPROVE_TARGET", "both")
    inst_f = opts.instance_filter or os.environ.get("APPROVE_INSTANCE", "all")
    vps_user = opts.vps_user or os.environ.get("VPS_USER", "")
    ssh_key = opts.ssh_key or os.environ.get("SSH_KEY_PATH", "")
    ts_tailnet = opts.ts_tailnet or os.environ.get("TS_TAILNET", "")
    ts_cid = opts.ts_client_id or os.environ.get("TS_CLIENT_ID", "")
    ts_csec = opts.ts_client_secret or os.environ.get("TS_CLIENT_SECRET", "")
    inst_map_path = opts.instance_map or os.environ.get("INSTANCE_MAP", "")
    ssot_root = opts.ssot_root or os.environ.get("SSOT_ROOT", ".")
    is_local = opts.local or os.environ.get("APPROVE_LOCAL", "") == "1"

    # ── Validierung (v2.2: Zwei-Format-Regex, Fail-Fast) ──
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

    # ── Lokaler Modus ──
    if is_local:
        d_result, stats = run_local_discovery(rid, derived_type, log=log)
        if d_result is None:
            result = build_result_json(
                status="not_found",
                request_id=rid,
                scanned=stats["scanned"],
                filters_applied=filters,
            )
            return emit(result, 1)

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
        return emit(result, 1)
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
        # Ein-Job-Inkonsistenz: ID in der SSH-Session gefunden, aber kein
        # APPROVE-Marker (Remote-Match/Approve fehlgeschlagen) → laut scheitern.
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
        status="approved",
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
