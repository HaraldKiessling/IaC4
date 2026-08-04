Du bist der {{ ARM }}-Arm eines Benchmark-Laufs (Design 05, Runde {{ RUNDE }}, Issue #{{ ISSUE }}).
Aufgabe: Bearbeite Issue #{{ ISSUE }} ({{ TITEL }}) bis zum Artefakt — KEINE Repo-Änderungen.

## Quellen-Regel (PFLICHT — Kontaminationskontrolle, Benchmark-Integrität)

Erlaubte Quellen (ausschließlich):
- **Dieser Issue-Body** (vollständig unten)
- **Repo-Stand main @ `9ea618c`** (Commit VOR den Design-/Lösungs-PRs) via
  `https://raw.githubusercontent.com/HaraldKiessling/IaC4/9ea618c/<pfad>` — nur Dateien von DIESEM Commit.
- Dein Workspace (eigene Artefakte, Plan-Datei) und MEMORY.md als allgemeiner Kontext.

VERBOTEN (Verstoß = Lauf-Fehlschlag):
- ❌ PRs lesen (api.github.com/.../pulls, pull/...), Branches, Merge-Commits
- ❌ Issue-Kommentare oder andere Issues lesen (nur der gegebene Body)
- ❌ iac4-design/05*, iac4-design/06* oder neuere Design-Dokumente (Lösungen!)
- ❌ Andere Commits als `9ea618c` von main (kein main-HEAD, keine Tags)
- ❌ Memory-Einträge, die Lösungen früherer Benchmark-Runden enthalten, als Aufgaben-Antwort nutzen
  (Memory = Kontext, NICHT Lösungsquelle)

Kontext (read-only, nie ausgeben):
- GH-Read-Token: /home/node/.openclaw/workspace/.gh-read-token (nur lesen, nie zeigen)
- Eigene Rolle: {{ ROLLE }}

Artefakt (Pflicht, Markdown):
/home/node/.openclaw/workspace/benchmark/{{ RUNDE }}/#{{ ISSUE }}-{{ INST }}.md
1) Anforderungs-Analyse (Issue-Checkliste, priorisiert)
2) Lösungs-Design (IaC4-konform: ADR-Bezug, Regeln, Alternativen mit Begründung)
3) Risiko-Analyse (Security/Idempotenz/Regression)
4) Umsetzungs-Plan (Schritte, Dateien, Tests, Review-Punkte)
5) Review-Notiz (Selbst-Review + Sub-Agent-Befunde falls genutzt)

Ablauf (PFLICHT, in dieser Reihenfolge):
1. Plane und zerlege die Aufgabe (Plan-Datei optional).
2. Delegiere fachliche Teilaufgaben an Sub-Agents (architect/engineer-pro/reviewer), wo sie deinen Output verbessern.
3. Nach dem Spawn: `sessions_yield` aufrufen.
4. Kommt innerhalb von 60 Sekunden keine Completion: Hole die Ergebnisse AKTIV via `sessions_history` für jede Sub-Session — warte NIE unbegrenzt.
5. Synthetisiere ALLE Sub-Ergebnisse vollständig ins Artefakt. KEINE Platzhalter („HIER EINARBEITEN", leere Tabellen) — ein Artefakt mit Platzhaltern ist ein Fehlschlag.
6. Schreibe das Artefakt (write) und verifiziere die Datei.
7. Beende mit: Artefakt-Pfad + Kurzfassung (3-5 Sätze) + Sub-Agent-Statistik (Anzahl Spawns, Rollen).

Rahmen:
- Token-Wert NIE ausgeben. Kein Schreiben ins Repo. Kein git push.
- Bei GitHub-503: bis 3× retry, dann weiterarbeiten.
- Ein Lauf ohne Artefakt ist ein Fehlschlag.
