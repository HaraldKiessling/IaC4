#!/usr/bin/env python3
"""Offline-Gate (ohne Secrets): erzwingt die Deploy-Haertung 2026-10-05.

Belegt statisch (YAML-Parsing, kein Ansible-Lauf, kein Netz):
  1. instance-body.yml installiert/verifiziert QMD + Google-Drive-MCP VOR dem Health-Gate
     (ein fehlgeschlagenes Health darf die Installation nicht mehr ueberspringen).
  2. Der Health-Check hat ein erhoehtes Retry-Budget (>=36 x >=10s) und vor der ersten
     Pruefung eine Stabilisierung (wait_for).
  3. instance.yml kapselt den Instanz-Ablauf in block/rescue -> ein Fehler einer Instanz
     ueberspringt die Folge-Instanzen nicht mehr.
  4. main.yml prueft am Ende per Aggregat-Assert fail-closed (Run rot bei ungesunder Instanz).
Exit != 0 bei Verletzung."""
import sys
import yaml

ROOT = 'ansible/roles/openclaw-gateway/tasks'
failures = []


def load(name):
    with open(f'{ROOT}/{name}') as f:
        return yaml.safe_load(f)


def names(tasks):
    return [t.get('name', '') for t in tasks if isinstance(t, dict)]


# --- instance-body.yml: Reihenfolge + Retry-Budget ---------------------------------------------
try:
    body = load('instance-body.yml')
    n = names(body)

    def idx(substr):
        for i, t in enumerate(n):
            if substr in t:
                return i
        return -1

    i_qmd = idx('QMD im Container installieren')
    i_qmd_v = idx('QMD-Version verifizieren')
    i_gd = idx('Google-Drive-MCP im Container installieren')
    i_gd_v = idx('Google-Drive-MCP-Version verifizieren')
    i_health = idx('Auf Health warten')
    i_wait = idx('Container-Port stabilisieren')
    i_start = idx('Container starten')

    if i_start < 0:
        failures.append('instance-body.yml: "Container starten" fehlt')
    for label, i in (('QMD install', i_qmd), ('QMD verify', i_qmd_v),
                     ('GDrive install', i_gd), ('GDrive verify', i_gd_v),
                     ('Health-Check', i_health), ('Port-Stabilisierung', i_wait)):
        if i < 0:
            failures.append(f'instance-body.yml: Task "{label}" fehlt')
    if all(i >= 0 for i in (i_start, i_wait, i_qmd, i_qmd_v, i_gd, i_gd_v, i_health)):
        if not (i_start < i_wait):
            failures.append('Reihenfolge: Stabilisierung muss nach "Container starten" liegen')
        if not (i_wait < i_qmd):
            failures.append('Reihenfolge: Install/Verify muss nach der Stabilisierung liegen')
        if not (i_qmd < i_gd < i_health) or not (i_qmd_v < i_health) or not (i_gd_v < i_health):
            failures.append('Reihenfolge: QMD/GDrive Install+Verify muessen VOR dem Health-Check liegen')

    # Health-Block: retries/delay
    health_task = next((t for t in body if 'Auf Health warten' in t.get('name', '')), None)
    if not health_task or 'block' not in health_task:
        failures.append('instance-body.yml: Health-Task ist kein block')
    else:
        uri = next((t for t in health_task['block']
                    if any(k.endswith('uri') for k in t)), None)
        if not uri:
            failures.append('instance-body.yml: Health-uri fehlt')
        else:
            if uri.get('retries', 0) < 36 or uri.get('delay', 0) < 10:
                failures.append(
                    f'Health-Retry zu klein: retries={uri.get("retries")} delay={uri.get("delay")} '
                    '(>=36 x >=10s erwartet)')
    # Stabilisierung nutzt wait_for + delay
    if i_wait >= 0:
        wf = next((t for t in body if 'Container-Port stabilisieren' in t.get('name', '')), None)
        wf_node = next((v for k, v in (wf or {}).items() if k.endswith('wait_for')), None)
        if not wf_node or wf_node.get('delay', 0) < 5:
            failures.append('instance-body.yml: Stabilisierung braucht wait_for mit delay>=5')
except Exception as ex:  # noqa: BLE001
    failures.append(f'instance-body.yml nicht parsebar: {ex}')

# --- instance.yml: block/rescue ----------------------------------------------------------------
try:
    wrap = load('instance.yml')
    first = wrap[0] if wrap else {}
    if 'block' not in first or 'rescue' not in first:
        failures.append('instance.yml: Wrapper braucht block + rescue (per-Instanz fail-safe)')
    else:
        rescue_names = names(first['rescue'])
        if not any('Ergebnis erfassen' in x for x in rescue_names):
            failures.append('instance.yml: rescue muss das Instanz-Ergebnis erfassen')
        blob = yaml.safe_dump(first, allow_unicode=True)
        if 'include_tasks' not in blob or 'instance-body.yml' not in blob:
            failures.append('instance.yml: block muss instance-body.yml einbinden')
except Exception as ex:  # noqa: BLE001
    failures.append(f'instance.yml nicht parsebar: {ex}')

# --- main.yml: Aggregat-Assert fail-closed -----------------------------------------------------
try:
    main = load('main.yml')
    agg = next((t for t in main if 'Aggregat-Assert' in t.get('name', '')), None)
    if not agg or not any(k.endswith('assert') for k in agg):
        failures.append('main.yml: Aggregat-Assert fehlt')
    else:
        args = next(v for k, v in agg.items() if k.endswith('assert'))
        that = args.get('that', [])
        joined = ' '.join(str(x) for x in that)
        if 'health' not in joined or 'failed' not in joined:
            failures.append('main.yml: Aggregat-Assert prueft nicht auf ungesunde Instanzen (fail-closed)')
        if 'openclaw_expected_instances' not in joined:
            failures.append('main.yml: Aggregat-Assert prueft nicht, dass ALLE erwarteten Instanzen bearbeitet wurden')
        if 'openclaw_instance_filter' not in joined:
            failures.append('main.yml: Aggregat-Assert prueft nicht auf den Zero-Match-Fall (openclaw_instance_filter)')
except Exception as ex:  # noqa: BLE001
    failures.append(f'main.yml nicht parsebar: {ex}')

if failures:
    print('FEHLER (Deploy-Haertung):')
    for f in failures:
        print(' -', f)
    sys.exit(1)
print('Deploy-Haertung verifiziert: Install vor Health, erhoehtes Retry-Budget, '
      'per-Instanz-rescue + Aggregat-Assert (fail-closed).')
