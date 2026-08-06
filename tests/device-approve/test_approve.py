"""Tests fuer tools/device-approve/approve.py – CLI-Fassade v2.2 (Design 05 v2.2, E3).

Abgedeckt: --discover-only (SSH + lokal), --summary (GITHUB_STEP_SUMMARY),
lokaler Modus (APPROVE_LOCAL=1, openclaw CLI), not_found-Pfad mit Test-IDs
(QVDCXJEM → pairing-Pfad; b0999c46-.../2e68bca9-... → device-Pfad; erwartet
not_found lokal), Typ-Ableitung (auto), Env-Var-Modus, Filter, Validierung.
"""

import json
import os
import subprocess
import sys

import pytest

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "device-approve")
sys.path.insert(0, os.path.abspath(TOOLS_DIR))

import approve  # noqa: E402

# DiscoveryResult ueber das approve-Modul (Kollisionsschutz: der bare Import
# "from discovery import ..." wuerde sys.modules["discovery"] mit dem v2-Modul
# belegen und die v1-Tests (test_discovery.py) brechen).
DiscoveryResult = approve.discovery.DiscoveryResult

# Test-IDs v2.2 (kalibriert an realen IDs, 2026-08-06)
TG_CODE = "QVDCXJEM"
DEVICE_HEX_64 = "9df47d697653fb4069407734e06849b342738ed3e9ec4b172402aca911925392"
REAL_ID = "b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5"
ALT_ID = "2e68bca9-4965-4e29-9a9d-d1a12644d644"


class FakeCompletedProcess:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def fake_devices_json(device_id):
    entry = {
        "deviceId": device_id,
        "publicKey": "abc",
        "platform": "Win32",
        "clientId": "openclaw-control-ui",
        "clientMode": "webchat",
        "role": "operator",
        "roles": ["operator"],
        "scopes": ["operator.admin"],
        "createdAtMs": 1785915850624,
    }
    return json.dumps({"pending": [entry], "paired": []})


def fake_pairing_json(code):
    return json.dumps({"channel": "telegram", "requests": [
        {"code": code, "userId": "7145674995", "channel": "telegram"},
    ]})


# ── Lokale Discovery (Δ1: getrennte Quellen) ──

class TestLocalDiscovery:
    def test_telegram_uses_pairing_path(self):
        """QVDCXJEM → openclaw pairing list telegram --json."""
        seen_cmds = []

        def runner(cmd, capture_output, text, timeout):
            seen_cmds.append(cmd)
            assert cmd[0] == "openclaw"
            assert cmd[1:3] == ["pairing", "list"]
            return FakeCompletedProcess(0, stdout=fake_pairing_json(TG_CODE))

        result, _ = approve.run_local_discovery(TG_CODE, "telegram", runner=runner)
        assert result is not None
        assert result.found_type == "telegram"
        assert result.instance == "local"

    def test_telegram_not_found_when_requests_empty(self):
        """pairing list mit leeren requests → not_found (F10-belegt, Sandbox)."""
        result, stats = approve.run_local_discovery(
            TG_CODE, "telegram",
            runner=lambda cmd, capture_output, text, timeout: FakeCompletedProcess(
                0, stdout=json.dumps({"channel": "telegram", "requests": []})
            ),
        )
        assert result is None
        assert stats["scanned"] == ["local/local"]

    def test_telegram_pairing_error_fail_safe(self):
        """pairing list ohne Kanal → rc!=0 → uebersprungen (F10 fail-safe)."""
        result, _ = approve.run_local_discovery(
            TG_CODE, "telegram",
            runner=lambda cmd, capture_output, text, timeout: FakeCompletedProcess(1, stderr="no channel"),
        )
        assert result is None

    def test_device_uses_devices_path(self):
        seen_cmds = []

        def runner(cmd, capture_output, text, timeout):
            seen_cmds.append(cmd)
            assert cmd[1:3] == ["devices", "list"]
            return FakeCompletedProcess(0, stdout=fake_devices_json(REAL_ID))

        result, _ = approve.run_local_discovery(REAL_ID, "device", runner=runner)
        assert result is not None
        assert result.found_type == "device"

    def test_both_scans_pairing_then_devices(self):
        seq = []

        def runner(cmd, capture_output, text, timeout):
            seq.append(cmd[1])
            if cmd[1] == "pairing":
                return FakeCompletedProcess(0, stdout=json.dumps({"channel": "telegram", "requests": []}))
            return FakeCompletedProcess(0, stdout=fake_devices_json(DEVICE_HEX_64))

        result, _ = approve.run_local_discovery(DEVICE_HEX_64, "both", runner=runner)
        assert result is not None
        assert result.found_type == "device"
        assert seq == ["pairing", "devices"]

    def test_alt_id_not_found_locally(self):
        """Test-ID 2e68bca9... → device-Pfad, keine pending → not_found."""
        result, _ = approve.run_local_discovery(
            ALT_ID, "device",
            runner=lambda cmd, capture_output, text, timeout: FakeCompletedProcess(
                0, stdout=json.dumps({"pending": [], "paired": []})
            ),
        )
        assert result is None

    def test_real_id_not_found_with_empty_pending(self):
        """Realfall: b0999c46... pending: [] → not_found."""
        result, _ = approve.run_local_discovery(
            REAL_ID, "device",
            runner=lambda cmd, capture_output, text, timeout: FakeCompletedProcess(
                0, stdout=json.dumps({"pending": [], "paired": []})
            ),
        )
        assert result is None

    def test_json_parse_error_returns_none(self):
        result, _ = approve.run_local_discovery(
            REAL_ID, "device",
            runner=lambda cmd, capture_output, text, timeout: FakeCompletedProcess(0, stdout="not json{{{"),
        )
        assert result is None

    def test_cli_not_found_returns_none(self):
        result, _ = approve.run_local_discovery(
            REAL_ID, "device",
            runner=lambda cmd, capture_output, text, timeout: FakeCompletedProcess(1, stdout=""),
        )
        assert result is None


# ── Lokaler Approve (Δ2: typ-spezifisches Kommando) ──

class TestLocalApprove:
    def test_telegram_command(self):
        seen = []

        def runner(cmd, capture_output, text, timeout):
            seen.append(cmd)
            return FakeCompletedProcess(0)

        rc = approve.run_local_approve(TG_CODE, "telegram", runner=runner)
        assert rc == 0
        assert seen[0] == ["openclaw", "pairing", "approve", "telegram", TG_CODE]

    def test_device_command(self):
        seen = []

        def runner(cmd, capture_output, text, timeout):
            seen.append(cmd)
            return FakeCompletedProcess(0)

        rc = approve.run_local_approve(REAL_ID, "device", runner=runner)
        assert rc == 0
        assert seen[0] == ["openclaw", "devices", "approve", REAL_ID]

    def test_failure(self):
        rc = approve.run_local_approve(REAL_ID, "device",
                                       runner=lambda cmd, capture_output, text, timeout: FakeCompletedProcess(1))
        assert rc == 1


# ── CLI --discover-only, --summary, --local ──

class TestApproveCli:
    def _write_map(self, tmp_path, entries):
        path = tmp_path / "instance-map.txt"
        path.write_text("\n".join(entries) + "\n", encoding="utf-8")
        return str(path)

    @pytest.fixture
    def local_env(self, monkeypatch):
        monkeypatch.setenv("APPROVE_LOCAL", "1")

    @pytest.fixture
    def ssh_env(self, monkeypatch):
        monkeypatch.setenv("APPROVE_ID", REAL_ID)
        monkeypatch.setenv("APPROVE_TYPE", "auto")
        monkeypatch.setenv("APPROVE_TARGET", "both")
        monkeypatch.setenv("APPROVE_INSTANCE", "all")
        monkeypatch.setenv("VPS_USER", "deploy")
        monkeypatch.setenv("SSH_KEY_PATH", "/tmp/key")
        monkeypatch.setenv("TS_TAILNET", "tailcfea8a.ts.net")
        monkeypatch.setenv("TS_CLIENT_ID", "cid")
        monkeypatch.setenv("TS_CLIENT_SECRET", "csec")

    # ── Local Mode ──

    def test_local_discover_only_not_found_telegram_code(self, monkeypatch, capsys, local_env):
        """QVDCXJEM --local --discover-only → not_found (pairing-Pfad)."""
        monkeypatch.setenv("APPROVE_ID", TG_CODE)
        monkeypatch.setattr(
            approve, "run_local_discovery",
            lambda request_id, derived_type, runner=None, log=None, timeout=15: (
                None, {"scanned": ["local/local"], "unreachable": []}
            ),
        )
        rc = approve.main(["--local", "--discover-only"])
        stdout = capsys.readouterr().out
        data = json.loads(stdout)
        assert data["status"] == "not_found"
        assert data["id"] == TG_CODE
        assert data["filters_applied"]["type"] == "telegram"
        assert rc == 1

    def test_local_discover_only_found_device(self, monkeypatch, capsys, local_env):
        monkeypatch.setenv("APPROVE_ID", REAL_ID)
        fake_result = DiscoveryResult(
            request_id=REAL_ID, instance="local", target="local",
            vps_ip=None, found_type="device",
            scanned=["local/local"], unreachable=[],
        )
        monkeypatch.setattr(
            approve, "run_local_discovery",
            lambda request_id, derived_type, runner=None, log=None, timeout=15: (fake_result, {"scanned": ["local/local"], "unreachable": []}),
        )
        rc = approve.main(["--local", "--discover-only"])
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "found"
        assert data["found"][0]["type"] == "device"
        assert rc == 0

    def test_local_full_approve_success_telegram(self, monkeypatch, capsys, local_env):
        """Vollausfuehrung: typ-spezifischer lokaler Approve."""
        monkeypatch.setenv("APPROVE_ID", TG_CODE)
        fake_result = DiscoveryResult(
            request_id=TG_CODE, instance="local", target="local",
            vps_ip=None, found_type="telegram",
            scanned=["local/local"], unreachable=[],
        )
        monkeypatch.setattr(approve, "run_local_discovery", lambda request_id, derived_type, runner=None, log=None, timeout=15: (fake_result, {"scanned": ["local/local"], "unreachable": []}))
        seen = []
        monkeypatch.setattr(approve, "run_local_approve",
                            lambda rid, found_type, runner=None, timeout=15: (seen.append((rid, found_type)) or 0))
        rc = approve.main(["--local"])
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "approved"
        assert data["found"][0]["type"] == "telegram"
        assert seen == [(TG_CODE, "telegram")]
        assert rc == 0

    def test_local_summary_writes_markdown(self, tmp_path, monkeypatch, capsys, local_env):
        """--summary --local: Markdown nach $GITHUB_STEP_SUMMARY (File-Open)."""
        sm = tmp_path / "summary.md"
        monkeypatch.setenv("APPROVE_ID", REAL_ID)
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(sm))
        monkeypatch.setattr(
            approve, "run_local_discovery",
            lambda request_id, derived_type, runner=None, log=None, timeout=15: (None, {"scanned": ["local/local"], "unreachable": []}),
        )
        approve.main(["--local", "--discover-only", "--summary"])
        content = sm.read_text(encoding="utf-8")
        assert REAL_ID in content
        assert "Device-Freigabe" in content
        assert "local/local" in content

    def test_local_summary_telegram_header(self, tmp_path, monkeypatch, capsys, local_env):
        """not_found ohne Fund → Header bleibt 'Device-Freigabe' (Fallback)."""
        sm = tmp_path / "summary.md"
        monkeypatch.setenv("APPROVE_ID", TG_CODE)
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(sm))
        monkeypatch.setattr(
            approve, "run_local_discovery",
            lambda request_id, derived_type, runner=None, log=None, timeout=15: (None, {"scanned": ["local/local"], "unreachable": []}),
        )
        approve.main(["--local", "--discover-only", "--summary"])
        content = sm.read_text(encoding="utf-8")
        assert TG_CODE in content
        assert "Kein Treffer" in content

    def test_local_alt_id_not_found(self, monkeypatch, capsys, local_env):
        """Test-ID 2e68bca9 → not_found lokal (Beleg Testbarkeit)."""
        monkeypatch.setenv("APPROVE_ID", ALT_ID)
        monkeypatch.setattr(
            approve, "run_local_discovery",
            lambda request_id, derived_type, runner=None, log=None, timeout=15: (None, {"scanned": ["local/local"], "unreachable": []}),
        )
        rc = approve.main(["--local", "--discover-only"])
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "not_found"
        assert data["id"] == ALT_ID
        assert data["filters_applied"]["type"] == "device"
        assert rc == 1

    def test_local_real_id_not_found(self, monkeypatch, capsys, local_env):
        """Test-ID b0999c46... → not_found lokal (Beleg Testbarkeit)."""
        monkeypatch.setenv("APPROVE_ID", REAL_ID)
        monkeypatch.setattr(
            approve, "run_local_discovery",
            lambda request_id, derived_type, runner=None, log=None, timeout=15: (None, {"scanned": ["local/local"], "unreachable": []}),
        )
        rc = approve.main(["--local", "--discover-only"])
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "not_found"
        assert data["id"] == REAL_ID
        assert rc == 1

    # ── Validierung (v2.2: Zwei-Format) ──

    def test_missing_request_id_exits_2(self, monkeypatch, capsys):
        monkeypatch.delenv("APPROVE_ID", raising=False)
        rc = approve.main(["--local", "--discover-only"])
        assert rc == 2

    def test_invalid_id_exits_2(self, monkeypatch, capsys, local_env):
        monkeypatch.setenv("APPROVE_ID", "bad$$id")
        rc = approve.main(["--local", "--discover-only"])
        assert rc == 2

    def test_code_as_device_rejected(self, monkeypatch, capsys, local_env):
        """QVDCXJEM ist Telegram-Format; expliziter type=device → exit 2."""
        monkeypatch.setenv("APPROVE_ID", TG_CODE)
        monkeypatch.setenv("APPROVE_TYPE", "device")
        rc = approve.main(["--local", "--discover-only"])
        assert rc == 2
        assert "Device-ID-Format" in capsys.readouterr().err

    def test_invalid_type_exits_2(self, monkeypatch, capsys, local_env):
        monkeypatch.setenv("APPROVE_ID", REAL_ID)
        monkeypatch.setenv("APPROVE_TYPE", "foobar")
        rc = approve.main(["--local", "--discover-only"])
        assert rc == 2

    def test_invalid_instance_filter_exits_2(self, monkeypatch, capsys, local_env):
        monkeypatch.setenv("APPROVE_ID", REAL_ID)
        monkeypatch.setenv("APPROVE_INSTANCE", "oc0")
        rc = approve.main(["--local", "--discover-only"])
        assert rc == 2

    # ── Env-Var Mode (SSH) ──

    def test_ssh_mode_with_env_vars_discover_only(self, tmp_path, monkeypatch, capsys, ssh_env):
        """SSH-Config ueber Env-Vars, --discover-only, device-Pfad."""
        map_path = self._write_map(tmp_path, ["oc1|dev"])
        monkeypatch.setenv("INSTANCE_MAP", map_path)
        monkeypatch.setattr(approve, "fetch_tailscale_token", lambda cid, cs: "tok")
        monkeypatch.setattr(approve, "resolve_vps_ip",
                            lambda tailnet, tok, node, timeout=30: "100.64.0.1")
        monkeypatch.setattr(approve, "list_entries_ssh",
                            lambda inst, ip, user, key, typ: json.dumps({"pending": [], "paired": []}))
        rc = approve.main(["--discover-only"])
        assert rc == 1  # not_found
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "not_found"
        assert data["filters_applied"]["type"] == "device"

    def test_ssh_mode_found_discover_only(self, tmp_path, monkeypatch, capsys, ssh_env):
        map_path = self._write_map(tmp_path, ["oc1|dev"])
        monkeypatch.setenv("INSTANCE_MAP", map_path)
        monkeypatch.setattr(approve, "fetch_tailscale_token", lambda cid, cs: "tok")
        monkeypatch.setattr(approve, "resolve_vps_ip",
                            lambda tailnet, tok, node, timeout=30: "100.64.0.1")
        monkeypatch.setattr(approve, "list_entries_ssh",
                            lambda inst, ip, user, key, typ: fake_devices_json(REAL_ID))
        rc = approve.main(["--discover-only"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "found"
        assert data["found"][0]["type"] == "device"
        assert data["found"][0]["instance"] == "oc1"

    def test_ssh_mode_full_approve(self, tmp_path, monkeypatch, capsys, ssh_env):
        """Vollausfuehrung SSH: run_discovery-Fund → run_approve_ssh (typ-spezifisch)."""
        monkeypatch.setenv("APPROVE_ID", TG_CODE)  # Telegram-Kurzcode → pairing-Pfad
        map_path = self._write_map(tmp_path, ["oc1|dev"])
        monkeypatch.setenv("INSTANCE_MAP", map_path)
        monkeypatch.setattr(approve, "fetch_tailscale_token", lambda cid, cs: "tok")
        monkeypatch.setattr(approve, "resolve_vps_ip",
                            lambda tailnet, tok, node, timeout=30: "100.64.0.1")
        monkeypatch.setattr(approve, "list_entries_ssh",
                            lambda inst, ip, user, key, typ: fake_pairing_json(TG_CODE))
        seen = []
        monkeypatch.setattr(
            approve, "run_approve_ssh",
            lambda found_type, instance, vps_ip, vps_user, ssh_key, request_id, **kw: (
                seen.append((found_type, instance, request_id)) or FakeCompletedProcess(0)
            ),
        )
        rc = approve.main([])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "approved"
        assert data["found"][0]["type"] == "telegram"
        assert seen == [("telegram", "oc1", TG_CODE)]

    def test_ssh_mode_missing_config_exits_2(self, tmp_path, monkeypatch, capsys):
        """Ohne SSH-Config im SSH-Modus → exit 2."""
        map_path = self._write_map(tmp_path, ["oc1|dev"])
        monkeypatch.setenv("INSTANCE_MAP", map_path)
        monkeypatch.setenv("APPROVE_ID", REAL_ID)
        rc = approve.main(["--discover-only"])
        assert rc == 2

    def test_no_instances_after_filter_exits_2(self, tmp_path, monkeypatch, capsys, ssh_env):
        map_path = self._write_map(tmp_path, ["oc1|dev"])
        monkeypatch.setenv("INSTANCE_MAP", map_path)
        monkeypatch.setenv("APPROVE_TARGET", "prod")
        rc = approve.main(["--discover-only"])
        assert rc == 2
        assert "Keine Instanzen" in capsys.readouterr().err
