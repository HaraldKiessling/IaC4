"""Tests fuer tools/telegram-approve-bot/sot_parser.py (Design 05, Major #7).

Fixtures sind Beispieldaten im Test (tmp_path) – KEINE echten Secrets/VPS-Daten.
Abgedeckt: enabled/disabled-Filterung, mehrere VPS-Dateien, Zukunft (M5):
target als Instanz-Attribut ueberschreibt Datei-level env.
"""

import os
import sys

import pytest

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "telegram-approve-bot")
sys.path.insert(0, os.path.abspath(TOOLS_DIR))

from sot_parser import DEFAULT_GLOB, iter_enabled_instances, main  # noqa: E402


def write_group_var(tmp_path, filename, content):
    target_dir = tmp_path / "ansible" / "group_vars"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / filename).write_text(content, encoding="utf-8")


VPS_DEV = """\
---
env: dev
openclaw_instances:
  - name: oc1
    enabled: true
    port: 18789
  - name: oc2
    enabled: true
    port: 18790
  - name: oc3
    enabled: false
    port: 18791
"""

VPS_PROD = """\
---
env: prod
openclaw_instances:
  - name: oc1
    enabled: true
    port: 18789
  - name: oc2
    enabled: false
    port: 18790
"""

VPS_COMBI = """\
---
env: combi
openclaw_instances:
  # M5: target als Instanz-Attribut (ein VPS hostet dev+prod)
  - name: oc1-dev
    target: dev
    enabled: true
    port: 18789
  - name: oc1-prod
    target: prod
    enabled: true
    port: 18790
  - name: oc3
    enabled: false
"""


@pytest.fixture
def sot_repo(tmp_path):
    """Repo-artige Struktur mit dev+prod group_vars (Beispieldaten, keine Secrets)."""
    write_group_var(tmp_path, "vps-dev.yml", VPS_DEV)
    write_group_var(tmp_path, "vps-prod.yml", VPS_PROD)
    return tmp_path


def test_enabled_filtering_single_file(tmp_path):
    """Nur enabled Instanzen, target = Datei-level env."""
    write_group_var(tmp_path, "vps-dev.yml", VPS_DEV)
    assert iter_enabled_instances(str(tmp_path)) == [("oc1", "dev"), ("oc2", "dev")]


def test_multiple_vps_files(sot_repo):
    """Mehrere VPS-Dateien: Globbing findet beide, disabled (prod oc2) gefiltert."""
    result = iter_enabled_instances(str(sot_repo))
    assert result == [("oc1", "dev"), ("oc2", "dev"), ("oc1", "prod")]


def test_target_attribute_per_instance_overrides_env(tmp_path):
    """Zukunft M5: Instanz-level 'target' gewinnt gegen Datei-level env."""
    write_group_var(tmp_path, "vps-combi.yml", VPS_COMBI)
    assert iter_enabled_instances(str(tmp_path)) == [("oc1-dev", "dev"), ("oc1-prod", "prod")]


def test_missing_env_key_defaults_unknown(tmp_path):
    write_group_var(tmp_path, "vps-x.yml", "openclaw_instances:\n  - name: oc1\n    enabled: true\n")
    assert iter_enabled_instances(str(tmp_path)) == [("oc1", "unknown")]


def test_no_files(tmp_path):
    assert iter_enabled_instances(str(tmp_path)) == []


def test_disabled_only(tmp_path):
    write_group_var(tmp_path, "vps-dev.yml", VPS_COMBI.replace("enabled: true", "enabled: false"))
    assert iter_enabled_instances(str(tmp_path)) == []


def test_empty_yaml_file(tmp_path):
    write_group_var(tmp_path, "vps-dev.yml", "# nur Kommentar\n")
    assert iter_enabled_instances(str(tmp_path)) == []


def test_main_cli_output(tmp_path, capsys):
    """CLI-Format: eine Zeile 'name|target' je Instanz (Workflow-06-Contract)."""
    write_group_var(tmp_path, "vps-dev.yml", VPS_DEV)
    rc = main([str(tmp_path), DEFAULT_GLOB])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.splitlines() == ["oc1|dev", "oc2|dev"]


def test_main_cli_without_args_uses_default_glob(tmp_path, monkeypatch, capsys):
    """Default-Glob 'ansible/group_vars/vps-*.yml' relativ zum root."""
    write_group_var(tmp_path, "vps-prod.yml", VPS_PROD)
    monkeypatch.chdir(tmp_path)
    rc = main([])
    assert rc == 0
    assert capsys.readouterr().out.splitlines() == ["oc1|prod"]
