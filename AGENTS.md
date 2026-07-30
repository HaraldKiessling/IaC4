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
| **Nie Secrets committen** – immer GH Secrets + `.env.example` | Alle |
| **Nie Gateway-Prozess killen** (Vorfall 2026-07-16, 6h Downtime) | Alle |
| **PR mergen** = Harald genehmigt → Agent merge | Orchestrator |
| **PROD-Deploy** = nur Harald | Orchestrator |

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

### P3 – Review mit 5W
Jeder PR muss beantworten:
- **W**as ändert sich?
- **W**arum (fachliche Begründung)?
- **W**elche Alternativen gab es?
- **W**ie wurde priorisiert?
- **W**as passiert bei Fehlschlag?

### P4 – Living Docs
Nach jeder Code-Änderung prüfen:
- Betrifft das arc42-Kapitel? → aktualisieren
- Betrifft das AGENTS.md? → aktualisieren
- Commit-Nachricht: "docs(scope): ..." für reine Doku-Änderungen

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
- **`dev` Branch → Push** = autonom
- **PR merge (main)** = nach Harald-Approval
- Technische Entscheidungen bis DEV: frei
- MAIN/PROD = Harald

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
