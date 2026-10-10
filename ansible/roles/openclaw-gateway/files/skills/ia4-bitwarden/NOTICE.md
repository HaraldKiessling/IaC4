# Herkunft

- Vorlage: `bitclawden` von typhonius, MIT-Lizenz (`LICENSE` unverändert
  übernommen).
- Quelle: <https://raw.githubusercontent.com/typhonius/bitclawden/main/SKILL.md>
  (ClawHub: <https://clawhub.ai/typhonius/bitclawden>), abgerufen 2026-10-10,
  SHA-256 `213f7056f76bcb5ab27c5c85d7cb43e31cc6123d1724b3c98ecb59ecebab8208`.
- Geprüft und angepasst für IaC4 (ADR-027, Issue #192):
  - Install-Skript entfernt (lud `bw` ungeprüft nach `~/.local/bin`, damit
    läge es auf dem PATH und in einem freigegebenen Pfad).
  - `bw` durch `/opt/ia4-bitwarden/ia4-bw` ersetzt (Anmelden und Entsperren
    automatisch, eine Telegram-Freigabe pro Aufruf).
  - Löschen ergänzt (nur Papierkorb), Freigabe-Hinweise und Leitplanken
    ergänzt.
  - Eindeutiger Name `ia4-bitwarden`, damit kein Workspace-Skill ihn
    überdeckt.
- Aktualisierung nur durch erneute Prüfung und PR, nie automatisch von ClawHub.
