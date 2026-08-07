#!/usr/bin/env python3
"""Telegram-Device-Approve-Bot (Design 05, M4-Vorbereitung – Deployment offen F1).

Reiner Trigger (Minor #10): Der Bot validiert User + Request-ID und stoesst ein
GitHub-`repository_dispatch`-Event ``device-approve`` an. Das Ergebnis ist im
GH-Actions-Run zu pruefen (Workflow 06-device-approve-telegram.yml); ein
Callback/Run-Polling ist dokumentierter Folgeausbau.

Sicherheits-Design (reviewed Konzept §2.3):
- Blocker #3: geankerte Regex ``^/approve\\s+([a-zA-Z0-9_-]{8,64})$`` –
  kein ungeankertes Suchen, keine Shell-Metazeichen durchlaessig.
- Whitelist: TELEGRAM_APPROVE_USERS (GH-Secret, kommagetrennte Telegram-User-IDs);
  Fallback-Konstante = Harald (einziger Owner).
- Minor #12: requests.post(..., timeout=10) + expliziter Timeout-Fehlerpfad.
- PAT: GH_DEVICE_APPROVE_PAT (GH-Secret, feingranular, repo-Scope) – wird nur als
  Env-Referenz genutzt, niemals committet.
"""

from __future__ import annotations

import os
import re
from typing import Optional

import requests

# Fallback-Whitelist (Konzept §2.3): Harald. Produktiv via Env/Secret
# TELEGRAM_APPROVE_USERS (kommagetrennt) ueberschrieben.
DEFAULT_AUTHORIZED_USERS = {7145674995}

# Geankerte Regex (Blocker #3): Kommando-Praefix + Capture-Group + Ende-Anker.
# Mehrdeutige Nachrichten ("Bitte bestaetige Kaffee-12345678 morgen") matchen NICHT.
APPROVE_RE = re.compile(r"^/approve\s+([a-zA-Z0-9_-]{8,64})$")

REPO = "HaraldKiessling/IaC4"
DISPATCH_URL = f"https://api.github.com/repos/{REPO}/dispatches"
TIMEOUT_SECONDS = 10  # Minor #12


def load_authorized_users() -> set[int]:
    """Whitelist aus TELEGRAM_APPROVE_USERS (kommagetrennt) oder Fallback."""
    raw = os.environ.get("TELEGRAM_APPROVE_USERS", "").strip()
    if raw:
        return {int(uid.strip()) for uid in raw.split(",") if uid.strip()}
    return set(DEFAULT_AUTHORIZED_USERS)


def parse_request_id(text: Optional[str]) -> Optional[str]:
    """Extrahiert Request-ID aus exaktem '/approve <id>' – sonst None (Blocker #3)."""
    if not text:
        return None
    match = APPROVE_RE.match(text.strip())
    return match.group(1) if match else None


def is_authorized(user_id: int, authorized_users: Optional[set[int]] = None) -> bool:
    """True, wenn user_id in der Whitelist (Konzept §2.3)."""
    users = authorized_users if authorized_users is not None else load_authorized_users()
    try:
        return int(user_id) in users
    except (TypeError, ValueError):
        return False


def dispatch_request(
    request_id: str,
    telegram_user_id: int,
    pat: str,
    repo: str = REPO,
    timeout: int = TIMEOUT_SECONDS,
) -> requests.Response:
    """Feuert repository_dispatch 'device-approve' mit client_payload {id, telegram_user_id}."""
    return requests.post(
        f"https://api.github.com/repos/{repo}/dispatches",
        headers={
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
        },
        json={
            "event_type": "device-approve",
            "client_payload": {
                "id": request_id,
                "telegram_user_id": str(telegram_user_id),
            },
        },
        timeout=timeout,
    )


def handle_message(
    user_id: int,
    text: Optional[str],
    pat: Optional[str] = None,
    authorized_users: Optional[set[int]] = None,
) -> str:
    """Bot-Handler: Auth-Check -> ID-Parse -> Dispatch. Gibt Antworttext zurueck."""
    if not is_authorized(user_id, authorized_users):
        return "❌ Nicht authorisiert"
    request_id = parse_request_id(text)
    if not request_id:
        return "❌ Keine gültige Request-ID. Format: /approve <id>"
    token = pat or os.environ.get("GH_DEVICE_APPROVE_PAT", "")
    if not token:
        return "❌ Server-Konfiguration: GH_DEVICE_APPROVE_PAT fehlt"
    try:
        resp = dispatch_request(request_id, user_id, token)
    except requests.exceptions.Timeout:
        return "❌ GH-API Timeout — bitte erneut versuchen"
    except requests.exceptions.RequestException as exc:
        return f"❌ GH-API Fehler: {exc.__class__.__name__}"
    if resp.status_code == 204:
        return f"✅ Pairing für {request_id} angestoßen → GH Actions Run"
    return f"❌ Fehler: {resp.status_code} {resp.text}"


if __name__ == "__main__":
    # Direktaufruf (z.B. systemd/Worker-Test): python3 bot.py "<user_id>" "<text>"
    import sys

    if len(sys.argv) < 3:
        sys.exit("Usage: bot.py <telegram_user_id> <message-text>")
    print(handle_message(int(sys.argv[1]), sys.argv[2]))
