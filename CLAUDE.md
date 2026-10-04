# IaC4 – Claude Code

@AGENTS.md

## Rollen in Claude Code

- **Hauptsession** = Engineer und Orchestrator: Planen, Umsetzen und Testen teilen sich Kontext und bleiben hier. Fachliche Fragen klärst du mit Harald im Gespräch (Grill), bevor du baust.
- **`reviewer`** (`.claude/agents/reviewer.md`): unabhängiger technischer Review, nur lesend. **Pflicht vor jeder Fertig-Meldung, vor dem DEV-Deploy und vor der Vorstellung bei Harald** (AGENTS.md P7, Checkliste Punkt 8). Gib ihm Diff, Ziel und Prüfausgaben (Lint, Syntax-Check) mit; er kann nichts selbst ausführen. Befunde einarbeiten, einmal erneut prüfen lassen, Ergebnis im PR-Thread mit Signatur `🔍 Reviewer` dokumentieren.
- **`architect`** (`.claude/agents/architect.md`): recherchiert Alternativen mit Quellen und liefert Empfehlung/ADR-Entwurf. Einsatz bei Konzepten ab Umfang "GROSS" (P2). Er kann Harald nichts fragen, offene fachliche Fragen kommen zurück an dich.
