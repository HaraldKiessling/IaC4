#!/usr/bin/env python3
"""Kontroll-Tool: Prüft nach einem Lauf, ob die Quellen-Regel eingehalten wurde.

Sucht in allen Sessions eines Laufs nach Zugriffen auf:
- verbotene Pfade: pulls/, pull/, issues/ (außer dem eigenen), iac4-design/05, iac4-design/06
- erlaubte: raw.githubusercontent.com/.../9ea618c/...
Gibt VERLETZUNGEN oder OK aus.

Nutzung: python3 scripts/benchmark/audit-sources.py <task-log.json> <issue-nr>
"""
import json, os, subprocess, sys

PORTS = {'oc1': 18789, 'oc2': 18790, 'oc3': 18791}

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
    issue = sys.argv[2] if len(sys.argv) > 2 else None
    runs = [json.loads(l) for l in open(tasklog) if l.strip()]
    total_violations = 0
    for run in runs:
        inst = run['inst']; port = PORTS[inst]
        violations = []
        ok_snapshot = 0
        sl = gw_call(port, 'sessions.list')
        for s in sl.get('sessions', []):
            k = s.get('key','')
            if f"benchmark-{run['runde']}" not in k and 'LMH' not in k.upper():
                continue
            r = gw_call(port, 'sessions.get', {'key': k})
            for m in r.get('messages', []):
                c = m.get('content', [])
                if isinstance(c, list):
                    for part in c:
                        if isinstance(part, dict) and part.get('type') == 'toolCall':
                            args = part.get('arguments', {})
                            for field in ('url', 'command'):
                                v = args.get(field, '')
                                if not v: continue
                                low = v.lower()
                                # Verbote
                                if any(x in low for x in ['/pulls', '/pull/', 'pulls?', 'issues?state', 'issues/comments', 'git/refs', 'branches']):
                                    violations.append(('PR/Branch/Issue-Zugriff', v[:120]))
                                if any(x in low for x in ['iac4-design/05', 'iac4-design/06', 'design/05', 'design/06']):
                                    violations.append(('Design-Doku (Lösung)', v[:120]))
                                if 'raw.githubusercontent.com' in low and '9ea618c' not in low:
                                    violations.append(('Nicht-Snapshot-Commit', v[:120]))
                                # Erlaubte Snapshot-Nutzung zählen
                                if '9ea618c' in low:
                                    ok_snapshot += 1
        status = 'OK' if not violations else f'{len(violations)} VERLETZUNGEN'
        print(f"{inst} (Runde {run['runde']}): {status} | Snapshot-Abrufe: {ok_snapshot}")
        for v in violations[:6]:
            print(f"  ❌ {v[0]}: {v[1]}")
        total_violations += len(violations)
    print(f"\nGesamt: {'✅ KEINE Verletzungen' if total_violations == 0 else f'❌ {total_violations} Verletzungen'}")

if __name__ == '__main__':
    main()
