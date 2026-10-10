#!/usr/bin/env python3
"""K2-3: Validiert openclaw.json.j2-Rendering (Schema) + Compose-YAML für alle Instanzen/Targets.
Läuft in CI (ansible bringt jinja2 mit). Exit != 0 bei Fehlern."""
import json, sys
import yaml
import jinja2

ROOT = 'ansible'
gv_all = yaml.safe_load(open(f'{ROOT}/group_vars/all.yml'))
def _bool_filter(v):
    # Ansible-Äquivalent: 'true'/'yes'/1/True -> True, alles andere -> False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ('true', 'yes', 'on', '1')
    return bool(v)

env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
env.filters['bool'] = _bool_filter
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
    e.filters['bool'] = _bool_filter
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
            # Memory-Konfiguration (Fix 2026-08-03): FTS-only explizit – kein Embedding-Default
            assert d['memory']['backend'] == 'qmd', f"{oc['name']}: memory.backend != qmd (lokal-konsistent)"
            assert d['agents']['defaults'].get('memorySearch', {}).get('provider') == 'local', \
                f"{oc['name']}: memorySearch.provider != local (QMD-Setup wie PROD-Host; Default 'openai' verursacht Index-Warnung)"
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
                    # OC1 (agents: []) hat agent_models nur fuer agents.defaults.model — kein list-Eintrag
                    if not oc['agents']:
                        assert d['agents']['defaults'].get('model', {}).get('primary') == mdl['primary'], \
                            f"{oc['name']}: defaults.model != {mdl['primary']} (OC1-Fairness-Fix)"
                        continue
                    a = next(x for x in d['agents']['list'] if x['id'] == eid)
                    assert a['model']['primary'] == mdl['primary'], \
                        f"{oc['name']}/{eid}: primary {a['model']['primary']} != {mdl['primary']}"
                    assert a['model']['fallbacks'] == mdl['fallbacks'], \
                        f"{oc['name']}/{eid}: fallbacks {a['model']['fallbacks']} != {mdl['fallbacks']}"
            if oc.get('agent_workspaces'):
                # Design 06: Per-Agent-Workspace NUR für Sub-Agents (Orchestrator behält Root)
                for a in oc['agents']:
                    aid = a.lower().replace(' ', '-')
                    ent = next(x for x in d['agents']['list'] if x['id'] == aid)
                    if aid == 'orchestrator':
                        assert 'workspace' not in ent, f"{oc['name']}/orchestrator: workspace unerwartet (Root bleibt)"
                    else:
                        assert ent.get('workspace') == f"/home/node/.openclaw/workspace/{aid}", \
                            f"{oc['name']}/{aid}: workspace fehlt/falsch"
            if oc.get('agent_thinking'):
                for a, lvl in oc['agent_thinking'].items():
                    eid = a.lower().replace(' ', '-')
                    ent = next(x for x in d['agents']['list'] if x['id'] == eid)
                    assert ent.get('thinkingDefault') == lvl, \
                        f"{oc['name']}/{eid}: thinkingDefault {ent.get('thinkingDefault')} != {lvl}"
            if oc.get('subagents_tools_deny'):
                assert d['tools']['subagents']['tools']['deny'] == oc['subagents_tools_deny'], \
                    f"{oc['name']}: tools.subagents.deny falsch"
            e2 = jinja2.Environment()
            e2.filters['bool'] = _bool_filter
            e2.globals['lookup'] = fake_lookup
            yaml.safe_load(e2.from_string(COMPOSE).render(
                oc=oc, openclaw_image=gv_all['openclaw_image'],
                openclaw_image_version=gv_all['openclaw_image_version'],
                docker_network='traefik-network', oc_gateway_token='tok', oc_telegram_bot_token=''))
            # N5: Key-Pfad (apiKey + models) mit Dummy-Keys durchrendern
            dummy_lookup = {v: 'k-' + k for k, v in target['openclaw_provider_envs'].items() if v}
            if dummy_lookup:
                e3 = jinja2.Environment()
                e3.filters['bool'] = _bool_filter
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

# Google-Drive-MCP file-based Credentials (Token-Hygiene 2026-10-05, Owner-Entscheid 'A'):
# Mit Dummy-Secrets muss openclaw.json gdrive enabled:true rendern, aber NUR Pfad/Scope-Env
# (keine sensiblen Werte); das Compose-Template mountet die Dateien read-only und rollt KEIN
# GDRIVE_*-Env mehr aus. Ohne Secrets: enabled:false und kein Mount/Env.
_gdrive_dummy = {
    'openclaw_gdrive_client_id': 'cid-dummy.apps.googleusercontent.com',
    'openclaw_gdrive_client_secret': 'csec-dummy',
    'openclaw_gdrive_refresh_token': 'refresh-dummy',
    'openclaw_gdrive_access_token': 'access-dummy',
}
TOKEN_PATH = '/home/node/.config/google-drive-mcp/tokens.json'
try:
    dev_t = yaml.safe_load(open(f'{ROOT}/group_vars/vps-dev.yml'))
    oc_t = dev_t['openclaw_instances'][0]
    _base = dict(oc=oc_t, openclaw_agent_models=gv_all['openclaw_agent_models'],
                 openclaw_provider_envs=dev_t['openclaw_provider_envs'],
                 openclaw_provider_models=gv_all['openclaw_provider_models'],
                 oc_llm_provider=oc_t['llm_provider'], oc_llm_api_key='k',
                 oc_websearch_api_key='k', oc_gateway_token='tok', oc_telegram_bot_token='')
    _compose_base = dict(oc=oc_t, openclaw_image=gv_all['openclaw_image'],
                         openclaw_image_version=gv_all['openclaw_image_version'],
                         docker_network='traefik-network', oc_gateway_token='tok',
                         oc_telegram_bot_token='', openclaw_data_root='/srv/openclaw')

    def _env():
        e = jinja2.Environment(trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
        e.filters['bool'] = _bool_filter
        e.globals['lookup'] = fake_lookup
        return e

    # mit Dummy-Secrets
    dg = json.loads(_env().from_string(SRC).render(**_base, **_gdrive_dummy))
    srv = dg['mcp']['servers']['gdrive']
    assert srv.get('enabled') is True, "gdrive nicht enabled trotz gesetzter Credentials"
    assert set(srv.get('env', {}).keys()) == {'GOOGLE_DRIVE_MCP_SCOPES', 'GOOGLE_DRIVE_MCP_TOKEN_PATH'}, \
        f"gdrive env nicht minimal (nur Pfad/Scope): {sorted(srv.get('env', {}))}"
    assert srv['env']['GOOGLE_DRIVE_MCP_TOKEN_PATH'] == TOKEN_PATH, "TOKEN_PATH falsch"
    blob = json.dumps(dg)
    for v in _gdrive_dummy.values():
        assert v not in blob, "sensible Dummy-Werte in openclaw.json-Render (Token-Hygiene verletzt)"

    comp = _env().from_string(COMPOSE).render(**_compose_base, **_gdrive_dummy)
    for leaked in ('GDRIVE_CLIENT_ID', 'GDRIVE_CLIENT_SECRET', 'GDRIVE_REFRESH_TOKEN', 'GDRIVE_ACCESS_TOKEN'):
        assert leaked not in comp, f"{leaked} leakt im Compose-Render (Env-Passthrough nicht entfernt)"
    assert comp.count('/home/node/.config/google-drive-mcp/') == 2, \
        "gdrive-Credential-Mounts fehlen/unvollstaendig im Compose-Render"
    assert './gdrive/tokens.json' in comp and ':ro' in comp, "Mount nicht read-only/relativ"

    # ohne Secrets -> disabled, keine Mounts
    comp_off = _env().from_string(COMPOSE).render(**_compose_base)
    assert '/home/node/.config/google-drive-mcp/' not in comp_off, "Mount trotz fehlender Secrets"
    assert 'GDRIVE_' not in comp_off, "GDRIVE-Env trotz fehlender Secrets"
except Exception as ex:
    failures.append(f"gdrive-file-based: {ex}")

# Agenten-Zugangsdaten (ADR-027): aktiv -> Exec-Freigaben + Telegram-Approver in openclaw.json,
# env_file + read-only Mounts (Skill, Wrapper) im Compose, KEINE Werte im Render. Inaktiv
# (Default, keine Secret-Datei) -> nichts davon, auch kein altes BITWARDEN_CLIENTSECRET.
try:
    _bw = dict(oc_bitwarden_active=True, openclaw_exec_approvers=gv_all['openclaw_exec_approvers'],
               openclaw_bitwarden_env_file=gv_all['openclaw_bitwarden_env_file'])
    db = json.loads(_env().from_string(SRC).render(**_base, **_bw))
    assert db['tools']['exec'] == {'mode': 'ask', 'strictInlineEval': True}, f"tools.exec falsch: {db['tools'].get('exec')}"
    _base_tg = dict(_base, oc_telegram_bot_token='tg-dummy')
    dbt = json.loads(_env().from_string(SRC).render(**_base_tg, **_bw))
    ea = dbt['channels']['telegram']['execApprovals']
    assert ea == {'enabled': True, 'approvers': gv_all['openclaw_exec_approvers'], 'target': 'dm'}, f"execApprovals falsch: {ea}"
    comp_bw = yaml.safe_load(_env().from_string(COMPOSE).render(**_compose_base, **_bw))
    svc = comp_bw['services']['openclaw']
    assert svc.get('env_file') == [gv_all['openclaw_bitwarden_env_file']], "env_file fehlt"
    for m in ('./bitwarden/skills/ia4-bitwarden:/home/node/.openclaw/skills/ia4-bitwarden:ro',
              './bitwarden/ia4-bw:/opt/ia4-bitwarden/ia4-bw:ro'):
        assert m in svc['volumes'], f"Mount fehlt: {m}"
    assert not any(k.startswith('BW_') or k == 'BITWARDEN_CLIENTSECRET' for k in svc.get('environment', {})), \
        "Bitwarden-Werte im Compose-environment (gehoeren nur in die Host-Datei)"
    dn = json.loads(_env().from_string(SRC).render(**_base_tg))
    assert 'exec' not in dn['tools'] and 'execApprovals' not in dn['channels']['telegram'], "Freigaben trotz inaktiv"
    comp_nb = yaml.safe_load(_env().from_string(COMPOSE).render(**_compose_base))['services']['openclaw']
    assert 'env_file' not in comp_nb and not any('bitwarden' in v for v in comp_nb['volumes']), "Bitwarden trotz inaktiv"
    assert 'BITWARDEN_CLIENTSECRET' not in _env().from_string(COMPOSE).render(**_compose_base), "alte Kette noch im Template"
except Exception as ex:
    failures.append(f"bitwarden-adr027: {ex}")

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
