#!/usr/bin/env python3
"""Issue-#113-Nachmessung: N Turns identischer Prompt je Instanz (Mess-Skript).

Umsetzung von Vorschlag 2 der Baseline-Evidenz (Phase 11, Issue #113):
- N Turns identischer Prompt gegen jede Instanz via Gateway-RPC (gepaarter
  CLI-Client, Token aus Env/Secret – nie ausgeben, nie committen)
- Nach JEDEM Turn `sessions.get`: Usage-Totals (input/output/cacheRead/
  reasoningTokens/totalTokens), Kontext-Wachstum (Delta input je Turn),
  Transkript-Analyse (wiederholte Bloecke = Issue-#113-H1/H2, Workspace-/
  Memory-Einblendungen AGENTS.md/MEMORY.md, Fehler/Latenz)
- Deterministische Session-Keys `agent:<id>:baseline-<runde>-<uuid8>`
  (Benchmark-Methodik §1.3: eindeutige Keys je Lauf, kein Lerneffekt)

Muster: benchmark-methodik.md §1.3/§2.3/§4.5 + scripts/benchmark/benchmark-
costs.py (sessions.get, usage.input/cacheRead/output, Preise) + run-round.py
(openclaw agent --session-key, OPENCLAW_GATEWAY_URL/TOKEN).

Nutzung:
  OPENCLAW_GATEWAY_TOKEN=<token> python3 scripts/benchmark/measure-session.py \
    --round R1 --turns 3 --prompt "Zaehle 1 bis 20 auf" --instances oc1,oc2

Ausgabe: JSON (Aggregate + Totals, KEIN Transkript-Text, KEIN Token).
Exit-Codes: 0 = Erfolg, 1 = Infrastruktur-/Auth-Fehler, 2 = Validierungsfehler.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

TOOLS_DIAGNOSE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "diagnose"
)
sys.path.insert(0, os.path.abspath(TOOLS_DIAGNOSE))
from context_metrics import compute_metrics  # noqa: E402

VERSION = "1.0.0"
DEFAULT_TAILNET = "vps-dev.tailcfea8a.ts.net"
# Benchmark-Methodik §1.1: OC1 = Single-Agent (main), OC2/OC3 = Team (orchestrator)
DEFAULT_AGENTS = {"oc1": "main", "oc2": "orchestrator", "oc3": "orchestrator"}
DEFAULT_PORTS = {"oc1": 18789, "oc2": 18790, "oc3": 18791}
TURN_TIMEOUT_S = 900  # identisch runTimeoutSeconds (Design 01: Konstante 900)


# ── Gateway-RPC (Muster benchmark-costs.py gw_call) ──

def gateway_url(port: int, tailnet: str) -> str:
    return f"wss://{tailnet}:{port}"


def gateway_token() -> str:
    """Token aus Env oder /tmp/tok.py (Repo-Muster, nie ausgeben/committen)."""
    tok = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")
    if tok:
        return tok
    try:
        sys.path.insert(0, "/tmp")
        from tok import TOKEN  # type: ignore  # noqa: PLC0415 - lokales Muster

        return TOKEN
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Kein Gateway-Token: OPENCLAW_GATEWAY_TOKEN setzen oder /tmp/tok.py "
            "(TOKEN) anlegen"
        ) from exc


def gw_call(port: int, tailnet: str, token: str, method: str,
            params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cmd = [
        "openclaw", "gateway", "call", method,
        "--url", gateway_url(port, tailnet),
        "--token", token, "--json",
    ]
    if params:
        cmd += ["--params", json.dumps(params)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        return {"error": proc.stderr.strip()[:500] or proc.stdout.strip()[:500]}
    try:
        data = json.loads(proc.stdout)
        return data if isinstance(data, dict) else {"raw": proc.stdout.strip()[:2000]}
    except ValueError:
        return {"raw": proc.stdout.strip()[:2000]}


# ── Turns ausfuehren (Muster run-round.py) ──

def run_turn(port: int, tailnet: str, token: str, agent_id: Optional[str],
             session_key: str, prompt: str) -> Tuple[int, str]:
    cmd = ["openclaw", "agent", "--message", prompt,
           "--session-key", session_key, "--json"]
    if agent_id:
        cmd.insert(2, "--agent")
        cmd.insert(3, agent_id)
    env = dict(os.environ)
    env["OPENCLAW_GATEWAY_URL"] = gateway_url(port, tailnet)
    env["OPENCLAW_GATEWAY_TOKEN"] = token
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TURN_TIMEOUT_S, env=env
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "timeout"


# ── Usage aus sessions.get (Muster benchmark-costs.py session_cost) ──

def normalize_usage(usage: Dict[str, Any]) -> Dict[str, int]:
    """sessions.get-Usage (input/output/cacheRead/reasoningTokens) -> DeepSeek-
    Schreibweise fuer context_metrics (input_tokens/output_tokens/...)."""
    def _i(*keys: str) -> int:
        for k in keys:
            val = usage.get(k)
            if val is not None:
                try:
                    return int(val)
                except (TypeError, ValueError):
                    pass
        return 0

    return {
        "input_tokens": _i("input", "input_tokens"),
        "output_tokens": _i("output", "output_tokens"),
        "prompt_cache_hit_tokens": _i("cacheRead", "prompt_cache_hit_tokens"),
        "prompt_cache_miss_tokens": _i("cacheWrite"),
        "reasoningTokens": _i("reasoningTokens", "reasoning"),
        "totalTokens": _i("totalTokens", "total"),
    }


def session_analysis(port: int, tailnet: str, token: str, session_key: str,
                     turn_index: int) -> Dict[str, Any]:
    """sessions.get je Turn: Usage-Totals + Transkript-Analyse (read-only)."""
    r = gw_call(port, tailnet, token, "sessions.get", {"key": session_key})
    messages = r.get("messages") or []
    totals = {
        "input": 0, "output": 0, "cacheRead": 0, "reasoningTokens": 0,
        "totalTokens": 0,
    }
    jsonl_lines: List[str] = []
    for msg in messages:
        usage = msg.get("usage")
        if isinstance(usage, dict):
            norm = normalize_usage(usage)
            totals["input"] += norm["input_tokens"]
            totals["output"] += norm["output_tokens"]
            totals["cacheRead"] += norm["prompt_cache_hit_tokens"]
            totals["reasoningTokens"] += norm["reasoningTokens"]
            totals["totalTokens"] += norm["totalTokens"]
        rec = {
            "type": msg.get("type", "message"),
            "role": msg.get("role"),
            "text": msg.get("text"),
            "latencyMs": msg.get("latencyMs") or msg.get("durationMs"),
            "status": msg.get("status"),
        }
        if isinstance(usage, dict):
            rec["usage"] = normalize_usage(usage)
        jsonl_lines.append(json.dumps(rec, ensure_ascii=False))

    metrics = compute_metrics("\n".join(jsonl_lines))
    return {
        "turn": turn_index,
        "messages": len(messages),
        "usage": totals,
        "metrics": metrics,
    }


def usage_delta(prev: Dict[str, int], cur: Dict[str, int]) -> int:
    """Kontext-Wachstum je Turn = Delta input gegenueber Vorturn (>= 0)."""
    return max(0, cur["input"] - prev["input"])


# ── Haupt ──

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Issue-#113-Nachmessung (Mess-Skript)")
    ap.add_argument("--round", default="R1", help="Runden-Label (Session-Key)")
    ap.add_argument("--turns", type=int, default=3, help="Anzahl identischer Turns")
    ap.add_argument("--prompt", default=None, help="Identischer Prompt je Turn")
    ap.add_argument("--prompt-file", default=None, help="Prompt aus Datei")
    ap.add_argument("--instances", default="oc1,oc2", help="Kommagetrennt, z.B. oc1,oc2")
    ap.add_argument("--tailnet", default=os.environ.get("GW_TAILNET", DEFAULT_TAILNET))
    ap.add_argument("--out", default=None, help="JSON-Ausgabedatei (Default: stdout)")
    args = ap.parse_args(argv)

    if args.turns < 1 or args.turns > 50:
        sys.stderr.write("--turns muss zwischen 1 und 50 liegen\n")
        return 2
    if args.prompt and args.prompt_file:
        sys.stderr.write("--prompt und --prompt-file schliessen sich aus\n")
        return 2
    prompt = args.prompt
    if args.prompt_file:
        with open(args.prompt_file, encoding="utf-8") as fh:
            prompt = fh.read()
    if not prompt or not prompt.strip():
        sys.stderr.write("Prompt fehlt (--prompt oder --prompt-file)\n")
        return 2

    instances = [i.strip() for i in args.instances.split(",") if i.strip()]
    if not instances:
        sys.stderr.write("--instances darf nicht leer sein\n")
        return 2
    for inst in instances:
        if inst not in DEFAULT_PORTS:
            sys.stderr.write(f"Unbekannte Instanz '{inst}' (bekannt: {', '.join(DEFAULT_PORTS)})\n")
            return 2

    token = gateway_token()
    if len(token) < 10:
        sys.stderr.write("Token unplausibel kurz – Abbruch (kein Token in Logs)\n")
        return 2

    round_label = args.round.strip().replace("/", "-") or "R1"
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
    report: Dict[str, Any] = {
        "tool": "measure-session",
        "version": VERSION,
        "date_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "round": round_label,
        "turns": args.turns,
        "prompt": {"hash": prompt_hash, "chars": len(prompt)},
        "tailnet": args.tailnet,
        "per_instance": {},
    }
    exit_code = 0

    for inst in instances:
        port = DEFAULT_PORTS[inst]
        agent_id = DEFAULT_AGENTS[inst]
        session_key = f"agent:{agent_id}:baseline-{round_label}-{uuid.uuid4().hex[:8]}"
        entry: Dict[str, Any] = {
            "instance": inst,
            "port": port,
            "agent_id": agent_id,
            "session_key": session_key,
            "turns": [],
        }
        prev: Optional[Dict[str, int]] = None
        for turn in range(1, args.turns + 1):
            rc, output = run_turn(port, args.tailnet, token, agent_id,
                                  session_key, prompt)
            if rc != 0:
                entry["turns"].append({
                    "turn": turn, "rc": rc, "error": output.strip()[:500],
                })
                exit_code = 1
                break
            analysis = session_analysis(port, args.tailnet, token,
                                        session_key, turn)
            analysis["delta_input_vs_prev"] = (
                usage_delta(prev, analysis["usage"]) if prev is not None else None
            )
            entry["turns"].append(analysis)
            prev = analysis["usage"]
        if entry["turns"]:
            first = entry["turns"][0]
            last = entry["turns"][-1]
            entry["delta_input_total"] = (
                last["usage"]["input"] - first["usage"]["input"]
                if last.get("usage") and first.get("usage") else None
            )
            entry["cache_hit_ratio"] = (
                round(last["usage"]["cacheRead"] / last["usage"]["input"], 4)
                if last.get("usage") and last["usage"]["input"] else None
            )
        report["per_instance"][inst] = entry

    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
    else:
        print(payload)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
