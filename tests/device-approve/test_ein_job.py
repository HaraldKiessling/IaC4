"""Tests für den Ein-Job-Fast-Path v3.0 (Workflow-05-Performance-Optimierung).

Abgedeckt (Design 05 §4/§6 + Review-Auflösung R02/R03/R08):
  - group_by_vps: Gruppierung nach target in Map-Reihenfolge (1 SSH pro VPS)
  - build_ein_job_remote_cmd: Telegram-/Device-/Both-Templates, Approve-Befehl
    typabhängig, `|| true` fail-safe, break (Break-Semantik), FOUND-Marker,
    KEIN jq (R08 – Match im Textpfad, Verifikation in Python)
  - parse_ein_job_output: dev+prod Fund/Approve (prod ohne Gate), kein Fund,
    Instanz-Down (leere Ausgabe), defektes JSON, type=both (beide Quellen in
    einer Session), Approve-Output
  - run_discovery (Ein-Job): 1 SSH-Call pro VPS, Break über VPS-Grenzen,
    UNREACHABLE-Skip, GITHUB_OUTPUT, discover-only vs. approve
  - Whitelist-ID-Regex (§6.1.3)
"""

import json
import os
import re
import sys

import pytest

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "device-approve")

from importlib.machinery import SourceFileLoader

discovery = SourceFileLoader(
    "device_approve.discovery",
    os.path.join(TOOLS_DIR, "discovery.py"),
).load_module()

# Test-IDs v3.0 (kalibriert an realen IDs, 2026-08-06)
TG_CODE = "QVDCXJEM"
DEVICE_UUID = "b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5"
# v3.3.1: 64er-PublicKey-Hash (pending[].deviceId) + fremde UUID
DEVICE_HEX_64 = "9df47d697653fb4069407734e06849b342738ed3e9ec4b172402aca911925392"
ALT_UUID = "2e68bca9-4965-4e29-9a9d-d1a12644d644"

MAP_DEV_PROD = [("oc1", "dev"), ("oc2", "dev"), ("oc1", "prod"), ("oc2", "prod")]


# ── Fixture-Builder (Marker-Format v3.0: Label = inst:typ) ──


def pairing_json(code, requests=None):
    entries = requests if requests is not None else [
        {"code": code, "userId": "7145674995", "channel": "telegram"},
    ]
    return json.dumps({"channel": "telegram", "requests": entries})


def devices_json(device_id, pending=None):
    entries = pending if pending is not None else [
        {"deviceId": device_id, "publicKey": "abc", "platform": "Win32",
         "clientId": "openclaw-control-ui", "clientMode": "webchat",
         "role": "operator", "roles": ["operator"], "scopes": ["operator.admin"],
         "createdAtMs": 1785915850624},
    ]
    return json.dumps({"pending": entries, "paired": []})


def json_block(instance, typ, body):
    return f"---JSON-BEGIN:{instance}:{typ}---\n{body}\n---JSON-END:{instance}:{typ}---\n"


def approve_block(instance, typ, output="Device approved."):
    return f"---APPROVE-BEGIN:{instance}:{typ}---\n{output}\n---APPROVE-END:{instance}:{typ}---\n"


def ein_job_stdout(instance, typ, body, *, approve=True, found=1, approve_output="Device approved."):
    out = json_block(instance, typ, body)
    if approve:
        out += approve_block(instance, typ, approve_output)
    out += f"---FOUND:{found}---\n"
    return out


# ── group_by_vps (§6.2.1) ──

class TestGroupByVps:
    def test_preserves_target_order(self):
        instance_map = [("oc1", "dev"), ("oc2", "dev"), ("oc1", "prod"), ("oc2", "prod")]
        groups = discovery.group_by_vps(instance_map)
        assert list(groups.keys()) == ["dev", "prod"]
        assert groups["dev"] == ["oc1", "oc2"]
        assert groups["prod"] == ["oc1", "oc2"]

    def test_preserves_instance_order(self):
        groups = discovery.group_by_vps([("oc3", "dev"), ("oc1", "dev"), ("oc2", "prod")])
        assert groups["dev"] == ["oc3", "oc1"]
        assert groups["prod"] == ["oc2"]

    def test_empty_map(self):
        assert list(discovery.group_by_vps([]).keys()) == []


# ── build_ein_job_remote_cmd (§6.2.2 + R02/R08) ──

class TestBuildEinJobRemoteCmd:
    def test_telegram_template(self):
        cmd = discovery.build_ein_job_remote_cmd("telegram", ["oc1", "oc2"], TG_CODE)
        assert "for inst in oc1 oc2; do" in cmd
        assert "openclaw pairing list telegram --json" in cmd
        assert f"openclaw pairing approve telegram {TG_CODE}" in cmd
        assert "---JSON-BEGIN:${inst}:telegram---" in cmd
        assert "---APPROVE-BEGIN:${inst}:telegram---" in cmd
        assert "---APPROVE-FAILED:${inst}:telegram---" in cmd  # B2: Fehler sichtbar
        assert "---FOUND:${FOUND}---" in cmd
        assert "|| true" in cmd          # fail-safe NUR für die Discovery-Quelle
        assert "break" in cmd            # Break-Semantik
        assert "devices list --json" not in cmd
        assert "jq" not in cmd           # R08: keine jq-Dependency

    def test_approve_exit_code_checked_no_or_true(self):
        """B2 (2. Review, Blocker): Approve-Erfolg wird geprüft – KEIN `|| true`
        um den Approve; FOUND=1 erst nach Exit-Code 0; APPROVE-FAILED-Marker."""
        cmd = discovery.build_ein_job_remote_cmd("telegram", ["oc1"], TG_CODE)
        approve_line = f"sudo docker exec openclaw-${{inst}} openclaw pairing approve telegram {TG_CODE} 2>&1"
        # KEIN || true um den Approve-Befehl
        assert f"{approve_line} || true" not in cmd
        assert "|| true" in cmd  # bleibt für die Discovery-Quelle (fail-safe)
        # Approve läuft in einer if-Abfrage auf den Exit-Code
        assert f"if {approve_line}; then" in cmd
        assert "FOUND=1" in cmd
        assert "---APPROVE-FAILED:${inst}:telegram---" in cmd
        # Reihenfolge: FOUND=1 NACH dem if (Approve-Erfolg), nicht davor
        assert cmd.index("if sudo docker exec") < cmd.index("FOUND=1")

    def test_device_template(self):
        cmd = discovery.build_ein_job_remote_cmd("device", ["oc1"], DEVICE_UUID)
        assert "openclaw devices list --json" in cmd
        assert f"openclaw devices approve {DEVICE_UUID}" in cmd
        assert "---JSON-BEGIN:${inst}:device---" in cmd
        assert "pairing" not in cmd

    def test_device_grep_matches_requestId_or_deviceId(self):
        """v3.3.1: Remote-grep matcht requestId ODER deviceId – die UUID-36
        steht in pending[].requestId (deviceId = 64er-Key-Hash, e2e-Beleg
        aee3a00); defensiv bleibt deviceId im Alternativen-Pfad."""
        cmd = discovery.build_ein_job_remote_cmd("device", ["oc1"], DEVICE_UUID)
        assert 'grep -qE \'"(requestId|deviceId)"' in cmd
        assert f'"{DEVICE_UUID}"' in cmd
        # kein Feld-exklusiver Match mehr (alter Bug: nur deviceId)
        assert 'grep -qE \'"deviceId"' not in cmd

    def test_telegram_grep_matches_code_only(self):
        """Telegram unveraendert: Remote-grep matcht nur `code`."""
        cmd = discovery.build_ein_job_remote_cmd("telegram", ["oc1"], TG_CODE)
        assert 'grep -qE \'"(code)"' in cmd

    def test_both_grep_has_requestId_alternation_for_device(self):
        """v3.3.1: type=both → device-Quelle matcht (requestId|deviceId)."""
        cmd = discovery.build_ein_job_remote_cmd("both", ["oc1"], DEVICE_UUID)
        assert 'grep -qE \'"(requestId|deviceId)"' in cmd
        assert 'grep -qE \'"(code)"' in cmd

    def test_both_template_queries_both_sources_in_one_session(self):
        """R02: type=both → pairing UND devices in DERSELBEN Session."""
        cmd = discovery.build_ein_job_remote_cmd("both", ["oc1", "oc2"], DEVICE_UUID)
        assert cmd.count("for inst in oc1 oc2; do") == 1   # EINE Remote-Schleife
        assert "openclaw pairing list telegram --json" in cmd
        assert "openclaw devices list --json" in cmd
        assert f"openclaw pairing approve telegram {DEVICE_UUID}" in cmd
        assert f"openclaw devices approve {DEVICE_UUID}" in cmd
        assert "---JSON-BEGIN:${inst}:telegram---" in cmd
        assert "---JSON-BEGIN:${inst}:device---" in cmd
        assert "---APPROVE-FAILED:${inst}:device---" in cmd  # B2: beide Typen

    def test_discover_only_has_no_approve(self):
        cmd = discovery.build_ein_job_remote_cmd("telegram", ["oc1"], TG_CODE, approve=False)
        assert "---APPROVE-BEGIN" not in cmd
        assert "approve telegram" not in cmd
        assert "---FOUND:${FOUND}---" in cmd

    def test_invalid_type_rejected(self):
        with pytest.raises(ValueError, match="Ungueltiger Typ"):
            discovery.build_ein_job_remote_cmd("foobar", ["oc1"], TG_CODE)

    def test_auto_type_rejected(self):
        with pytest.raises(ValueError, match="Ungueltiger Typ"):
            discovery.build_ein_job_remote_cmd("auto", ["oc1"], TG_CODE)

    def test_invalid_instance_rejected(self):
        with pytest.raises(ValueError, match="Ungueltige"):
            discovery.build_ein_job_remote_cmd("telegram", ["oc0"], TG_CODE)

    def test_valid_instance_oc99(self):
        cmd = discovery.build_ein_job_remote_cmd("telegram", ["oc99"], TG_CODE)
        assert "for inst in oc99; do" in cmd

    def test_empty_instances_rejected(self):
        with pytest.raises(ValueError, match="Keine Instanzen"):
            discovery.build_ein_job_remote_cmd("telegram", [], TG_CODE)

    def test_invalid_request_id_rejected(self):
        with pytest.raises(ValueError):
            discovery.build_ein_job_remote_cmd("telegram", ["oc1"], "bad$id")

    def test_device_id_in_telegram_context_rejected(self):
        """Format-Sperre: Device-ID ist kein gültiger Telegram-Kurzcode."""
        with pytest.raises(ValueError):
            discovery.build_ein_job_remote_cmd("telegram", ["oc1"], DEVICE_UUID)

    def test_telegram_code_in_device_context_rejected(self):
        with pytest.raises(ValueError):
            discovery.build_ein_job_remote_cmd("device", ["oc1"], TG_CODE)


# ── parse_ein_job_output (§4.3 + §6.1) ──

class TestParseEinJobOutput:
    def test_dev_find_and_approve(self):
        """Fund auf dev → Approve direkt in der Remote-Schleife."""
        stdout = ein_job_stdout("oc1", "telegram", pairing_json(TG_CODE))
        result = discovery.parse_ein_job_output(stdout, "telegram", request_id=TG_CODE, target="dev")
        assert result is not None
        assert result.request_id == TG_CODE
        assert result.instance == "oc1"
        assert result.target == "dev"
        assert result.found_type == "telegram"
        assert result.approved is True
        assert "Device approved." in result.approve_output

    def test_prod_find_and_approve_without_gate(self):
        """Fund auf prod → Approve direkt (kein Environment-Gate, Owner-Entscheidung)."""
        stdout = ein_job_stdout("oc2", "device", devices_json(DEVICE_UUID))
        result = discovery.parse_ein_job_output(stdout, "device", request_id=DEVICE_UUID, target="prod")
        assert result is not None
        assert result.target == "prod"
        assert result.instance == "oc2"
        assert result.found_type == "device"
        assert result.approved is True

    def test_device_requestId_match_found_and_approved(self):
        """v3.3.1: pending-Eintrag mit UUID-36 im requestId-Feld (deviceId =
        64er-Hash) wird gefunden und approved – der Workflow-Bugfall
        (7 not_found-Runs, u.a. 31165552730/31165829570)."""
        entry = {"deviceId": DEVICE_HEX_64, "requestId": DEVICE_UUID,
                 "platform": "Linux armv81"}
        stdout = ein_job_stdout("oc2", "device", json.dumps({"pending": [entry], "paired": []}))
        result = discovery.parse_ein_job_output(stdout, "device", request_id=DEVICE_UUID, target="prod")
        assert result is not None
        assert result.instance == "oc2"
        assert result.found_type == "device"
        assert result.approved is True

    def test_device_requestId_mismatch_not_found(self):
        """Fremde UUID matcht weder requestId noch deviceId → kein Fund."""
        entry = {"deviceId": DEVICE_HEX_64, "requestId": ALT_UUID}
        stdout = ein_job_stdout("oc2", "device", json.dumps({"pending": [entry], "paired": []}), found=0)
        assert discovery.parse_ein_job_output(stdout, "device", request_id=DEVICE_UUID, target="prod") is None

    def test_no_find_returns_none(self):
        stdout = ein_job_stdout(
            "oc1", "telegram", json.dumps({"channel": "telegram", "requests": []}), found=0
        )
        assert discovery.parse_ein_job_output(stdout, "telegram", request_id=TG_CODE, target="dev") is None

    def test_break_on_first_find_fixture(self):
        """Fixture: nur oc1-Blöcke → oc2 wurde nie gescannt (Break-Semantik)."""
        stdout = ein_job_stdout("oc1", "telegram", pairing_json(TG_CODE))
        assert "oc2" not in stdout
        result = discovery.parse_ein_job_output(stdout, "telegram", request_id=TG_CODE, target="dev")
        assert result.instance == "oc1"

    def test_instance_down_fail_safe(self):
        """Instanz down → leere Ausgabe → kein Fund (fail-safe)."""
        stdout = "---JSON-BEGIN:oc1:telegram---\n\n---JSON-END:oc1:telegram---\n---FOUND:0---\n"
        assert discovery.parse_ein_job_output(stdout, "telegram", request_id=TG_CODE, target="dev") is None

    def test_malformed_json_fail_safe(self):
        stdout = ein_job_stdout("oc1", "telegram", "{broken", found=0)
        assert discovery.parse_ein_job_output(stdout, "telegram", request_id=TG_CODE, target="dev") is None

    def test_approve_failure_detected(self):
        """B2 (2. Review, Blocker): Approve-Exit-Code != 0 → APPROVE-FAILED-
        Marker + FOUND=0 → approved=False, Fehler-Output bleibt sichtbar."""
        stdout = (
            json_block("oc1", "telegram", pairing_json(TG_CODE))
            + "---APPROVE-BEGIN:oc1:telegram---\n"
            + "ERROR: pairing already approved / denied\n"
            + "---APPROVE-END:oc1:telegram---\n"
            + "---APPROVE-FAILED:oc1:telegram---\n"
            + "---FOUND:0---\n"
        )
        result = discovery.parse_ein_job_output(stdout, "telegram", request_id=TG_CODE, target="dev")
        assert result is not None
        assert result.approved is False
        assert "ERROR: pairing already approved / denied" in result.approve_output

    def test_approve_failed_marker_forces_not_approved(self):
        """Auch bei inkonsistentem FOUND=1: APPROVE-FAILED-Marker → nicht approved."""
        stdout = (
            json_block("oc1", "telegram", pairing_json(TG_CODE))
            + "---APPROVE-BEGIN:oc1:telegram---\nboom\n---APPROVE-END:oc1:telegram---\n"
            + "---APPROVE-FAILED:oc1:telegram---\n"
            + "---FOUND:1---\n"
        )
        result = discovery.parse_ein_job_output(stdout, "telegram", request_id=TG_CODE, target="dev")
        assert result is not None
        assert result.approved is False

    def test_both_types_in_one_session(self):
        """R02: beide Quellen in einer Session; Fund im device-Pfad."""
        stdout = (
            json_block("oc1", "telegram", json.dumps({"channel": "telegram", "requests": []}))
            + json_block("oc1", "device", devices_json(DEVICE_UUID))
            + approve_block("oc1", "device")
            + "---FOUND:1---\n"
        )
        result = discovery.parse_ein_job_output(stdout, "both", request_id=DEVICE_UUID, target="prod")
        assert result is not None
        assert result.found_type == "device"
        assert result.instance == "oc1"
        assert result.approved is True

    def test_found_without_approve_marker(self):
        """Inkonsistenz: ID in JSON, aber kein APPROVE-Marker → approved=False."""
        stdout = ein_job_stdout("oc1", "telegram", pairing_json(TG_CODE), approve=False)
        result = discovery.parse_ein_job_output(stdout, "telegram", request_id=TG_CODE, target="dev")
        assert result is not None
        assert result.found_type == "telegram"
        assert result.approved is False

    def test_approve_output_captured(self):
        stdout = ein_job_stdout(
            "oc1", "telegram", pairing_json(TG_CODE),
            approve_output="Device QVDCXJEM approved.",
        )
        result = discovery.parse_ein_job_output(stdout, "telegram", request_id=TG_CODE, target="dev")
        assert result.approve_output == "Device QVDCXJEM approved."

    def test_scanned_reflects_blocks(self):
        """Scan-Liste = Instanzen mit JSON-Blöcken (in Reihenfolge)."""
        stdout = (
            json_block("oc1", "telegram", json.dumps({"channel": "telegram", "requests": []}))
            + json_block("oc2", "telegram", pairing_json(TG_CODE))
            + approve_block("oc2", "telegram")
            + "---FOUND:1---\n"
        )
        result = discovery.parse_ein_job_output(stdout, "telegram", request_id=TG_CODE, target="dev")
        assert result.instance == "oc2"
        assert result.scanned == ["dev/oc1", "dev/oc2"]

    def test_device_pending_only_matched(self):
        """Device-Pfad: nur pending-Einträge matchen (paired bleibt unberührt)."""
        stdout = ein_job_stdout(
            "oc1", "device",
            json.dumps({"pending": [], "paired": [{"deviceId": DEVICE_UUID}]}),
            found=0,
        )
        assert discovery.parse_ein_job_output(stdout, "device", request_id=DEVICE_UUID, target="dev") is None


# ── Whitelist-ID-Regex (§6.1.3) ──

class TestSenderIdRegex:
    """Telegram-Whitelist-ID-Format: numerisch, 6-12 Stellen."""

    def test_valid(self):
        assert bool(re.match(r"^[0-9]{6,12}$", "123456789")) is True

    def test_invalid_alpha(self):
        assert bool(re.match(r"^[0-9]{6,12}$", "abc123")) is False

    def test_empty(self):
        assert bool(re.match(r"^[0-9]{6,12}$", "")) is False


# ── run_discovery Ein-Job-Integration (§6.3, R02/R03) ──

class TestRunDiscoveryEinJob:
    def test_one_ssh_call_per_vps(self):
        """1 SSH pro VPS: Fund auf prod/oc2 → genau 2 SSH-Calls (dev+prod)."""
        calls = []

        def run_remote(ip, remote_cmd):
            calls.append(ip)
            if ip == "100.64.0.2":  # prod
                return ein_job_stdout("oc2", "device", devices_json(DEVICE_UUID))
            return ein_job_stdout("oc1", "device", devices_json("other"), found=0)

        result = discovery.run_discovery(
            MAP_DEV_PROD, DEVICE_UUID, derived_type="device",
            resolve_ip=lambda node: "100.64.0.1" if node == "vps-dev" else "100.64.0.2",
            run_remote=run_remote,
        )
        assert result.target == "prod"
        assert result.instance == "oc2"
        assert result.approved is True
        assert calls == ["100.64.0.1", "100.64.0.2"]

    def test_break_across_vps(self):
        """Fund auf dev → prod wird NICHT mehr gescannt (Break über VPS-Grenzen)."""
        calls = []

        def run_remote(ip, remote_cmd):
            calls.append(ip)
            return ein_job_stdout("oc1", "telegram", pairing_json(TG_CODE))

        result = discovery.run_discovery(
            MAP_DEV_PROD, TG_CODE, derived_type="telegram",
            resolve_ip=lambda node: "100.64.0.1",
            run_remote=run_remote,
        )
        assert (result.target, result.instance) == ("dev", "oc1")
        assert calls == ["100.64.0.1"]

    def test_unreachable_vps_skipped(self):
        """dev down → prod trotzdem gescannt; dev in unreachable-Liste."""
        calls = []

        def run_remote(ip, remote_cmd):
            calls.append(ip)
            return ein_job_stdout("oc2", "device", devices_json(DEVICE_UUID))

        result = discovery.run_discovery(
            MAP_DEV_PROD, DEVICE_UUID, derived_type="device",
            resolve_ip=lambda node: None if node == "vps-dev" else "100.64.0.2",
            run_remote=run_remote,
        )
        assert result.target == "prod"
        assert calls == ["100.64.0.2"]
        assert "vps-dev" in result.unreachable

    def test_remote_cmd_contains_approve_for_both_types(self):
        """R02: bei type=both enthält der Remote-Call beide Approve-Kommandos."""
        seen = []

        def run_remote(ip, remote_cmd):
            seen.append(remote_cmd)
            return ein_job_stdout("oc1", "telegram", pairing_json(TG_CODE))

        discovery.run_discovery(
            MAP_DEV_PROD, TG_CODE, derived_type="both",
            resolve_ip=lambda node: "100.64.0.1",
            run_remote=run_remote,
        )
        assert "openclaw pairing approve telegram" in seen[0]
        assert "openclaw devices approve" in seen[0]

    def test_discover_only_returns_found_without_approve(self):
        def run_remote(ip, remote_cmd):
            return ein_job_stdout("oc1", "telegram", pairing_json(TG_CODE), approve=False)

        result = discovery.run_discovery(
            MAP_DEV_PROD, TG_CODE, derived_type="telegram",
            resolve_ip=lambda node: "100.64.0.1",
            run_remote=run_remote,
            approve=False,
        )
        assert result.found_type == "telegram"
        assert result.approved is False

    def test_not_found_raises(self):
        with pytest.raises(discovery.RequestNotFoundError):
            discovery.run_discovery(
                MAP_DEV_PROD, TG_CODE, derived_type="telegram",
                resolve_ip=lambda node: "100.64.0.1",
                run_remote=lambda ip, cmd: ein_job_stdout("oc1", "telegram", pairing_json("ZZZZZZ"), found=0),
            )

    def test_github_output_written(self, tmp_path):
        out = tmp_path / "gh_out"
        discovery.run_discovery(
            MAP_DEV_PROD, TG_CODE, derived_type="telegram",
            resolve_ip=lambda node: "100.64.0.1",
            run_remote=lambda ip, cmd: ein_job_stdout("oc1", "telegram", pairing_json(TG_CODE)),
            github_output=str(out),
        )
        content = out.read_text(encoding="utf-8")
        assert f"request_id={TG_CODE}" in content
        assert "found_type=telegram" in content
        assert "found_instance=oc1" in content
