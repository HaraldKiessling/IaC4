#!/usr/bin/env python3
"""Korrekte Benchmark-Zeitmessung (Harald 2026-08-04).

Problem: run.json durationMs misst nur den CLI-Turn (Turn1). Die echte Laufzeit
bis zum fertigen Artefakt umfasst Sub-Agent-Arbeit + Synthese + Recovery.

Metriken je Lauf:
- time_to_artifact: Session-Start (1. Message) -> Artefakt-updatedAt (Workspace)
- turn1_duration:    CLI-Turn (run.json durationMs)
- sub_work_window:   min(Sub-Start) -> max(Sub-Ende) im Runden-Fenster
- post_turn1:        time_to_artifact - turn1_duration (Synthese/Sub/Runner-Anteil)

Nutzung: python3 scripts/benchmark/benchmark-timing.py <task-log.json> <runde>
"""
import json, os, subprocess, sys

PORTS = {'oc1': 18789, 'oc2': 18790, 'oc3': 18791}
AIDS = {'oc1': 'main', 'oc2': 'orchestrator', 'oc3': 'orchestrator'}

def gw_call(port, method, params=None):
    sys.path.insert(0, '/tmp')
    from tok import TOKEN
    cmd = ['openclaw', 'gateway', 'call', method, '--url', f'wss://vps-dev.tailcfea8a.ts.net:{port}', '--token', TOKEN, '--json']
    if params: cmd += ['--params', json.dumps(params)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try: return json.loads(r.stdout)
    except: return {'error': r.stdout[:200]}

def main():
    tasklog = sys.argv[1]
    runde = sys.argv[2] if len(sys.argv) > 2 else '?'
    runs = [json.loads(l) for l in open(tasklog) if l.strip()]
    print(f"{'Instanz':<6} {'Turn1':>7} {'Time2Art':>9} {'postTurn1':>9} {'SubWindow':>10} | Größe")
    for run in runs:
        inst = run['inst']; port = PORTS[inst]; aid = AIDS[inst]
        key = run['sessionKey']
        # Turn1-Dauer
        out = json.load(open(run['out'])) if os.path.exists(run['out']) else {}
        turn1 = out.get('result',{}).get('meta',{}).get('durationMs',0)/1000
        # Session-Start
        r = gw_call(port, 'sessions.get', {'key': key})
        msgs = r.get('messages', [])
        t0 = msgs[0].get('timestamp',0) if msgs else 0
        # Artefakt-Zeit
        issue = run['issue']
        wl = gw_call(port, 'agents.workspace.list', {'agentId': aid, 'path': f'benchmark/{runde}'})
        art = next((f for f in wl.get('entries',[]) if f.get('name')==f'#{issue}-{inst}.md'), None)
        art_ms = art.get('updatedAtMs') if art else 0
        tta = (art_ms - t0)/1000 if art_ms and t0 else 0
        post = max(0, tta - turn1)
        # Sub-Work-Window im Runden-Fenster
        sl = gw_call(port, 'sessions.list')
        sub_starts, sub_ends = [], []
        for s in sl.get('sessions', []):
            k = s.get('key','')
            if 'subagent' not in k: continue
            r2 = gw_call(port, 'sessions.get', {'key': k})
            m2 = r2.get('messages', [])
            if not m2: continue
            fs, ls = m2[0].get('timestamp',0), m2[-1].get('timestamp',0)
            if fs >= t0 and fs <= (art_ms or t0):  # im Runden-Fenster
                sub_starts.append(fs); sub_ends.append(ls)
        subwin = (max(sub_ends) - min(sub_starts))/1000 if sub_starts else 0
        size = art.get('size','?') if art else 'FEHLT'
        print(f"{inst:<6} {turn1:>6.0f}s {tta:>8.0f}s {post:>8.0f}s {subwin:>9.0f}s | {size}")

if __name__ == '__main__':
    main()
