"""Tests fuer tools/telegram-approve-bot/discovery.py (Design 05, D1 – Nachtrag 2026-08-06).

Abgedeckt: 'ID auf Instanz X gefunden -> target/instance korrekt abgeleitet',
'ID auf keiner Instanz gefunden -> klare Fehlermeldung (exit 1)', UNREACHABLE-
Sammlung, Break-Semantik (erster Fund), GITHUB_OUTPUT-Schreiben, CLI-Wiring.
Alle Netzwerk-/SSH-Calls sind gemockt – KEINE echten Tailscale-/SSH-Calls.
"""

import os
import sys

import pytest

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "telegram-approve-bot")
sys.path.insert(0, os.path.abspath(TOOLS_DIR))

import discovery  # noqa: E402

# Realfall 2026-08-06 (Orchestrator): ID war auf dem lokalen Gateway nicht pending.
REAL_REQUEST_ID = "b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5"

MAP_DEV_PROD = [("oc1", "dev"), ("oc2", "dev"), ("oc1", "prod"), ("oc2", "prod")]


def dev_list(request_id):
    """Fetcher-Fake: oc1/dev enthaelt request_id, alle anderen leer."""

    def _list_devices(instance, target, ip):
        if instance == "oc1" and target == "dev":
            return f"pending: [{request_id}]"
        return "pending: []"

    return _list_devices


class TestRunDiscovery:
    def test_found_on_instance_derives_target_and_instance(self):
        """ID auf Instanz X -> (instance, target, vps_ip) korrekt abgeleitet."""
        result = discovery.run_discovery(
            MAP_DEV_PROD,
            REAL_REQUEST_ID,
            resolve_ip=lambda node: "100.64.0.1" if node == "vps-dev" else "100.64.0.2",
            list_devices=dev_list(REAL_REQUEST_ID),
        )
        assert result == ("oc1", "dev", "100.64.0.1")

    def test_found_on_later_instance(self):
        """ID liegt auf prod/oc2 -> prod wird abgeleitet (nicht das erste Element)."""

        def _list_devices(instance, target, ip):
            return f"pending: [{REAL_REQUEST_ID}]" if (instance, target) == ("oc2", "prod") else "pending: []"

        result = discovery.run_discovery(
            MAP_DEV_PROD,
            REAL_REQUEST_ID,
            resolve_ip=lambda node: "100.64.0.2",
            list_devices=_list_devices,
        )
        assert result == ("oc2", "prod", "100.64.0.2")

    def test_first_match_wins_break_semantics(self):
        """ID auf mehreren Instanzen -> erster Fund im Map-Order gewinnt (break)."""
        calls = []

        def _list_devices(instance, target, ip):
            calls.append((instance, target))
            return f"pending: [{REAL_REQUEST_ID}]"

        result = discovery.run_discovery(
            MAP_DEV_PROD,
            REAL_REQUEST_ID,
            resolve_ip=lambda node: "100.64.0.1",
            list_devices=_list_devices,
        )
        assert result[0:2] == ("oc1", "dev")
        assert calls == [("oc1", "dev")]  # Loop abgebrochen, prod nie gescannt

    def test_not_found_anywhere_raises_clear_error(self):
        """ID auf keiner Instanz -> RequestNotFoundError mit klarer Meldung."""
        with pytest.raises(discovery.RequestNotFoundError) as excinfo:
            discovery.run_discovery(
                MAP_DEV_PROD,
                REAL_REQUEST_ID,
                resolve_ip=lambda node: "100.64.0.1",
                list_devices=lambda instance, target, ip: "pending: []",
            )
        assert REAL_REQUEST_ID in str(excinfo.value)
        assert "auf keiner enabled Instanz gefunden" in str(excinfo.value)
        assert "keine" in str(excinfo.value)  # UNREACHABLE leer -> 'keine'

    def test_unreachable_vps_collected_in_error(self):
        """VPS down (resolve_ip -> None) -> Node in Fehlermeldung (Minor #15)."""

        def _resolve_ip(node):
            return "100.64.0.1" if node == "vps-dev" else None  # vps-prod down

        with pytest.raises(discovery.RequestNotFoundError) as excinfo:
            discovery.run_discovery(
                MAP_DEV_PROD,
                REAL_REQUEST_ID,
                resolve_ip=_resolve_ip,
                list_devices=lambda instance, target, ip: "pending: []",
            )
        assert "vps-prod" in str(excinfo.value)
        assert "Übersprungen (VPS down): vps-prod" in str(excinfo.value)

    def test_unreachable_skipped_and_scan_continues(self):
        """VPS down wird uebersprungen, Fund auf anderem VPS trotzdem gefunden."""

        def _resolve_ip(node):
            return None if node == "vps-dev" else "100.64.0.2"

        def _list_devices(instance, target, ip):
            return f"pending: [{REAL_REQUEST_ID}]" if target == "prod" else "pending: []"

        result = discovery.run_discovery(
            MAP_DEV_PROD,
            REAL_REQUEST_ID,
            resolve_ip=_resolve_ip,
            list_devices=_list_devices,
        )
        assert result == ("oc1", "prod", "100.64.0.2")

    def test_substring_match_is_literal_no_regex_overmatch(self):
        """Substring-Match literal: '.' in der ID matcht kein beliebiges Zeichen."""
        map_one = [("oc1", "dev")]
        # Liste enthaelt 'b0999c46Xebe3...' (X statt '-') -> darf NICHT matchen.
        with pytest.raises(discovery.RequestNotFoundError):
            discovery.run_discovery(
                map_one,
                REAL_REQUEST_ID,
                resolve_ip=lambda node: "100.64.0.1",
                list_devices=lambda instance, target, ip: "pending: [b0999c46Xebe3-4c46-a72b-8b0a7c1df2d5]",
            )

    def test_github_output_written(self, tmp_path):
        """GITHUB_OUTPUT-Datei bekommt found_*-Zeilen (Workflow-Contract)."""
        out_file = tmp_path / "github_output"
        discovery.run_discovery(
            MAP_DEV_PROD,
            REAL_REQUEST_ID,
            resolve_ip=lambda node: "100.64.0.1",
            list_devices=dev_list(REAL_REQUEST_ID),
            github_output=str(out_file),
        )
        content = out_file.read_text(encoding="utf-8").splitlines()
        assert content == [
            "found_instance=oc1",
            "found_target=dev",
            "found_vps_ip=100.64.0.1",
        ]

    def test_empty_instance_map_not_found(self):
        with pytest.raises(discovery.RequestNotFoundError) as excinfo:
            discovery.run_discovery(
                [], REAL_REQUEST_ID, resolve_ip=lambda n: "1.2.3.4",
                list_devices=lambda i, t, ip: "pending: []",
            )
        assert "keiner enabled Instanz" in str(excinfo.value)


class TestNodeAndResolve:
    def _fake_api(self, monkeypatch, devices):
        """Mockt die Tailscale-API und liefert die uebergebene Device-Liste."""
        import json as _json

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return _json.dumps({"devices": devices}).encode()

        monkeypatch.setattr(discovery.urllib.request, "urlopen", lambda req, timeout=30: FakeResp())

    def test_node_for_target(self):
        assert discovery.node_for_target("dev") == "vps-dev"
        assert discovery.node_for_target("prod") == "vps-prod"

    def test_resolve_vps_ip_exact_match(self, monkeypatch):
        self._fake_api(monkeypatch, [{"hostname": "vps-dev", "addresses": ["100.64.0.1"]}])
        assert discovery.resolve_vps_ip("tailnet", "tok", "vps-dev", timeout=5) == "100.64.0.1"

    def test_resolve_vps_ip_dash_one_fallback(self, monkeypatch):
        """Major #6: Hostname mit '-1'-Suffix wird gefunden."""
        self._fake_api(monkeypatch, [{"hostname": "vps-dev-1", "addresses": ["100.64.0.9"]}])
        assert discovery.resolve_vps_ip("tailnet", "tok", "vps-dev", timeout=5) == "100.64.0.9"

    def test_resolve_vps_ip_first_match_in_api_order(self, monkeypatch):
        """jq-aquivalent: erster Treffer in API-Reihenfolge gewinnt (exakt ODER '-1')."""
        self._fake_api(
            monkeypatch,
            [
                {"hostname": "vps-dev-1", "addresses": ["100.64.0.9"]},
                {"hostname": "vps-dev", "addresses": ["100.64.0.1"]},
            ],
        )
        assert discovery.resolve_vps_ip("tailnet", "tok", "vps-dev", timeout=5) == "100.64.0.9"

    def test_resolve_vps_ip_no_addresses(self, monkeypatch):
        self._fake_api(monkeypatch, [{"hostname": "vps-dev", "addresses": []}])
        assert discovery.resolve_vps_ip("tailnet", "tok", "vps-dev", timeout=5) is None

    def test_resolve_vps_ip_not_found(self, monkeypatch):
        self._fake_api(monkeypatch, [{"hostname": "vps-other", "addresses": ["100.64.0.5"]}])
        assert discovery.resolve_vps_ip("tailnet", "tok", "vps-dev", timeout=5) is None


class TestCli:
    def _write_map(self, tmp_path, entries):
        path = tmp_path / "instance-map.txt"
        path.write_text("\n".join(entries) + "\n", encoding="utf-8")
        return str(path)

    def test_cli_found_writes_github_output(self, tmp_path, monkeypatch, capsys):
        """CLI-Wiring: Fund -> exit 0, found_*-Zeilen in GITHUB_OUTPUT, Log auf stderr."""
        out_file = tmp_path / "gh_output"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_file))
        monkeypatch.setattr(
            discovery, "fetch_tailscale_token", lambda cid, cs, timeout=30: "tok"
        )
        monkeypatch.setattr(discovery, "resolve_vps_ip", lambda tailnet, tok, node, timeout=30: "100.64.0.1")
        monkeypatch.setattr(
            discovery, "list_devices_ssh",
            lambda instance, ip, user, key: f"pending: [{REAL_REQUEST_ID}]" if instance == "oc1" else "pending: []",
        )
        rc = discovery.main([
            "--instance-map", self._write_map(tmp_path, ["oc1|dev", "oc2|dev"]),
            "--request-id", REAL_REQUEST_ID,
            "--vps-user", "deploy",
            "--ssh-key", "/tmp/key",
            "--ts-tailnet", "tailcfea8a.ts.net",
            "--ts-client-id", "cid",
            "--ts-client-secret", "csecret",
        ])
        assert rc == 0
        assert out_file.read_text(encoding="utf-8").splitlines() == [
            "found_instance=oc1",
            "found_target=dev",
            "found_vps_ip=100.64.0.1",
        ]
        err = capsys.readouterr().err
        assert "Suche in dev/oc1" in err
        assert "gefunden" in err

    def test_cli_not_found_exits_1_with_clear_message(self, tmp_path, monkeypatch, capsys):
        """CLI-Wiring: kein Fund -> exit 1, klare Fehlermeldung mit UNREACHABLE."""
        monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "gh_out"))
        monkeypatch.setattr(discovery, "fetch_tailscale_token", lambda cid, cs, timeout=30: "tok")
        monkeypatch.setattr(discovery, "resolve_vps_ip", lambda tailnet, tok, node, timeout=30: "100.64.0.1")
        monkeypatch.setattr(
            discovery, "list_devices_ssh",
            lambda instance, ip, user, key: "pending: []",
        )
        rc = discovery.main([
            "--instance-map", self._write_map(tmp_path, ["oc1|dev"]),
            "--request-id", REAL_REQUEST_ID,
            "--vps-user", "deploy",
            "--ssh-key", "/tmp/key",
            "--ts-tailnet", "tailcfea8a.ts.net",
            "--ts-client-id", "cid",
            "--ts-client-secret", "csecret",
        ])
        assert rc == 1
        err = capsys.readouterr().err
        assert f"Request-ID '{REAL_REQUEST_ID}' auf keiner enabled Instanz gefunden" in err
        assert "Übersprungen (VPS down): keine" in err

    def test_cli_unreachable_shown(self, tmp_path, monkeypatch, capsys):
        """CLI-Wiring: VPS down -> Node in Fehlermeldung (Minor #15)."""
        monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "gh_out"))
        monkeypatch.setattr(discovery, "fetch_tailscale_token", lambda cid, cs, timeout=30: "tok")
        monkeypatch.setattr(
            discovery, "resolve_vps_ip",
            lambda tailnet, tok, node, timeout=30: None,  # alle VPS down
        )
        rc = discovery.main([
            "--instance-map", self._write_map(tmp_path, ["oc1|dev"]),
            "--request-id", REAL_REQUEST_ID,
            "--vps-user", "deploy",
            "--ssh-key", "/tmp/key",
            "--ts-tailnet", "tailcfea8a.ts.net",
            "--ts-client-id", "cid",
            "--ts-client-secret", "csecret",
        ])
        assert rc == 1
        err = capsys.readouterr().err
        assert "VPS vps-dev nicht erreichbar, überspringe" in err
        assert "Übersprungen (VPS down): vps-dev" in err


class TestTailscaleTokenFetch:
    def test_fetch_tailscale_token(self, monkeypatch):
        """Token-Fetch postet client_id/secret, liefert access_token (gemockt)."""
        captured = {}

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b'{"access_token": "ts-token-abc"}'

        def fake_urlopen(req, timeout=30):
            captured["url"] = req.full_url
            captured["data"] = req.data.decode()
            captured["timeout"] = timeout
            return FakeResp()

        monkeypatch.setattr(discovery.urllib.request, "urlopen", fake_urlopen)
        token = discovery.fetch_tailscale_token("cid-123", "csec-456")
        assert token == "ts-token-abc"
        assert captured["url"] == "https://api.tailscale.com/api/v2/oauth/token"
        assert "client_id=cid-123" in captured["data"]
        assert "client_secret=csec-456" in captured["data"]
        assert captured["timeout"] == 30


def test_real_world_id_matches_workflow_regex():
    """Realfall-ID erfuellt die Workflow-Regex ^[a-zA-Z0-9_-]{8,64}$ (36 Zeichen, nur hex+Dash)."""
    import re

    assert re.fullmatch(r"[a-zA-Z0-9_-]{8,64}", REAL_REQUEST_ID)
    assert 8 <= len(REAL_REQUEST_ID) <= 64
