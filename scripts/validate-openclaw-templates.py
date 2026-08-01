#!/usr/bin/env python3
"""K2-3: Validiert openclaw.json.j2-Rendering (Schema) + Compose-YAML für alle Instanzen/Targets.
Läuft in CI (ansible bringt jinja2 mit). Exit != 0 bei Fehlern."""
import json, sys
import yaml
import jinja2

ROOT = 'ansible'
gv_all = yaml.safe_load(open(f'{ROOT}/group_vars/all.yml'))
env = jinja2.Environment()
SRC = open(f'{ROOT}/roles/openclaw-gateway/templates/openclaw.json.j2').read()
COMPOSE = open(f'{ROOT}/roles/openclaw-gateway/templates/docker-compose.yml.j2').read()

def fake_lookup(name, *a, **kw):
    return ''  # ohne Secrets rendern (leere Keys) – Struktur-Validierung

def render(oc, target):
    e = jinja2.Environment()
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
            e2 = jinja2.Environment()
            e2.globals['lookup'] = fake_lookup
            yaml.safe_load(e2.from_string(COMPOSE).render(
                oc=oc, openclaw_image=gv_all['openclaw_image'],
                openclaw_image_version=gv_all['openclaw_image_version'],
                docker_network='traefik-network', oc_gateway_token='tok', oc_telegram_bot_token=''))
        except Exception as ex:
            failures.append(f"{tf}/{oc['name']}: {ex}")

if failures:
    print("FEHLER:")
    [print(" -", f) for f in failures]
    sys.exit(1)
print("Alle openclaw-Templates validiert (dev+prod, alle Instanzen)")
