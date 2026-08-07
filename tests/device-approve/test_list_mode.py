"""Tests fuer den Listen-Modus v3.1 (Design 05-workflow-listen-modus.md,
Review-Befunde R01-R09).

Abgedeckt:
  - TestBuildListRemoteCmd: Telegram-/Device-/Both-Templates, KEIN Approve
    (Hard-Gate), LIST-BEGIN/END-Marker, R05 (validate_instance), R01-Regression
    (JSON-Bloecke identisch zu build_ein_job_remote_cmd)
  - TestParseListOutput: telegram+device gemischt, leere/defekte Ausgabe,
    platform-Default (R04), createdAtMs-Default, requestId-Extraktion (v3.3)
  - TestRunListDiscovery: 1 SSH pro VPS, scanned/unreachable, leere Liste ist
    KEIN Fehler, vps_ip wird gesetzt
  - TestListResultToMarkdown: Tabelle (R03 Sortierung, R04 platform "" → "—",
    v3.3 Request-ID-Spalte mit voller UUID), Leer-Fall, unreachable, Filter,
    UTC-Datum, ID-Kuerzung
  - TestListModeCli: --list-only-Flag (R02: --request-id ignoriert, keine
    Validierung), Flag-Konflikte, Exit 0 bei leerer Liste, Exit 2 bei
    fehlenden Credentials, type=auto → both (O3), --summary-Markdown
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

# Test-IDs (kalibriert an realen IDs, 2026-08-06)
TG_CODE = "QVDCXJEM"
DEVICE_UUID = "b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5"
DEVICE_HEX_64 = "9df47d697653fb4069407734e06849b342738ed3e9ec4b172402aca911925392"
# v3.3: requestId (UUID-36) ist die approve/reject-ID des pending-Eintrags
# (e2e-Beleg aee3a00); deviceId im pending[] ist der 64er-PublicKey-Hash.
DEVICE_REQUEST_ID = "21e6459c-8b1e-4c3a-9d07-0c0e1f2a3b4c"

MAP_DEV_PROD = [("oc1", "dev"), ("oc2", "dev"), ("oc1", "prod"), ("oc2", "prod")]


# ── Fixture-Builder (Marker-Format v3.1: Label = inst:typ, wie v3.0) ──


def pairing_json(code, requests=None):
    entries = requests if requests is not None else [
        {"code": code, "userId": "7145674995", "channel": "telegram"},
    ]
    return json.dumps({"channel": "telegram", "requests": entries})


def devices_json(device_id, pending=None, platform="Win32", created=1785915850624,
                  request_id=DEVICE_REQUEST_ID):
    entries = pending if pending is not None else [
        {"deviceId": device_id, "requestId": request_id, "publicKey": "abc",
         "platform": platform, "createdAtMs": created},
    ]
    return json.dumps({"pending": entries, "paired": []})


def list_stdout(blocks):
    """Listen-Remote-Ausgabe: LIST-BEGIN + JSON-Bloecke + LIST-END."""
    out = "---LIST-BEGIN---\n"
    for instance, typ, body in blocks:
        out += f"---JSON-BEGIN:{instance}:{typ}---\n{body}\n---JSON-END:{instance}:{typ}---\n"
    out += "---LIST-END---\n"
    return out


# ── build_list_remote_cmd (§4.1 + R01/R05) ──

class TestBuildListRemoteCmd:
    def test_telegram_template(self):
        cmd = discovery.build_list_remote_cmd("telegram", ["oc1", "oc2"])
        assert "echo '---LIST-BEGIN---'" in cmd
        assert "for inst in oc1 oc2; do" in cmd
        assert "openclaw pairing list telegram --json" in cmd
        assert "---JSON-BEGIN:${inst}:telegram---" in cmd
        assert "---JSON-END:${inst}:telegram---" in cmd
        assert 'echo "---LIST-END---"' in cmd
        assert "|| true" in cmd  # fail-safe bei Instanz-Down

    def test_device_template(self):
        cmd = discovery.build_list_remote_cmd("device", ["oc1"])
        assert "openclaw devices list --json" in cmd
        assert "---JSON-BEGIN:${inst}:device---" in cmd
        assert "pairing" not in cmd

    def test_both_queries_both_sources_in_one_session(self):
        """R02: type=both → pairing UND devices in DERSELBEN Session."""
        cmd = discovery.build_list_remote_cmd("both", ["oc1", "oc2"])
        assert cmd.count("for inst in oc1 oc2; do") == 1
        assert "openclaw pairing list telegram --json" in cmd
        assert "openclaw devices list --json" in cmd
        assert "---JSON-BEGIN:${inst}:telegram---" in cmd
        assert "---JSON-BEGIN:${inst}:device---" in cmd

    def test_no_approve_commands(self):
        """Hard-Gate: der Listen-Modus enthaelt NIE Approve-Befehle/Marker."""
        for typ in ("telegram", "device", "both"):
            cmd = discovery.build_list_remote_cmd(typ, ["oc1"])
            assert "approve" not in cmd
            assert "---APPROVE" not in cmd
            assert "---FOUND" not in cmd
            assert "break" not in cmd

    def test_json_blocks_identical_to_ein_job(self):
        """R01-Regression: JSON-Block-Generierung ist geteilt – die
        JSON-Begin/End-Marker + List-Cmds sind in beiden Buildern identisch
        (keine 60%-Duplikation)."""
        for typ in ("telegram", "device", "both"):
            ein_job = discovery.build_ein_job_remote_cmd(
                typ, ["oc1", "oc2"], TG_CODE if typ != "device" else DEVICE_UUID,
                approve=False,
            )
            lst = discovery.build_list_remote_cmd(typ, ["oc1", "oc2"])
            ein_lines = [l for l in ein_job.splitlines()
                         if "JSON-BEGIN" in l or "JSON-END" in l or "openclaw " in l]
            lst_lines = [l for l in lst.splitlines()
                         if "JSON-BEGIN" in l or "JSON-END" in l or "openclaw " in l]
            assert ein_lines == lst_lines, f"R01 verletzt fuer typ={typ}"

    def test_invalid_type_rejected(self):
        with pytest.raises(ValueError, match="Ungueltiger Typ"):
            discovery.build_list_remote_cmd("foobar", ["oc1"])

    def test_auto_type_rejected(self):
        """auto ist kein Remote-Typ (wird vom Aufrufer aufgeloest, O3)."""
        with pytest.raises(ValueError, match="Ungueltiger Typ"):
            discovery.build_list_remote_cmd("auto", ["oc1"])

    def test_empty_instances_rejected(self):
        with pytest.raises(ValueError, match="Keine Instanzen"):
            discovery.build_list_remote_cmd("telegram", [])

    def test_invalid_instance_rejected(self):
        """R05: Defense-in-Depth – validate_instance wie im Approve-Modus."""
        with pytest.raises(ValueError, match="Ungueltige Instanz"):
            discovery.build_list_remote_cmd("telegram", ["oc0"])
        with pytest.raises(ValueError, match="Ungueltige Instanz"):
            discovery.build_list_remote_cmd("telegram", ["oc1;rm -rf /"])

    def test_valid_instances_accepted(self):
        cmd = discovery.build_list_remote_cmd("telegram", ["oc1", "oc99"])
        assert "for inst in oc1 oc99; do" in cmd


# ── parse_list_output (§4.2 + R04) ──

class TestParseListOutput:
    def test_telegram_entries(self):
        out = list_stdout([("oc1", "telegram", pairing_json(TG_CODE))])
        entries = discovery.parse_list_output(out, "dev")
        assert len(entries) == 1
        e = entries[0]
        assert e.instance == "oc1"
        assert e.target == "dev"
        assert e.entry_type == "telegram"
        assert e.entry_id == TG_CODE

    def test_device_entries_with_platform_and_created(self):
        out = list_stdout([("oc2", "device", devices_json(DEVICE_UUID))])
        entries = discovery.parse_list_output(out, "prod")
        assert len(entries) == 1
        e = entries[0]
        assert e.entry_id == DEVICE_UUID
        assert e.platform == "Win32"
        assert e.created_at_ms == 1785915850624

    def test_device_entry_request_id_extracted(self):
        """v3.3: pending[].requestId (UUID-36) wird extrahiert – das ist die
        approve/reject-ID (e2e-Beleg aee3a00: deviceId ist der 64er-Hash)."""
        out = list_stdout([("oc2", "device", devices_json(DEVICE_UUID))])
        e = discovery.parse_list_output(out, "prod")[0]
        assert e.request_id == DEVICE_REQUEST_ID

    def test_request_id_explicit_per_entry(self):
        """v3.3: explizite requestId im pending[]-Eintrag schlaegt den Default."""
        rid = "57570237-d1f4-4b89-bf89-64bc0b9ed2ec"  # e2e-Beleg (Run 31156554728)
        out = list_stdout([("oc1", "device", json.dumps(
            {"pending": [{"deviceId": DEVICE_HEX_64, "requestId": rid,
                           "platform": "Linux"}], "paired": []}
        ))])
        e = discovery.parse_list_output(out, "dev")[0]
        assert e.request_id == rid
        assert e.entry_id == DEVICE_HEX_64

    def test_request_id_missing_defaults_empty(self):
        """v3.3: pending-Eintrag ohne requestId-Feld → "" (R04-konsistent)."""
        out = list_stdout([("oc1", "device", json.dumps(
            {"pending": [{"deviceId": DEVICE_UUID, "platform": "Linux"}],
             "paired": []}
        ))])
        e = discovery.parse_list_output(out, "dev")[0]
        assert e.request_id == ""

    def test_telegram_entry_request_id_default_empty(self):
        """v3.3: Telegram-pairing-requests haben kein requestId-Feld (ID-Feld
        dort ist `code`) → request_id "". Konsistent zur Approve-Logik
        (entry_matches_id matcht bei telegram `code`)."""
        out = list_stdout([("oc1", "telegram", pairing_json(TG_CODE))])
        e = discovery.parse_list_output(out, "dev")[0]
        assert e.entry_id == TG_CODE
        assert e.request_id == ""

    def test_mixed_both_types(self):
        out = list_stdout([
            ("oc1", "telegram", pairing_json(TG_CODE)),
            ("oc1", "device", devices_json(DEVICE_UUID)),
        ])
        entries = discovery.parse_list_output(out, "dev")
        assert [e.entry_type for e in entries] == ["telegram", "device"]
        assert [e.entry_id for e in entries] == [TG_CODE, DEVICE_UUID]

    def test_empty_output(self):
        assert discovery.parse_list_output("", "dev") == []
        assert discovery.parse_list_output("---LIST-BEGIN---\n---LIST-END---\n", "dev") == []

    def test_empty_blocks_skipped(self):
        out = list_stdout([
            ("oc1", "telegram", ""),
            ("oc2", "device", devices_json(DEVICE_UUID)),
        ])
        entries = discovery.parse_list_output(out, "dev")
        assert len(entries) == 1
        assert entries[0].instance == "oc2"

    def test_malformed_json_skipped(self):
        out = list_stdout([
            ("oc1", "telegram", "{broken"),
            ("oc2", "telegram", pairing_json(TG_CODE)),
        ])
        entries = discovery.parse_list_output(out, "dev")
        assert len(entries) == 1
        assert entries[0].instance == "oc2"

    def test_platform_default_empty(self):
        """R04: platform "" ist die Wahrheit bei Telegram (kein platform-Feld)."""
        out = list_stdout([("oc1", "telegram", pairing_json(TG_CODE))])
        e = discovery.parse_list_output(out, "dev")[0]
        assert e.platform == ""

    def test_created_at_ms_default_zero(self):
        out = list_stdout([("oc1", "telegram", json.dumps(
            {"channel": "telegram", "requests": [{"code": TG_CODE}]}
        ))])
        e = discovery.parse_list_output(out, "dev")[0]
        assert e.created_at_ms == 0

    def test_entry_without_known_id_field(self):
        out = list_stdout([("oc1", "device", json.dumps(
            {"pending": [{"foo": "bar"}], "paired": []}
        ))])
        e = discovery.parse_list_output(out, "dev")[0]
        assert e.entry_id == "?"
        assert e.request_id == ""

    def test_pending_entry_to_dict_includes_request_id(self):
        """v3.3: Listen-JSON-Schema enthaelt entries[].requestId (UUID-36)."""
        out = list_stdout([("oc2", "device", devices_json(DEVICE_UUID))])
        e = discovery.parse_list_output(out, "prod")[0]
        d = discovery.pending_entry_to_dict(e)
        assert d["requestId"] == DEVICE_REQUEST_ID
        assert d["id"] == DEVICE_UUID
        assert set(d) == {"instance", "target", "type", "id", "requestId",
                          "platform", "createdAtMs", "vps_ip"}


# ── run_list_discovery (§4.3) ──

class TestRunListDiscovery:
    def test_one_ssh_call_per_vps(self):
        calls = []

        def run_remote(ip, remote_cmd):
            calls.append(ip)
            if ip == "100.64.0.2":  # prod
                return list_stdout([("oc2", "device", devices_json(DEVICE_UUID))])
            return list_stdout([("oc1", "telegram", pairing_json(TG_CODE))])

        result = discovery.run_list_discovery(
            MAP_DEV_PROD, derived_type="both",
            resolve_ip=lambda node: "100.64.0.1" if node == "vps-dev" else "100.64.0.2",
            run_remote=run_remote,
        )
        assert calls == ["100.64.0.1", "100.64.0.2"]  # 1 SSH pro VPS
        assert len(result.entries) == 2

    def test_vps_ip_set_on_entries(self):
        def run_remote(ip, remote_cmd):
            return list_stdout([("oc1", "telegram", pairing_json(TG_CODE))])

        result = discovery.run_list_discovery(
            [("oc1", "dev")], derived_type="telegram",
            resolve_ip=lambda node: "100.64.0.1",
            run_remote=run_remote,
        )
        assert result.entries[0].vps_ip == "100.64.0.1"

    def test_unreachable_vps_skipped_and_listed(self):
        calls = []

        def run_remote(ip, remote_cmd):
            calls.append(ip)
            return list_stdout([("oc1", "telegram", pairing_json(TG_CODE))])

        result = discovery.run_list_discovery(
            MAP_DEV_PROD, derived_type="telegram",
            resolve_ip=lambda node: None if node == "vps-dev" else "100.64.0.2",
            run_remote=run_remote,
        )
        assert calls == ["100.64.0.2"]
        assert result.unreachable == ["vps-dev"]
        assert result.entries[0].target == "prod"

    def test_empty_list_is_valid(self):
        """Leere Liste = gueltiges Ergebnis (Exit 0, KEINE Exception)."""
        def run_remote(ip, remote_cmd):
            return list_stdout([("oc1", "telegram", json.dumps(
                {"channel": "telegram", "requests": []}
            ))])

        result = discovery.run_list_discovery(
            MAP_DEV_PROD, derived_type="telegram",
            resolve_ip=lambda node: "100.64.0.1",
            run_remote=run_remote,
        )
        assert result.entries == []
        assert result.scanned == ["dev/oc1", "dev/oc2", "prod/oc1", "prod/oc2"]
        assert result.unreachable == []

    def test_scanned_reflects_groups(self):
        result = discovery.run_list_discovery(
            [("oc1", "dev"), ("oc2", "dev")], derived_type="telegram",
            resolve_ip=lambda node: "100.64.0.1",
            run_remote=lambda ip, cmd: list_stdout([]),
        )
        assert result.scanned == ["dev/oc1", "dev/oc2"]

    def test_defective_remote_output_fail_safe(self):
        result = discovery.run_list_discovery(
            [("oc1", "dev")], derived_type="telegram",
            resolve_ip=lambda node: "100.64.0.1",
            run_remote=lambda ip, cmd: "garbage output without markers",
        )
        assert result.entries == []
        assert result.unreachable == []

    def test_no_approve_in_remote_cmd(self):
        """Hard-Gate: der an SSH uebergebene Remote-Cmd enthaelt keinen Approve."""
        seen = []

        def run_remote(ip, remote_cmd):
            seen.append(remote_cmd)
            return list_stdout([("oc1", "telegram", json.dumps({"channel": "telegram", "requests": []}))])

        discovery.run_list_discovery(
            MAP_DEV_PROD, derived_type="both",
            resolve_ip=lambda node: "100.64.0.1",
            run_remote=run_remote,
        )
        for cmd in seen:
            assert "approve" not in cmd
            assert "---APPROVE" not in cmd


# ── list_result_to_markdown (§5.1 + R03/R04) ──

class TestListResultToMarkdown:
    def test_table_with_entries(self):
        result = {
            "status": "list_ok",
            "entries": [
                {"instance": "oc1", "target": "dev", "type": "telegram",
                 "id": TG_CODE, "requestId": "", "platform": "",
                 "createdAtMs": 1785900000000, "vps_ip": "100.64.0.1"},
                {"instance": "oc2", "target": "prod", "type": "device",
                 "id": DEVICE_UUID, "requestId": DEVICE_REQUEST_ID,
                 "platform": "Win32", "createdAtMs": 1785915850624,
                 "vps_ip": "100.64.0.2"},
            ],
            "scanned": ["dev/oc1", "dev/oc2", "prod/oc1", "prod/oc2"],
            "unreachable": [],
            "filters_applied": {"type": "both", "target": "both", "instance": "all"},
        }
        md = summary.list_result_to_markdown(result)
        assert "## 📋 Pending-Requests — Übersicht" in md
        assert "| # | Instanz | Typ | Request-ID | ID | Platform | Erstellt |" in md
        assert "| 1 | prod/oc2 | 📱 Device |" in md  # neueste zuerst (R03)
        assert "| 2 | dev/oc1 | ✈️ Telegram |" in md
        assert "Win32" in md
        assert "Discovery-Scan" in md
        assert "Nicht erreichbar" in md
        assert "Filter" in md and "type=both" in md

    def test_request_id_column_full_guid(self):
        """v3.3: requestId (UUID-36) wird VOLL gerendert (Owner-Auftrag „GUID
        in der Liste") – bewusste Ausnahme zur ID-Kuerzung (ID-Spalte bleibt
        gekuerzt); Telegram ohne requestId → "—"."""
        result = {
            "status": "list_ok",
            "entries": [
                {"instance": "oc2", "target": "prod", "type": "device",
                 "id": DEVICE_HEX_64, "requestId": DEVICE_REQUEST_ID,
                 "platform": "Linux", "createdAtMs": 1785915850624,
                 "vps_ip": None},
                {"instance": "oc1", "target": "dev", "type": "telegram",
                 "id": TG_CODE, "requestId": "", "platform": "",
                 "createdAtMs": 1000, "vps_ip": None},
            ],
            "scanned": [], "unreachable": [], "filters_applied": {},
        }
        md = summary.list_result_to_markdown(result)
        dev_row = [l for l in md.splitlines() if l.startswith("| 1 |")][0]
        assert DEVICE_REQUEST_ID in dev_row  # GUID voll in der Tabelle
        tg_row = [l for l in md.splitlines() if l.startswith("| 2 |")][0]
        assert "| — |" in tg_row  # Telegram: keine requestId → Darstellung —

    def test_sorted_desc_by_created_at(self):
        """R03: createdAtMs DESC (neueste zuerst); Sekundaerschluessel stabil."""
        result = {
            "status": "list_ok",
            "entries": [
                {"instance": "oc1", "target": "dev", "type": "telegram",
                 "id": "OLDCODE", "platform": "", "createdAtMs": 1000, "vps_ip": None},
                {"instance": "oc2", "target": "dev", "type": "telegram",
                 "id": "NEWCODE", "platform": "", "createdAtMs": 9999, "vps_ip": None},
                {"instance": "oc1", "target": "dev", "type": "telegram",
                 "id": "MIDCODE", "platform": "", "createdAtMs": 5000, "vps_ip": None},
            ],
            "scanned": [], "unreachable": [], "filters_applied": {},
        }
        md = summary.list_result_to_markdown(result)
        assert md.index("NEWCODE") < md.index("MIDCODE") < md.index("OLDCODE")

    def test_platform_empty_renders_dash(self):
        """R04: platform "" (JSON-Wahrheit) → "—" in der Tabelle (Darstellung)."""
        result = {
            "status": "list_ok",
            "entries": [
                {"instance": "oc1", "target": "dev", "type": "telegram",
                 "id": TG_CODE, "platform": "", "createdAtMs": 1785900000000, "vps_ip": None},
            ],
            "scanned": [], "unreachable": [], "filters_applied": {},
        }
        md = summary.list_result_to_markdown(result)
        row = [l for l in md.splitlines() if l.startswith("| 1 |")][0]
        assert "| — |" in row  # Platform-Spalte zeigt —

    def test_empty_list_placeholder(self):
        result = {
            "status": "list_ok", "entries": [],
            "scanned": ["dev/oc1", "prod/oc1"],
            "unreachable": ["vps-prod"],
            "filters_applied": {"type": "both", "target": "both", "instance": "all"},
        }
        md = summary.list_result_to_markdown(result)
        assert "Keine offenen Requests" in md
        assert "| — | — | — | — | — | — | — |" in md
        assert "vps-prod" in md
        assert "Nicht erreichbar" in md

    def test_unreachable_none_rendered(self):
        result = {
            "status": "list_ok", "entries": [], "scanned": [],
            "unreachable": [], "filters_applied": {},
        }
        md = summary.list_result_to_markdown(result)
        assert "**Nicht erreichbar:** keine" in md

    def test_created_at_formatted_utc(self):
        """O2: createdAtMs → lesbares UTC-Datum (YYYY-MM-DD HH:MM)."""
        result = {
            "status": "list_ok",
            "entries": [
                {"instance": "oc1", "target": "dev", "type": "device",
                 "id": DEVICE_UUID, "platform": "Linux", "createdAtMs": 1785915850624,
                 "vps_ip": None},
            ],
            "scanned": [], "unreachable": [], "filters_applied": {},
        }
        md = summary.list_result_to_markdown(result)
        assert "2026-08-05" in md  # 1785915850624 ms UTC

    def test_created_at_zero_renders_dash(self):
        result = {
            "status": "list_ok",
            "entries": [
                {"instance": "oc1", "target": "dev", "type": "telegram",
                 "id": TG_CODE, "platform": "", "createdAtMs": 0, "vps_ip": None},
            ],
            "scanned": [], "unreachable": [], "filters_applied": {},
        }
        md = summary.list_result_to_markdown(result)
        assert "| — |" in [l for l in md.splitlines() if l.startswith("| 1 |")][0]

    def test_long_id_truncated(self):
        result = {
            "status": "list_ok",
            "entries": [
                {"instance": "oc1", "target": "dev", "type": "device",
                 "id": DEVICE_HEX_64, "requestId": DEVICE_REQUEST_ID,
                 "platform": "Linux", "createdAtMs": 1000,
                 "vps_ip": None},
            ],
            "scanned": [], "unreachable": [], "filters_applied": {},
        }
        md = summary.list_result_to_markdown(result)
        row = [l for l in md.splitlines() if l.startswith("| 1 |")][0]
        assert "…" in row
        assert DEVICE_HEX_64 not in row  # Voll-ID nur im JSON (Darstellung gekuerzt)
        # v3.3: die requestId (36 Zeichen) wird dagegen VOLL angezeigt
        assert DEVICE_REQUEST_ID in row


# ── CLI: --list-only (approve.py main, §3 + R02/O3/Exit-Codes) ──

class TestListModeCli:
    def test_list_only_conflicts_with_full_run(self):
        with pytest.raises(SystemExit) as exc:
            approve.main(["--list-only", "--full-run", "--local"])
        assert exc.value.code == 2

    def test_list_only_conflicts_with_discover_only(self):
        with pytest.raises(SystemExit) as exc:
            approve.main(["--list-only", "--discover-only", "--local"])
        assert exc.value.code == 2

    def test_list_only_with_request_id_warns_and_ignores(self, monkeypatch, capsys):
        """R02: --request-id + --list-only → Warning, id wird ignoriert
        (keine Validierung, kein Fehler)."""
        seen = []

        def fake_runner(cmd, capture_output, text, timeout):
            seen.append(cmd)
            return type("P", (), {"returncode": 0, "stdout": json.dumps(
                {"channel": "telegram", "requests": []}
            ), "stderr": ""})()

        monkeypatch.setattr(approve.subprocess, "run", fake_runner)
        rc = approve.main(["--list-only", "--request-id", "BAD$ID", "--local"])
        assert rc == 0
        err = capsys.readouterr().err
        assert "ignoriert" in err
        assert "keine Such-ID" in err
        # Die kaputte ID wurde NIE validiert/verwendet – nur Liste laeuft
        assert any("openclaw" in c and "pairing" in c for c in seen)

    def test_list_only_local_empty_exit_0(self, monkeypatch, capsys):
        """Exit-Code-Vertrag: 0 bei leerer Liste (gruener Run)."""
        def fake_runner(cmd, capture_output, text, timeout):
            return type("P", (), {"returncode": 0, "stdout": json.dumps(
                {"channel": "telegram", "requests": []}
            ), "stderr": ""})()

        monkeypatch.setattr(approve.subprocess, "run", fake_runner)
        rc = approve.main(["--list-only", "--local"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "list_ok"
        assert out["entries"] == []
        assert out["filters_applied"]["type"] == "both"  # O3: auto → both

    def test_list_only_local_with_entries(self, monkeypatch, capsys):
        def fake_runner(cmd, capture_output, text, timeout):
            if cmd[1] == "pairing":
                body = json.dumps({"channel": "telegram", "requests": [
                    {"code": TG_CODE, "userId": "7145674995"},
                ]})
            else:
                body = json.dumps({"pending": [
                    {"deviceId": DEVICE_UUID, "requestId": DEVICE_REQUEST_ID,
                     "platform": "Win32", "createdAtMs": 1785915850624},
                ], "paired": []})
            return type("P", (), {"returncode": 0, "stdout": body, "stderr": ""})()

        monkeypatch.setattr(approve.subprocess, "run", fake_runner)
        rc = approve.main(["--list-only", "--local", "--type-filter", "both"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "list_ok"
        ids = {e["id"] for e in out["entries"]}
        assert ids == {TG_CODE, DEVICE_UUID}
        # v3.3: requestId fließt ins Listen-JSON (device-Eintrag; Telegram "").
        dev = [e for e in out["entries"] if e["type"] == "device"][0]
        assert dev["requestId"] == DEVICE_REQUEST_ID
        tg = [e for e in out["entries"] if e["type"] == "telegram"][0]
        assert tg["requestId"] == ""

    def test_list_only_ssh_missing_credentials_exit_2(self, monkeypatch, capsys, tmp_path):
        """Exit 2 = Config-Fehler (fehlende Credentials) – kein SSH-Versuch."""
        mp = tmp_path / "map.txt"
        mp.write_text("oc1|dev\n", encoding="utf-8")

        def boom(*a, **k):
            raise AssertionError("fetch_tailscale_token darf nicht laufen")

        monkeypatch.setattr(approve, "fetch_tailscale_token", boom)
        rc = approve.main([
            "--list-only", "--instance-map", str(mp),
            "--type-filter", "both",
            # KEINE VPS_USER/SSH_KEY/TS_*-Credentials
        ])
        assert rc == 2
        assert "benoetigt" in capsys.readouterr().err

    def test_list_only_ssh_empty_exit_0(self, monkeypatch, capsys, tmp_path):
        """SSH-Listen-Modus: leere Antworten aller VPS → Exit 0 (gruen)."""
        mp = tmp_path / "map.txt"
        mp.write_text("oc1|dev\noc2|dev\n", encoding="utf-8")
        monkeypatch.setattr(approve, "fetch_tailscale_token", lambda cid, cs: "tok")
        monkeypatch.setattr(approve, "resolve_vps_ip", lambda tailnet, token, node: "100.64.0.1")

        def fake_remote(ip, vps_user, ssh_key, remote_cmd):
            assert "approve" not in remote_cmd  # Hard-Gate
            return "---LIST-BEGIN---\n---LIST-END---\n"

        monkeypatch.setattr(approve, "run_remote_ssh", fake_remote)
        rc = approve.main([
            "--list-only", "--instance-map", str(mp),
            "--type-filter", "both",
            "--vps-user", "deploy", "--ssh-key", "/tmp/key",
            "--ts-tailnet", "tailcfea8a.ts.net",
            "--ts-client-id", "cid", "--ts-client-secret", "csec",
        ])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "list_ok"
        assert out["entries"] == []
        assert out["scanned"] == ["dev/oc1", "dev/oc2"]

    def test_list_only_ssh_aggregates_entries(self, monkeypatch, capsys, tmp_path):
        mp = tmp_path / "map.txt"
        mp.write_text("oc1|dev\n", encoding="utf-8")
        monkeypatch.setattr(approve, "fetch_tailscale_token", lambda cid, cs: "tok")
        monkeypatch.setattr(approve, "resolve_vps_ip", lambda tailnet, token, node: "100.64.0.1")

        def fake_remote(ip, vps_user, ssh_key, remote_cmd):
            return list_stdout([("oc1", "telegram", pairing_json(TG_CODE))])

        monkeypatch.setattr(approve, "run_remote_ssh", fake_remote)
        rc = approve.main([
            "--list-only", "--instance-map", str(mp),
            "--type-filter", "both",
            "--vps-user", "deploy", "--ssh-key", "/tmp/key",
            "--ts-tailnet", "tailcfea8a.ts.net",
            "--ts-client-id", "cid", "--ts-client-secret", "csec",
        ])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["entries"][0]["id"] == TG_CODE
        assert out["entries"][0]["type"] == "telegram"

    def test_list_only_summary_writes_markdown(self, monkeypatch, tmp_path, capsys):
        """--summary: Markdown-Tabelle in $GITHUB_STEP_SUMMARY (File-Open)."""
        sm = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(sm))

        def fake_runner(cmd, capture_output, text, timeout):
            return type("P", (), {"returncode": 0, "stdout": json.dumps(
                {"channel": "telegram", "requests": [{"code": TG_CODE}]}
            ), "stderr": ""})()

        monkeypatch.setattr(approve.subprocess, "run", fake_runner)
        rc = approve.main(["--list-only", "--local", "--summary"])
        assert rc == 0
        md = sm.read_text(encoding="utf-8")
        assert "## 📋 Pending-Requests" in md
        assert TG_CODE in md

    def test_list_only_invalid_type_filter_exit_2(self, monkeypatch, capsys):
        rc = approve.main(["--list-only", "--local", "--type-filter", "foobar"])
        assert rc == 2
        assert "Ungueltiger Typ" in capsys.readouterr().err

    def test_list_only_invalid_instance_filter_exit_2(self, monkeypatch, capsys):
        rc = approve.main(["--list-only", "--local", "--instance-filter", "oc0"])
        assert rc == 2
        assert "Ungueltige Instanz" in capsys.readouterr().err

    def test_list_only_respects_filters(self, monkeypatch, capsys, tmp_path):
        """Filter target/instance greifen auch im Listen-Modus."""
        mp = tmp_path / "map.txt"
        mp.write_text("oc1|dev\noc2|prod\n", encoding="utf-8")
        calls = []
        monkeypatch.setattr(approve, "fetch_tailscale_token", lambda cid, cs: "tok")
        monkeypatch.setattr(approve, "resolve_vps_ip", lambda tailnet, token, node: "100.64.0.1")

        def fake_remote(ip, vps_user, ssh_key, remote_cmd):
            calls.append(ip)
            return "---LIST-BEGIN---\n---LIST-END---\n"

        monkeypatch.setattr(approve, "run_remote_ssh", fake_remote)
        rc = approve.main([
            "--list-only", "--instance-map", str(mp),
            "--type-filter", "both", "--target-filter", "dev",
            "--instance-filter", "all",
            "--vps-user", "deploy", "--ssh-key", "/tmp/key",
            "--ts-tailnet", "tailcfea8a.ts.net",
            "--ts-client-id", "cid", "--ts-client-secret", "csec",
        ])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["scanned"] == ["dev/oc1"]  # prod/oc2 herausgefiltert
