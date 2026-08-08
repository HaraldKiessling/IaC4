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

v3.6 (Instanz-Remove, scope=instance, Owner-Entscheidungen 2026-08-08):
  - TestBuildInstanceRemoveRemoteCmd: DEV-REMOVE-Marker je Geraet, ALLE
    paired[]-deviceIds (kein ID-Filter), B2-Semantik (kein `|| true`),
    Shell-Hard-Cap MAX_REMOVE_DEVICES=50 (DEV-REMOVE-LIMIT-Marker),
    Instance-Validierung, Regression scope=device unveraendert
  - TestParsePairedOutput: paired[]-Plan (deviceId/platform/clientId),
    pending/telegram/kaputtes JSON uebersprungen
  - TestParseInstanceRemoveOutput: removed/failed (Output), limit_hit,
    Marker-Isolation zu Einzel-REMOVE
  - TestRunInstanceRemove/TestCollectPairedDevices: 1 SSH pro VPS,
    UNREACHABLE-Semantik, Limit-Weitergabe an den Builder
  - TestInstanceRemoveCli: scope-Validierung (nur --remove-only, Konflikt
    id+scope=instance → Exit 2), lokaler/SSH-Flow (removed/partial/error/
    not_found/Limit), Idempotenz (leer → not_found Exit 0), Regression
    scope=device (Default)
  - TestInstanceRemoveSummary: instance_remove_to_markdown (removed_count,
    per_instance, failed-Liste), status "partial"
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


# ── v3.6 (Instanz-Remove, scope=instance): build/parse/CLI/Summary ──
# Owner-Entscheidungen 2026-08-08: „Instanz leeren“ (ALLE gepaarten Geraete,
# nicht „neuestes“), kein Confirm-Gate, max 50 Geraete pro Lauf (Exit 2
# VOR jedem Remove), Teilerfolg Exit 1 (failed im Summary), Idempotenz
# (leer → not_found, Exit 0). scope=device = unveraenderter v3.5-Pfad.


class TestBuildInstanceRemoveRemoteCmd:
    def test_template_removes_all_paired_devices(self):
        """Kern: extrahiert ALLE deviceIds aus paired[] und entfernt jede
        einzeln per REMOVE_CMD_TEMPLATES[device] (DRY)."""
        cmd = discovery.build_instance_remove_remote_cmd(["oc1", "oc2"])
        assert "for inst in oc1 oc2; do" in cmd
        assert "openclaw devices list --json" in cmd
        assert "openclaw devices remove $did" in cmd
        assert "---JSON-BEGIN:${inst}:device---" in cmd
        assert "---DEV-REMOVE-BEGIN:${inst}:$did---" in cmd
        assert "---DEV-REMOVE-END:${inst}:$did---" in cmd
        assert "---DEV-REMOVE-FAILED:${inst}:$did---" in cmd
        assert "---FOUND:${FOUND}---" in cmd
        assert "jq" not in cmd  # R08: keine jq-Dependency
        assert "pairing" not in cmd  # nur device-Quelle

    def test_paired_array_extraction_without_id_filter(self):
        """sed extrahiert das `paired`-Array (nicht pending); KEIN
        (requestId|deviceId)-Filter – ALLE Eintraege werden entfernt."""
        cmd = discovery.build_instance_remove_remote_cmd(["oc1"])
        assert '"paired"[[:space:]]*:[[:space:]]*\\[' in cmd
        assert "grep -oE '" + '"deviceId"' in cmd  # deviceId-Extraktion je Eintrag
        assert "(requestId|deviceId)" not in cmd

    def test_remove_exit_code_checked_no_or_true(self):
        """B2-Semantik: KEIN `|| true` um den Remove; FOUND=1 erst nach
        Exit-Code 0; DEV-REMOVE-FAILED-Marker bei Fehler."""
        cmd = discovery.build_instance_remove_remote_cmd(["oc1"])
        remove_line = "sudo docker exec openclaw-${inst} openclaw devices remove $did 2>&1"
        assert f"{remove_line} || true" not in cmd
        assert f"if {remove_line}; then" in cmd
        assert "FOUND=1" in cmd
        assert "---DEV-REMOVE-FAILED:${inst}:$did---" in cmd

    def test_limit_hard_cap_default_50(self):
        """Sicherheits-Limit (Owner-Entscheidung): Shell-Hard-Cap 50 mit
        DEV-REMOVE-LIMIT-Marker + break (Defense-in-Depth)."""
        cmd = discovery.build_instance_remove_remote_cmd(["oc1"])
        assert "COUNT=0" in cmd
        assert "COUNT=$((COUNT+1))" in cmd
        assert f'[ "$COUNT" -gt {discovery.MAX_REMOVE_DEVICES} ]' in cmd
        assert discovery.MAX_REMOVE_DEVICES == 50
        assert "---DEV-REMOVE-LIMIT:${inst}:device---" in cmd
        assert "break" in cmd

    def test_limit_hard_cap_custom_value(self):
        cmd = discovery.build_instance_remove_remote_cmd(["oc1"], max_devices=3)
        assert '[ "$COUNT" -gt 3 ]' in cmd

    def test_invalid_instance_rejected(self):
        with pytest.raises(ValueError, match="Ungueltige"):
            discovery.build_instance_remove_remote_cmd(["oc0"])

    def test_empty_instances_rejected(self):
        with pytest.raises(ValueError, match="Keine Instanzen"):
            discovery.build_instance_remove_remote_cmd([])

    def test_no_approve_or_reject_markers(self):
        cmd = discovery.build_instance_remove_remote_cmd(["oc1"])
        assert "approve" not in cmd
        assert "reject" not in cmd
        assert "---APPROVE" not in cmd
        assert "---REJECT" not in cmd

    def test_single_device_remove_path_unchanged(self):
        """Regression scope=device: Einzel-Remove (v3.5) bleibt unangetastet
        (paired-Array + deviceId-Grep + REMOVE-* statt DEV-REMOVE-*)."""
        cmd = discovery.build_ein_job_remote_cmd(
            "device", ["oc1"], TARGET_DEVICE_ID, action="remove"
        )
        assert "---REMOVE-BEGIN:${inst}:device---" in cmd
        assert "---DEV-REMOVE" not in cmd
        assert f'"{TARGET_DEVICE_ID}"' in cmd


class TestParsePairedOutput:
    def test_parses_paired_entries(self):
        out = json_block("oc1", "device", paired_json(TARGET_DEVICE_ID))
        devs = discovery.parse_paired_output(out, "prod")
        assert len(devs) == 1
        assert devs[0].instance == "oc1"
        assert devs[0].target == "prod"
        assert devs[0].device_id == TARGET_DEVICE_ID
        assert devs[0].platform == "Linux armv81"
        assert devs[0].client_id == "openclaw-control-ui"

    def test_skips_pending_entries(self):
        out = json_block("oc1", "device", pending_only_json(REAL_REQUEST_ID, TARGET_DEVICE_ID))
        assert discovery.parse_paired_output(out, "prod") == []

    def test_skips_telegram_blocks(self):
        out = json_block("oc1", "telegram",
                         json.dumps({"channel": "telegram", "requests": []}))
        assert discovery.parse_paired_output(out, "prod") == []

    def test_malformed_json_skipped(self):
        out = json_block("oc1", "device", "{kaputt")
        assert discovery.parse_paired_output(out, "prod") == []

    def test_empty_paired_returns_empty(self):
        out = json_block("oc1", "device", json.dumps({"pending": [], "paired": []}))
        assert discovery.parse_paired_output(out, "prod") == []

    def test_multiple_entries_same_block(self):
        extra = {"deviceId": PREEXISTING_DEVICE_ID, "platform": "Win32",
                 "clientId": "openclaw-control-ui"}
        out = json_block("oc2", "device", paired_json(TARGET_DEVICE_ID, extra))
        devs = discovery.parse_paired_output(out, "prod")
        assert [d.device_id for d in devs] == [TARGET_DEVICE_ID, PREEXISTING_DEVICE_ID]
        assert all(d.instance == "oc2" for d in devs)


class TestParseInstanceRemoveOutput:
    def test_all_removed(self):
        out = (
            json_block("oc1", "device", paired_json(TARGET_DEVICE_ID))
            + f"---DEV-REMOVE-BEGIN:oc1:{TARGET_DEVICE_ID}---\nRemoved…\n---DEV-REMOVE-END:oc1:{TARGET_DEVICE_ID}---\n"
            + "---FOUND:1---\n"
        )
        res = discovery.parse_instance_remove_output(out, "prod")
        assert res.removed == [("oc1", TARGET_DEVICE_ID)]
        assert res.failed == []
        assert res.limit_hit is False
        assert res.scanned == ["prod/oc1"]

    def test_partial_failure_lists_failed_with_output(self):
        out = (
            json_block("oc1", "device", paired_json(TARGET_DEVICE_ID))
            + f"---DEV-REMOVE-BEGIN:oc1:{TARGET_DEVICE_ID}---\nERROR: not paired\n---DEV-REMOVE-END:oc1:{TARGET_DEVICE_ID}---\n"
            + f"---DEV-REMOVE-FAILED:oc1:{TARGET_DEVICE_ID}---\n"
            + "---FOUND:0---\n"
        )
        res = discovery.parse_instance_remove_output(out, "prod")
        assert res.removed == []
        assert len(res.failed) == 1
        assert res.failed[0][0] == "oc1"
        assert res.failed[0][1] == TARGET_DEVICE_ID
        assert "ERROR: not paired" in res.failed[0][2]

    def test_limit_marker_detected(self):
        out = (
            json_block("oc1", "device", paired_json(TARGET_DEVICE_ID))
            + "---DEV-REMOVE-LIMIT:oc1:device---\n"
            + "---FOUND:0---\n"
        )
        res = discovery.parse_instance_remove_output(out, "prod")
        assert res.limit_hit is True
        assert res.removed == []
        assert res.failed == []

    def test_no_blocks_returns_empty(self):
        res = discovery.parse_instance_remove_output("---FOUND:0---\n", "prod")
        assert res.removed == [] and res.failed == [] and res.limit_hit is False

    def test_scanned_deduped_across_instances(self):
        out = (
            json_block("oc1", "device", paired_json(TARGET_DEVICE_ID))
            + json_block("oc2", "device", paired_json(PREEXISTING_DEVICE_ID))
        )
        res = discovery.parse_instance_remove_output(out, "prod")
        assert res.scanned == ["prod/oc1", "prod/oc2"]

    def test_failed_marker_after_end_not_in_body(self):
        """DEV-REMOVE-FAILED kommt NACH dem END-Marker – der Body eines
        entfernten Blocks enthaelt keinen FAILED-Marker (kein False-Positiv)."""
        out = (
            json_block("oc1", "device", paired_json(TARGET_DEVICE_ID))
            + f"---DEV-REMOVE-BEGIN:oc1:{TARGET_DEVICE_ID}---\nok\n---DEV-REMOVE-END:oc1:{TARGET_DEVICE_ID}---\n"
            + f"---DEV-REMOVE-FAILED:oc1:{TARGET_DEVICE_ID}---\n"
            + "---FOUND:0---\n"
        )
        res = discovery.parse_instance_remove_output(out, "prod")
        assert res.removed == []
        assert len(res.failed) == 1
        assert res.failed[0][2] == "ok"

    def test_single_remove_markers_not_confused(self):
        """Marker-Isolation: REMOVE-* (Einzel) wird NICHT als DEV-REMOVE
        gelesen und umgekehrt (disjunkte Marker-Sets)."""
        out = (
            json_block("oc1", "device", paired_json(TARGET_DEVICE_ID))
            + f"---REMOVE-BEGIN:oc1:device---\nok\n---REMOVE-END:oc1:device---\n"
            + "---FOUND:1---\n"
        )
        res = discovery.parse_instance_remove_output(out, "prod")
        assert res.removed == [] and res.failed == []


class TestRunInstanceRemove:
    def test_orchestrates_per_vps_and_aggregates(self):
        seen = []

        def run_remote(ip, remote_cmd):
            seen.append(remote_cmd)
            return (
                json_block("oc1", "device", paired_json(TARGET_DEVICE_ID))
                + f"---DEV-REMOVE-BEGIN:oc1:{TARGET_DEVICE_ID}---\nRemoved…\n---DEV-REMOVE-END:oc1:{TARGET_DEVICE_ID}---\n"
                + "---FOUND:1---\n"
            )

        res = discovery.run_instance_remove(
            MAP_PROD,
            resolve_ip=lambda node: "100.64.0.2",
            run_remote=run_remote,
        )
        assert len(seen) == 1  # 1 SSH pro VPS (oc1+oc2 in EINER Gruppe)
        assert res.removed == [("oc1", TARGET_DEVICE_ID)]
        assert res.scanned == ["prod/oc1"]
        assert res.unreachable == []
        assert "openclaw devices remove $did" in seen[0]

    def test_unreachable_vps_skipped(self):
        res = discovery.run_instance_remove(
            MAP_PROD,
            resolve_ip=lambda node: None,
            run_remote=lambda ip, cmd: "",
        )
        assert res.removed == []
        assert res.unreachable == ["vps-prod"]

    def test_limit_forwarded_to_builder(self):
        seen = []

        def run_remote(ip, remote_cmd):
            seen.append(remote_cmd)
            return ""

        discovery.run_instance_remove(
            MAP_PROD,
            resolve_ip=lambda node: "100.64.0.2",
            run_remote=run_remote,
            max_devices=7,
        )
        assert '[ "$COUNT" -gt 7 ]' in seen[0]

    def test_empty_map_no_calls(self):
        res = discovery.run_instance_remove(
            [], resolve_ip=lambda node: "100.64.0.2", run_remote=lambda ip, cmd: ""
        )
        assert res.removed == [] and res.scanned == []


class TestCollectPairedDevices:
    def test_plan_with_vps_ip(self):
        plan, scanned, unreachable = discovery.collect_paired_devices(
            MAP_PROD,
            resolve_ip=lambda node: "100.64.0.2",
            run_remote=lambda ip, cmd: json_block("oc1", "device", paired_json(TARGET_DEVICE_ID)),
        )
        assert len(plan) == 1
        assert plan[0].vps_ip == "100.64.0.2"
        assert scanned == ["prod/oc1", "prod/oc2"]
        assert unreachable == []

    def test_empty_plan(self):
        plan, _scanned, _unreachable = discovery.collect_paired_devices(
            MAP_PROD,
            resolve_ip=lambda node: "100.64.0.2",
            run_remote=lambda ip, cmd: json_block("oc1", "device",
                                                  json.dumps({"pending": [], "paired": []})),
        )
        assert plan == []

    def test_unreachable_recorded(self):
        _plan, _scanned, unreachable = discovery.collect_paired_devices(
            MAP_PROD, resolve_ip=lambda node: None, run_remote=lambda ip, cmd: ""
        )
        assert unreachable == ["vps-prod"]


class TestInstanceRemoveCli:
    def test_scope_instance_without_remove_only_exit_2(self):
        rc = approve.main(["--scope", "instance", "--local"])
        assert rc == 2

    def test_scope_instance_with_discover_only_exit_2(self):
        rc = approve.main(["--scope", "instance", "--discover-only", "--local"])
        assert rc == 2

    def test_scope_instance_with_request_id_conflict_exit_2(self):
        rc = approve.main(["--remove-only", "--scope", "instance",
                           "--request-id", TARGET_DEVICE_ID])
        assert rc == 2

    def test_invalid_scope_value_rejected(self):
        with pytest.raises(SystemExit) as exc:
            approve.main(["--remove-only", "--scope", "foobar", "--local"])
        assert exc.value.code == 2

    def test_local_instance_remove_all_removed(self, monkeypatch, capsys):
        """scope=instance lokal: ALLE paired[]-Geraete entfernt → status
        removed, Exit 0, removed_count + per_instance im JSON."""
        calls = []
        paired = json.dumps({"pending": [], "paired": [
            {"deviceId": TARGET_DEVICE_ID, "platform": "Linux armv81"},
            {"deviceId": PREEXISTING_DEVICE_ID, "platform": "Win32"},
        ]})

        class FakeProc:
            def __init__(self, cmd):
                calls.append(cmd)
                self.returncode = 0
                self.stdout = paired if (cmd[1] == "devices" and cmd[2] == "list") else "Removed…"
                self.stderr = ""

        monkeypatch.setattr(approve.subprocess, "run", lambda cmd, **kw: FakeProc(cmd))
        rc = approve.main(["--remove-only", "--scope", "instance", "--local"])
        out = capsys.readouterr().out
        assert rc == 0
        assert '"status": "removed"' in out
        assert '"scope": "instance"' in out
        assert '"removed_count": 2' in out
        assert '"per_instance"' in out
        removes = [c for c in calls if c[1] == "devices" and c[2] == "remove"]
        assert len(removes) == 2
        assert removes[0][3] == TARGET_DEVICE_ID
        assert removes[1][3] == PREEXISTING_DEVICE_ID

    def test_local_instance_remove_partial_exit_1(self, monkeypatch, capsys):
        """Teilerfolg (1 entfernt, 1 fehlgeschlagen) → status partial,
        Exit 1, failed-Details im JSON (Owner-Entscheidung)."""
        calls = []
        paired = json.dumps({"pending": [], "paired": [
            {"deviceId": TARGET_DEVICE_ID},
            {"deviceId": PREEXISTING_DEVICE_ID},
        ]})

        class FakeProc:
            def __init__(self, cmd):
                calls.append(cmd)
                if cmd[1] == "devices" and cmd[2] == "list":
                    self.returncode = 0
                    self.stdout = paired
                else:
                    self.returncode = 1 if cmd[3] == PREEXISTING_DEVICE_ID else 0
                    self.stdout = ""
                    self.stderr = "boom"

        monkeypatch.setattr(approve.subprocess, "run", lambda cmd, **kw: FakeProc(cmd))
        rc = approve.main(["--remove-only", "--scope", "instance", "--local"])
        out = capsys.readouterr().out
        assert rc == 1
        assert '"status": "partial"' in out
        assert '"removed_count": 1' in out
        assert PREEXISTING_DEVICE_ID in out  # failed-Details (Voll-ID im JSON)

    def test_local_instance_remove_all_failed_exit_1(self, monkeypatch, capsys):
        calls = []
        paired = json.dumps({"pending": [], "paired": [{"deviceId": TARGET_DEVICE_ID}]})

        class FakeProc:
            def __init__(self, cmd):
                calls.append(cmd)
                if cmd[1] == "devices" and cmd[2] == "list":
                    self.returncode = 0
                    self.stdout = paired
                else:
                    self.returncode = 1
                    self.stdout = ""
                    self.stderr = "kaputt"

        monkeypatch.setattr(approve.subprocess, "run", lambda cmd, **kw: FakeProc(cmd))
        rc = approve.main(["--remove-only", "--scope", "instance", "--local"])
        out = capsys.readouterr().out
        assert rc == 1
        assert '"status": "error"' in out
        assert '"removed_count": 0' in out

    def test_local_instance_remove_not_found_exit_0(self, monkeypatch, capsys):
        """Idempotenz: leere Instanz (kein paired) → not_found, Exit 0,
        KEIN remove-Befehl (2. Lauf gruen)."""
        calls = []

        class FakeProc:
            def __init__(self, cmd):
                calls.append(cmd)
                self.returncode = 0
                self.stdout = json.dumps({"pending": [], "paired": []})
                self.stderr = ""

        monkeypatch.setattr(approve.subprocess, "run", lambda cmd, **kw: FakeProc(cmd))
        rc = approve.main(["--remove-only", "--scope", "instance", "--local"])
        out = capsys.readouterr().out
        assert rc == 0
        assert '"status": "not_found"' in out
        assert not any(c[2] == "remove" for c in calls)

    def test_local_instance_remove_limit_exit_2(self, monkeypatch, capsys):
        """Sicherheits-Limit: 51 Geraete (> max 50) → Exit 2 VOR jedem
        Remove (kein Massen-Remove), limit_hit=true."""
        calls = []
        paired = json.dumps({"pending": [], "paired": [
            {"deviceId": f"{i:064x}"} for i in range(51)
        ]})

        class FakeProc:
            def __init__(self, cmd):
                calls.append(cmd)
                self.returncode = 0
                self.stdout = paired
                self.stderr = ""

        monkeypatch.setattr(approve.subprocess, "run", lambda cmd, **kw: FakeProc(cmd))
        rc = approve.main(["--remove-only", "--scope", "instance", "--local"])
        out = capsys.readouterr().out
        assert rc == 2
        assert '"limit_hit": true' in out
        assert not any(c[2] == "remove" for c in calls)  # KEIN Remove ausgefuehrt

    def test_scope_device_default_regression(self, monkeypatch, capsys):
        """Regression: Default scope=device = bisheriger ID-basierter Pfad
        (v3.5) – status removed, genau EIN remove-Befehl."""
        calls = []
        paired = paired_json(TARGET_DEVICE_ID)

        class FakeProc:
            def __init__(self, cmd):
                calls.append(cmd)
                self.returncode = 0
                self.stdout = paired if (cmd[1] == "devices" and cmd[2] == "list") else "Removed…"
                self.stderr = ""

        monkeypatch.setattr(approve.subprocess, "run", lambda cmd, **kw: FakeProc(cmd))
        rc = approve.main(["--remove-only", "--local", "--request-id", TARGET_DEVICE_ID])
        out = capsys.readouterr().out
        assert rc == 0
        assert '"status": "removed"' in out
        assert '"scope"' not in out  # kein scope-Feld im device-Schema
        removes = [c for c in calls if c[1] == "devices" and c[2] == "remove"]
        assert len(removes) == 1

    def test_ssh_instance_remove_wiring(self, monkeypatch, capsys, tmp_path):
        """SSH-Pfad: zweiphasig – Plan (collect_paired_devices), dann
        run_instance_remove; alle entfernt → status removed, Exit 0."""
        plan = [discovery.PairedDevice(
            instance="oc1", target="prod", vps_ip="100.64.0.2",
            device_id=TARGET_DEVICE_ID, platform="Linux armv81", client_id="cli",
        )]
        res = discovery.InstanceRemoveResult()
        res.removed.append(("oc1", TARGET_DEVICE_ID))
        res.scanned.append("prod/oc1")
        monkeypatch.setattr(approve, "fetch_tailscale_token", lambda *a, **k: "tok")
        monkeypatch.setattr(approve, "collect_paired_devices", lambda *a, **k: (plan, ["prod/oc1"], []))
        monkeypatch.setattr(approve, "run_instance_remove", lambda *a, **k: res)
        inst_map = tmp_path / "instances.txt"
        inst_map.write_text("oc1|prod\n")
        rc = approve.main([
            "--remove-only", "--scope", "instance", "--full-run",
            "--target-filter", "prod", "--instance-filter", "all",
            "--instance-map", str(inst_map),
            "--vps-user", "u", "--ssh-key", "/tmp/k",
            "--ts-tailnet", "t", "--ts-client-id", "c", "--ts-client-secret", "s",
        ])
        out = capsys.readouterr().out
        assert rc == 0
        assert '"status": "removed"' in out
        assert '"removed_count": 1' in out
        assert '"per_instance"' in out

    def test_ssh_instance_remove_partial_exit_1(self, monkeypatch, capsys, tmp_path):
        plan = [discovery.PairedDevice(
            instance="oc1", target="prod", vps_ip="100.64.0.2",
            device_id=TARGET_DEVICE_ID, platform="Linux", client_id="cli",
        )]
        res = discovery.InstanceRemoveResult()
        res.failed.append(("oc1", TARGET_DEVICE_ID, "ERROR"))
        res.scanned.append("prod/oc1")
        monkeypatch.setattr(approve, "fetch_tailscale_token", lambda *a, **k: "tok")
        monkeypatch.setattr(approve, "collect_paired_devices", lambda *a, **k: (plan, ["prod/oc1"], []))
        monkeypatch.setattr(approve, "run_instance_remove", lambda *a, **k: res)
        inst_map = tmp_path / "instances.txt"
        inst_map.write_text("oc1|prod\n")
        rc = approve.main([
            "--remove-only", "--scope", "instance", "--full-run",
            "--instance-map", str(inst_map),
            "--vps-user", "u", "--ssh-key", "/tmp/k",
            "--ts-tailnet", "t", "--ts-client-id", "c", "--ts-client-secret", "s",
        ])
        out = capsys.readouterr().out
        assert rc == 1
        assert '"status": "error"' in out  # 0 entfernt + Fehler
        assert TARGET_DEVICE_ID in out

    def test_ssh_instance_remove_limit_plan_exit_2(self, monkeypatch, capsys, tmp_path):
        """Plan > 50: Abbruch VOR jedem Remove (Exit 2), run_instance_remove
        wird NICHT aufgerufen."""
        plan = [discovery.PairedDevice(
            instance="oc1", target="prod", vps_ip="100.64.0.2",
            device_id=f"{i:064x}", platform="Linux", client_id="cli",
        ) for i in range(51)]
        called = {"remove": False}
        monkeypatch.setattr(approve, "fetch_tailscale_token", lambda *a, **k: "tok")
        monkeypatch.setattr(approve, "collect_paired_devices",
                            lambda *a, **k: (plan, ["prod/oc1"], []))
        monkeypatch.setattr(approve, "run_instance_remove",
                            lambda *a, **k: called.update(remove=True) or discovery.InstanceRemoveResult())
        inst_map = tmp_path / "instances.txt"
        inst_map.write_text("oc1|prod\n")
        rc = approve.main([
            "--remove-only", "--scope", "instance", "--full-run",
            "--instance-map", str(inst_map),
            "--vps-user", "u", "--ssh-key", "/tmp/k",
            "--ts-tailnet", "t", "--ts-client-id", "c", "--ts-client-secret", "s",
        ])
        out = capsys.readouterr().out
        assert rc == 2
        assert '"limit_hit": true' in out
        assert called["remove"] is False  # KEIN Remove-Lauf


class TestInstanceRemoveSummary:
    def test_status_header_partial(self):
        md = summary.status_header("partial", {"found": [{"type": "device"}]})
        assert "Teilweise entfernt" in md
        assert "⚠️" in md

    def test_instance_remove_markdown_removed(self):
        md = summary.instance_remove_to_markdown({
            "status": "removed",
            "scope": "instance",
            "removed_count": 2,
            "per_instance": [{"instance": "oc1", "removed": 2, "failed": 0}],
            "failed": [],
            "scanned": ["prod/oc1"],
            "filters_applied": {"type": "device", "target": "prod", "instance": "all"},
        })
        assert "Alle entfernt" in md
        assert "| **Entfernt** | 2 |" in md
        assert "oc1" in md

    def test_instance_remove_markdown_partial_lists_failed(self):
        md = summary.instance_remove_to_markdown({
            "status": "partial",
            "scope": "instance",
            "removed_count": 1,
            "per_instance": [{"instance": "oc1", "removed": 1, "failed": 1}],
            "failed": [{"instance": "oc1", "device_id": TARGET_DEVICE_ID,
                         "output": "ERROR: not paired"}],
            "scanned": ["prod/oc1"],
            "filters_applied": {},
        })
        assert "Teilweise entfernt" in md
        assert "Fehlgeschlagene Geraete" in md
        assert "ERROR: not paired" in md
        assert TARGET_DEVICE_ID[:24] in md  # gekuerzte deviceId in der Tabelle

    def test_instance_remove_markdown_not_found(self):
        md = summary.instance_remove_to_markdown({
            "status": "not_found",
            "scope": "instance",
            "removed_count": 0,
            "per_instance": [{"instance": "oc1", "removed": 0, "failed": 0}],
            "failed": [],
            "scanned": ["prod/oc1"],
            "filters_applied": {},
        })
        assert "Keine gepaarten Geraete" in md
        assert "| **Entfernt** | 0 |" in md
