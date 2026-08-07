"""Tests fuer den Reject-Modus v3.2 (Diagnose-Folgeauftrag 2026-08-07).

Abgedeckt:
  - TestBuildRejectRemoteCmd: REJECT-BEGIN/END/FAILED-Marker, Kommando
    `openclaw devices reject <ID>`, KEINE APPROVE-Marker, FOUND-Marker,
    B2-Semantik (kein `|| true` um den Reject), Device-only-Hard-Gate
    (telegram/both → ValueError), ID-Format-Sperre unveraendert
  - TestParseRejectOutput: rejected (REJECT-Marker + FOUND=1), FAILED-Marker,
    Marker-Isolation (Reject-Output wird vom Approve-Parser nicht als Aktion
    gelesen und umgekehrt), not_found → None, fail-safe bei Instanz-Down
  - TestRunDiscoveryReject: Ein-Job-Reject (Remote-Cmd enthaelt devices reject,
    Ergebnis action="reject"), approve-Regression
  - TestRejectCli: --reject-only-Flag-Konflikte (--list-only/--discover-only),
    device-only-Validierung (Telegram-Code → Exit 2), lokaler Reject-Flow
    (status "rejected"), not_found lokal → Exit 0 (gruen)
  - TestRejectSummary: status_header/status_label fuer "rejected"
"""

import json
import os
import sys
from importlib.machinery import SourceFileLoader

import pytest

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "device-approve")
sys.path.insert(0, os.path.abspath(TOOLS_DIR))

discovery = SourceFileLoader(
    "device_approve.discovery",
    os.path.join(TOOLS_DIR, "discovery.py"),
).load_module()

import approve  # noqa: E402
import summary  # noqa: E402

# Test-IDs (kalibriert an realen IDs, 2026-08-06/07)
TG_CODE = "QVDCXJEM"
DEVICE_UUID = "b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5"
REAL_REQUEST_ID = "21e6459c-7323-43aa-bdb0-a3105e9d8255"  # Diagnose-Request oc2 (prod)

MAP_PROD = [("oc1", "prod"), ("oc2", "prod")]


def devices_json(device_id, pending=None):
    entries = pending if pending is not None else [
        {"deviceId": device_id, "publicKey": "abc", "platform": "Win32",
         "clientId": "openclaw-control-ui", "createdAtMs": 1785915850624},
    ]
    return json.dumps({"pending": entries, "paired": []})


def realistic_devices_json():
    """v3.3.1: ECHTE pending[]-Struktur (e2e-Beleg aee3a00/Run 31156554728):
    deviceId = 64er-PublicKey-Hash, requestId = UUID-36 (die reject-ID)."""
    return json.dumps({"pending": [
        {"deviceId": "9df47d697653fb4069407734e06849b342738ed3e9ec4b172402aca911925392",
         "requestId": REAL_REQUEST_ID, "publicKey": "abc", "platform": "Win32"},
    ], "paired": []})


def json_block(instance, typ, body):
    return f"---JSON-BEGIN:{instance}:{typ}---\n{body}\n---JSON-END:{instance}:{typ}---\n"


def reject_block(instance, typ, output="Request rejected."):
    return f"---REJECT-BEGIN:{instance}:{typ}---\n{output}\n---REJECT-END:{instance}:{typ}---\n"


def reject_stdout(instance, typ, body, *, rejected=True, found=1, output="Request rejected."):
    out = json_block(instance, typ, body)
    if rejected:
        out += reject_block(instance, typ, output)
    out += f"---FOUND:{found}---\n"
    return out


# ── build_ein_job_remote_cmd(action="reject") ──

class TestBuildRejectRemoteCmd:
    def test_device_template_reject_markers(self):
        cmd = discovery.build_ein_job_remote_cmd(
            "device", ["oc1", "oc2"], REAL_REQUEST_ID, action="reject"
        )
        assert "for inst in oc1 oc2; do" in cmd
        assert "openclaw devices list --json" in cmd
        assert f"openclaw devices reject {REAL_REQUEST_ID}" in cmd
        assert "---JSON-BEGIN:${inst}:device---" in cmd
        assert "---REJECT-BEGIN:${inst}:device---" in cmd
        assert "---REJECT-END:${inst}:device---" in cmd
        assert "---REJECT-FAILED:${inst}:device---" in cmd  # B2: Fehler sichtbar
        assert "---FOUND:${FOUND}---" in cmd
        assert "|| true" in cmd          # fail-safe NUR fuer die Discovery-Quelle
        assert "break" in cmd            # Break-Semantik (erster Fund stoppt)
        assert "jq" not in cmd           # R08: keine jq-Dependency

    def test_no_approve_in_reject_cmd(self):
        """Reject-Modus enthaelt NIE Approve-Kommandos/-Marker (Hard-Gate)."""
        cmd = discovery.build_ein_job_remote_cmd("device", ["oc1"], DEVICE_UUID, action="reject")
        assert "approve" not in cmd
        assert "---APPROVE" not in cmd
        assert "pairing" not in cmd

    def test_reject_exit_code_checked_no_or_true(self):
        """B2-Semantik: KEIN `|| true` um den Reject; FOUND=1 erst nach
        Exit-Code 0; REJECT-FAILED-Marker bei Fehler."""
        cmd = discovery.build_ein_job_remote_cmd("device", ["oc1"], DEVICE_UUID, action="reject")
        reject_line = f"sudo docker exec openclaw-${{inst}} openclaw devices reject {DEVICE_UUID} 2>&1"
        assert f"{reject_line} || true" not in cmd
        assert f"if {reject_line}; then" in cmd
        assert "FOUND=1" in cmd
        assert "---REJECT-FAILED:${inst}:device---" in cmd
        assert cmd.index("if sudo docker exec") < cmd.index("FOUND=1")

    def test_device_only_hard_gate(self):
        """v3.2: Reject nur fuer device-Requests – die openclaw CLI hat kein
        'pairing reject' (empirisch 2026-08-07)."""
        with pytest.raises(ValueError, match="nur device-Requests"):
            discovery.build_ein_job_remote_cmd("telegram", ["oc1"], TG_CODE, action="reject")
        with pytest.raises(ValueError, match="nur device-Requests"):
            discovery.build_ein_job_remote_cmd("both", ["oc1"], DEVICE_UUID, action="reject")

    def test_unknown_action_rejected(self):
        with pytest.raises(ValueError, match="Unbekannte Aktion"):
            discovery.build_ein_job_remote_cmd("device", ["oc1"], DEVICE_UUID, action="foobar")

    def test_invalid_request_id_still_rejected(self):
        """ID-Format-Sperre unveraendert (v3.2): Injection-Versuch → ValueError."""
        with pytest.raises(ValueError):
            discovery.build_ein_job_remote_cmd("device", ["oc1"], "bad$id", action="reject")

    def test_invalid_instance_rejected(self):
        with pytest.raises(ValueError, match="Ungueltige"):
            discovery.build_ein_job_remote_cmd("device", ["oc0"], DEVICE_UUID, action="reject")

    def test_approve_default_unchanged(self):
        """Default action="approve" – bestehendes Verhalten unveraendert."""
        cmd = discovery.build_ein_job_remote_cmd("device", ["oc1"], DEVICE_UUID)
        assert "---APPROVE-BEGIN:${inst}:device---" in cmd
        assert "---REJECT" not in cmd


# ── parse_ein_job_output(action="reject") ──

class TestParseRejectOutput:
    def test_find_and_reject(self):
        stdout = reject_stdout("oc2", "device", devices_json(REAL_REQUEST_ID))
        result = discovery.parse_ein_job_output(
            stdout, "device", request_id=REAL_REQUEST_ID, target="prod", action="reject"
        )
        assert result is not None
        assert result.request_id == REAL_REQUEST_ID
        assert result.instance == "oc2"
        assert result.target == "prod"
        assert result.found_type == "device"
        assert result.action == "reject"
        assert result.approved is True  # historischer Feldname = Aktion ok
        assert "Request rejected." in result.approve_output

    def test_reject_by_request_id_uuid36_realistic_structure(self):
        """v3.3.1 (Owner-Kritik 09:31): Reject per UUID-36 (requestId) über den
        Workflow-Match-Pfad mit ECHTER pending[]-Struktur (deviceId=64er-Hash
        + requestId=UUID-36) → rejected (approved=True). Vorher: not_found."""
        stdout = reject_stdout("oc2", "device", realistic_devices_json())
        result = discovery.parse_ein_job_output(
            stdout, "device", request_id=REAL_REQUEST_ID, target="prod", action="reject"
        )
        assert result is not None
        assert result.found_type == "device"
        assert result.request_id == REAL_REQUEST_ID
        assert result.approved is True
        assert result.action == "reject"

    def test_reject_failure_detected(self):
        """B2: Reject-Exit-Code != 0 → REJECT-FAILED-Marker + FOUND=0 →
        approved=False, Fehler-Output bleibt sichtbar."""
        stdout = (
            json_block("oc1", "device", devices_json(DEVICE_UUID))
            + "---REJECT-BEGIN:oc1:device---\n"
            + "ERROR: request not found\n"
            + "---REJECT-END:oc1:device---\n"
            + "---REJECT-FAILED:oc1:device---\n"
            + "---FOUND:0---\n"
        )
        result = discovery.parse_ein_job_output(
            stdout, "device", request_id=DEVICE_UUID, target="prod", action="reject"
        )
        assert result is not None
        assert result.approved is False
        assert "ERROR: request not found" in result.approve_output

    def test_reject_failed_marker_forces_not_rejected(self):
        """Auch bei inkonsistentem FOUND=1: REJECT-FAILED-Marker → approved=False."""
        stdout = (
            json_block("oc1", "device", devices_json(DEVICE_UUID))
            + "---REJECT-BEGIN:oc1:device---\nboom\n---REJECT-END:oc1:device---\n"
            + "---REJECT-FAILED:oc1:device---\n"
            + "---FOUND:1---\n"
        )
        result = discovery.parse_ein_job_output(
            stdout, "device", request_id=DEVICE_UUID, target="prod", action="reject"
        )
        assert result is not None
        assert result.approved is False

    def test_marker_isolation_reject_output_invisible_to_approve_parser(self):
        """Reject-Output + approve-Parser: Fund, aber approved=False (kein
        APPROVE-Marker) – kein falscher Approve-Erfolg."""
        stdout = reject_stdout("oc2", "device", devices_json(REAL_REQUEST_ID))
        result = discovery.parse_ein_job_output(
            stdout, "device", request_id=REAL_REQUEST_ID, target="prod"
        )
        assert result is not None
        assert result.approved is False
        assert result.action == "approve"

    def test_marker_isolation_approve_output_invisible_to_reject_parser(self):
        stdout = (
            json_block("oc1", "device", devices_json(DEVICE_UUID))
            + "---APPROVE-BEGIN:oc1:device---\nok\n---APPROVE-END:oc1:device---\n"
            + "---FOUND:1---\n"
        )
        result = discovery.parse_ein_job_output(
            stdout, "device", request_id=DEVICE_UUID, target="prod", action="reject"
        )
        assert result is not None
        assert result.approved is False
        assert result.action == "reject"

    def test_no_find_returns_none(self):
        stdout = reject_stdout(
            "oc1", "device", json.dumps({"pending": [], "paired": []}), found=0
        )
        assert discovery.parse_ein_job_output(
            stdout, "device", request_id=DEVICE_UUID, target="prod", action="reject"
        ) is None

    def test_instance_down_fail_safe(self):
        stdout = "---JSON-BEGIN:oc1:device---\n\n---JSON-END:oc1:device---\n---FOUND:0---\n"
        assert discovery.parse_ein_job_output(
            stdout, "device", request_id=DEVICE_UUID, target="prod", action="reject"
        ) is None

    def test_device_pending_only_matched(self):
        """Nur pending-Eintraege matchen (paired bleibt unberuehrt)."""
        stdout = reject_stdout(
            "oc1", "device",
            json.dumps({"pending": [], "paired": [{"deviceId": DEVICE_UUID}]}),
            found=0,
        )
        assert discovery.parse_ein_job_output(
            stdout, "device", request_id=DEVICE_UUID, target="prod", action="reject"
        ) is None


# ── run_discovery(action="reject") ──

class TestRunDiscoveryReject:
    def test_ein_job_reject(self):
        """1 SSH pro VPS; Remote-Cmd enthaelt `devices reject`; Ergebnis
        action="reject" + approved=True."""
        seen = []

        def run_remote(ip, remote_cmd):
            seen.append(remote_cmd)
            return reject_stdout("oc2", "device", devices_json(REAL_REQUEST_ID))

        result = discovery.run_discovery(
            MAP_PROD, REAL_REQUEST_ID, derived_type="device",
            resolve_ip=lambda node: "100.64.0.2",
            run_remote=run_remote,
            action="reject",
        )
        assert result.target == "prod"
        assert result.instance == "oc2"
        assert result.approved is True
        assert result.action == "reject"
        assert "openclaw devices reject" in seen[0]
        assert "---REJECT-BEGIN" in seen[0]

    def test_ein_job_reject_by_request_id_uuid36_realistic(self):
        """v3.3.1 (Owner-Kritik 09:31): Reject per UUID-36 (requestId) ueber den
        vollen run_discovery-Workflow-Pfad mit ECHTER pending[]-Struktur
        (deviceId=64er-Hash + requestId=UUID-36) → rejected (approved=True)."""
        seen = []

        def run_remote(ip, remote_cmd):
            seen.append(remote_cmd)
            return reject_stdout("oc2", "device", realistic_devices_json())

        result = discovery.run_discovery(
            MAP_PROD, REAL_REQUEST_ID, derived_type="device",
            resolve_ip=lambda node: "100.64.0.2",
            run_remote=run_remote,
            action="reject",
        )
        assert result.target == "prod"
        assert result.instance == "oc2"
        assert result.found_type == "device"
        assert result.approved is True
        assert result.action == "reject"
        # Remote-Grep enthaelt die (requestId|deviceId)-Alternation
        assert '(requestId|deviceId)' in seen[0]

    def test_approve_regression(self):
        """Default-Aktion approve bleibt unveraendert (action="approve")."""
        def run_remote(ip, remote_cmd):
            return (
                json_block("oc1", "device", devices_json(DEVICE_UUID))
                + "---APPROVE-BEGIN:oc1:device---\nok\n---APPROVE-END:oc1:device---\n"
                + "---FOUND:1---\n"
            )

        result = discovery.run_discovery(
            MAP_PROD, DEVICE_UUID, derived_type="device",
            resolve_ip=lambda node: "100.64.0.2",
            run_remote=run_remote,
        )
        assert result.approved is True
        assert result.action == "approve"

    def test_not_found_raises(self):
        with pytest.raises(discovery.RequestNotFoundError):
            discovery.run_discovery(
                MAP_PROD, DEVICE_UUID, derived_type="device",
                resolve_ip=lambda node: "100.64.0.2",
                run_remote=lambda ip, cmd: reject_stdout(
                    "oc1", "device",
                    json.dumps({"pending": [], "paired": []}), found=0,
                ),
                action="reject",
            )


# ── CLI: --reject-only (approve.py main) ──

class TestRejectCli:
    def test_reject_only_conflicts_with_list_only(self):
        with pytest.raises(SystemExit) as exc:
            approve.main(["--reject-only", "--list-only", "--local"])
        assert exc.value.code == 2

    def test_reject_only_conflicts_with_discover_only(self):
        with pytest.raises(SystemExit) as exc:
            approve.main(["--reject-only", "--discover-only", "--local"])
        assert exc.value.code == 2

    def test_reject_only_allowed_with_full_run(self):
        """--full-run --reject-only = Ein-Job-Reject (Workflow mode=reject)."""
        # ohne Credentials → Exit 2 (Config) statt argparse-Fehler
        rc = approve.main(["--reject-only", "--full-run", "--request-id", DEVICE_UUID])
        assert rc == 2

    def test_telegram_id_rejected_exit_2(self):
        """v3.2: Reject nur device – Telegram-Kurzcode → Exit 2 (Fail-Fast)."""
        rc = approve.main(["--reject-only", "--local", "--request-id", TG_CODE])
        assert rc == 2

    def test_local_reject_flow(self, monkeypatch, capsys):
        """Lokaler Reject: devices list → Fund → `openclaw devices reject` →
        status "rejected", Exit 0."""
        pending = devices_json(REAL_REQUEST_ID)
        calls = []

        class FakeProc:
            def __init__(self, cmd):
                calls.append(cmd)
                self.returncode = 0
                if cmd[1] == "devices" and cmd[2] == "list":
                    self.stdout = pending
                else:
                    self.stdout = "Request rejected."
                self.stderr = ""

        monkeypatch.setattr(approve.subprocess, "run", lambda cmd, **kw: FakeProc(cmd))
        rc = approve.main(["--reject-only", "--local", "--request-id", REAL_REQUEST_ID])
        out = capsys.readouterr().out
        assert rc == 0
        assert '"status": "rejected"' in out
        assert any(c[1] == "devices" and c[2] == "reject" and c[3] == REAL_REQUEST_ID for c in calls)

    def test_local_reject_not_found_exit_0(self, monkeypatch, capsys):
        """not_found lokal → Exit 0 (gruen, Owner-Vereinbarung 15:06)."""
        calls = []

        class FakeProc:
            def __init__(self, cmd):
                calls.append(cmd)
                self.returncode = 0
                self.stdout = json.dumps({"pending": [], "paired": []})
                self.stderr = ""

        monkeypatch.setattr(approve.subprocess, "run", lambda cmd, **kw: FakeProc(cmd))
        rc = approve.main(["--reject-only", "--local", "--request-id", DEVICE_UUID])
        out = capsys.readouterr().out
        assert rc == 0
        assert '"status": "not_found"' in out
        assert not any("reject" in c for c in calls)  # kein Reject-Befehl

    def test_local_reject_failure_exit_1(self, monkeypatch, capsys):
        """Reject-Fehler (Exit != 0) → status "error", Exit 1."""
        pending = devices_json(DEVICE_UUID)
        calls = []

        class FakeProc:
            def __init__(self, cmd):
                calls.append(cmd)
                self.stderr = ""
                if cmd[1] == "devices" and cmd[2] == "list":
                    self.returncode = 0
                    self.stdout = pending
                else:
                    self.returncode = 1
                    self.stdout = ""
                    self.stderr = "boom"

        monkeypatch.setattr(approve.subprocess, "run", lambda cmd, **kw: FakeProc(cmd))
        rc = approve.main(["--reject-only", "--local", "--request-id", DEVICE_UUID])
        out = capsys.readouterr().out
        assert rc == 1
        assert '"status": "error"' in out


# ── summary.py: "rejected"-Status ──

class TestRejectSummary:
    def test_status_header_rejected(self):
        md = summary.status_header("rejected", {"found": [{"type": "device"}]})
        assert "Device-Reject" in md
        assert "✅" in md

    def test_result_to_markdown_rejected(self):
        md = summary.result_to_markdown({
            "status": "rejected",
            "id": DEVICE_UUID,
            "found": [{"target": "prod", "instance": "oc2", "type": "device", "vps_ip": "100.64.0.2"}],
            "scanned": ["prod/oc2"],
            "filters_applied": {"type": "device", "target": "prod", "instance": "all"},
        })
        assert "Abgelehnt" in md
        assert "prod/oc2" in md
