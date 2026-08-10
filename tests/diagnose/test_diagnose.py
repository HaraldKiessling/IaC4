"""Tests für tools/diagnose/diagnose.py – SSoT, Filter, Command-Builder (read-only).

Kein SSH/Tailscale in diesen Tests – nur reine Funktionen (Unit-Level).
"""
import json
import os
import re
import shlex
import subprocess
import sys

import pytest

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "diagnose")
sys.path.insert(0, os.path.abspath(TOOLS_DIR))
import diagnose  # noqa: E402
from context_metrics import compute_metrics  # noqa: E402


def _write_group_vars(root, path, env, instances):
    data = {"env": env, "openclaw_instances": instances}
    full = os.path.join(root, "ansible", "group_vars")
    os.makedirs(full, exist_ok=True)
    with open(os.path.join(full, path), "w", encoding="utf-8") as fh:
        json.dump(data, fh)


@pytest.fixture
def root(tmp_path):
    _write_group_vars(tmp_path, "vps-dev.yml", "dev", [
        {"name": "oc1", "enabled": True, "port": 18789},
        {"name": "oc2", "enabled": True, "port": 18790},
        {"name": "oc3", "enabled": True, "port": 18791},
    ])
    _write_group_vars(tmp_path, "vps-prod.yml", "prod", [
        {"name": "oc1", "enabled": True, "port": 18789},
        {"name": "oc2", "enabled": True, "port": 18790},
        {"name": "oc3", "enabled": False, "port": 18791},
    ])
    return str(tmp_path)


def test_load_instances_all_targets(root):
    insts = diagnose.load_instances(root, "both", "all")
    names = sorted(f"{i['target']}/{i['name']}" for i in insts)
    assert names == [
        "dev/oc1", "dev/oc2", "dev/oc3",
        "prod/oc1", "prod/oc2",
    ]  # prod/oc3 disabled -> ausgeschlossen


def test_load_instances_target_filter(root):
    insts = diagnose.load_instances(root, "dev", "all")
    assert [i["name"] for i in insts] == ["oc1", "oc2", "oc3"]
    assert all(i["target"] == "dev" for i in insts)


def test_load_instances_instance_filter(root):
    insts = diagnose.load_instances(root, "both", "oc1")
    assert sorted(f"{i['target']}/{i['name']}" for i in insts) == ["dev/oc1", "prod/oc1"]
    assert all(i["port"] == 18789 for i in insts)


def test_load_instances_disabled_excluded(root):
    insts = diagnose.load_instances(root, "prod", "oc3")
    assert insts == []  # prod/oc3 ist enabled: false


def test_validate_instance(monkeypatch):
    exits = []
    monkeypatch.setattr(diagnose.sys, "exit", lambda code: exits.append(code))
    diagnose.validate_instance("oc1")  # ok, kein Exit
    assert exits == []
    diagnose.validate_instance("all")  # ok
    assert exits == []
    diagnose.validate_instance("oc0")
    assert exits == [2]
    diagnose.validate_instance("oc2x")
    assert len(exits) == 2


def test_validate_mode(monkeypatch):
    exits = []
    monkeypatch.setattr(diagnose.sys, "exit", lambda code: exits.append(code))
    for m in ("health", "sessions", "context", "tokens", "all"):
        diagnose.validate_mode(m)
    assert exits == []
    diagnose.validate_mode("delete")
    assert exits == [2]


def test_build_health_cmds_read_only():
    cmds = diagnose.build_health_cmds("oc1", 18789)
    assert len(cmds) == 2
    for c in cmds:
        assert c.startswith("sudo docker exec openclaw-oc1 openclaw gateway ")
        assert "--json" in c


def test_ssh_host_joins_user_and_ip():
    """SSH-Ziel ist 'user@ip' (Regression: vorher nur nackte IP -> ssh fiel auf
    den Runner-Lokaluser 'runner' zurueck -> Permission denied, rc=255)."""
    assert diagnose.ssh_host("deploy-user", "100.64.0.1") == "deploy-user@100.64.0.1"
    assert diagnose.ssh_host("root", "100.64.0.2") == "root@100.64.0.2"
    assert "@" in diagnose.ssh_host("deploy-user", "100.64.0.1")


def test_default_vps_user_matches_inventory_sot():
    """Default --vps-user = deploy-user (SSoT: ansible_user in Inventaren)."""
    assert diagnose.DEFAULT_VPS_USER == "deploy-user"


def _run_main_health(monkeypatch, root, extra_args):
    """CLI-Durchlauf (Modus health) mit gemockter Tailscale-IP + run_ssh.
    Liefert (rc, liste_der_ssh_hosts)."""
    hosts = []
    monkeypatch.setattr(diagnose, "vps_ip", lambda *a, **k: "100.64.0.1")
    monkeypatch.setattr(
        diagnose, "run_ssh",
        lambda ssh, host, cmd, timeout=60: hosts.append(host) or (0, "{}", ""),
    )
    args = ["--mode", "health", "--target", "dev", "--instance", "oc1",
            "--ssh-key", "/tmp/id", "--ts-tailnet", "t", "--ts-client-id", "i",
            "--ts-client-secret", "s", "--repo-root", root] + extra_args
    rc = diagnose.main(args)
    return rc, hosts


def test_main_ssh_host_uses_vps_user(monkeypatch, root):
    """Regression: jede SSH-Invokation zielt auf 'user@ip' (expliziter User)."""
    rc, hosts = _run_main_health(monkeypatch, root, ["--vps-user", "deploy-user"])
    assert rc == 0
    assert hosts, "run_ssh wurde nicht aufgerufen"
    assert all(h == "deploy-user@100.64.0.1" for h in hosts)


def test_main_ssh_host_default_user(monkeypatch, root):
    """Regression: ohne --vps-user greift der Default deploy-user (SSoT)."""
    rc, hosts = _run_main_health(monkeypatch, root, [])
    assert rc == 0
    assert hosts
    assert all(h == "deploy-user@100.64.0.1" for h in hosts)


def test_main_rejects_empty_vps_user(monkeypatch, root):
    """Leerer --vps-user ist ein Config-Fehler (Exit 2, kein '@ip'-SSH)."""
    rc, hosts = _run_main_health(monkeypatch, root, ["--vps-user", ""])
    assert rc == 2
    assert hosts == []


def test_build_sessions_cmd_read_only():
    c = diagnose.build_sessions_cmd("oc2", 18790)
    assert c == "sudo docker exec openclaw-oc2 openclaw sessions --all-agents --json"


def test_build_usage_cmd_read_only():
    c = diagnose.build_usage_cmd("oc1", 18789, 7)
    assert "usage-cost --days 7 --all-agents --json" in c


def test_build_context_cmd_bounded_and_read_only():
    c = diagnose.build_context_cmd("oc1", 18789)
    assert c.startswith("sudo docker exec openclaw-oc1 sh -lc '")
    assert "find /home/node/.openclaw" in c
    assert "tail -c 300000" in c
    assert ".deleted" in c  # Archiv-Dateien ausgeschlossen


def test_build_context_cmd_shlc_quotes_balanced():
    """Regression: inneres Kommando enthaelt einfache Quotes ('*.jsonl',
    '*session*', '*.deleted.*', '==FILE== '), die das aeussere sh -lc-Wrapping
    NICHT vorzeitig terminieren duerfen. Vor dem Fix brach die Remote-Shell ab
    mit 'Syntax error: end of file unexpected (expecting \"done\")' (rc=2).

    Pruefungen:
      1) shlex.split der Gesamt-Kommandozeile -> sh -lc-Argument ist EIN Wort
      2) das innere Kommando ist selbst parsebar (sh -n, nur Syntax, kein Run)
      3) ==FILE==-Marker und find-Pattern bleiben erhalten (Semantik)
    """
    c = diagnose.build_context_cmd("oc1", 18789)
    # 1) Gesamtzeile als Shell-Wortliste: keine unbalancierten Quotes
    parts = shlex.split(c)
    assert parts[:6] == ["sudo", "docker", "exec", "openclaw-oc1", "sh", "-lc"]
    inner = parts[6]
    assert len(parts) == 7, "sh -lc-Argument muss ein einzelnes Shell-Wort sein"
    # 2) inneres Kommando syntaktisch valide (sh -n parst, fuehrt nicht aus)
    r = subprocess.run(["sh", "-n", "-c", inner], capture_output=True, text=True)
    assert r.returncode == 0, f"inneres Kommando nicht parsebar: {r.stderr}"
    # 3) Semantik unveraendert: Marker + Quoting-Pattern noch vorhanden
    assert "==FILE== " in inner
    assert "'*.jsonl'" in inner and "'*session*'" in inner
    assert "'*.deleted.*'" in inner
    assert "while read -r f; do" in inner and "done" in inner


def test_build_context_cmd_quote_roundtrip():
    """Round-trip: shlex.split(inner) liefert exakt die gewollten Tokens."""
    inner = shlex.split(diagnose.build_context_cmd("oc1", 18789))[6]
    tokens = shlex.split(inner)
    assert tokens[0:6] == ["find", "/home/node/.openclaw", "-name",
                           "*.jsonl", "-path", "*session*"]
    assert "==FILE== " in tokens  # echo-Argument mit Marker
    assert any(t.startswith("$f") for t in tokens)  # "$f"; -> '$f;' (posix-split)
    assert "done" == tokens[-1]


def test_all_remote_cmds_parse_with_sh_n():
    """Alle gebauten Remote-Kommandozeilen sind syntaktisch valide Shell
    (sh -n): deckt auch das docker_exec-Quoting-Haertung ab (gleiches Muster
    wie der sh -lc-Defekt)."""
    cmds = [
        *diagnose.build_health_cmds("oc1", 18789),
        diagnose.build_sessions_cmd("oc2", 18790),
        diagnose.build_usage_cmd("oc1", 18789, 7),
        diagnose.build_context_cmd("oc2", 18790),
    ]
    assert cmds
    for c in cmds:
        r = subprocess.run(["sh", "-n", "-c", c], capture_output=True, text=True)
        assert r.returncode == 0, f"Nicht parsebar: {c!r} -> {r.stderr}"


def test_commands_never_mutating():
    """Alle gebauten Remote-Kommandos sind read-only (Wort-Whitelist negativ)."""
    # Wort-Token nur als ganze Worte pruefen (\b), damit Ausnahmen wie die
    # Archiv-Ausschluss-Option '-not -name "*.deleted.*"' (read-only-Filter)
    # nicht faelschlich als Schreibzugriff gewertet werden. '2>/dev/null' ist
    # eine stderr-Unterdrueckung (kein File-Write) und daher kein Verstoss.
    forbidden_words = ("approve", "reject", "remove", "delete", "clean", "reset")
    forbidden_fragments = ("rm ", "tee ")
    cmds = [
        *diagnose.build_health_cmds("oc1", 18789),
        diagnose.build_sessions_cmd("oc1", 18789),
        diagnose.build_usage_cmd("oc1", 18789, 7),
        diagnose.build_context_cmd("oc1", 18789),
    ]
    for c in cmds:
        for f in forbidden_words:
            assert not re.search(rf"\b{f}\b", c), \
                f"Verbotenes Wort '{f}' in read-only-Kommando: {c}"
        for f in forbidden_fragments:
            assert f not in c, f"Verbotenes Fragment '{f}' in read-only-Kommando: {c}"


def test_parse_sessions_json():
    payload = json.dumps({
        "count": 2, "totalCount": 2, "limitApplied": 100, "hasMore": False,
        "sessions": [
            {"key": "agent:main:main", "agentId": "main", "model": "deepseek/deepseek-v4-flash"},
            {"key": "agent:engineer-pro:telegram:direct:1", "agentId": "engineer-pro",
             "model": "deepseek/deepseek-v4-flash"},
        ],
    })
    out = diagnose.parse_sessions(payload)
    assert out["count"] == 2
    assert out["sessions"][1]["key"] == "agent:engineer-pro:telegram:direct:1"


def test_parse_sessions_raw_fallback():
    out = diagnose.parse_sessions("kein json")
    assert out.get("unparsed") is True


def test_parse_context_markers():
    inner = (
        "==FILE== /home/node/.openclaw/agents/main/sessions/transcripts/x.jsonl\n"
        '{"type": "model", "usage": {"input_tokens": 10, "output_tokens": 5, '
        '"prompt_cache_hit_tokens": 8, "prompt_cache_miss_tokens": 2}}\n'
    )
    out = diagnose.parse_context(inner)
    assert out["files_found"] == 1
    agg = out["aggregated"]
    assert agg["input_tokens"] == 10
    assert agg["cache_hit_ratio"] == 0.8


def test_parse_context_empty():
    out = diagnose.parse_context("")
    assert out["files_found"] == 0
    assert out["aggregated"]["turns_with_usage"] == 0


def test_parse_json_or_raw():
    assert diagnose.parse_json_or_raw('{"a": 1}')["json"]["a"] == 1
    assert diagnose.parse_json_or_raw("nix")["raw"] == "nix"


def test_context_metrics_roundtrip_via_cli_module():
    """Integration: compute_metrics ueber das diagnose-Modul erreichbar."""
    m = compute_metrics('{"type": "model", "usage": {"input_tokens": 5}}')
    assert m["input_tokens"] == 5
