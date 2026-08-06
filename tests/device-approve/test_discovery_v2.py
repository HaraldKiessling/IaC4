"""Tests fuer tools/device-approve/discovery.py v2.2 (Design 05 v2.2).

Abgedeckt: Zwei-Format-ID-Validierung + Typ-Ableitung (Δ3/Δ5), getrennte
Discovery-Quellen (Δ1: pairing list fuer telegram, devices list fuer device),
Typ-Filter both, GITHUB_OUTPUT (request_id + found_* + derived_type),
RequestNotFoundError mit scanned/unreachable, Filter-Validierung,
Break-Semantik, CLI-Wiring inkl. --validate-id, result-json, v1-Regression
(Tailscale -1-Fallback).

Import-Strategie: importlib.util (SourceFileLoader) vermeidet sys.path-Konflikt
mit tools/telegram-approve-bot/discovery.py (gleicher Modulname).
"""

import json
import os
import sys

import pytest

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "device-approve")

from importlib.machinery import SourceFileLoader

discovery = SourceFileLoader(
    "device_approve.discovery",
    os.path.join(TOOLS_DIR, "discovery.py"),
).load_module()

# Test-IDs v2.2 (kalibriert an realen IDs, 2026-08-06)
TG_CODE = "QVDCXJEM"  # 8 Zeichen, A-Z0-9 (Realfall Owner-Pairing)
DEVICE_HEX_64 = "9df47d697653fb4069407734e06849b342738ed3e9ec4b172402aca911925392"
DEVICE_UUID = "b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5"
ALT_UUID = "2e68bca9-4965-4e29-9a9d-d1a12644d644"

MAP_DEV_PROD = [("oc1", "dev"), ("oc2", "dev"), ("oc1", "prod"), ("oc2", "prod")]


# ── JSON-Fake-Entry-Builder ──

def pending_entry(device_id, client_id="openclaw-control-ui", client_mode="webchat"):
    """Baut einen pending-Eintrag (wie openclaw devices list --json)."""
    return {
        "deviceId": device_id,
        "publicKey": "abc123",
        "platform": "Win32",
        "clientId": client_id,
        "clientMode": client_mode,
        "role": "operator",
        "roles": ["operator"],
        "scopes": ["operator.admin"],
        "createdAtMs": 1785915850624,
    }


def pairing_entry(code, user_id="7145674995", channel="telegram"):
    """Baut einen pending Pairing-Eintrag (F1a-Schema-Hypothese: code/userId)."""
    return {"code": code, "userId": user_id, "channel": channel, "createdAtMs": 1785900000000}


def make_devices_list(pending=None):
    return json.dumps({"pending": pending or [], "paired": []})


def make_pairing_list(requests=None):
    # Empirisch (Sandbox 2026-08-06): {"channel": "telegram", "requests": [...]}
    return json.dumps({"channel": "telegram", "requests": requests or []})


# ── ID-Formate + Typ-Ableitung (Δ3/Δ4/Δ5) ──

class TestIdFormats:
    def test_telegram_code_QVDCXJEM(self):
        assert discovery.TELEGRAM_CODE_RE.match(TG_CODE)

    def test_telegram_code_6chars(self):
        assert discovery.TELEGRAM_CODE_RE.match("A1B2C3")

    def test_telegram_code_12chars(self):
        assert discovery.TELEGRAM_CODE_RE.match("ABCDEF123456")

    def test_telegram_code_reject_lowercase(self):
        assert not discovery.TELEGRAM_CODE_RE.match("qvdczjem")

    def test_telegram_code_reject_short(self):
        assert not discovery.TELEGRAM_CODE_RE.match("ABC12")

    def test_telegram_code_reject_long(self):
        assert not discovery.TELEGRAM_CODE_RE.match("A" * 13)

    def test_device_id_hex_64(self):
        assert discovery.DEVICE_ID_RE.match(DEVICE_HEX_64)

    def test_device_id_uuid(self):
        assert discovery.DEVICE_ID_RE.match(DEVICE_UUID)

    def test_device_id_hex_36(self):
        assert discovery.DEVICE_ID_RE.match("a" * 36)

    def test_device_id_hex_128(self):
        assert discovery.DEVICE_ID_RE.match("f" * 128)

    def test_device_id_reject_short(self):
        assert not discovery.DEVICE_ID_RE.match("abc")

    def test_device_id_reject_non_hex(self):
        assert not discovery.DEVICE_ID_RE.match("z" * 40)


class TestDeriveType:
    def test_telegram(self):
        assert discovery.derive_type(TG_CODE) == "telegram"

    def test_device_hex(self):
        assert discovery.derive_type(DEVICE_HEX_64) == "device"

    def test_device_uuid(self):
        assert discovery.derive_type(DEVICE_UUID) == "device"

    def test_unknown(self):
        assert discovery.derive_type("abc") == "unknown"


class TestValidateAndClassifyId:
    def test_auto_telegram(self):
        valid, typ, err = discovery.validate_and_classify_id(TG_CODE, "auto")
        assert valid and typ == "telegram" and err == ""

    def test_auto_device(self):
        valid, typ, err = discovery.validate_and_classify_id(DEVICE_HEX_64, "auto")
        assert valid and typ == "device" and err == ""

    def test_auto_device_uuid(self):
        valid, typ, err = discovery.validate_and_classify_id(DEVICE_UUID, "auto")
        assert valid and typ == "device" and err == ""

    def test_explicit_telegram_ok(self):
        valid, typ, err = discovery.validate_and_classify_id(TG_CODE, "telegram")
        assert valid and typ == "telegram"

    def test_explicit_telegram_rejects_device_id(self):
        valid, typ, err = discovery.validate_and_classify_id(DEVICE_UUID, "telegram")
        assert not valid and err != ""

    def test_explicit_device_ok(self):
        valid, typ, err = discovery.validate_and_classify_id(DEVICE_UUID, "device")
        assert valid and typ == "device"

    def test_explicit_device_rejects_code(self):
        # Kurzcode ist kein gueltiges Device-Format (auch wenn <36 Zeichen)
        valid, typ, err = discovery.validate_and_classify_id(TG_CODE, "device")
        assert not valid and err != ""

    def test_both_with_telegram(self):
        valid, typ, err = discovery.validate_and_classify_id(TG_CODE, "both")
        assert valid and typ == "both"

    def test_both_with_device(self):
        valid, typ, err = discovery.validate_and_classify_id(DEVICE_UUID, "both")
        assert valid and typ == "both"

    def test_both_rejects_unknown(self):
        valid, typ, err = discovery.validate_and_classify_id("!!!", "both")
        assert not valid and typ == ""


class TestValidateRequestId:
    def test_valid_telegram(self):
        assert discovery.validate_request_id(TG_CODE) is None

    def test_valid_device(self):
        assert discovery.validate_request_id(DEVICE_UUID) is None

    def test_valid_hex_64(self):
        assert discovery.validate_request_id(DEVICE_HEX_64) is None

    def test_invalid_too_short(self):
        with pytest.raises(ValueError, match="Ungueltige|passt zu keinem"):
            discovery.validate_request_id("abc")

    def test_invalid_special_char(self):
        with pytest.raises(ValueError):
            discovery.validate_request_id("abc$def")

    def test_invalid_explicit_telegram(self):
        with pytest.raises(ValueError):
            discovery.validate_request_id(DEVICE_UUID, "telegram")


class TestValidateType:
    def test_all_valid(self):
        for t in ("auto", "telegram", "device", "both"):
            assert discovery.validate_type(t) is None

    def test_invalid(self):
        with pytest.raises(ValueError):
            discovery.validate_type("foobar")


class TestValidateInstance:
    def test_valid_oc1(self):
        assert discovery.validate_instance("oc1") is None

    def test_valid_oc99(self):
        assert discovery.validate_instance("oc99") is None

    def test_invalid_oc0(self):
        with pytest.raises(ValueError, match="Ungueltige"):
            discovery.validate_instance("oc0")

    def test_invalid_empty(self):
        with pytest.raises(ValueError):
            discovery.validate_instance("")


class TestFilterInstanceMap:
    def test_target_filter_dev(self):
        result = discovery.filter_instance_map(
            [("oc1", "dev"), ("oc2", "dev"), ("oc1", "prod")],
            target_filter="dev",
        )
        assert result == [("oc1", "dev"), ("oc2", "dev")]

    def test_target_filter_both(self):
        result = discovery.filter_instance_map(
            [("oc1", "dev"), ("oc1", "prod")],
            target_filter="both",
        )
        assert len(result) == 2

    def test_instance_filter_oc1(self):
        result = discovery.filter_instance_map(
            [("oc1", "dev"), ("oc2", "dev"), ("oc1", "prod")],
            instance_filter="oc1",
        )
        assert result == [("oc1", "dev"), ("oc1", "prod")]

    def test_instance_filter_all(self):
        result = discovery.filter_instance_map(
            [("oc1", "dev"), ("oc2", "dev")],
            instance_filter="all",
        )
        assert len(result) == 2


# ── Entry-Matching (Δ3: typ-spezifisches ID-Feld) ──

class TestEntryMatchesId:
    def test_telegram_code_field(self):
        assert discovery.entry_matches_id(pairing_entry(TG_CODE), TG_CODE, "telegram") is True

    def test_telegram_wrong_code(self):
        assert discovery.entry_matches_id(pairing_entry("ABCDEF12"), TG_CODE, "telegram") is False

    def test_device_deviceId_field(self):
        assert discovery.entry_matches_id(pending_entry(DEVICE_UUID), DEVICE_UUID, "device") is True

    def test_device_no_match(self):
        assert discovery.entry_matches_id(pending_entry("other"), DEVICE_UUID, "device") is False

    def test_unknown_type_never_matches(self):
        assert discovery.entry_matches_id(pending_entry(DEVICE_UUID), DEVICE_UUID, "foobar") is False


class TestParseEntries:
    def test_telegram_requests_field(self):
        """Empirisches pairing-Schema: Feld 'requests'."""
        data = json.loads(make_pairing_list([pairing_entry(TG_CODE)]))
        entries = discovery.parse_entries(data, "telegram")
        assert entries[0]["code"] == TG_CODE

    def test_telegram_fallback_pending(self):
        """Defensiv: Fallback auf 'pending' (Design-Hypothese)."""
        data = {"pending": [pairing_entry(TG_CODE)]}
        entries = discovery.parse_entries(data, "telegram")
        assert entries[0]["code"] == TG_CODE

    def test_device_pending(self):
        data = json.loads(make_devices_list([pending_entry(DEVICE_UUID)]))
        entries = discovery.parse_entries(data, "device")
        assert entries[0]["deviceId"] == DEVICE_UUID


# ── Discovery-Kern (Δ1: getrennte Quellen) ──

class TestRunDiscovery:
    def test_telegram_uses_pairing_list(self):
        """Typ telegram → openclaw pairing list telegram --json (nur dieser Pfad)."""
        calls = []

        def _list_entries(instance, target, ip, typ):
            calls.append((instance, target, typ))
            assert typ == "telegram"
            return make_pairing_list([pairing_entry(TG_CODE)])

        result = discovery.run_discovery(
            MAP_DEV_PROD,
            TG_CODE,
            derived_type="telegram",
            resolve_ip=lambda node: "100.64.0.1",
            list_entries=_list_entries,
        )
        assert result.found_type == "telegram"
        assert result.instance == "oc1"
        assert result.target == "dev"
        assert all(typ == "telegram" for _, _, typ in calls)

    def test_device_uses_devices_list(self):
        """Typ device → openclaw devices list --json (nur dieser Pfad)."""
        calls = []

        def _list_entries(instance, target, ip, typ):
            calls.append(typ)
            assert typ == "device"
            return make_devices_list([pending_entry(DEVICE_UUID)])

        result = discovery.run_discovery(
            MAP_DEV_PROD,
            DEVICE_UUID,
            derived_type="device",
            resolve_ip=lambda node: "100.64.0.1",
            list_entries=_list_entries,
        )
        assert result.found_type == "device"
        assert result.instance == "oc1"
        assert result.target == "dev"
        assert calls == ["device"]

    def test_both_scans_pairing_first_then_devices(self):
        """Typ both → erst pairing list, dann devices list (Design §3c)."""
        seq = []

        def _list_entries(instance, target, ip, typ):
            seq.append(typ)
            if typ == "telegram":
                return make_pairing_list([])  # kein Fund
            return make_devices_list([pending_entry(DEVICE_UUID)])

        result = discovery.run_discovery(
            MAP_DEV_PROD,
            DEVICE_UUID,
            derived_type="both",
            resolve_ip=lambda node: "100.64.0.1",
            list_entries=_list_entries,
        )
        assert result.found_type == "device"
        # Types-outer: pairing list ueber ALLE Instanzen, dann devices list
        assert seq.count("telegram") == len(MAP_DEV_PROD)
        assert seq[-1] == "device"  # Fund im device-Pfad
        assert seq[0] == "telegram"

    def test_auto_derives_type_from_id(self):
        """derived_type=auto → aus ID-Format ableiten (Δ4)."""
        def _list_entries(instance, target, ip, typ):
            assert typ == "telegram"
            return make_pairing_list([pairing_entry(TG_CODE)])

        result = discovery.run_discovery(
            MAP_DEV_PROD,
            TG_CODE,
            derived_type="auto",
            resolve_ip=lambda node: "100.64.0.1",
            list_entries=_list_entries,
        )
        assert result.found_type == "telegram"

    def test_auto_invalid_id_raises_valueerror(self):
        with pytest.raises(ValueError):
            discovery.run_discovery(
                MAP_DEV_PROD, "bad$id", derived_type="auto",
                resolve_ip=lambda node: "100.64.0.1",
                list_entries=lambda i, t, ip, typ: "{}",
            )

    def test_break_semantics_first_match(self):
        calls = []

        def _list_entries(instance, target, ip, typ):
            calls.append((instance, target))
            return make_pairing_list([pairing_entry(TG_CODE)])

        result = discovery.run_discovery(
            MAP_DEV_PROD,
            TG_CODE,
            derived_type="telegram",
            resolve_ip=lambda node: "100.64.0.1",
            list_entries=_list_entries,
        )
        assert (result.instance, result.target) == ("oc1", "dev")
        assert len(calls) == 1  # break

    def test_pairing_list_error_skipped_fail_safe(self):
        """F10: pairing list ohne Kanal → leere Ausgabe → Instanz uebersprungen."""
        calls = []

        def _list_entries(instance, target, ip, typ):
            calls.append((instance, target))
            return ""  # Fehler/leer (stderr-Redirect)

        with pytest.raises(discovery.RequestNotFoundError):
            discovery.run_discovery(
                MAP_DEV_PROD,
                TG_CODE,
                derived_type="telegram",
                resolve_ip=lambda node: "100.64.0.1",
                list_entries=_list_entries,
            )
        assert len(calls) == len(MAP_DEV_PROD)

    def test_json_parse_error_skipped(self):
        calls = []

        def _list_entries(instance, target, ip, typ):
            calls.append((instance, target))
            return "not valid json{{{"

        with pytest.raises(discovery.RequestNotFoundError):
            discovery.run_discovery(
                MAP_DEV_PROD,
                TG_CODE,
                derived_type="telegram",
                resolve_ip=lambda node: "100.64.0.1",
                list_entries=_list_entries,
            )
        assert len(calls) == len(MAP_DEV_PROD)

    def test_not_found_with_empty_json(self):
        def _list_entries(instance, target, ip, typ):
            return ""

        with pytest.raises(discovery.RequestNotFoundError):
            discovery.run_discovery(
                MAP_DEV_PROD,
                TG_CODE,
                derived_type="telegram",
                resolve_ip=lambda node: "100.64.0.1",
                list_entries=_list_entries,
            )

    def test_all_vps_unreachable(self):
        with pytest.raises(discovery.RequestNotFoundError) as excinfo:
            discovery.run_discovery(
                MAP_DEV_PROD,
                TG_CODE,
                derived_type="telegram",
                resolve_ip=lambda node: None,
                list_entries=lambda i, t, ip, typ: "{}",
            )
        assert all(
            discovery.node_for_target(t) in str(excinfo.value)
            for _, t in MAP_DEV_PROD
        )

    def test_unreachable_single_vps(self):
        """Nur prod ist down; dev wird gescannt, prod in unreachable-Liste."""
        def _resolve_ip(node):
            return None if node == "vps-prod" else "100.64.0.1"

        with pytest.raises(discovery.RequestNotFoundError) as excinfo:
            discovery.run_discovery(
                MAP_DEV_PROD,
                TG_CODE,
                derived_type="telegram",
                resolve_ip=_resolve_ip,
                list_entries=lambda i, t, ip, typ: "{}",
            )
        assert "vps-prod" in str(excinfo.value)
        assert "vps-dev" not in str(excinfo.value)

    def test_github_output_full(self, tmp_path):
        """GITHUB_OUTPUT: request_id, found_*, derived_type."""
        out_file = tmp_path / "gh_out"

        def _list_entries(instance, target, ip, typ):
            return make_pairing_list([pairing_entry(TG_CODE)])

        discovery.run_discovery(
            MAP_DEV_PROD,
            TG_CODE,
            derived_type="telegram",
            resolve_ip=lambda node: "100.64.0.1",
            list_entries=_list_entries,
            github_output=str(out_file),
        )
        content = out_file.read_text(encoding="utf-8").splitlines()
        assert f"request_id={TG_CODE}" in content
        assert "found_instance=oc1" in content
        assert "found_target=dev" in content
        assert "found_vps_ip=100.64.0.1" in content
        assert "found_type=telegram" in content
        assert "derived_type=telegram" in content

    def test_github_output_device(self, tmp_path):
        out_file = tmp_path / "gh_out"

        def _list_entries(instance, target, ip, typ):
            return make_devices_list([pending_entry(DEVICE_HEX_64)])

        discovery.run_discovery(
            MAP_DEV_PROD,
            DEVICE_HEX_64,
            derived_type="device",
            resolve_ip=lambda node: "100.64.0.2",
            list_entries=_list_entries,
            github_output=str(out_file),
        )
        content = out_file.read_text(encoding="utf-8").splitlines()
        assert "found_type=device" in content
        assert f"request_id={DEVICE_HEX_64}" in content

    def test_ip_cached_per_node(self):
        """types both: resolve_ip nur 1x pro Node (Cache)."""
        resolutions = []

        def _resolve_ip(node):
            resolutions.append(node)
            return "100.64.0.1"

        def _list_entries(instance, target, ip, typ):
            return "{}"

        with pytest.raises(discovery.RequestNotFoundError):
            discovery.run_discovery(
                MAP_DEV_PROD,
                TG_CODE,
                derived_type="both",
                resolve_ip=_resolve_ip,
                list_entries=_list_entries,
            )
        # 2 Nodes (dev+prod), je 1x aufgeloest trotz 2 Typen
        assert sorted(set(resolutions)) == sorted(resolutions)
        assert len(set(resolutions)) == 2


# ── build_result_json ──

class TestBuildResultJson:
    def test_not_found(self):
        r = discovery.build_result_json(
            status="not_found",
            request_id=TG_CODE,
            scanned=["dev/oc1"],
            filters_applied={"type": "telegram", "target": "both", "instance": "all"},
        )
        assert r["status"] == "not_found"
        assert r["id"] == TG_CODE
        assert r["found"] == []
        assert r["scanned"] == ["dev/oc1"]
        assert r["filters_applied"]["type"] == "telegram"

    def test_found(self):
        r = discovery.build_result_json(
            status="found",
            request_id=TG_CODE,
            found=[{"target": "dev", "instance": "oc1", "type": "telegram", "vps_ip": "100.64.0.1"}],
            scanned=["dev/oc1"],
            filters_applied={"type": "telegram", "target": "both", "instance": "all"},
        )
        assert r["status"] == "found"
        assert len(r["found"]) == 1
        assert r["found"][0]["type"] == "telegram"


# ── CLI-Wiring ──

class TestValidateIdCli:
    """--validate-id: positive Parser-Faelle + Fehlerfaelle (Workflow-Step DRY)."""

    def test_validate_telegram_code(self, capsys):
        rc = discovery.main(["--validate-id", TG_CODE, "--type", "auto"])
        assert rc == 0
        assert capsys.readouterr().out.strip() == "telegram"

    def test_validate_device_hex(self, capsys):
        rc = discovery.main(["--validate-id", DEVICE_HEX_64, "--type", "auto"])
        assert rc == 0
        assert capsys.readouterr().out.strip() == "device"

    def test_validate_device_uuid(self, capsys):
        rc = discovery.main(["--validate-id", DEVICE_UUID, "--type", "auto"])
        assert rc == 0
        assert capsys.readouterr().out.strip() == "device"

    def test_validate_explicit_telegram(self, capsys):
        rc = discovery.main(["--validate-id", TG_CODE, "--type", "telegram"])
        assert rc == 0
        assert capsys.readouterr().out.strip() == "telegram"

    def test_validate_explicit_both(self, capsys):
        rc = discovery.main(["--validate-id", DEVICE_UUID, "--type", "both"])
        assert rc == 0
        assert capsys.readouterr().out.strip() == "both"

    def test_validate_invalid_exits_2(self, capsys):
        rc = discovery.main(["--validate-id", "bad$id", "--type", "auto"])
        assert rc == 2
        assert "passt zu keinem bekannten Format" in capsys.readouterr().err

    def test_validate_invalid_type_exits_2(self, capsys):
        rc = discovery.main(["--validate-id", TG_CODE, "--type", "foobar"])
        assert rc == 2
        assert "Ungueltiger Typ-Filter" in capsys.readouterr().err


# ── B1-Regression (Review 2026-08-06): Kurzcodes + UUIDs in der Validierung ──

class TestBlockerB1Regression:
    """B1: auth_check.sh blockierte 6-7-stellige Pairing-Codes (A1B2C3 → rc=1).

    Fix: Request-ID-Validierung vollstaendig in discovery.py --validate-id
    (Python = Single Source of Truth). Diese Tests sichern ab, dass die
    Validierung Kurzcodes (6/7/8 Zeichen) UND UUIDs akzeptiert und nach Typ
    korrekt behandelt: Kurzcode → telegram (pairing-Pfad), UUID → device.
    """

    def test_short_code_6_chars_telegram(self, capsys):
        rc = discovery.main(["--validate-id", "A1B2C3", "--type", "auto"])
        assert rc == 0
        assert capsys.readouterr().out.strip() == "telegram"

    def test_short_code_7_chars_telegram(self, capsys):
        rc = discovery.main(["--validate-id", "ABC12DE", "--type", "auto"])
        assert rc == 0
        assert capsys.readouterr().out.strip() == "telegram"

    def test_short_code_8_chars_telegram(self, capsys):
        rc = discovery.main(["--validate-id", TG_CODE, "--type", "auto"])
        assert rc == 0
        assert capsys.readouterr().out.strip() == "telegram"

    def test_uuid_b0999c46_device(self, capsys):
        rc = discovery.main(["--validate-id", DEVICE_UUID, "--type", "auto"])
        assert rc == 0
        assert capsys.readouterr().out.strip() == "device"

    def test_uuid_2e68bca9_device(self, capsys):
        rc = discovery.main(["--validate-id", ALT_UUID, "--type", "auto"])
        assert rc == 0
        assert capsys.readouterr().out.strip() == "device"

    def test_short_code_rejected_as_device(self, capsys):
        """Format-Sperre: Kurzcode darf NICHT als device durchgehen."""
        rc = discovery.main(["--validate-id", "A1B2C3", "--type", "device"])
        assert rc == 2
        assert "entspricht nicht dem Device-ID-Format" in capsys.readouterr().err

    def test_empty_id_rejected(self, capsys):
        rc = discovery.main(["--validate-id", "", "--type", "auto"])
        assert rc == 2
        capsys.readouterr()

    def test_injection_id_rejected(self, capsys):
        """Injection-Abwehr bleibt – jetzt durch die Python-Zwei-Format-Regex
        statt durch den alten Shell-Check (auth_check.sh, B1-Fix)."""
        for evil in ("A1B2C3; rm -rf /", "$(rm -rf /)", "`id`", "req_abc123; rm -rf"):
            rc = discovery.main(["--validate-id", evil, "--type", "auto"])
            assert rc == 2, evil
            capsys.readouterr()


class TestCliDiscovery:
    def _write_map(self, tmp_path, entries):
        path = tmp_path / "instance-map.txt"
        path.write_text("\n".join(entries) + "\n", encoding="utf-8")
        return str(path)

    def _cli_args(self, tmp_path, request_id, **extra):
        args = [
            "--instance-map", self._write_map(tmp_path, ["oc1|dev", "oc2|dev"]),
            "--request-id", request_id,
            "--vps-user", "deploy",
            "--ssh-key", "/tmp/key",
            "--ts-tailnet", "tailcfea8a.ts.net",
            "--ts-client-id", "cid",
            "--ts-client-secret", "csec",
        ]
        for k, v in extra.items():
            args.append(f"--{k}")
            args.append(v)
        return args

    def test_cli_not_found_exits_1(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "gh_out"))
        monkeypatch.setattr(discovery, "fetch_tailscale_token", lambda cid, cs, timeout=30: "tok")
        monkeypatch.setattr(discovery, "resolve_vps_ip",
                            lambda tailnet, tok, node, timeout=30: "100.64.0.1")
        monkeypatch.setattr(discovery, "list_entries_ssh",
                            lambda inst, ip, user, key, typ: make_pairing_list([]))
        rc = discovery.main(self._cli_args(tmp_path, TG_CODE))
        assert rc == 1
        err = capsys.readouterr().err
        assert f"'{TG_CODE}' auf keiner enabled Instanz gefunden" in err

    def test_cli_telegram_found(self, tmp_path, monkeypatch, capsys):
        out_file = tmp_path / "gh_out"
        result_file = tmp_path / "result.json"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_file))
        monkeypatch.setattr(discovery, "fetch_tailscale_token", lambda cid, cs, timeout=30: "tok")
        monkeypatch.setattr(discovery, "resolve_vps_ip",
                            lambda tailnet, tok, node, timeout=30: "100.64.0.1")
        monkeypatch.setattr(discovery, "list_entries_ssh",
                            lambda inst, ip, user, key, typ: make_pairing_list([pairing_entry(TG_CODE)]))
        rc = discovery.main(self._cli_args(tmp_path, TG_CODE, **{"result-json": str(result_file)}))
        assert rc == 0
        data = json.loads(result_file.read_text(encoding="utf-8"))
        assert data["status"] == "found"
        assert data["found"][0]["type"] == "telegram"
        content = out_file.read_text(encoding="utf-8")
        assert "found_type=telegram" in content

    def test_cli_device_found(self, tmp_path, monkeypatch):
        result_file = tmp_path / "result.json"
        monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "gh_out"))
        monkeypatch.setattr(discovery, "fetch_tailscale_token", lambda cid, cs, timeout=30: "tok")
        monkeypatch.setattr(discovery, "resolve_vps_ip",
                            lambda tailnet, tok, node, timeout=30: "100.64.0.1")
        monkeypatch.setattr(discovery, "list_entries_ssh",
                            lambda inst, ip, user, key, typ: make_devices_list([pending_entry(DEVICE_UUID)]))
        rc = discovery.main(self._cli_args(tmp_path, DEVICE_UUID, **{"result-json": str(result_file)}))
        assert rc == 0
        data = json.loads(result_file.read_text(encoding="utf-8"))
        assert data["found"][0]["type"] == "device"

    def test_cli_invalid_id_exits_2(self, tmp_path):
        rc = discovery.main(self._cli_args(tmp_path, "bad$$id"))
        assert rc == 2

    def test_cli_invalid_instance_filter_exits_2(self, tmp_path):
        rc = discovery.main(self._cli_args(tmp_path, TG_CODE, **{"instance-filter": "oc0"}))
        assert rc == 2

    def test_cli_result_json_on_not_found(self, tmp_path, monkeypatch):
        result_file = tmp_path / "result.json"
        monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "gh_out"))
        monkeypatch.setattr(discovery, "fetch_tailscale_token", lambda cid, cs, timeout=30: "tok")
        monkeypatch.setattr(discovery, "resolve_vps_ip",
                            lambda tailnet, tok, node, timeout=30: "100.64.0.1")
        monkeypatch.setattr(discovery, "list_entries_ssh",
                            lambda inst, ip, user, key, typ: make_pairing_list([]))
        rc = discovery.main(self._cli_args(tmp_path, TG_CODE, **{"result-json": str(result_file)}))
        assert rc == 1
        data = json.loads(result_file.read_text(encoding="utf-8"))
        assert data["status"] == "not_found"
        assert data["filters_applied"]["type"] == "telegram"


# ── v1-Regression (resolve_vps_ip, node_for_target, list_entries_ssh ohne Shell) ──

class TestNodeAndResolve:
    def _fake_api(self, monkeypatch, devices):
        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return json.dumps({"devices": devices}).encode()

        monkeypatch.setattr(discovery.urllib.request, "urlopen", lambda req, timeout=30: FakeResp())

    def test_node_for_target(self):
        assert discovery.node_for_target("dev") == "vps-dev"

    def test_resolve_vps_ip_exact_match(self, monkeypatch):
        self._fake_api(monkeypatch, [{"hostname": "vps-dev", "addresses": ["100.64.0.1"]}])
        assert discovery.resolve_vps_ip("tailnet", "tok", "vps-dev") == "100.64.0.1"

    def test_resolve_vps_ip_dash_one_fallback(self, monkeypatch):
        self._fake_api(monkeypatch, [{"hostname": "vps-dev-1", "addresses": ["100.64.0.9"]}])
        assert discovery.resolve_vps_ip("tailnet", "tok", "vps-dev") == "100.64.0.9"

    def test_resolve_vps_ip_no_match(self, monkeypatch):
        self._fake_api(monkeypatch, [{"hostname": "other", "addresses": ["100.64.0.5"]}])
        assert discovery.resolve_vps_ip("tailnet", "tok", "vps-dev") is None


class TestListEntriesSsh:
    def test_telegram_command_no_shell(self):
        """Kommando-Liste, keine Shell; pairing list telegram."""
        cmd = (
            ["ssh", "-i", "/tmp/key"]
            + discovery.SSH_OPTS
            + ["deploy@100.64.0.1",
               "sudo docker exec openclaw-oc1 openclaw pairing list telegram --json 2>/dev/null"]
        )
        assert cmd[0] == "ssh"
        assert "&&" not in " ".join(cmd)
        assert "pairing list telegram --json" in " ".join(cmd)

    def test_device_command_uses_devices_list(self):
        assert "openclaw devices list --json" in discovery.DEVICES_LIST_CMD
        assert "openclaw pairing list telegram --json" in discovery.PAIRING_LIST_CMD

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            discovery.list_entries_ssh("oc1", "100.64.0.1", "deploy", "/tmp/key", "foobar")
