# IaC4 – Agent Context

> **Leitprinzipien für JEDEN Agenten, der in diesem Repo arbeitet.**
> Bei Konflikten: Diese Datei > arc42-Doku > mündliche Absprachen.
> **Regel-Änderungen IMMER in AGENTS.md UND `.roo/rules/*.mdc` spiegeln** (P4) – `.roo` wird auch von Roo/Zoo Code gelesen.

## Repository
**Name:** HaraldKiessling/IaC4
**Architektur:** arc42-light in `docs/arc42/` (DE)
**Branch:** `main` (geschützt) | `dev` (autonomer Push) | `feature/*` (Entwicklung) | `session-*/<topic>` (Worktree-Isolation, Issue #29)

## 🔴 Harte Regeln (brechen = Rollback)

| Regel | Gilt für |
|-------|----------|
| **Nie `overwrite_existing_content = true`** in Terraform-ACL – geteilte Ressourcen integrativ ändern, nie ersetzen (Vorfall 2026-07-30: Tailscale lahmgelegt) | Alle |
| **Nie direkter Push auf `main`** – nur via PR | Alle |
| **`dev` Push** = autonom (kein PR nötig) | Orchestrator |
| **PR `grün` vor Fertig-Meldung** – erst done, wenn alle CI-Checks pass | Alle |
| **Nie Secrets committen** – immer GH Secrets + `.env.example` | Alle |
| **Nie Gateway-Prozess killen** (Vorfall 2026-07-16, 6h Downtime) | Alle |
| **PR mergen** = Harald genehmigt → Agent merge (Approval = Auftrag, nicht erneut rückfragen) | Orchestrator |
| **PROD-Deploy** = nur Harald | Orchestrator |
| **Pre-Flight Validation vor Push** – yamllint + markdownlint lokal prüfen | Alle |
| **Nie `sed`/Regex-Editing auf YAML/JSON/Templates** – gezielt editieren + Parser-Validierung (P4b) | Alle |
| **Kein Overclaiming** – „garantiert korrekt"/„verifiziert" nur mit Validierungsnachweis (P9) | Alle |
| **Force-Push nicht auf PR-Branches** – nur auf ungeteilte Feature-/`session-*`-Branches (1 Branch = 1 Worktree) | Alle |
| **PR-Checkliste vor Fertig-Meldung** – CI grün, Doku aktuell, Secrets-Check, Branch rebased | Orchestrator |

## ✅ Autonom (kein Approval nötig)
- Feature-Branch → Push → DEV-Deploy
- **`dev` Branch → Push** = direkt (kein PR)
- **PR merge (main)** = nach Harald-Approval → **dann ohne Rückfrage ausführen** (merge, Issues schließen, Branch aufräumen, P7c)
- Code schreiben, testen, committen
- Issue-Templates verwenden (Feature/Bug/Change)
- arc42-Doku aktuell halten (P4)

## 📋 Prinzipien P1–P10 (ausführlich)

### P1 – Evidenz
Jede Behauptung braucht einen Beleg. Nutze `web_search` oder `web_fetch` für:
- Architekturentscheidungen (→ docs/arc42/09)
- Tool-Empfehlungen (Vendor-Docs)
- Performance-Behauptungen (→ Benchmarks)

**Nicht:** "Ich glaube", "Meiner Erfahrung nach" ohne Quelle.

Zusätzlich:
- **Referenzierte Ressourcen im IST-Zustand verifizieren** (ACL-Tags, Secrets, Hosts, Collections): vor Nutzung prüfen (`gh secret list`, ACL/State lesen, `ansible-galaxy collection list`) – nie aus dem Gedächtnis oder IaC3-Wissen übernehmen.
- **Funktions-Behauptungen mit Test-Kontext:** "funktioniert", "erreichbar", "grün" nur mit Angabe: von wo getestet, mit welchem Key/User, gegen welche Quelle (z.B. "SSH-Check via Tailscale von vps-dev mit deploy-user").
- **Evidenz-Typologie:** Quellen in PRs/Kommentaren kennzeichnen – `[V]` Vendor-/Primärdoku · `[I]` IST-Zustand (verifiziert) · `[A]` Annahme (nicht verifiziert, explizit als solche markieren).
- **Hypothese vor Analyse:** Bei Fehler-/Gap-Analysen zuerst Hypothese formulieren, dann gegen IST/Logs prüfen (statt blind zu probieren).

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
- **W**as passiert bei Fehlschlag? → **Worst-Case konkret benennen + Rollback-Weg** (Pflicht bei Netzwerk-/SSH-/ACL-/Firewall-Änderungen: Lockout-Risiko denken)
- **PR-Body MUSS `Closes #<nummer>` enthalten**, wenn der PR ein Issue löst

### P3b – Separation of Concerns + Scope-Disziplin
Ein PR macht **genau eine Sache**:
- `fix/*` → Code-Reparaturen
- `feat/*` → Neue Features
- `chore/*` → CI/Tooling/Config
- `docs/*` → Doku/Regeln
- **Nicht:** Code + CI + Doku-Regeln im selben PR

**Scope-Disziplin:**
- Analyse-Auftrag = **read-only**: nichts umkonfigurieren, nichts ändern – nur Befunde liefern
- Änderungs-Auftrag = genau die beauftragte Sache, nichts anderes anfassen

### P4 – Living Docs
Nach jeder Code-Änderung prüfen:
- Betrifft das arc42-Kapitel? → aktualisieren
- Betrifft das AGENTS.md? → aktualisieren
- Commit-Nachricht: "docs(scope): ..." für reine Doku-Änderungen

**Regel-Spiegelung:** Regel-Änderungen IMMER in AGENTS.md **und** `.roo/rules/*.mdc` aufnehmen – `.roo` wird von Roo/Zoo Code gelesen, nur OpenClaw-intern reicht nicht.

### P4b – Pre-Flight Validation (vor Push)
Vor `git push` immer lokal prüfen:
- **YAML:** `yamllint .github/workflows/*.yml ansible/**/*.yml`
- **Markdown:** `markdownlint docs/**/*.md`
- **Ansible:** `ansible-playbook --syntax-check` (wenn Playbooks betroffen)
- **Workflow-Syntax:** Gibt es `***`-Reste oder offensichtliche Fehler?
- **Secrets:** Kein Token/Passwort im Diff?
- **Kein `sed`/Regex-Editing** auf strukturierte Dateien (YAML/JSON/Templates): gezielt editieren, danach Parser-Validierung (`yamllint`, `python -m json.tool`, `ansible-playbook --syntax-check`)

### P5 – Gap-Analysen
Regelmäßig (alle 2-3 Iterationen): IST vs. SOLL in docs/arc42/
- Fehlende Anforderungen? → Issues
- Veraltete Doku? → P4

### P6 – Nachhaltigkeit
- **Keine Workarounds** – wenn temporär, in K11 dokumentieren
- Tech-Debt nie verstecken → `docs/arc42/11_risiken_und_technische_schulden.md`
- Alte Workarounds aus IaC3 nicht blind übernehmen
- **Integrativ statt ersetzend:** Geteilte Ressourcen (Tailscale-ACL, OAuth-Client, Configs) nie ersetzen, sondern IST-Zustand laden → merge → validieren → anwenden. Ziel: andere Systeme nie rauskicken (Vorfall 2026-07-30)

### P7 – Autonome Entwicklung
- Feature/BugFix → DEV-Deploy = autonom
- **PR erst als "erledigt" melden, wenn CI grün ist**
- **`dev` Branch → Push** = autonom
- **PR merge (main)** = nach Harald-Approval → **dann ausführen, ohne erneute Rückfrage** (Approval = Auftrag)
- Technische Entscheidungen bis DEV: frei
- MAIN/PROD = Harald
- **Nachweis vor Genehmigungs-Anfrage:** Merge-/PROD-Anfragen nur mit Beleg – CI-Run-Link (grün) + Testnachweis gegen Anforderungen

### Checkliste vor Fertig-Meldung
Bevor ein PR als "ready" gemeldet wird:
1. ✅ CI-Checks alle grün
2. ✅ PR-Beschreibung: Was + Warum + Alternativen + Fehlschlag/Worst-Case + `Closes #N` bei Issue-Bezug (P3)
3. ✅ Living Docs: arc42 + AGENTS.md aktuell
4. ✅ Secrets-Check: nichts committet
5. ✅ Branch auf aktuellem `main` (ggf. rebased)
6. ✅ Kein Force-Push auf PR-Branches
7. ✅ Overclaiming-Check: jede "fertig/funktioniert/garantiert"-Aussage mit Validierungsnachweis + Test-Kontext (P1/P9)

### P7c – Post-Merge-Checkliste
Nach jedem erfolgreichen Merge nach `main` (autonom ausführen, nicht rückfragen):
1. Feature-Branch lokal + remote löschen (`git branch -d <name> && git push origin --delete <name>`)
2. Offene PR-Branches auf neuen `main` rebasen (`git rebase origin/main`)
3. Obsolete PRs schließen (Kommentar mit Begründung)
4. Issue-Closing prüfen: Wurden im PR referenzierte Issues (`Closes #...`) automatisch geschlossen?
5. **Erledigte Issues schließen** – auch ohne `Closes` im PR, wenn der Stand es belegt

### P8 – Wiederholungsfehler-Stopp
Derselbe Fehler **2×** → **STOPP**:
1. Ursache analysieren (Logs, IST-Zustand), nicht dritten Versuch raten
2. Regel/Checkliste prüfen – fehlt eine Regel? → P10
3. Plan B aus Quelle/Referenz (z.B. bewährtes IaC3-Verhalten als Vorlage, P1-geprüft)

### P9 – Kein Overclaiming
- "garantiert korrekt", "verifiziert", "fertig", "funktioniert" **nur nach tatsächlich gelaufener Validierung** (Lint, Testlauf, Quellenvergleich)
- Berichte trennen: "geprüft gegen X" vs. "vermutet/nicht geprüft"
- Kein "garantiert korrekt" aus dem Gedächtnis (Vorfall 2026-07-30: cloud-config mehrfach falsch)

### P10 – Regel-Loop
Jede Korrektur von Harald, jeder Review-Befund (K1/K2), jeder Vorfall → **Regel-/Checklisten-Lücke prüfen und im selben Sprint ergänzen** – nicht erst beim nächsten Mal. Regel-Änderungen sind selbst ein PR (docs).

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
| `.roo/rules/*.mdc` | Regelwerk – auch für Roo/Zoo Code (P4) |
| `.roo/rules/vendor-docs-mandatory.mdc` | Vendor-Docs-Pflicht (neue APIs, Fehler, Entscheidungen) |
| `.roo/rules/ssh-restriction.mdc` | SSH-Transition (Phasen 0-2c) |

## 🔒 SSH-Restriktion
- Phase 0-2a: SSH via Public-IP (Bootstrap, nötig)
- Phase 2b: SSH über öffentliche IP blocken (UFW)
- Ab Phase 2c: SSH NUR via Tailscale
- **Details + aktuelle Umsetzung:** `.roo/rules/ssh-restriction.mdc` (Regel-Korrektur Interface-basiert folgt separat, siehe Issue #11)

## 🚫 Was ich NICHT mache
- ❌ IaC3-RFCs lesen (sind Legacy)
- ❌ IaC3-Scripte direkt portieren (ohne P1-Prüfung)
- ❌ Petrus-Striktur (war Grund für Redesign)
- ❌ Heimlich Tech-Debt akkumulieren (→ K11)
- ❌ Bei Analyse-Aufträgen Dinge umkonfigurieren (P3b)
