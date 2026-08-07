"""Tests fuer den Remove-Modus v3.5 (Owner-Auftrag 2026-08-07 12:14 „mode=remove
als Follow-up-Feature in Workflow 05“, Antwort „2 b“).

Abgedeckt:
  - TestBuildRemoveRemoteCmd: REMOVE-BEGIN/END/FAILED-Marker, Kommando
    `openclaw devices remove <ID>`, Array `paired` + ID-Feld `deviceId`
    (64-hex, NICHT requestId) im Remote-grep, KEINE APPROVE-/REJECT-Marker,
    FOUND-Marker, B2-Semantik (kein `|| true` um den Remove),
    Device-only-Hard-Gate (telegram/both → ValueError),
    ID-Format-Sperre unveraendert
  - TestParseRemoveOutput: removed (REMOVE-Marker + FOUND=1),
    FAILED-Marker, Marker-Isolation (Remove-Output wird vom Approve-/Reject-
    Parser nicht als Aktion gelesen und umgekehrt), not_found → None,
    fail-safe bei Instanz-Down, matched NUR paired[] (pending-Only → None)
  - TestRunDiscoveryRemove: Ein-Job-Remove (Remote-Cmd enthaelt devices
    remove, Ergebnis action="remove"), deviceId-Match ueber ECHTE paired[]-
    Struktur, approve-/reject-Regression
  - TestRemoveCli: --remove-only-Flag-Konflikte (--list-only/--discover-only/
    --reject-only), device-only-Validierung (Telegram-Code → Exit 2),
    lokaler Remove-Flow (status "removed"), not_found lokal → Exit 0 (gruen),
    Remove-Fehler → Exit 1
  - TestRemoveSummary: status_header/status_label fuer "removed"
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

# Test-IDs (kalibriert an realen IDs, 2026-08-07):
TG_CODE = "QVDCXJEM"
DEVICE_UUID = "b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5"
# Owner-Ziel-Geraet (Request 2daff7a2-d681-4151-836e-d01820bf699b, approved
# 2026-08-07 10:00 auf prod/oc1): deviceId = 64-hex Public-Key-Hash
TARGET_DEVICE_ID = "ea9b406af6e96b2f4dca0c76adc93466d06b52a6047c06cdef57bb25c8b1c653"
# Vorbestehendes Win32-control-ui-Geraet (paired, darf unveraendert bleiben)
PREEXISTING_DEVICE_ID = "9df47d697653fb4069407734e06849b342738ed3e9ec4b172402aca911925392"
REAL_REQUEST_ID = "21e6459c-7323-43aa-bdb0-a3105e9d8255"  # pending-requestId (UUID-36)

MAP_PROD = [("oc1", "prod"), ("oc2", "prod")]


def paired_json(device_id, extra=None):
    """ECHTE paired[]-Struktur (CLI-Fakt OpenClaw 2026.7.1): deviceId =
    64-hex, KEINE requestId; plus optionaler vorbestehender Eintrag."""
    entries = [{
        "deviceId": device_id,
        "publicKey": "abc",
        "platform": "Linux armv81",
        "clientId": "openclaw-control-ui",
        "role": "operator",
        "approvedAtMs": 1786096800000,
    }]
    if extra:
        entries.append(extra)
    return json.dumps({"pending": [], "paired": entries})


def pending_only_json(request_id, device_id):
    """pending[] mit requestId (UUID-36) – fuer remove IRRELEVANT (remove
    matcht nur paired[])."""
    return json.dumps({"pending": [
        {"deviceId": device_id, "requestId": request_id, "platform": "Win32"},
    ], "paired": []})


def json_block(instance, typ, body):
    return f"---JSON-BEGIN:{instance}:{typ}---\n{body}\n---JSON-END:{instance}:{typ}---\n"


def remove_block(instance, typ, output="Removed ea9b406a…"):
    return f"---REMOVE-BEGIN:{instance}:{typ}---\n{output}\n---REMOVE-END:{instance}:{typ}---\n"


def remove_stdout(instance, typ, body, *, removed=True, found=1, output="Removed ea9b406a…"):
    out = json_block(instance, typ, body)
    if removed:
        out += remove_block(instance, typ, output)
    out += f"---FOUND:{found}---\n"
    return out


# ── build_ein_job_remote_cmd(action="remove") ──

class TestBuildRemoveRemoteCmd:
    def test_device_template_remove_markers(self):
        cmd = discovery.build_ein_job_remote_cmd(
            "device", ["oc1", "oc2"], TARGET_DEVICE_ID, action="remove"
        )
        assert "for inst in oc1 oc2; do" in cmd
        assert "openclaw devices list --json" in cmd
        assert f"openclaw devices remove {TARGET_DEVICE_ID}" in cmd
        assert "---JSON-BEGIN:${inst}:device---" in cmd
        assert "---REMOVE-BEGIN:${inst}:device---" in cmd
        assert "---REMOVE-END:${inst}:device---" in cmd
        assert "---REMOVE-FAILED:${inst}:device---" in cmd  # B2: Fehler sichtbar
        assert "---FOUND:${FOUND}---" in cmd
        assert "|| true" in cmd          # fail-safe NUR fuer die Discovery-Quelle
        assert "break" in cmd            # Break-Semantik (erster Fund stoppt)
        assert "jq" not in cmd           # R08: keine jq-Dependency

    def test_remove_matches_paired_array_and_device_id(self):
        """v3.5-Kern: remove matcht Array `paired` + ID-Feld `deviceId`
        (64-hex) – NICHT pending/requestId (approve/reject-Semantik)."""
        cmd = discovery.build_ein_job_remote_cmd(
            "device", ["oc1"], TARGET_DEVICE_ID, action="remove"
        )
        # sed extrahiert das "paired"-Array (nicht "pending")
        assert '"paired"[[:space:]]*:[[:space:]]*\\[' in cmd
        assert '"pending"[[:space:]]*:[[:space:]]*\\[' not in cmd
        # grep matcht NUR "deviceId" – keine (requestId|deviceId)-Alternation
        # (Capture-Group-Klammern im grep-Muster: '(deviceId)').
        assert f'"(deviceId)"[[:space:]]*:[[:space:]]*"{TARGET_DEVICE_ID}"' in cmd
        assert "(requestId|deviceId)" not in cmd

    def test_no_approve_or_reject_in_remove_cmd(self):
        """Remove-Modus enthaelt NIE Approve-/Reject-Kommandos/-Marker."""
        cmd = discovery.build_ein_job_remote_cmd(
            "device", ["oc1"], TARGET_DEVICE_ID, action="remove"
        )
        assert "approve" not in cmd
        assert "reject" not in cmd
        assert "---APPROVE" not in cmd
        assert "---REJECT" not in cmd
        assert "pairing" not in cmd

    def test_remove_exit_code_checked_no_or_true(self):
        """B2-Semantik: KEIN `|| true` um den Remove; FOUND=1 erst nach
        Exit-Code 0; REMOVE-FAILED-Marker bei Fehler."""
        cmd = discovery.build_ein_job_remote_cmd(
            "device", ["oc1"], TARGET_DEVICE_ID, action="remove"
        )
        remove_line = f"sudo docker exec openclaw-${{inst}} openclaw devices remove {TARGET_DEVICE_ID} 2>&1"
        assert f"{remove_line} || true" not in cmd
        assert f"if {remove_line}; then" in cmd
        assert "FOUND=1" in cmd
        assert "---REMOVE-FAILED:${inst}:device---" in cmd
        assert cmd.index("if sudo docker exec") < cmd.index("FOUND=1")

    def test_device_only_hard_gate(self):
        """v3.5: Remove nur fuer device – die openclaw CLI hat kein
        'pairing remove' (empirisch 2026-08-07: `openclaw pairing` kennt nur
        approve|list|help)."""
        with pytest.raises(ValueError, match="nur device"):
            discovery.build_ein_job_remote_cmd("telegram", ["oc1"], TG_CODE, action="remove")
        with pytest.raises(ValueError, match="nur device"):
            discovery.build_ein_job_remote_cmd("both", ["oc1"], TARGET_DEVICE_ID, action="remove")

    def test_unknown_action_rejected(self):
        with pytest.raises(ValueError, match="Unbekannte Aktion"):
            discovery.build_ein_job_remote_cmd("device", ["oc1"], TARGET_DEVICE_ID, action="foobar")

    def test_invalid_request_id_still_rejected(self):
        """ID-Format-Sperre unveraendert (v3.5): Injection-Versuch → ValueError."""
        with pytest.raises(ValueError):
            discovery.build_ein_job_remote_cmd("device", ["oc1"], "bad$id", action="remove")

    def test_invalid_instance_rejected(self):
        with pytest.raises(ValueError, match="Ungueltige"):
            discovery.build_ein_job_remote_cmd("device", ["oc0"], TARGET_DEVICE_ID, action="remove")

    def test_approve_default_unchanged(self):
        """Default action="approve" – bestehendes Verhalten unveraendert."""
        cmd = discovery.build_ein_job_remote_cmd("device", ["oc1"], DEVICE_UUID)
        assert "---APPROVE-BEGIN:${inst}:device---" in cmd
        assert "---REMOVE" not in cmd
        assert "---REJECT" not in cmd

    def test_reject_still_device_only_and_unchanged(self):
        """Reject-Pfad unveraendert (v3.2): requestId-Match + REJECT-Marker."""
        cmd = discovery.build_ein_job_remote_cmd(
            "device", ["oc1"], REAL_REQUEST_ID, action="reject"
        )
        assert "openclaw devices reject" in cmd
        assert "(requestId|deviceId)" in cmd
        assert "---REJECT-BEGIN:${inst}:device---" in cmd


# ── parse_ein_job_output(action="remove") ──

class TestParseRemoveOutput:
    def test_find_and_remove(self):
        stdout = remove_stdout("oc1", "device", paired_json(TARGET_DEVICE_ID))
        result = discovery.parse_ein_job_output(
            stdout, "device", request_id=TARGET_DEVICE_ID, target="prod", action="remove"
        )
        assert result is not None
        assert result.request_id == TARGET_DEVICE_ID
        assert result.instance == "oc1"
        assert result.target == "prod"
        assert result.found_type == "device"
        assert result.action == "remove"
        assert result.approved is True  # historischer Feldname = Aktion ok
        assert "Removed ea9b406a…" in result.approve_output

    def test_remove_by_device_id_64hex_realistic(self):
        """Remove per 64-hex deviceId ueber ECHTE paired[]-Struktur (keine
        requestId im Eintrag) → removed (approved=True)."""
        stdout = remove_stdout("oc1", "device", paired_json(TARGET_DEVICE_ID))
        result = discovery.parse_ein_job_output(
            stdout, "device", request_id=TARGET_DEVICE_ID, target="prod", action="remove"
        )
        assert result is not None
        assert result.found_type == "device"
        assert result.request_id == TARGET_DEVICE_ID
        assert result.approved is True
        assert result.action == "remove"

    def test_pending_request_id_does_not_match_remove(self):
        """v3.5: remove matcht NICHT pending[]-requestId (UUID-36) – nur
        paired[].deviceId. UUID-36 in pending[] → kein Fund (None)."""
        stdout = remove_stdout(
            "oc1", "device", pending_only_json(REAL_REQUEST_ID, TARGET_DEVICE_ID),
            found=0,
        )
        assert discovery.parse_ein_job_output(
            stdout, "device", request_id=REAL_REQUEST_ID, target="prod", action="remove"
        ) is None

    def test_remove_failure_detected(self):
        """B2: Remove-Exit-Code != 0 → REMOVE-FAILED-Marker + FOUND=0 →
        approved=False, Fehler-Output bleibt sichtbar."""
        stdout = (
            json_block("oc1", "device", paired_json(TARGET_DEVICE_ID))
            + "---REMOVE-BEGIN:oc1:device---\n"
            + "ERROR: device not paired\n"
            + "---REMOVE-END:oc1:device---\n"
            + "---REMOVE-FAILED:oc1:device---\n"
            + "---FOUND:0---\n"
        )
        result = discovery.parse_ein_job_output(
            stdout, "device", request_id=TARGET_DEVICE_ID, target="prod", action="remove"
        )
        assert result is not None
        assert result.approved is False
        assert "ERROR: device not paired" in result.approve_output

    def test_remove_failed_marker_forces_not_removed(self):
        """Auch bei inkonsistentem FOUND=1: REMOVE-FAILED-Marker → approved=False."""
        stdout = (
            json_block("oc1", "device", paired_json(TARGET_DEVICE_ID))
            + "---REMOVE-BEGIN:oc1:device---\nboom\n---REMOVE-END:oc1:device---\n"
            + "---REMOVE-FAILED:oc1:device---\n"
            + "---FOUND:1---\n"
        )
        result = discovery.parse_ein_job_output(
            stdout, "device", request_id=TARGET_DEVICE_ID, target="prod", action="remove"
        )
        assert result is not None
        assert result.approved is False

    def test_marker_isolation_remove_output_invisible_to_approve_parser(self):
        """Remove-Output + approve-Parser: der paired-Eintrag liegt NICHT im
        pending[]-Scan des approve-Parsers → kein Fund (None) und damit kein
        falscher Approve-Erfolg. Zusatz: Eintrag in pending UND paired +
        REMOVE-Marker → approved=False (kein APPROVE-Marker)."""
        stdout = remove_stdout("oc1", "device", paired_json(TARGET_DEVICE_ID))
        result = discovery.parse_ein_job_output(
            stdout, "device", request_id=TARGET_DEVICE_ID, target="prod"
        )
        assert result is None  # paired-Eintrag ist fuer den approve-Parser unsichtbar

        both = json.dumps({
            "pending": [{"deviceId": TARGET_DEVICE_ID, "requestId": REAL_REQUEST_ID}],
            "paired": [{"deviceId": TARGET_DEVICE_ID}],
        })
        stdout2 = remove_stdout("oc1", "device", both)
        result2 = discovery.parse_ein_job_output(
            stdout2, "device", request_id=TARGET_DEVICE_ID, target="prod"
        )
        assert result2 is not None
        assert result2.approved is False  # kein APPROVE-Marker → kein Erfolg
        assert result2.action == "approve"

    def test_marker_isolation_remove_output_invisible_to_reject_parser(self):
        """Remove-Output + reject-Parser: paired-Eintrag ist fuer den
        reject-Parser (pending[]-Scan) unsichtbar → None; Eintrag in pending
        UND paired + REMOVE-Marker → approved=False (kein REJECT-Marker)."""
        stdout = remove_stdout("oc1", "device", paired_json(TARGET_DEVICE_ID))
        result = discovery.parse_ein_job_output(
            stdout, "device", request_id=TARGET_DEVICE_ID, target="prod", action="reject"
        )
        assert result is None

        both = json.dumps({
            "pending": [{"deviceId": TARGET_DEVICE_ID, "requestId": REAL_REQUEST_ID}],
            "paired": [{"deviceId": TARGET_DEVICE_ID}],
        })
        stdout2 = remove_stdout("oc1", "device", both)
        result2 = discovery.parse_ein_job_output(
            stdout2, "device", request_id=TARGET_DEVICE_ID, target="prod", action="reject"
        )
        assert result2 is not None
        assert result2.approved is False  # kein REJECT-Marker → kein Erfolg
        assert result2.action == "reject"

    def test_marker_isolation_approve_output_invisible_to_remove_parser(self):
        stdout = (
            json_block("oc1", "device", paired_json(TARGET_DEVICE_ID))
            + "---APPROVE-BEGIN:oc1:device---\nok\n---APPROVE-END:oc1:device---\n"
            + "---FOUND:1---\n"
        )
        result = discovery.parse_ein_job_output(
            stdout, "device", request_id=TARGET_DEVICE_ID, target="prod", action="remove"
        )
        assert result is not None
        assert result.approved is False
        assert result.action == "remove"

    def test_no_find_returns_none(self):
        stdout = remove_stdout(
            "oc1", "device", json.dumps({"pending": [], "paired": []}), found=0
        )
        assert discovery.parse_ein_job_output(
            stdout, "device", request_id=TARGET_DEVICE_ID, target="prod", action="remove"
        ) is None

    def test_instance_down_fail_safe(self):
        stdout = "---JSON-BEGIN:oc1:device---\n\n---JSON-END:oc1:device---\n---FOUND:0---\n"
        assert discovery.parse_ein_job_output(
            stdout, "device", request_id=TARGET_DEVICE_ID, target="prod", action="remove"
        ) is None

    def test_pending_only_not_matched(self):
        """Nur pending-Eintraege vorhanden (kein paired) → kein Remove-Fund."""
        stdout = remove_stdout(
            "oc1", "device",
            pending_only_json(REAL_REQUEST_ID, TARGET_DEVICE_ID),
            found=0,
        )
        assert discovery.parse_ein_job_output(
            stdout, "device", request_id=TARGET_DEVICE_ID, target="prod", action="remove"
        ) is None


# ── run_discovery(action="remove") ──

class TestRunDiscoveryRemove:
    def test_ein_job_remove(self):
        """1 SSH pro VPS; Remote-Cmd enthaelt `devices remove`; Ergebnis
        action="remove" + approved=True."""
        seen = []

        def run_remote(ip, remote_cmd):
            seen.append(remote_cmd)
            return remove_stdout("oc1", "device", paired_json(TARGET_DEVICE_ID))

        result = discovery.run_discovery(
            MAP_PROD, TARGET_DEVICE_ID, derived_type="device",
            resolve_ip=lambda node: "100.64.0.2",
            run_remote=run_remote,
            action="remove",
        )
        assert result.target == "prod"
        assert result.instance == "oc1"
        assert result.approved is True
        assert result.action == "remove"
        assert "openclaw devices remove" in seen[0]
        assert "---REMOVE-BEGIN" in seen[0]
        # paired-Array + deviceId-Match (keine requestId-Alternation)
        assert '"paired"' in seen[0]
        assert "(requestId|deviceId)" not in seen[0]

    def test_remove_only_matches_target_device_keeps_preexisting(self):
        """Remove matcht NUR die Ziel-deviceId – der vorbestehende
        Win32-Eintrag (paarweise im paired[]) wird nicht entfernt."""
        extra = {
            "deviceId": PREEXISTING_DEVICE_ID,
            "publicKey": "xyz",
            "platform": "Win32",
            "clientId": "openclaw-control-ui",
            "role": "operator",
            "approvedAtMs": 1785915850624,
        }
        stdout = remove_stdout("oc1", "device", paired_json(TARGET_DEVICE_ID, extra))
        result = discovery.parse_ein_job_output(
            stdout, "device", request_id=TARGET_DEVICE_ID, target="prod", action="remove"
        )
        assert result is not None
        assert result.approved is True
        assert result.request_id == TARGET_DEVICE_ID

    def test_approve_regression(self):
        """Default-Aktion approve bleibt unveraendert (action="approve")."""
        def run_remote(ip, remote_cmd):
            return (
                json_block("oc1", "device", pending_only_json(DEVICE_UUID, "abc"))
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

    def test_reject_regression(self):
        """Reject (v3.2) bleibt unveraendert: action="reject" + requestId-Match."""
        def run_remote(ip, remote_cmd):
            return (
                json_block("oc2", "device", pending_only_json(REAL_REQUEST_ID, "abc"))
                + "---REJECT-BEGIN:oc2:device---\nok\n---REJECT-END:oc2:device---\n"
                + "---FOUND:1---\n"
            )

        result = discovery.run_discovery(
            MAP_PROD, REAL_REQUEST_ID, derived_type="device",
            resolve_ip=lambda node: "100.64.0.2",
            run_remote=run_remote,
            action="reject",
        )
        assert result.approved is True
        assert result.action == "reject"

    def test_not_found_raises(self):
        with pytest.raises(discovery.RequestNotFoundError):
            discovery.run_discovery(
                MAP_PROD, TARGET_DEVICE_ID, derived_type="device",
                resolve_ip=lambda node: "100.64.0.2",
                run_remote=lambda ip, cmd: remove_stdout(
                    "oc1", "device",
                    json.dumps({"pending": [], "paired": []}), found=0,
                ),
                action="remove",
            )


# ── CLI: --remove-only (approve.py main) ──

class TestRemoveCli:
    def test_remove_only_conflicts_with_list_only(self):
        with pytest.raises(SystemExit) as exc:
            approve.main(["--remove-only", "--list-only", "--local"])
        assert exc.value.code == 2

    def test_remove_only_conflicts_with_discover_only(self):
        with pytest.raises(SystemExit) as exc:
            approve.main(["--remove-only", "--discover-only", "--local"])
        assert exc.value.code == 2

    def test_remove_only_conflicts_with_reject_only(self):
        with pytest.raises(SystemExit) as exc:
            approve.main(["--remove-only", "--reject-only", "--local"])
        assert exc.value.code == 2

    def test_remove_only_allowed_with_full_run(self):
        """--full-run --remove-only = Ein-Job-Remove (Workflow mode=remove)."""
        # ohne Credentials → Exit 2 (Config) statt argparse-Fehler
        rc = approve.main(["--remove-only", "--full-run", "--request-id", TARGET_DEVICE_ID])
        assert rc == 2

    def test_telegram_id_rejected_exit_2(self):
        """v3.5: Remove nur device – Telegram-Kurzcode → Exit 2 (Fail-Fast)."""
        rc = approve.main(["--remove-only", "--local", "--request-id", TG_CODE])
        assert rc == 2

    def test_local_remove_flow(self, monkeypatch, capsys):
        """Lokaler Remove: devices list (paired[]) → Fund → `openclaw devices
        remove <deviceId>` → status "removed", Exit 0."""
        paired = paired_json(TARGET_DEVICE_ID)
        calls = []

        class FakeProc:
            def __init__(self, cmd):
                calls.append(cmd)
                self.returncode = 0
                if cmd[1] == "devices" and cmd[2] == "list":
                    self.stdout = paired
                else:
                    self.stdout = f"Removed {TARGET_DEVICE_ID[:8]}…"
                self.stderr = ""

        monkeypatch.setattr(approve.subprocess, "run", lambda cmd, **kw: FakeProc(cmd))
        rc = approve.main(["--remove-only", "--local", "--request-id", TARGET_DEVICE_ID])
        out = capsys.readouterr().out
        assert rc == 0
        assert '"status": "removed"' in out
        assert any(c[1] == "devices" and c[2] == "remove" and c[3] == TARGET_DEVICE_ID for c in calls)

    def test_local_remove_not_found_exit_0(self, monkeypatch, capsys):
        """not_found lokal (deviceId nicht gepaart) → Exit 0 (gruen,
        Owner-Vereinbarung 15:06) und KEIN remove-Befehl."""
        calls = []

        class FakeProc:
            def __init__(self, cmd):
                calls.append(cmd)
                self.returncode = 0
                self.stdout = json.dumps({"pending": [], "paired": []})
                self.stderr = ""

        monkeypatch.setattr(approve.subprocess, "run", lambda cmd, **kw: FakeProc(cmd))
        rc = approve.main(["--remove-only", "--local", "--request-id", TARGET_DEVICE_ID])
        out = capsys.readouterr().out
        assert rc == 0
        assert '"status": "not_found"' in out
        assert not any("remove" in c for c in calls)  # kein Remove-Befehl

    def test_local_remove_request_id_uuid_not_matched(self, monkeypatch, capsys):
        """v3.5: requestId (UUID-36) wird von remove NICHT gematcht – die
        UUID steht in pending[] (nicht paired[]) → not_found, Exit 0."""
        calls = []

        class FakeProc:
            def __init__(self, cmd):
                calls.append(cmd)
                self.returncode = 0
                self.stdout = pending_only_json(REAL_REQUEST_ID, TARGET_DEVICE_ID)
                self.stderr = ""

        monkeypatch.setattr(approve.subprocess, "run", lambda cmd, **kw: FakeProc(cmd))
        rc = approve.main(["--remove-only", "--local", "--request-id", REAL_REQUEST_ID])
        out = capsys.readouterr().out
        assert rc == 0
        assert '"status": "not_found"' in out
        assert not any("remove" in c for c in calls)

    def test_local_remove_failure_exit_1(self, monkeypatch, capsys):
        """Remove-Fehler (Exit != 0) → status "error", Exit 1."""
        paired = paired_json(TARGET_DEVICE_ID)
        calls = []

        class FakeProc:
            def __init__(self, cmd):
                calls.append(cmd)
                self.stderr = ""
                if cmd[1] == "devices" and cmd[2] == "list":
                    self.returncode = 0
                    self.stdout = paired
                else:
                    self.returncode = 1
                    self.stdout = ""
                    self.stderr = "boom"

        monkeypatch.setattr(approve.subprocess, "run", lambda cmd, **kw: FakeProc(cmd))
        rc = approve.main(["--remove-only", "--local", "--request-id", TARGET_DEVICE_ID])
        out = capsys.readouterr().out
        assert rc == 1
        assert '"status": "error"' in out


# ── summary.py: "removed"-Status ──

class TestRemoveSummary:
    def test_status_header_removed(self):
        md = summary.status_header("removed", {"found": [{"type": "device"}]})
        assert "Device-Remove" in md
        assert "✅" in md

    def test_result_to_markdown_removed(self):
        md = summary.result_to_markdown({
            "status": "removed",
            "id": TARGET_DEVICE_ID,
            "found": [{"target": "prod", "instance": "oc1", "type": "device", "vps_ip": "100.64.0.2"}],
            "scanned": ["prod/oc1"],
            "filters_applied": {"type": "device", "target": "prod", "instance": "all"},
        })
        assert "Entfernt (removed)" in md
        assert "prod/oc1" in md
