"""Tests fuer tools/telegram-approve-bot/bot.py (Design 05, Blocker #3 + Whitelist).

Keine echten Secrets, kein Netzwerk: dispatch_request() wird in handle_message-
Tests gemockt (Fake-Response bzw. Timeout-Raise).
"""

import os
import sys

import pytest
import requests

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "telegram-approve-bot")
sys.path.insert(0, os.path.abspath(TOOLS_DIR))

import bot  # noqa: E402

HARALD = 7145674995
WHITELIST = {HARALD, 111222333}


class FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


# --- parse_request_id: positive Faelle -----------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("/approve req_abc123", "req_abc123"),
        ("/approve 12345678", "12345678"),
        ("/approve   req_abc123", "req_abc123"),  # \s+ erlaubt mehrere Spaces
        ("  /approve req_abc123  ", "req_abc123"),  # strip vor Match
        ("/approve ABCDEFGH-ijkl_mnop", "ABCDEFGH-ijkl_mnop"),  # 16 Zeichen, alle Klassen
        # Realfall 2026-08-06: UUID-Format (36 Zeichen, hex + Dash) aus der Control-UI
        ("/approve b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5", "b0999c46-ebe3-4c46-a72b-8b0a7c1df2d5"),
        ("/approve " + "a" * 64, "a" * 64),  # 64 = OK (Grenze)
    ],
)
def test_parse_positive(text, expected):
    assert bot.parse_request_id(text) == expected


# --- parse_request_id: negative Faelle (Blocker #3) ------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "",                      # leer
        None,                    # None
        "/approve",              # keine ID
        "/approve ",             # nur Whitespace nach Kommando
        "/approve 1234567",      # 7 Zeichen = zu kurz
        "/approve req_abc123; rm -rf",      # Injection: Semikolon
        "/approve req_abc123$(id)",         # Injection: Kommandosubstitution
        "/approve $(rm -rf /)",             # Injection: Kommandosubstitution pur
        "/approve req_abc123; echo pwned",  # Injection: Kette
        "/approve req_abc123 extra",        # Mehrdeutig/zu lang
        "/approve req_abc123!",             # '!' nicht erlaubt
        "req_abc123",            # ohne /approve-Praefix
        "Bitte bestätige Kaffee-12345678 morgen",  # Mehrdeutigkeit: kein /approve
        "Bitte bestätige Kaffee-12345678 morgen /approve",  # Praefix nicht am Anfang
        "/approve " + "a" * 65,  # 65 Zeichen = zu lang
    ],
)
def test_parse_negative(text):
    assert bot.parse_request_id(text) is None


# --- Whitelist-Check ------------------------------------------------------------

@pytest.mark.parametrize(
    "user_id,authorized,expected",
    [
        (HARALD, None, True),             # Default-Fallback (Harald)
        (111222333, WHITELIST, True),     # explizite Whitelist
        (999999999, WHITELIST, False),    # nicht autorisiert
        (None, WHITELIST, False),         # leer/None
        ("", WHITELIST, False),           # leerer String
        ("not-a-number", WHITELIST, False),
        (".*", WHITELIST, False),         # Regex-Injection als User-ID (Blocker #1-Haertung)
        (HARALD, set(), False),           # leere Whitelist
    ],
)
def test_is_authorized(user_id, authorized, expected):
    assert bot.is_authorized(user_id, authorized) is expected


def test_load_authorized_users_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_APPROVE_USERS", " 111, 222 ,333 ")
    assert bot.load_authorized_users() == {111, 222, 333}


def test_load_authorized_users_fallback(monkeypatch):
    monkeypatch.delenv("TELEGRAM_APPROVE_USERS", raising=False)
    assert bot.load_authorized_users() == {HARALD}


# --- handle_message: End-to-End ohne Netzwerk ------------------------------------

def test_handle_message_unauthorized_user(monkeypatch):
    """Nicht-whitelisted User: Ablehnung, KEIN Dispatch-Call."""
    called = []

    def fake_dispatch(*args, **kwargs):
        called.append(args)
        return FakeResponse(204)

    monkeypatch.setattr(bot, "dispatch_request", fake_dispatch)
    msg = bot.handle_message(999999999, "/approve req_abc123", pat="x")
    assert msg == "❌ Nicht authorisiert"
    assert called == []


def test_handle_message_injection_rejected(monkeypatch):
    """Injection-Versuch: Format-Fehler, KEIN Dispatch-Call."""
    called = []

    def fake_dispatch(*args, **kwargs):
        called.append(args)
        return FakeResponse(204)

    monkeypatch.setattr(bot, "dispatch_request", fake_dispatch)
    msg = bot.handle_message(HARALD, "/approve req_abc123; rm -rf", pat="x")
    assert msg == "❌ Keine gültige Request-ID. Format: /approve <id>"
    assert called == []


def test_handle_message_missing_pat(monkeypatch):
    """Authorisiert + valide ID, aber kein PAT: Konfigurations-Fehler."""
    monkeypatch.delenv("GH_DEVICE_APPROVE_PAT", raising=False)
    msg = bot.handle_message(HARALD, "/approve req_abc123", pat=None)
    assert "GH_DEVICE_APPROVE_PAT fehlt" in msg


def test_handle_message_success(monkeypatch):
    """Erfolgsfall: Dispatch mit client_payload {id, telegram_user_id}, 204 -> OK."""
    captured = {}

    def fake_dispatch(request_id, user_id, pat, **kwargs):
        captured["request_id"] = request_id
        captured["user_id"] = user_id
        captured["pat"] = pat
        return FakeResponse(204)

    monkeypatch.setattr(bot, "dispatch_request", fake_dispatch)
    msg = bot.handle_message(HARALD, "/approve req_abc123", pat="secret-pat")
    assert msg == "✅ Pairing für req_abc123 angestoßen → GH Actions Run"
    assert captured == {"request_id": "req_abc123", "user_id": HARALD, "pat": "secret-pat"}


def test_handle_message_api_error(monkeypatch):
    monkeypatch.setattr(bot, "dispatch_request", lambda *a, **k: FakeResponse(401, "Bad credentials"))
    msg = bot.handle_message(HARALD, "/approve req_abc123", pat="x")
    assert msg == "❌ Fehler: 401 Bad credentials"


def test_handle_message_timeout(monkeypatch):
    """Minor #12: Timeout wird abgefangen, kein Crash."""

    def raise_timeout(*args, **kwargs):
        raise requests.exceptions.Timeout("slow")

    monkeypatch.setattr(bot, "dispatch_request", raise_timeout)
    msg = bot.handle_message(HARALD, "/approve req_abc123", pat="x")
    assert msg == "❌ GH-API Timeout — bitte erneut versuchen"


def test_dispatch_request_payload_and_headers(monkeypatch):
    """Payload-Schema (Konzept §2.1): event_type + client_payload {id, telegram_user_id}."""
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs["headers"]
        captured["json"] = kwargs["json"]
        captured["timeout"] = kwargs["timeout"]
        return FakeResponse(204)

    monkeypatch.setattr(bot.requests, "post", fake_post)
    resp = bot.dispatch_request("req_abc123", HARALD, "pat-xyz")
    assert resp.status_code == 204
    assert captured["url"] == "https://api.github.com/repos/HaraldKiessling/IaC4/dispatches"
    assert captured["headers"]["Authorization"] == "Bearer pat-xyz"
    assert captured["json"] == {
        "event_type": "device-approve",
        "client_payload": {"id": "req_abc123", "telegram_user_id": str(HARALD)},
    }
    assert captured["timeout"] == 10  # Minor #12
