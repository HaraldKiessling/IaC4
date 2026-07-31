# IaC4 – Arbeitsmethodik

> Basierend auf der Session vom 2026-07-30.
> Diese Methode gilt für JEDES neue Thema (gross oder klein).

## Der IaC4-Workflow

### Schritt 0: Themenaufnahme
**Wer:** Du (Harald) → Nova (Orchestrator)
**Was:** Ein Thema, ein Goal, keine Lösung.
**Format:** "Ich möchte, dass…" / "Ziel ist…"

### Schritt 1: Anforderungen strukturieren
**Wer:** Nova (Orchestrator)
**Was:** Anforderungen als MD-Dokument zusammenschreiben
**Output:** `iac4-design/NN-thema.md` (oder docs/arc42/ bei Architektur)
**Enthält:**
- Ziel / Kontext
- Übernommenes aus IaC3 (mit Prüfung!)
- Gewünschte Komponenten
- Offene Fragen an Harald

### Schritt 2: Klärung
**Wer:** Nova → Harald
**Was:** Vertiefungsfragen zu den Anforderungen
**Regel:** Nicht raten – fragen. Nicht annehmen – klären.

| Frage-Typ | Beispiele |
|-----------|----------|
| Entscheidung | "arc42 oder RFC?" |
| Priorisierung | "Ollama jetzt oder später?" |
| Technisch | "Welches Embedding-Modell?" |
| Abgrenzung | "Monorepo oder getrennt?" |

### Schritt 3: Entscheidung
**Wer:** Harald
**Was:** Antworten auf die Fragen + Validierung
**Output:** Freigabe für Konzept-Phase

### Schritt 4: Konzept-Design
**Wer:** 🏗️ Architect (Sub-Agent) mit Nova
**Was:** Struktur, Abhängigkeiten, Alternativen
**Prüfung:**
- ✅ P1: Quellen belegt?
- ✅ P2: Konzept dokumentiert?
- ✅ P3: 5W beantwortet?
- ✅ Security-Gates (SSH, ACL, Secrets)?
- ✅ IaC3-Übernahmen auf P1 geprüft?
**Output:** Design-Dokument (z.B. Repo-Struktur, arc42-Kapitel)

### Schritt 5: Umsetzung
**Wer:** 🔧 Engineer (Sub-Agent)
**Was:** Code nach Spezifikation
**Regeln:**
- 1 Task = 1 Branch (Worktree-Sessions: `session-*/<topic>`, Issue #29)
- Evidenz via web_search vor Annahmen
- Quellen in Commit-Nachricht
**Output:** Code + Doku + Tests

### Schritt 6: Review
**Wer:** 🔍 Reviewer (Sub-Agent)
**Was:** Prüfung vor Commit
**Checkliste:**
- [ ] Secrets? → Block
- [ ] NOPASSWD:`***` vs `***`? → Ganz genau!
- [ ] IaC3 blind kopiert? → Prüfen
- [ ] Idempotent? (2. Lauf = 1. Lauf?)
- [ ] P4: arc42 aktualisiert?
- [ ] Commit-Nachricht informativ?
**Regel (Issue #37):** Autor ≠ Reviewer. Review-Ergebnis wird im PR-Thread dokumentiert (✅ Freigabe oder Befundliste); Befunde werden bearbeitet oder explizit als Follow-up verfolgt – kein stiller Tod.
**Output:** "Befund: Zeile 42 …" oder "✅ Freigabe"

### Schritt 7: Integration
**Wer:** Nova (Orchestrator)
**Was:** Commit + Push + Workflow starten
**Regel:** Erst committen wenn Reviewer freigegeben hat.

### Schritt 8: Gap-Analyse
**Wer:** Nova
**Was:** Nach Fertigstellung: IST vs. SOLL
**Output:** issue/gap-report
**P5:** Regelmässiger Abgleich

## Sub-Agent-Einsatz

| Aufgabe | Zeit | Sub-Agent |
|---------|------|-----------|
| Einfacher Fix (< 5 Min, 1 Datei) | 🔵 | Nova allein |
| Mehrere Dateien, bekanntes Muster | 🟡 | 🔧 Engineer + 🔍 Reviewer |
| Neues Konzept / Architektur | 🔴 | 🏗️ Architect + 🔧 Engineer + 🔍 Reviewer |
| Security/ACL/Secrets relevant | 🔴 | IMMER 🏗️ Architect + 🔍 Reviewer |

## Prinzipien (P1-P7)

Siehe AGENTS.md oder docs/arc42/01.

## Datei-Struktur

| Phase | Artefakt | Ort |
|-------|----------|-----|
| Schritt 1-3 | Anforderungsdokument | `iac4-design/NN-thema.md` |
| Schritt 4 | Design-Dokument | `iac4-design/NN-thema.md` |
| Schritt 5-6 | Code + Doku | Repo-Struktur + docs/arc42/ |
| Schritt 8 | Gap-Analyse | Commit-Nachricht + Issue |
