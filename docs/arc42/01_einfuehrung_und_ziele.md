# 1. Einführung & Ziele

## Aufgabenstellung
IaC4 verwaltet die Infrastruktur für Haralds VPS-Systeme: Provisionierung, Konfiguration,
Services (Qdrant, Code-Server, OpenClaw) und Netzwerk (Tailscale).

## Qualitätsziele (Top 3)
1. **Reproduzierbarkeit** – Nach einem Crash ist der VPS in < 5 Minuten wiederhergestellt
2. **Performance** – Basis-Deploy in < 2 Minuten, Gesamt-Deploy in < 10 Minuten
3. **Autonomie** – Feature → DEV-Deploy ohne menschliches Zutun (P7)

## Stakeholder
| Rolle | Erwartung |
|-------|-----------|
| Harald (Betreiber) | Sicheres, wartbares Infrastruktur-Setup |
| Nova (Orchestrator) | Autonomer DEV-Deploy, klare Prozesse |
