#!/usr/bin/env python3
"""Diagnose-Workflow 06 – read-only Issue-#113-Metriken auf OpenClaw-Instanzen.

Liest per SSH (deploy-user via Tailscale) read-only Metriken aus den
Instanz-Containern (docker exec openclaw-<name> openclaw ...) – Workflow 06
(.github/workflows/06-diagnose.yml) ruft dieses CLI mit den Workflow-Inputs auf.

Modi (--mode):
  health   – Gateway-Health (gateway health + gateway status)
  sessions – aktive/gelistete Sessions (sessions --all-agents --json)
  context  – Kontext-Metriken aus Transkript-JSONL (bounded geholt,
             tools/diagnose/context_metrics.py): Kontext-Groesse je Turn,
             wiederholte Bloecke, Workspace-Einblendungen, Fehler/Latenz
  tokens   – Input/Output-Tokens je Turn + Cache-Hit-Anteil (usage-cost +
             Transkript-Usage)
  all      – health + sessions + context + tokens (Default)

Instanz-Quelle: ansible/group_vars/vps-*.yml (SSoT, enabled-Instanzen).
NIE schreibend: es werden ausschliesslich read-only-Kommandos ausgefuehrt
(kein approve/reject/remove/delete/clean, keine Gateway-Config-Aenderung).
Tokens/Secrets werden nie ausgegeben (nur Env-/Secret-Nutzung im Workflow).

Exit-Codes: 0 = Erfolg (auch "nicht messbar"/leer – gruen, Idempotenz),
1 = Infrastruktur-/Auth-/SSH-Fehler, 2 = Validierungs-/Config-Fehler.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover - Workflow installiert pyyaml vorab
    sys.stderr.write("Fehler: PyYAML nicht installiert (python3 -m pip install pyyaml)\n")
    sys.exit(2)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from context_metrics import compute_metrics  # noqa: E402

VERSION = "1.0.0"
DEFAULT_GLOB = "ansible/group_vars/vps-*.yml"
VALID_MODES = ("health", "sessions", "context", "tokens", "all")
VALID_TARGETS = ("dev", "prod", "both")
SSH_OPTS = [
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "ConnectTimeout=10",
    "-o", "BatchMode=yes",
    "-o", "LogLevel=ERROR",
]
TRANSCRIPT_TAIL_BYTES = 300_000
TRANSCRIPT_MAX_FILES = 20


# ── SSoT (Instanz-Map aus group_vars, analog tools/telegram-approve-bot/sot_parser.py) ──

def load_instances(
    root: str = ".", target_filter: str = "both", instance_filter: str = "all"
) -> List[Dict[str, Any]]:
    """Enabled Instanzen aus allen vps-*.yml, gefiltert nach target + instance."""
    result: List[Dict[str, Any]] = []
    for path in sorted(glob.glob(os.path.join(root, DEFAULT_GLOB))):
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        file_target = str(data.get("env", "unknown"))
        for inst in data.get("openclaw_instances", []) or []:
            if not inst.get("enabled", False):
                continue
            name = inst.get("name")
            if not name:
                continue
            target = str(inst.get("target", file_target))
            if target_filter != "both" and target != target_filter:
                continue
            if instance_filter != "all" and name != instance_filter:
                continue
            result.append({
                "name": name,
                "target": target,
                "port": int(inst.get("port", 18789)),
            })
    # Kein sys.exit hier: reine Filterfunktion (Unit-testbar, gibt [] zurueck).
    # Die CLI-Exit-Code-Entscheidung (2 = Config-Fehler) faellt in main().
    return result


def validate_instance(instance: str) -> None:
    if instance != "all" and not re.match(r"^oc[1-9][0-9]*$", instance):
        sys.stderr.write(
            f"Ungueltige Instanz: '{instance}' (erlaubt: 'all' oder 'oc1', 'oc2', …)\n"
        )
        sys.exit(2)


def validate_mode(mode: str) -> None:
    if mode not in VALID_MODES:
        sys.stderr.write(f"Ungueltiger Modus: '{mode}' (erlaubt: {', '.join(VALID_MODES)})\n")
        sys.exit(2)


# ── Tailscale (VPS-IP, etabliertes Muster aus Workflow 05 e2e) ──

def vps_ip(target: str, tailnet: str, client_id: str, client_secret: str) -> str:
    """VPS-IP via Tailscale-API (vps-<target>, Fallback vps-<target>-1)."""
    req = urllib.request.Request(
        "https://api.tailscale.com/api/v2/oauth/token",
        data=f"client_id={client_id}&client_secret={client_secret}".encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        token = json.loads(resp.read().decode())["access_token"]
    req2 = urllib.request.Request(
        f"https://api.tailscale.com/api/v2/tailnet/{tailnet}/devices?fields=hostname,addresses",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req2, timeout=20) as resp:
        devices = json.loads(resp.read().decode()).get("devices", [])
    for dev in devices:
        if dev.get("hostname") in (f"vps-{target}", f"vps-{target}-1"):
            addrs = dev.get("addresses") or []
            if addrs:
                return str(addrs[0])
    raise RuntimeError(f"VPS-IP fuer vps-{target} nicht gefunden (Tailscale-API)")


# ── Remote-Kommandos (NUR read-only) ──

def docker_exec(name: str, port: int, args: List[str]) -> str:
    return "sudo docker exec openclaw-{0} openclaw {1}".format(
        name, " ".join(args)
    )


def build_health_cmds(name: str, port: int) -> List[str]:
    return [
        docker_exec(name, port, ["gateway", "health", "--port", str(port), "--json"]),
        docker_exec(name, port, ["gateway", "status", "--json"]),
    ]


def build_sessions_cmd(name: str, port: int) -> str:
    return docker_exec(name, port, ["sessions", "--all-agents", "--json"])


def build_usage_cmd(name: str, port: int, days: int) -> str:
    return docker_exec(
        name, port, ["gateway", "usage-cost", "--days", str(days), "--all-agents", "--json"]
    )


def build_context_cmd(name: str, port: int) -> str:
    inner = (
        "find /home/node/.openclaw -name '*.jsonl' -path '*session*' "
        f"-not -name '*.deleted.*' 2>/dev/null | head -{TRANSCRIPT_MAX_FILES} | "
        "while read -r f; do echo '==FILE== ' \"$f\"; tail -c "
        f"{TRANSCRIPT_TAIL_BYTES} \"$f\"; done"
    )
    return f"sudo docker exec openclaw-{name} sh -lc '{inner}'"


def run_ssh(
    ssh: List[str], host: str, remote_cmd: str, timeout: int = 60
) -> Tuple[int, str, str]:
    proc = subprocess.run(
        ssh + [host, remote_cmd],
        capture_output=True, text=True, timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


# ── Parsing (defensiv) ──

def parse_json_or_raw(text: str) -> Dict[str, Any]:
    try:
        data = json.loads(text)
        return {"json": data} if isinstance(data, (dict, list)) else {"raw": text.strip()}
    except (ValueError, TypeError):
        return {"raw": text.strip()[:2000]}


def parse_sessions(text: str) -> Dict[str, Any]:
    parsed = parse_json_or_raw(text)
    data = parsed.get("json")
    out: Dict[str, Any] = {"raw_length": len(text)}
    if isinstance(data, dict):
        sessions = data.get("sessions") or []
        out["count"] = len(sessions)
        out["totalCount"] = data.get("totalCount")
        out["sessions"] = [
            {"key": s.get("key"), "agentId": s.get("agentId"), "model": s.get("model")}
            for s in sessions
        ]
    else:
        out["unparsed"] = True
    return out


def parse_usage_cost(text: str) -> Dict[str, Any]:
    parsed = parse_json_or_raw(text)
    data = parsed.get("json")
    out: Dict[str, Any] = {"raw_length": len(text)}
    if isinstance(data, dict):
        out.update({k: v for k, v in data.items() if k != "raw"})
    else:
        out["unparsed"] = True
    return out


def parse_context(text: str) -> Dict[str, Any]:
    """==FILE==-markierte Transkript-Chunks je Datei + Gesamt-Aggregation."""
    per_file: Dict[str, Dict[str, Any]] = {}
    current: Optional[str] = None
    chunks: Dict[str, List[str]] = {}
    for line in text.splitlines():
        if line.startswith("==FILE== "):
            current = line[len("==FILE== "):].strip()
            chunks.setdefault(current, [])
        elif current is not None:
            chunks[current].append(line)
    for path, lines in chunks.items():
        per_file[path] = compute_metrics("\n".join(lines))
    combined = compute_metrics("\n".join(text.splitlines()))
    combined.pop("context_chars_per_turn", None)
    agg = {
        "files_found": len(per_file),
        "files": per_file,
        "aggregated": combined,
    }
    return agg


# ── Ausfuehrung ──

def run_mode(
    ssh: List[str], host: str, inst: Dict[str, Any], mode: str, days: int
) -> Dict[str, Any]:
    name, port = inst["name"], inst["port"]
    result: Dict[str, Any] = {"instance": f"{inst['target']}/{name}", "port": port}
    cmds: List[Tuple[str, str]] = []
    if mode in ("health", "all"):
        for c in build_health_cmds(name, port):
            cmds.append(("health", c))
    if mode in ("sessions", "all"):
        cmds.append(("sessions", build_sessions_cmd(name, port)))
    if mode in ("tokens", "all"):
        cmds.append(("usage", build_usage_cmd(name, port, days)))
    if mode in ("context", "tokens", "all"):
        cmds.append(("context", build_context_cmd(name, port)))

    failures = 0
    for label, cmd in cmds:
        try:
            rc, out, err = run_ssh(ssh, host, cmd)
        except subprocess.TimeoutExpired:
            result[label] = {"error": "ssh timeout"}
            failures += 1
            continue
        entry: Dict[str, Any] = {"rc": rc}
        if rc != 0:
            entry["error"] = err.strip()[:500] or out.strip()[:500]
            failures += 1
        elif label == "health":
            entry["health"] = parse_json_or_raw(out)
        elif label == "sessions":
            entry["sessions"] = parse_sessions(out)
        elif label == "usage":
            entry["usage"] = parse_usage_cost(out)
        elif label == "context":
            entry["context"] = parse_context(out)
        result[label] = entry

    result["failures"] = failures
    return result


def summarize(per_instance: Dict[str, Dict[str, Any]], mode: str) -> str:
    lines = [
        f"## 🔍 Diagnose (Issue #113) – Modus `{mode}`",
        "",
        "| Instanz | Health | Sessions | Input-Tokens | Cache-Hit | Wiederholte Blöcke | Fehler |",
        "|---|---|---|---|---|---|---|",
    ]
    for key, r in sorted(per_instance.items()):
        health = r.get("health")
        h_ok = "–"
        if isinstance(health, dict):
            h = health.get("health", {}).get("json")
            if isinstance(h, dict):
                h_ok = "✅ ok" if h.get("ok") else "⚠️ nicht ok"
            elif health.get("rc") == 0:
                h_ok = "✅ rc0"
            else:
                h_ok = f"❌ {str(health.get('error'))[:40]}"
        sess = r.get("sessions", {}).get("sessions")
        n_sess = len(sess) if isinstance(sess, list) else "–"
        usage = r.get("usage", {}).get("usage", {})
        in_tok = usage.get("inputTokens") or usage.get("input_tokens") or "–"
        agg = r.get("context", {}).get("context", {}).get("aggregated", {})
        hit = agg.get("cache_hit_ratio")
        hit_s = f"{hit:.1%}" if isinstance(hit, (int, float)) else "–"
        reps = agg.get("repeated_blocks", {}).get("distinct_repeated", "–")
        errs = agg.get("errors", "–")
        lines.append(f"| {key} | {h_ok} | {n_sess} | {in_tok} | {hit_s} | {reps} | {errs} |")
    lines.append("")
    lines.append("_Read-only Diagnose – keine Aenderungen an Instanzen. "
                 "Details: tools/diagnose/README.md (Issue #113)._")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Read-only Diagnose (Issue #113)")
    ap.add_argument("--mode", default="all", help="health|sessions|context|tokens|all")
    ap.add_argument("--target", default="dev", help="dev|prod|both")
    ap.add_argument("--instance", default="all", help="all|oc1|oc2|…")
    ap.add_argument("--days", type=int, default=7, help="Usage-Fenster (Tage)")
    ap.add_argument("--vps-user", required=True)
    ap.add_argument("--ssh-key", required=True)
    ap.add_argument("--ts-tailnet", required=True)
    ap.add_argument("--ts-client-id", required=True)
    ap.add_argument("--ts-client-secret", required=True)
    ap.add_argument("--summary", action="store_true", help="Markdown-Summary auf stderr")
    ap.add_argument("--repo-root", default=".", help="Repo-Root (SSoT-Parsing)")
    args = ap.parse_args(argv)

    validate_mode(args.mode)
    validate_instance(args.instance)
    if args.target not in VALID_TARGETS:
        sys.stderr.write(f"Ungueltiges Target: '{args.target}'\n")
        return 2
    if args.days < 1 or args.days > 365:
        sys.stderr.write("--days muss zwischen 1 und 365 liegen\n")
        return 2

    instances = load_instances(args.repo_root, args.target, args.instance)
    if not instances:
        sys.stderr.write(
            f"Keine enabled Instanzen fuer target={args.target} instance={args.instance} "
            f"in {DEFAULT_GLOB}\n"
        )
        return 2
    by_target: Dict[str, List[Dict[str, Any]]] = {}
    for inst in instances:
        by_target.setdefault(inst["target"], []).append(inst)

    ssh = ["ssh", "-i", args.ssh_key] + SSH_OPTS
    per_instance: Dict[str, Dict[str, Any]] = {}
    infra_failures = 0
    for target, insts in by_target.items():
        try:
            host = vps_ip(target, args.ts_tailnet, args.ts_client_id, args.ts_client_secret)
        except Exception as e:  # noqa: BLE001 - Infrastrukturfehler melden, nicht werfen
            infra_failures += 1
            for inst in insts:
                per_instance[f"{target}/{inst['name']}"] = {
                    "instance": f"{target}/{inst['name']}",
                    "error": f"Tailscale/IP: {e}",
                    "failures": 1,
                }
            continue
        for inst in insts:
            key = f"{target}/{inst['name']}"
            per_instance[key] = run_mode(ssh, host, inst, args.mode, args.days)

    exit_code = 2 if infra_failures == len(by_target) and by_target else (
        1 if any(r.get("failures", 0) for r in per_instance.values()) else 0
    )

    report = {
        "tool": "diagnose",
        "version": VERSION,
        "date_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": args.mode,
        "days": args.days,
        "target": args.target,
        "instance_filter": args.instance,
        "instances": [f"{i['target']}/{i['name']}" for i in instances],
        "per_instance": per_instance,
        "exit": exit_code,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.summary:
        md = summarize(per_instance, args.mode)
        sm = os.environ.get("GITHUB_STEP_SUMMARY", "")
        if sm:
            with open(sm, "a", encoding="utf-8") as fh:
                fh.write(md + "\n")
        else:
            print(md, file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
