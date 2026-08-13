#!/usr/bin/env python3
"""Tests fuer den Multi-Account-Parameter (#126 Pilot oc4, Workflow 05).

Abgedeckt:
  - approve_step.build_approve_cmd: `--account <id>` bei Telegram (belegt:
    docs/channels/pairing.md „Multi-account channels take `--account <id>`“)
  - discovery.build_list_remote_cmd: `--account <id>` bei pairing list
  - discovery._account_arg: nur Telegram-Quellen bekommen den Suffix
  - approve._local_list_cmd / _local_approve_cmd: lokale CLI-Pfade mit account
  - Default (leerer account) bleibt unveraendert (Kanal-weite Sicht)

WICHTIG: das device-approve-discovery-Modul wird NICHT unter dem Namen
"discovery" importiert (Kollision mit tools/telegram-approve-bot/discovery.py
v1, die test_discovery.py als "discovery" importiert) – stattdessen via
approve.discovery (eindeutiger Modulname "device_approve.discovery", gleiches
Muster wie die Library selbst).
"""

from __future__ import annotations

import sys

sys.path.insert(0, "tools/device-approve")
import approve  # noqa: E402
import approve_step  # noqa: E402

# device-approve-discovery (eindeutiger Modulname, keine sys.modules-Kollision)
discovery = approve.discovery

TG_CODE = "QVDCXJEM"


def test_remote_approve_cmd_with_account():
    cmd = approve_step.build_approve_cmd("telegram", "oc4", TG_CODE, account="harald")
    assert cmd == (
        "sudo docker exec openclaw-oc4 openclaw pairing approve telegram "
        "QVDCXJEM --account harald"
    )


def test_remote_approve_cmd_without_account_unchanged():
    cmd = approve_step.build_approve_cmd("telegram", "oc4", TG_CODE)
    assert cmd == (
        "sudo docker exec openclaw-oc4 openclaw pairing approve telegram QVDCXJEM"
    )


def test_remote_list_cmd_with_account():
    cmd = discovery.build_list_remote_cmd("telegram", ["oc4"], account="anna")
    assert "openclaw pairing list telegram --json --account anna" in cmd


def test_remote_list_cmd_without_account_unchanged():
    cmd = discovery.build_list_remote_cmd("telegram", ["oc4"])
    assert "openclaw pairing list telegram --json 2>/dev/null" in cmd
    assert "--account" not in cmd


def test_account_arg_only_telegram():
    assert discovery._account_arg("harald", "telegram") == " --account harald"
    assert discovery._account_arg("harald", "device") == ""
    assert discovery._account_arg("", "telegram") == ""


def test_local_list_cmd_with_account():
    cmd = approve._local_list_cmd("telegram", account="harald")
    assert cmd == ["openclaw", "pairing", "list", "telegram", "--json", "--account", "harald"]


def test_local_approve_cmd_with_account():
    cmd = approve._local_approve_cmd("telegram", TG_CODE, account="anna")
    assert cmd == ["openclaw", "pairing", "approve", "telegram", TG_CODE, "--account", "anna"]


def test_local_cmds_without_account_unchanged():
    assert approve._local_list_cmd("telegram") == [
        "openclaw", "pairing", "list", "telegram", "--json"
    ]
    assert approve._local_approve_cmd("telegram", TG_CODE) == [
        "openclaw", "pairing", "approve", "telegram", TG_CODE
    ]
    assert approve._local_list_cmd("device") == ["openclaw", "devices", "list", "--json"]
