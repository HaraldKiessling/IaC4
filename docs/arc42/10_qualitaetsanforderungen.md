# 10. Qualitätsanforderungen

## Messbare Ziele

| Qualität | Ziel | Metrik | Priorität |
|----------|------|--------|-----------|
| Deploy-Dauer Phase 1 (Baseline) | < 2 Minuten | `time ansible-playbook` | Hoch |
| Deploy-Dauer Gesamt (1–2e) | < 10 Minuten | `time ansible-playbook` | Hoch |
| SSH-Transition (Phase 2b) | < 1 Minute nach Tailscale-Join | UFW-Regel gesetzt | 🔴 Security |
| Recovery nach Crash | < 10 Minuten | Stoppuhr | Mittel |
| CI-Dauer | < 3 Minuten | GH Actions Logs | Mittel |

## Security-Ziele
- Öffentliches SSH maximal 5 Minuten offen (Phasen 0-2a)
- Alle Secrets in GH Actions (nie im Repo)
- Keine öffentlichen Ports; Service-Ports (80/8080/11434) nur via Tailscale erreichbar, UFW-restricted auf 100.64.0.0/10 (ADR-018/019/021)
