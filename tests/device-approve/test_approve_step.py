"""Tests fuer tools/device-approve/approve_step.py v3.0 (Library-Modul).

Abgedeckt: typ-spezifisches Approve-Kommando (telegram → pairing approve
telegram <CODE>, device → devices approve <ID>), ID/Instanz-Validierung
(defense in depth), subprocess-Erfolg/Fehler/Timeout, CLI-Wiring,
build_approve_result.

v3.0 (R03-E12): approve_step.py wird vom Workflow NICHT mehr aufgerufen
(Ein-Job-Design – Approve läuft in der SSH-Session, discovery.py
build_ein_job_remote_cmd). Dieses Modul bleibt als Library erhalten; die
Templates werden aus discovery.py re-exportiert (Single Source of Truth).
"""

import json
import os
import subprocess
import sys

import pytest

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "device-approve")
sys.path.insert(0, os.path.abspath(TOOLS_DIR))

import approve_step  # noqa: E402

TG_CODE = "QVDCXJEM"
DEVICE_ID = "b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5"


class TestBuildApproveCmd:
    def test_telegram_command(self):
        cmd = approve_step.build_approve_cmd("telegram", "oc1", TG_CODE)
        assert cmd == "sudo docker exec openclaw-oc1 openclaw pairing approve telegram QVDCXJEM"

    def test_device_command(self):
        cmd = approve_step.build_approve_cmd("device", "oc2", DEVICE_ID)
        assert cmd == f"sudo docker exec openclaw-oc2 openclaw devices approve {DEVICE_ID}"

    def test_device_cmd_does_not_contain_pairing(self):
        cmd = approve_step.build_approve_cmd("device", "oc1", DEVICE_ID)
        assert "pairing" not in cmd

    def test_telegram_rejects_device_id(self):
        """Device-ID im telegram-Kontext → ValueError (Format-Sperre)."""
        with pytest.raises(ValueError, match="Telegram-Kurzcode"):
            approve_step.build_approve_cmd("telegram", "oc1", DEVICE_ID)

    def test_device_rejects_short_code(self):
        """Kurzcode im device-Kontext → ValueError (Format-Sperre)."""
        with pytest.raises(ValueError, match="Device-ID-Format"):
            approve_step.build_approve_cmd("device", "oc1", TG_CODE)

    def test_unknown_type_rejected(self):
        with pytest.raises(ValueError, match="Unbekannter Typ"):
            approve_step.build_approve_cmd("foobar", "oc1", DEVICE_ID)

    def test_invalid_instance_rejected(self):
        with pytest.raises(ValueError, match="Ungueltige"):
            approve_step.build_approve_cmd("device", "oc0", DEVICE_ID)


class TestValidateAndBuildCmd:
    def test_command_is_list_no_shell(self):
        """Aufruf ohne Shell, Argument-Liste (subprocess.run sicher)."""
        cmd = approve_step.validate_and_build_cmd(
            "telegram", "oc1", "100.64.0.1", "deploy", "/tmp/key", TG_CODE,
        )
        assert isinstance(cmd, list)
        assert "&&" not in " ".join(cmd)
        assert ";" not in " ".join(cmd)  # kein Shell-Zugriff
        assert "ssh" in cmd
        assert any("100.64.0.1" in str(c) for c in cmd)
        assert "openclaw-oc1" in " ".join(cmd)
        assert TG_CODE in " ".join(cmd)
        assert "pairing approve telegram" in " ".join(cmd)

    def test_device_command_list(self):
        cmd = approve_step.validate_and_build_cmd(
            "device", "oc2", "100.64.0.2", "deploy", "/tmp/key", DEVICE_ID,
        )
        assert "devices approve" in " ".join(cmd)
        assert DEVICE_ID in " ".join(cmd)

    def test_invalid_request_id_rejected(self):
        with pytest.raises(ValueError, match="Device-ID-Format|Ungueltige|passt zu keinem"):
            approve_step.validate_and_build_cmd(
                "device", "oc1", "100.64.0.1", "deploy", "/tmp/key", "bad$id",
            )

    def test_invalid_instance_rejected(self):
        with pytest.raises(ValueError, match="Ungueltige"):
            approve_step.validate_and_build_cmd(
                "device", "oc0", "100.64.0.1", "deploy", "/tmp/key", DEVICE_ID,
            )

    def test_valid_instance_oc99(self):
        """oc99 ist gueltig (Minor #4)."""
        cmd = approve_step.validate_and_build_cmd(
            "device", "oc99", "100.64.0.1", "deploy", "/tmp/key", DEVICE_ID,
        )
        assert "openclaw-oc99" in " ".join(cmd)


class FakeCompletedProcess:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestRunApproveSsh:
    def test_success_telegram(self):
        proc = approve_step.run_approve_ssh(
            "telegram", "oc1", "100.64.0.1", "deploy", "/tmp/key", TG_CODE,
            runner=lambda cmd, capture_output, text, timeout: FakeCompletedProcess(0),
        )
        assert proc.returncode == 0

    def test_success_device(self):
        proc = approve_step.run_approve_ssh(
            "device", "oc1", "100.64.0.1", "deploy", "/tmp/key", DEVICE_ID,
            runner=lambda cmd, capture_output, text, timeout: FakeCompletedProcess(0),
        )
        assert proc.returncode == 0

    def test_failure(self):
        proc = approve_step.run_approve_ssh(
            "device", "oc1", "100.64.0.1", "deploy", "/tmp/key", DEVICE_ID,
            runner=lambda cmd, capture_output, text, timeout: FakeCompletedProcess(1, stderr="error"),
        )
        assert proc.returncode == 1

    def test_timeout_propagated(self):
        def _timeout_runner(cmd, capture_output, text, timeout):
            raise subprocess.TimeoutExpired(cmd="ssh", timeout=timeout)

        with pytest.raises(subprocess.TimeoutExpired):
            approve_step.run_approve_ssh(
                "device", "oc1", "100.64.0.1", "deploy", "/tmp/key", DEVICE_ID,
                runner=_timeout_runner, timeout=5,
            )

    def test_invalid_id_raises_valueerror(self):
        with pytest.raises(ValueError):
            approve_step.run_approve_ssh(
                "device", "oc1", "100.64.0.1", "deploy", "/tmp/key", ";inject",
            )

    def test_telegram_id_in_device_context_raises(self):
        with pytest.raises(ValueError):
            approve_step.run_approve_ssh(
                "device", "oc1", "100.64.0.1", "deploy", "/tmp/key", TG_CODE,
            )


class TestBuildApproveResult:
    def test_approved_telegram(self):
        r = approve_step.build_approve_result(
            "approved", TG_CODE, target="dev", instance="oc1",
            found_type="telegram", vps_ip="100.64.0.1",
        )
        assert r["status"] == "approved"
        assert r["found"][0]["target"] == "dev"
        assert r["found"][0]["instance"] == "oc1"
        assert r["found"][0]["type"] == "telegram"
        assert r["scanned"] == ["dev/oc1"]
        assert r["filters_applied"]["type"] == "telegram"

    def test_error(self):
        r = approve_step.build_approve_result("error", DEVICE_ID)
        assert r["status"] == "error"
        assert r["found"] == []


class TestCli:
    def test_cli_success_telegram(self, tmp_path, monkeypatch, capsys):
        result_file = tmp_path / "result.json"
        monkeypatch.setattr(
            approve_step, "run_approve_ssh",
            lambda **kw: FakeCompletedProcess(0),
        )
        rc = approve_step.main([
            "--found-type", "telegram",
            "--found-instance", "oc1",
            "--target", "dev",
            "--vps-ip", "100.64.0.1",
            "--vps-user", "deploy",
            "--ssh-key", "/tmp/key",
            "--request-id", TG_CODE,
            "--result-json", str(result_file),
        ])
        assert rc == 0
        stdout = capsys.readouterr().out
        data = json.loads(stdout)
        assert data["status"] == "approved"
        assert data["found"][0]["type"] == "telegram"
        assert result_file.exists()
        file_data = json.loads(result_file.read_text(encoding="utf-8"))
        assert file_data["status"] == "approved"

    def test_cli_success_device(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            approve_step, "run_approve_ssh",
            lambda **kw: FakeCompletedProcess(0),
        )
        rc = approve_step.main([
            "--found-type", "device",
            "--found-instance", "oc2",
            "--target", "prod",
            "--vps-ip", "100.64.0.2",
            "--vps-user", "deploy",
            "--ssh-key", "/tmp/key",
            "--request-id", DEVICE_ID,
        ])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "approved"
        assert data["found"][0]["type"] == "device"

    def test_cli_failure(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            approve_step, "run_approve_ssh",
            lambda **kw: FakeCompletedProcess(1, stderr="approve error"),
        )
        rc = approve_step.main([
            "--found-type", "device",
            "--found-instance", "oc1",
            "--target", "dev",
            "--vps-ip", "100.64.0.1",
            "--vps-user", "deploy",
            "--ssh-key", "/tmp/key",
            "--request-id", DEVICE_ID,
        ])
        assert rc == 1

    def test_cli_validation_error_exits_2(self, tmp_path, monkeypatch, capsys):
        """Ungueltige Instanz → exit 2."""
        rc = approve_step.main([
            "--found-type", "device",
            "--found-instance", "oc0",
            "--target", "dev",
            "--vps-ip", "100.64.0.1",
            "--vps-user", "deploy",
            "--ssh-key", "/tmp/key",
            "--request-id", DEVICE_ID,
        ])
        assert rc == 2

    def test_cli_type_mismatch_exits_2(self, tmp_path, monkeypatch, capsys):
        """Telegram-Code mit found-type=device → exit 2 (Format-Sperre)."""
        rc = approve_step.main([
            "--found-type", "device",
            "--found-instance", "oc1",
            "--target", "dev",
            "--vps-ip", "100.64.0.1",
            "--vps-user", "deploy",
            "--ssh-key", "/tmp/key",
            "--request-id", TG_CODE,
        ])
        assert rc == 2
