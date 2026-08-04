#!/usr/bin/env python3
"""Benchmark-Runde starten (Design 05): 3 Arme, gleiche Aufgabe, Prompt-Template.

Nutzung:
  python3 scripts/benchmark/run-round.py <runde> <issue> <titel>
  z.B. python3 scripts/benchmark/run-round.py H 65 "Code-Server auf DEV deployen"

Erzeugt Prompts aus templates/benchmark-task.md (OC1=Single-Agent, OC2/OC3=Team),
startet 3 Agent-Turns parallel (Env-Gateway), schreibt task-log.json.
"""
import json, os, subprocess, sys, uuid

ROUND = sys.argv[1]
ISSUE = sys.argv[2]
TITLE = sys.argv[3]
BASE = os.path.dirname(os.path.abspath(__file__))
TPL = open(os.path.join(BASE, 'templates', 'benchmark-task.md')).read()

def gw_token():
    sys.path.insert(0, '/tmp')
    from tok import TOKEN
    return TOKEN

def render(inst, aid, role):
    return (TPL.replace('{{ ARM }}', inst.upper())
               .replace('{{ RUNDE }}', ROUND)
               .replace('{{ ISSUE }}', ISSUE)
               .replace('{{ TITEL }}', TITLE)
               .replace('{{ INST }}', inst)
               .replace('{{ ROLLE }}', role))

runs = [
    ('oc1', 18789, None, 'Single-Agent (Vanilla-Baseline): Du arbeitest als Single-Agent OHNE Sub-Agent-Delegation. Bearbeite das Issue vollständig in deinem eigenen Thread.'),
    ('oc2', 18790, 'orchestrator', 'Orchestrator mit Sub-Agents (architect/engineer-pro/reviewer) — du VERTEILST, du führst nicht aus.'),
    ('oc3', 18791, 'orchestrator', 'Orchestrator mit Sub-Agents (architect/engineer-pro/reviewer) — du VERTEILST, du führst nicht aus.'),
]
TOKEN = gw_token()
log = []
for inst, port, aid, role in runs:
    prompt = render(inst, aid, role)
    # Issue-Body anhängen
    body = subprocess.run(['gh', 'issue', 'view', ISSUE, '--repo', 'HaraldKiessling/IaC4', '--json', 'body', '--jq', '.body'],
                          capture_output=True, text=True).stdout
    prompt += f"\n\n## Issue #{ISSUE} (vollständiger Body)\n{body}"
    pf = f"/tmp/bench-{ROUND.lower()}-{inst}.md"
    open(pf, 'w').write(prompt)
    sk = f"agent:{aid or 'main'}:benchmark-{ROUND}-{uuid.uuid4().hex[:8]}"
    env = dict(os.environ)
    env['OPENCLAW_GATEWAY_URL'] = f'wss://vps-dev.tailcfea8a.ts.net:{port}'
    env['OPENCLAW_GATEWAY_TOKEN'] = TOKEN
    cmd = ['openclaw', 'agent', '--message-file', pf, '--session-key', sk, '--json']
    if aid:
        cmd.insert(2, '--agent'); cmd.insert(3, aid)
    outdir = os.path.expanduser(f'~/.openclaw/workspace/benchmark/bench-{ROUND.lower()}')
    os.makedirs(outdir, exist_ok=True)
    out = f"{outdir}/{inst}.run.json"
    err = f"{outdir}/{inst}.err.log"
    with open(out, 'w') as fo, open(err, 'w') as fe:
        p = subprocess.Popen(cmd, stdout=fo, stderr=fe, start_new_session=True, env=env)
    log.append({'inst': inst, 'sessionKey': sk, 'pid': p.pid, 'out': out, 'runde': ROUND, 'issue': int(ISSUE)})
    print(f"{inst}: gestartet pid={p.pid} key={sk}")

with open(f"{outdir}/task-log.json", 'w') as f:
    for e in log:
        f.write(json.dumps(e) + '\n')
print(f"=== RUNDE {ROUND} GESTARTET (Issue #{ISSUE}) === (Task-Log: {outdir}/task-log.json)")
# S-2c integriert (Harald 2026-08-04): warte auf Abschluss -> Follow-up -> Kosten
import time
print("Warte auf Abschluss aller 3 Arme (max 15 min)...")
for i in range(180):
    time.sleep(5)
    done = sum(1 for e in log if os.path.exists(e['out']) and json.load(open(e['out'])).get('status','') in ('ok','timeout'))
    if done == 3: break
print(f"Alle 3 Arme beendet nach ~{(i+1)*5}s. Follow-up-Synthese...")
subprocess.run(['python3', os.path.join(BASE, 'followup-synthesis.py'), f'{outdir}/task-log.json'], timeout=600)
print("Kosten berechnen...")
subprocess.run(['python3', os.path.join(BASE, 'benchmark-costs.py'), f'{outdir}/task-log.json', '--eur'], timeout=120)
