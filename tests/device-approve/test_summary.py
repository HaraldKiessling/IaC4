"""Tests fuer tools/device-approve/summary.py (Minor #7, einheitliches Schema).

Abgedeckt: result_to_markdown Mapping (scanned → Discovery-Scan, filters_applied → Filter),
Status-Headers (approved/found/not_found/error), CLI (stdin→$GITHUB_STEP_SUMMARY).
"""

import json
import os
import sys

import pytest

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "device-approve")
sys.path.insert(0, os.path.abspath(TOOLS_DIR))

import summary  # noqa: E402

REAL_ID = "b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5"


def make_result(status, found=None, scanned=None, filters_applied=None):
    return {
        "status": status,
        "id": REAL_ID,
        "found": found or [],
        "scanned": scanned or [],
        "filters_applied": filters_applied or {},
    }


class TestResultToMarkdown:
    def test_approved_with_found(self):
        r = make_result("approved", found=[
            {"target": "dev", "instance": "oc1", "type": "device", "vps_ip": "100.64.0.1"},
        ], scanned=["dev/oc1"], filters_applied={"type": "both", "target": "both", "instance": "all"})
        md = summary.result_to_markdown(r)
        assert "Erfolgreich" in md
        assert REAL_ID in md
        assert "dev/oc1" in md
        assert "100.64.0.1" in md
        assert "Discovery-Scan" in md
        assert "Filter" in md
        assert "type=both" in md

    def test_not_found(self):
        r = make_result("not_found", scanned=["dev/oc1", "dev/oc2", "prod/oc1"])
        md = summary.result_to_markdown(r)
        assert "Kein Treffer" in md
        assert "Nicht gefunden" in md
        assert "dev/oc1" in md

    def test_error(self):
        r = make_result("error")
        md = summary.result_to_markdown(r)
        assert "Fehler" in md

    def test_found_status(self):
        r = make_result("found", found=[
            {"target": "dev", "instance": "oc2", "type": "telegram", "vps_ip": "100.64.0.2"},
        ], scanned=["dev/oc1", "dev/oc2"])
        md = summary.result_to_markdown(r)
        assert "Gefunden (Discovery)" in md
        assert "telegram" in md

    def test_scanned_mapped_to_discovery_scan(self):
        """Minor #7: scanned → Discovery-Scan."""
        r = make_result("found", scanned=["dev/oc1", "dev/oc2", "dev/oc3"])
        md = summary.result_to_markdown(r)
        assert "Discovery-Scan" in md
        assert "3 Instanz" in md  # Count
        assert "dev/oc1" in md
        assert "dev/oc2" in md

    def test_filters_applied_mapped_to_filter(self):
        """Minor #7: filters_applied → Filter."""
        r = make_result("not_found", filters_applied={"type": "telegram", "target": "both", "instance": "all"})
        md = summary.result_to_markdown(r)
        assert "**Filter:**" in md
        assert "telegram" in md

    def test_count_integrated_minor_5(self):
        """Minor #5: Count in Discovery-Scan integriert."""
        r = make_result("found", scanned=["dev/oc1", "dev/oc2"])
        md = summary.result_to_markdown(r)
        assert "2 Instanz" in md

    def test_empty_scanned_and_filters(self):
        r = make_result("error", scanned=[], filters_applied={})
        md = summary.result_to_markdown(r)
        assert "Discovery-Scan" not in md
        assert "Filter" not in md


class TestStatusHeader:
    def test_approved(self):
        assert "Erfolgreich" in summary.status_header("approved")

    def test_found(self):
        assert "Gefunden" in summary.status_header("found")

    def test_not_found(self):
        assert "Kein Treffer" in summary.status_header("not_found")

    def test_error(self):
        assert "Fehler" in summary.status_header("error")


class TestSummaryCli:
    def test_stdin_to_github_step_summary(self, tmp_path, monkeypatch, capsys):
        """CLI: stdin JSON → Markdown in $GITHUB_STEP_SUMMARY (File-Open, Major #3)."""
        sm = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(sm))
        from unittest.mock import patch
        import io
        with patch("sys.stdin", io.StringIO(json.dumps(make_result("found")))):
            rc = summary.main([])
        assert rc == 0
        content = sm.read_text(encoding="utf-8")
        assert REAL_ID in content

    def test_cli_no_input(self, capsys):
        monkeypatch_done = True
        # Test empty stdin → exit 1
        import io
        from unittest.mock import patch
        with patch("sys.stdin", io.StringIO("")):
            rc = summary.main([])
        assert rc == 1

    def test_cli_invalid_json(self, capsys):
        import io
        from unittest.mock import patch
        with patch("sys.stdin", io.StringIO("not json")):
            rc = summary.main([])
        assert rc == 2

    def test_cli_local_fallback(self, tmp_path, monkeypatch, capsys):
        """Ohne GITHUB_STEP_SUMMARY → Markdown auf stdout (lokaler Modus)."""
        monkeypatch.setattr(
            summary.sys.stdin, "read",
            lambda: json.dumps(make_result("found"))
        )
        rc = summary.main([])
        assert rc == 0
        out = capsys.readouterr().out
        assert REAL_ID in out
        assert "Discovery-Scan" not in out  # scanned ist leer
