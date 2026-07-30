# 1. Einführung & Ziele

## Aufgabenstellung
IaC4 ist der Nachfolger von IaC3 und verwaltet die Infrastruktur für Haralds VPS-Systeme:
Provisionierung, Konfiguration, Services (Qdrant, Code-Server, OpenClaw) und Netzwerk (Tailscale).

**Abgrenzung zu IaC3:** Kein Petrus-Striktur, kein RFC/ADR-Wirrwarr,
VPS-User ist `deploy-user` (nicht `openclaw`).

## Qualitätsziele (Top 3)
1. **Reproduzierbarkeit** – Nach einem Crash ist der VPS in < 10 Minuten wiederhergestellt
2. **Security** – SSH nur via Tailscale, öffentliche IP nach Bootstrap geschlossen 🔒
3. **Autonomie** – Feature → DEV-Deploy ohne menschliches Zutun (P7)

## Stakeholder
| Rolle | Erwartung |
|-------|-----------|
| Harald (Betreiber) | Sicheres, wartbares Infrastruktur-Setup |
| Nova (Orchestrator) | Autonomer DEV-Deploy, klare Prozesse |

## Prinzipien
Siehe P1–P7 in docs/workflows/deploy-stages.md
