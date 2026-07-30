# IaC4 – Agent Context

> **Leitprinzipien für JEDEN Agenten, der in diesem Repo arbeitet.**
> Bei Konflikten: Diese Datei > arc42-Doku > mündliche Absprachen.

## Repository
**Name:** HaraldKiessling/IaC4
**Architektur:** arc42-light in `docs/arc42/` (DE)
**Branch:** `main` (geschützt) | `dev` (autonomer Push) | `feature/*` (Entwicklung)

## 🔴 Harte Regeln (brechen = Rollback)

| Regel | Gilt für |
|-------|----------|
| **Nie `overwrite_existing_content = true`** in Terraform-ACL (Vorfall 2026-07-30) | Alle |
| **Nie direkter Push auf `main`** – nur via PR | Alle |
| **`dev` Push** = autonom (kein PR nötig) | Orchestrator |
| **PR `grün` vor Fertig-Meldung** – erst done, wenn alle CI-Checks pass | Alle |
| **Nie Secrets committen** – immer GH Secrets + `.env.example` | Alle |
| **Nie Gateway-Prozess killen** (Vorfall 2026-07-16, 6h Downtime) | Alle |
| **PR mergen** = Harald genehmigt → Agent merge | Orchestrator |
| **PROD-Deploy** = nur Harald | Orchestrator |
| **Pre-Flight Validation vor Push** – yamllint + markdownlint lokal prüfen | Alle |
| **Force-Push nicht auf PR-Branches** – nur auf ungeteilte Feature-Branches | Alle |
| **PR-Checkliste vor Fertig-Meldung** – CI grün, Doku aktuell, Secrets-Check, Branch rebased | Orchestrator |

## ✅ Autonom (kein Approval nötig)
- Feature-Branch → Push → DEV-Deploy
- **`dev` Branch → Push** = direkt (kein PR)
- **PR merge (main)** = nach Harald-Approval
- Code schreiben, testen, committen
- Issue-Templates verwenden (Feature/Bug/Change)
- arc42-Doku aktuell halten (P4)

## 📋 Prinzipien P1–P7 (ausführlich)

### P1 – Evidenz
Jede Behauptung braucht einen Beleg. Nutze `web_search` oder `web_fetch` für:
- Architekturentscheidungen (→ docs/arc42/09)
- Tool-Empfehlungen (Vendor-Docs)
- Performance-Behauptungen (→ Benchmarks)

**Nicht:** "Ich glaube", "Meiner Erfahrung nach" ohne Quelle.

### P2 – Konzepte vor Code
Jede Änderung beginnt mit einem Konzept:
- NEU: Issue erstellen (Feature/Bug/Change)
- GROSS (>1h Arbeit): Kurzkonzept in docs/decisions/ ablegen
- Dann: Branch → Code → PR

### P3 – Entscheidungen statt "könnte"
Kein "könnte", "vielleicht", "man könnte". Stattdessen:
1. **Alternativen evidenzbasiert ausarbeiten** (fachlich, nicht spekulativ)
2. **Mit Begründung eine Entscheidung treffen** oder **mindestens eine Empfehlung**
3. Wenn Daten fehlen: nachfragen, nicht raten

Jeder PR muss beantworten (5W):
- **W**as ändert sich?
- **W**arum (fachliche Begründung)?
- **W**elche Alternativen gab es?
- **W**ie wurde priorisiert?
- **W**as passiert bei Fehlschlag?

### P3b – Separation of Concerns
Ein PR macht **genau eine Sache**:
- `fix/*` → Code-Reparaturen
- `feat/*` → Neue Features
- `chore/*` → CI/Tooling/Config
- `docs/*` → Doku/Regeln
- **Nicht:** Code + CI + Doku-Regeln im selben PR

### P4 – Living Docs
Nach jeder Code-Änderung prüfen:
- Betrifft das arc42-Kapitel? → aktualisieren
- Betrifft das AGENTS.md? → aktualisieren
- Commit-Nachricht: "docs(scope): ..." für reine Doku-Änderungen

### P4b – Pre-Flight Validation (vor Push)
Vor `git push` immer lokal prüfen:
- **YAML:** `yamllint .github/workflows/*.yml ansible/**/*.yml`
- **Markdown:** `markdownlint docs/**/*.md`
- **Workflow-Syntax:** Gibt es `***`-Reste oder offensichtliche Fehler?
- **Secrets:** Kein Token/Passwort im Diff?

### P5 – Gap-Analysen
Regelmäßig (alle 2-3 Iterationen): IST vs. SOLL in docs/arc42/
- Fehlende Anforderungen? → Issues
- Veraltete Doku? → P4

### P6 – Nachhaltigkeit
- **Keine Workarounds** – wenn temporär, in K11 dokumentieren
- Tech-Debt nie verstecken → `docs/arc42/11_risiken_und_technische_schulden.md`
- Alte Workarounds aus IaC3 nicht blind übernehmen

### P7 – Autonome Entwicklung
- Feature/BugFix → DEV-Deploy = autonom
- **PR erst als "erledigt" melden, wenn CI grün ist**
- **`dev` Branch → Push** = autonom
- **`dev` Branch → Push** = autonom
- **PR merge (main)** = nach Harald-Approval
- Technische Entscheidungen bis DEV: frei
- MAIN/PROD = Harald

### Checkliste vor Fertig-Meldung
Bevor ein PR als "ready" gemeldet wird:
1. ✅ CI-Checks alle grün
2. ✅ PR-Beschreibung: Was + Warum + Alternativen (P3)
3. ✅ Living Docs: arc42 + AGENTS.md aktuell
4. ✅ Secrets-Check: nichts committet
5. ✅ Branch auf aktuellem `main` (ggf. rebased)
6. ✅ Kein Force-Push auf PR-Branches

### P7c – Post-Merge-Checkliste
Nach jedem erfolgreichen Merge nach `main`:
1. Feature-Branch lokal + remote löschen (`git branch -d <name> && git push origin --delete <name>`)
2. Offene PR-Branches auf neuen `main` rebasen (`git rebase origin/main`)
3. Obsolete PRs schließen (Kommentar mit Begründung)
4. Issue-Closing prüfen: Wurden im PR referenzierte Issues (`Closes #...`) automatisch geschlossen?

## 🏗️ Repo-Struktur
```
IaC4/
├── .github/workflows/    → CI/CD (Phase 1-2e)
├── .github/ISSUE_TEMPLATE/ → Feature/Bug/Change
├── ansible/              → Playbooks + Rollen (Phasen 1-2e)
│   ├── playbooks/        → 7 Playbooks (00-05 + site.yml)
│   └── roles/            → 7 Ansible-Rollen
├── docs/arc42/           → Architektur (12 Kapitel DE)
├── docs/workflows/       → Branching + Deploy-Doku
├── services/             → Docker-Compose-Stacks
├── terraform/            → Tailscale-OAuth-Client
├── qa/                   → Quality-Gates + Testplan
├── scripts/              → verify-deployment.sh, restore.sh
├── cloud-config.yaml     → VPS-Bootstrap
├── .env.example          → Secrets-Referenz
├── Makefile              → CLI-Targets
└── AGENTS.md             ← Du bist hier
```

## 🔗 Wichtige Dateien
| Datei | Zweck |
|-------|-------|
| `docs/arc42/09_architekturentscheidungen.md` | Alle ADRs mit Abhängigkeiten |
| `docs/arc42/11_risiken_und_technische_schulden.md` | Tech-Debt (P6) |
| `docs/workflows/deploy-stages.md` | Phasen + SSH-Transition |
| `cloud-config.yaml` | VPS-Bootstrap |
| `.env.example` | Alle benötigten GH Secrets |

## 🚫 Was ich NICHT mache
- ❌ IaC3-RFCs lesen (sind Legacy)
- ❌ IaC3-Scripte direkt portieren (ohne P1-Prüfung)
- ❌ Petrus-Striktur (war Grund für Redesign)
- ❌ Heimlich Tech-Debt akkumulieren (→ K11)
