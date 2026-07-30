# 10. Qualitätsanforderungen

## Messbare Ziele

| Qualität | Ziel | Metrik |
|----------|------|--------|
| Deploy-Dauer Phase 1 | < 2 Minuten | `time ansible-playbook` |
| Deploy-Dauer Gesamt | < 10 Minuten | `time ansible-playbook` |
| Recovery nach Crash | < 5 Minuten | Stoppuhr |
| CI-Dauer | < 3 Minuten | GH Actions Logs |

*(Weitere bei Bedarf ergänzen)*
