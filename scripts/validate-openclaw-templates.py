#!/usr/bin/env python3
"""K2-3: Validiert openclaw.json.j2-Rendering (Schema) + Compose-YAML für alle Instanzen/Targets.
Läuft in CI (ansible bringt jinja2 mit). Exit != 0 bei Fehlern."""
import json, sys
import yaml
import jinja2

ROOT = 'ansible'
gv_all = yaml.safe_load(open(f'{ROOT}/group_vars/all.yml'))
env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
SRC = open(f'{ROOT}/roles/openclaw-gateway/templates/openclaw.json.j2').read()
COMPOSE = open(f'{ROOT}/roles/openclaw-gateway/templates/docker-compose.yml.j2').read()

def make_lookup(keys):
    def _l(name, *a, **kw):
        return keys.get(a[0], '') if name == 'env' and a else ''
    return _l

def fake_lookup(name, *a, **kw):
    return ''  # ohne Secrets rendern (leere Keys) – Struktur-Validierung

def render(oc, target):
    e = jinja2.Environment(trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
    e.globals['lookup'] = fake_lookup
    t = e.from_string(SRC)
    ctx = dict(oc=oc, openclaw_agent_models=gv_all['openclaw_agent_models'],
               openclaw_provider_envs=target['openclaw_provider_envs'],
               openclaw_provider_models=gv_all['openclaw_provider_models'],
               oc_llm_provider=oc['llm_provider'], oc_llm_api_key='',
               oc_websearch_api_key='', oc_gateway_token='tok', oc_telegram_bot_token='')
    return json.loads(t.render(**ctx))

failures = []
for tf in ('vps-dev.yml', 'vps-prod.yml'):
    target = yaml.safe_load(open(f'{ROOT}/group_vars/{tf}'))
    for oc in target['openclaw_instances']:
        try:
            d = render(oc, target)
            # Schema-Checks (K1-1/K1-2-Regression)
            assert 'providers' not in d, "Root-providers verboten (models.providers)"
            assert 'models' in d and 'providers' in d['models']
            for a in oc['agents']:
                aid = a.lower().replace(' ', '-')
                assert any(x.get('id') == aid for x in d['agents'].get('list', [])), f"agent id {aid} fehlt"
            # OC2/OC3-Benchmark (Design 01-oc2-oc3-benchmark): per-Instanz-Conditionals
            if 'subagents_defaults' not in oc:
                # Byte-Identitäts-Garantie: Instanzen ohne Konfiguration bekommen KEINEN subagents-Key
                assert 'subagents' not in d['agents']['defaults'], f"{oc['name']}: subagents-Key unerwartet (Byte-Identität verletzt)"
            else:
                assert d['agents']['defaults'].get('subagents') == oc['subagents_defaults'], \
                    f"{oc['name']}: subagents_defaults nicht gerendert"
            if oc.get('subagents_allow_agents'):
                orch = next(x for x in d['agents']['list'] if x['id'] == 'orchestrator')
                assert orch.get('subagents', {}).get('allowAgents') == oc['subagents_allow_agents'], \
                    f"{oc['name']}: allowAgents fehlt/falsch (nur Orchestrator)"
            if 'agent_models' in oc:
                for aid, mdl in oc['agent_models'].items():
                    eid = aid.lower().replace(' ', '-')
                    a = next(x for x in d['agents']['list'] if x['id'] == eid)
                    assert a['model']['primary'] == mdl['primary'], \
                        f"{oc['name']}/{eid}: primary {a['model']['primary']} != {mdl['primary']}"
                    assert a['model']['fallbacks'] == mdl['fallbacks'], \
                        f"{oc['name']}/{eid}: fallbacks {a['model']['fallbacks']} != {mdl['fallbacks']}"
            if oc.get('subagents_tools_deny'):
                assert d['tools']['subagents']['tools']['deny'] == oc['subagents_tools_deny'], \
                    f"{oc['name']}: tools.subagents.deny falsch"
            e2 = jinja2.Environment()
            e2.globals['lookup'] = fake_lookup
            yaml.safe_load(e2.from_string(COMPOSE).render(
                oc=oc, openclaw_image=gv_all['openclaw_image'],
                openclaw_image_version=gv_all['openclaw_image_version'],
                docker_network='traefik-network', oc_gateway_token='tok', oc_telegram_bot_token=''))
            # N5: Key-Pfad (apiKey + models) mit Dummy-Keys durchrendern
            dummy_lookup = {v: 'k-' + k for k, v in target['openclaw_provider_envs'].items() if v}
            if dummy_lookup:
                e3 = jinja2.Environment()
                e3.globals['lookup'] = make_lookup(dummy_lookup)
                dk = json.loads(e3.from_string(SRC).render(
                    oc=oc, openclaw_agent_models=gv_all['openclaw_agent_models'],
                    openclaw_provider_envs=target['openclaw_provider_envs'],
                    openclaw_provider_models=gv_all['openclaw_provider_models'],
                    oc_llm_provider=oc['llm_provider'], oc_llm_api_key='k',
                    oc_websearch_api_key='k', oc_gateway_token='tok', oc_telegram_bot_token=''))
                assert 'providers' not in dk
                for pn, envname in target['openclaw_provider_envs'].items():
                    if envname:
                        assert dk['models']['providers'][pn].get('apiKey') == 'k-' + pn, f"apiKey fehlt bei {pn}"
        except Exception as ex:
            failures.append(f"{tf}/{oc['name']}: {ex}")

# Golden-File-Renderdiff (Design 01 Kap. 4.4 Worst-Case 3, DoD Issue #63): OC1-Render
# (kanonische JSON-Form) muss identisch zum committeten Referenz-Render bleiben – fängt
# semantische Template-Regressionen. OC1 ist seit 2026-08-01 aktiver Benchmark-Arm
# (Creator-Baseline, subagents_defaults explizit) – Golden-File wird nur bei BEWUSSTER
# OC1-Änderung aktualisiert. Schutzumfang (Architect MINOR-4/5): Absence-Assert schuetzt
# PROD-Instanzen + Instanzen ohne Feld (kein subagents-Key); Equality-Assert schuetzt
# DEV-OC2/OC3 (subagents_defaults exakt gerendert); OC2 hat bewusst KEIN Golden-File
# (Scope-Entscheidung, Design 01 Kap. 4.4 Worst-Case 3).
GOLDEN = f'{ROOT}/../scripts/validate/golden/oc1-openclaw.json'
try:
    with open(GOLDEN) as gf:
        golden = gf.read()
    dev = yaml.safe_load(open(f'{ROOT}/group_vars/vps-dev.yml'))
    oc1 = next(oc for oc in dev['openclaw_instances'] if oc['name'] == 'oc1')
    current = json.dumps(render(oc1, dev), indent=2, ensure_ascii=False) + '\n'
    if current != golden:
        failures.append("Golden-File-Renderdiff: OC1-Render weicht byte-genau ab (Template-Regression)")
except FileNotFoundError:
    failures.append(f"Golden-File fehlt: {GOLDEN}")

if failures:
    print("FEHLER:")
    [print(" -", f) for f in failures]
    sys.exit(1)
print("Alle openclaw-Templates validiert (dev+prod, alle Instanzen, inkl. Golden-File-Renderdiff)")
