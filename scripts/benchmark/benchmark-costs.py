#!/usr/bin/env python3
"""Benchmark-Kosten je OC (LLM-Tokens → €).

Liest Session-Transkripte der Benchmark-Runde (via Gateway-API) und berechnet
die KI-Kosten je Instanz/Agent mit DeepSeek-Listenpreisen (2026-08-03, Quelle:
https://api-docs.deepseek.com/quick_start/pricing/).

Preise je 1M Tokens (USD):
  deepseek-v4-flash: input-miss 0.14, input-hit 0.0028, output 0.28
  deepseek-v4-pro:   input-miss 1.74, input-hit 0.0145, output 3.48
  (promo-Preise $0.435/$0.87 aus Design 05 sind NICHT Listenpreis → nicht verwenden)

Nutzung:
  python3 scripts/benchmark/benchmark-costs.py <task-log.json> [--eur] [--agent-detail]

task-log.json: JSONL mit {inst, sessionKey, ...} je Lauf (Hauptsession).
Alle Sub-Sessions der Instanz werden automatisch mitgezählt.
Token je Message aus usage.totalTokens; input/output/cacheRead aus usage.
"""
import json, subprocess, sys, os

import os
# K4-4 (PR #83): Konfiguration via Env mit Defaults (keine hartcodierten Umgebungswerte)
# Beispiel: GW_TAILNET=vps-dev.tailcfea8a.ts.net GW_PORTS_OC1=18789 BENCH_DS_FLASH_IN_MISS=0.14
GW_TAILNET = os.environ.get("GW_TAILNET", "vps-dev.tailcfea8a.ts.net")
GW_PORTS = {
    "oc1": int(os.environ.get("GW_PORTS_OC1", "18789")),
    "oc2": int(os.environ.get("GW_PORTS_OC2", "18790")),
    "oc3": int(os.environ.get("GW_PORTS_OC3", "18791")),
}
PRICES = {
    "deepseek-v4-flash": {
        "in_miss": float(os.environ.get("BENCH_DS_FLASH_IN_MISS", "0.14")),
        "in_hit": float(os.environ.get("BENCH_DS_FLASH_IN_HIT", "0.0028")),
        "out": float(os.environ.get("BENCH_DS_FLASH_OUT", "0.28")),
    },
    "deepseek-v4-pro": {
        "in_miss": float(os.environ.get("BENCH_DS_PRO_IN_MISS", "1.74")),
        "in_hit": float(os.environ.get("BENCH_DS_PRO_IN_HIT", "0.0145")),
        "out": float(os.environ.get("BENCH_DS_PRO_OUT", "3.48")),
    },
}
DEFAULT_PRICE = PRICES["deepseek-v4-flash"]
EUR_PER_USD = float(os.environ.get("BENCH_EUR_PER_USD", "1.14"))  # Stand 2026-08 (Design 05)

def gw_call(port, method, params=None):
    token = os.environ.get("GW_TOKEN")
    if not token:
        sys.path.insert(0, "/tmp")
        from tok import TOKEN
        token = TOKEN
    cmd = ["openclaw", "gateway", "call", method,
           "--url", f"wss://{GW_TAILNET}:{port}",
           "--token", token, "--json"]
    if params:
        cmd += ["--params", json.dumps(params)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"error": r.stdout[:300]}

def session_cost(port, key):
    """Summiert Tokens+Kosten einer Session. Rückgabe: dict."""
    r = gw_call(port, "sessions.get", {"key": key})
    msgs = r.get("messages", [])
    agg = {"in_miss": 0, "in_hit": 0, "out": 0, "total": 0, "msgs": len(msgs)}
    usd = 0.0
    for m in msgs:
        u = m.get("usage") or {}
        model = (m.get("model") or "deepseek-v4-flash").split("/")[-1]
        p = PRICES.get(model, DEFAULT_PRICE)
        inp = u.get("input", 0) or 0
        out = u.get("output", 0) or 0
        hit = u.get("cacheRead", 0) or 0
        miss = max(0, inp - hit)
        agg["in_miss"] += miss
        agg["in_hit"] += hit
        agg["out"] += out
        agg["total"] += u.get("totalTokens", 0) or 0
        usd += miss/1e6 * p["in_miss"] + hit/1e6 * p["in_hit"] + out/1e6 * p["out"]
    return agg, usd

def main():
    tasklog = sys.argv[1]
    eur = "--eur" in sys.argv
    detail = "--agent-detail" in sys.argv
    runs = []
    with open(tasklog) as f:
        for line in f:
            if line.strip():
                runs.append(json.loads(line))
    ports = GW_PORTS
    totals = {}
    for run in runs:
        inst = run["inst"]
        port = ports[inst]
        main_key = run["sessionKey"]
        # Hauptsession
        main_agg, main_usd = session_cost(port, main_key)
        inst_total_usd = main_usd
        inst_total_agg = dict(main_agg)
        # Alle Sub-Sessions der Instanz (außer main/benchmark/memfinal)
        sl = gw_call(port, "sessions.list")
        subs = []
        for s in sl.get("sessions", []):
            k = s.get("key", "")
            if k in ("agent:orchestrator:main", "agent:main:main", main_key):
                continue
            if "memfinal" in k or "memorycheck" in k or "memcheck" in k:
                continue
            if f"benchmark-{run.get('runde','d07')}" in k and k != main_key:
                continue  # andere Runden-Sessions nicht einmischen
            sub_agg, sub_usd = session_cost(port, k)
            inst_total_usd += sub_usd
            for kk in inst_total_agg:
                inst_total_agg[kk] += sub_agg[kk]
            subs.append((k, sub_agg, sub_usd))
        totals[inst] = (main_agg, main_usd, subs, inst_total_agg, inst_total_usd)
    print(f"{'Instanz':<6} {'Miss-in':>12} {'Hit-in':>12} {'Output':>12} {'USD':>10} {'EUR':>10}")
    for inst in ["oc1", "oc2", "oc3"]:
        if inst not in totals:
            continue
        main_agg, main_usd, subs, agg, usd = totals[inst]
        e = usd / EUR_PER_USD
        print(f"{inst:<6} {agg['in_miss']:>12,} {agg['in_hit']:>12,} {agg['out']:>12,} {usd:>10.4f} {e:>10.4f}")
        if detail:
            print(f"  Hauptsession: {main_usd:.4f} USD ({main_agg['total']:,} tok)")
            for k, sa, su in subs:
                print(f"  Sub {k.split(':')[-1][:20]:<22} {su:.4f} USD ({sa['total']:,} tok)")

if __name__ == "__main__":
    main()
