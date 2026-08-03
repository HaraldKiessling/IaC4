#!/usr/bin/env python3
"""S-2c: Runner-Follow-up — stellt Synthese sicher, wenn ein Lauf nach yield endet.

Nutzung: python3 scripts/benchmark/followup-synthesis.py <task-log.json>
Prüft je Lauf: existiert das Artefakt (workspace.list)? Wenn nicht: Follow-up-Turn
"Hole Sub-Ergebnisse und schreibe das Artefakt" an denselben Agent/Key.
"""
import json, os, subprocess, sys, time

def gw_call(port, method, params=None):
    sys.path.insert(0, '/tmp')
    from tok import TOKEN
    cmd = ['openclaw', 'gateway', 'call', method, '--url', f'wss://vps-dev.tailcfea8a.ts.net:{port}', '--token', TOKEN, '--json']
    if params: cmd += ['--params', json.dumps(params)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try: return json.loads(r.stdout)
    except: return {'error': r.stdout[:200]}

def run_turn(port, aid, key, msg):
    sys.path.insert(0, '/tmp')
    from tok import TOKEN
    env = dict(os.environ)
    env['OPENCLAW_GATEWAY_URL'] = f'wss://vps-dev.tailcfea8a.ts.net:{port}'
    env['OPENCLAW_GATEWAY_TOKEN'] = TOKEN
    cmd = ['openclaw', 'agent', '--agent', aid, '--message', msg, '--session-key', key, '--json']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
    try: return json.loads(r.stdout)
    except: return {'error': r.stdout[:300]}

PORTS = {'oc1': 18789, 'oc2': 18790, 'oc3': 18791}
AIDS = {'oc1': None, 'oc2': 'orchestrator', 'oc3': 'orchestrator'}  # oc1: default

def main():
    tasklog = sys.argv[1]
    rundir = os.path.dirname(tasklog)
    runs = [json.loads(l) for l in open(tasklog) if l.strip()]
    for run in runs:
        inst = run['inst']; port = PORTS[inst]; aid = AIDS[inst]
        key = run['sessionKey']
        # Artefakt-Existenz prüfen: Workspace-Listing im Runden-Ordner (robust)
        runde = run.get('runde', '?')
        wl = gw_call(port, 'agents.workspace.list', {'agentId': aid or 'main', 'path': f'benchmark/{runde}'})
        files = wl.get('entries', wl.get('files', []))
        names = [f.get('name','') for f in files]
        # Artefakt = exakt #<issue>-<inst>.md (kein -draft, kein -plan, kein Plan)
        expected = f"#{run['issue']}-{inst}.md"
        has_artifact = expected in names
        # Zusätzlich: Lauf-Output enthält Artefakt-Pfad?
        out = json.load(open(run['out'])) if os.path.exists(run['out']) else {}
        payloads = out.get('result', {}).get('payloads', [])
        has_artifact = has_artifact or any(expected in (p.get('text','') or '') for p in payloads) if payloads else has_artifact
        # Zusätzlich: letzte Session-Message auf Artefakt-Pfad prüfen
        r = gw_call(port, 'sessions.get', {'key': key})
        msgs = r.get('messages', [])
        last_text = ''
        for m in reversed(msgs):
            c = m.get('content', [])
            if isinstance(c, list):
                for part in c:
                    if isinstance(part, dict) and part.get('type') == 'text':
                        last_text = part.get('text','')
                        break
            if last_text: break
        artifact_mentioned = expected in last_text or (f"#{run['issue']}-{inst}" in last_text and '-plan' not in last_text and '-draft' not in last_text)
        has_artifact = has_artifact or artifact_mentioned
        if not has_artifact:
            print(f"{inst}: KEIN Artefakt-Nachweis -> Follow-up-Turn")
            msg = ("Deine Sub-Agent-Ergebnisse sind da. Hole sie via sessions_history und schreibe JETZT das Artefakt "
                   f"(Pflicht, Markdown, EXAKTER Dateiname): /home/node/.openclaw/workspace/benchmark/{run['runde']}/#{run['issue']}-{inst}.md "
                   "mit den 5 Abschnitten (Anforderungs-Analyse, Lösungs-Design, Risiko-Analyse, Umsetzungs-Plan, Review-Notiz). "
                   "Integriere ALLE Sub-Ergebnisse — keine Platzhalter, kein '-draft', kein '-plan' im Dateinamen. "
                   "Antworte mit Artefakt-Pfad.")
            res = run_turn(port, aid or 'main', key, msg)
            pl = res.get('result', {}).get('payloads', [])
            print(f"  Follow-up: {pl[0].get('text','')[:200] if pl else '(kein payload)'}")
        else:
            print(f"{inst}: Artefakt-Nachweis vorhanden, kein Follow-up nötig")

if __name__ == '__main__':
    main()
