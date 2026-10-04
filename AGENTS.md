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
| **Tailscale-ACL: KEINE Änderung ohne Owner-Zustimmung** (Owner-Regel 2026-09-06) – auch nicht in Feature-Branches / über GH Actions auf Branches; Owner-Vorlage nur mit reviewed Auswirkungen (Autor ≠ Reviewer) + Rollback-Pfad; Details: `.roo/rules/tailscale-acl.mdc` | Alle |
| **Tailscale-ACL ist Infrastruktur und wird in IaC4 verwaltet** (Owner-Entscheid 2026-09-11) – EINE Regelquelle `acl/tailscale-acl.hujson` für beide Tag-Welten (`tag:ia4` + `tag:ha`/`tag:ha-ci`), fester Reihenfolge `tagOwners → acls → ssh`; einziger Apply-Weg `.github/workflows/00-acl-apply.yml` (manuell, `dry_run`/`confirm`) – **nie automatisch**; Details: `docs/adr/ADR-026-*.md`, `acl/README.md` | Alle |
| **Nie direkter Push auf `main`** – nur via PR | Alle |
| **`dev` Push** = autonom (kein PR nötig); Push und Merge auf den Branch `dev` sind frei; Merge-Gate und Merge-Freigabe gelten nur für `main`. Der DEV-Deploy (`workflow_dispatch`, `target=dev`) bleibt erst nach bestandenem Agenten-Review erlaubt, auch wenn der Code auf `dev` liegt | Orchestrator |
| **PR `grün` vor Fertig-Meldung** – erst done, wenn alle CI-Checks pass | Alle |
| **Nie Secrets committen** – immer GH Secrets + `.env.example` | Alle |
| **Nie Gateway-Prozess killen** (Vorfall 2026-07-16, 6h Downtime) | Alle |
| **`main` bleibt immer sauber: Merge auf `main` erst nach bestandenem unabhängigem Agenten-Review, DEV-Vorstellung + expliziter Freigabe** – Ergebnis auf DEV (Deploy-Run-Link, Testnachweis, Test-Kontext) MUSS Harald vorgestellt sein; erst seine ausdrückliche Freigabe danach = Auftrag zum Merge (dann nicht erneut rückfragen). Freigabe vor der DEV-Vorstellung zählt nicht. Gilt auch für andere Repos von Harald (u. a. Home Assistant) | Alle |
| **PROD-Deploy** = nur Harald | Orchestrator |
| **Pre-Flight Validation vor Push** – yamllint + markdownlint lokal prüfen | Alle |
| **Nie `sed`/Regex-Editing auf YAML/JSON/Templates** – gezielt editieren + Parser-Validierung (P4b) | Alle |
| **Kein Overclaiming** – „garantiert korrekt"/„verifiziert" nur mit Validierungsnachweis (P9) | Alle |
| **Force-Push nicht auf PR-Branches** – nur auf ungeteilte Feature- und `session-*`-Branches (1 Branch = 1 Worktree) | Alle |
| **PR-Checkliste vor Fertig-Meldung** – CI grün, Doku aktuell, Secrets-Check, Branch rebased, **unabhängiger Review dokumentiert** (Autor ≠ Reviewer, Issue #37) | Orchestrator |

## ✅ Autonom (kein Approval nötig; Review-Gate und Merge-Gate bleiben unberührt)
- Feature-Branch → Push → CI grün → Agenten-Review bestanden → DEV-Deploy
- **`dev` Branch → Push** = direkt (kein PR)
- **DEV-Deploy auslösen** (Vorbedingung: Agenten-Review bestanden; auch aus Cloud-Sessions, z. B. vom Handy): `03`/`04-service-deploy` mit `target=dev` per `workflow_dispatch` (Tests: `04-bdd-tests` lesend) – siehe „Agenten-Auslösung von Workflows"
- Code schreiben, testen, committen
- Issue-Templates verwenden (Feature/Bug/Change)
- arc42-Doku aktuell halten (P4)

## 📋 Prinzipien P0–P10 (ausführlich)

### P0 – Entscheidungsrollen und Arbeitsweise
- **Harald entscheidet ausschließlich fachlich, nie technisch.** Technische Entscheidungen treffen die Agenten selbst, begründet und belegt (P1/P3). Betrifft eine technische Frage Harald, wird sie auf eine **fachliche Frage zurückgeführt** (Auswirkung, Nutzen, Risiko, Kosten) und mit Empfehlung gestellt. Beispiel: nicht "opus oder inherit?", sondern "Wie viel Prüftiefe ist dir die Mehrkosten wert?". Die harten Regeln und Owner-Freigaben (z. B. ACL, PROD, Merge-Freigabe, Owner-only-Workflows) bleiben Freigaben durch Harald, weil sie Risiko-/Fachentscheidungen sind.
- **Evidenzbasiert auf authentischen Quellen:** Grundlage sind Primärquellen (Hersteller-/Vendor-Doku, Original-Repository, Spezifikation) und der verifizierte IST-Zustand. Sekundärquellen (Blogs, Zusammenfassungen, Modellwissen) sind nur Hinweise und bleiben `[A]`, bis eine Primärquelle sie belegt (P1).
- **Üblicher Standard je Rolle:** Alle Rollen (Engineer, Architect, Reviewer, Orchestrator) arbeiten nach den üblichen Disziplinen eines Senior Developers/Engineers/Architects/Reviewers, z. B. Ursache statt Symptom beheben, kleine nachvollziehbare Änderungen, Verifikation vor Behauptung, Rollback mitdenken, Sicherheit und Idempotenz, ehrliche Angabe von Unsicherheit.

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
- Feature/BugFix → DEV-Deploy = autonom, aber erst nach bestandenem Agenten-Review (siehe Ablauf unten)
- **PR erst als "erledigt" melden, wenn CI grün ist**
- **`dev` Branch → Push** = autonom
- **Ablauf (verbindlich):** fachliche Klärung im Gespräch (Grill) → Branch → CI grün → **unabhängiger Agenten-Review bestanden** (Befunde eingearbeitet und erneut geprüft) → DEV-Deploy vom Branch + Verifikation → Ergebnis Harald vorstellen (fachlich erklärt, Run-Links, Testnachweis) → ausdrückliche Freigabe → Merge. Harald entscheidet fachlich und prüft keine PR-Reviews; der technische Review läuft durch Agenten **vor** seiner Sicht.
- **PR merge (main)** = erst nach bestandenem Review, **DEV-Vorstellung** und **ausdrücklicher Freigabe durch Harald** → **dann ausführen, ohne erneute Rückfrage** (Freigabe = Auftrag; danach Issues schließen, Branch aufräumen, P7c). Eine Freigabe vor der Vorstellung ersetzt sie nicht. **`main` bleibt immer sauber:** nichts Ungeprüftes oder Unfreigegebenes (auch kein Terraform-Auto-Apply durch einen Merge ohne Freigabe).
- Technische Entscheidungen treffen die Agenten (P0), ohne harte Regeln und Freigaben zu berühren; Harald entscheidet nur fachlich
- MAIN/PROD = Harald
- **Nachweis vor Genehmigungs-Anfrage:** Merge-/PROD-Anfragen nur mit Beleg – CI-Run-Link (grün) + Review bestanden (Rollen-Signatur im PR-Thread) + DEV-Deploy-Run-Link + Testnachweis gegen Anforderungen (Test-Kontext nach P1: von wo, welcher Target, gegen welche Quelle)
- **Repo-übergreifend:** Diese Merge-Regel gilt auch für Harald's weitere Repos (insbesondere Home Assistant); sie wird dort in die jeweilige AGENTS.md/CLAUDE.md übernommen

### Agenten-Auslösung von Workflows (Cloud-Sessions, Claude Code)
Agenten (auch Claude-Code-Cloud-Sessions) haben **keinen Host-Zugang** zu den VPS; Analyse und Eingriffe sind darauf ausgelegt, ausschließlich über GH-Actions-Workflows zu laufen (Stand 2026-10-04, `[A]`: keine technische Sperre geprüft).

| Klasse | Workflows | Regel |
|--------|-----------|-------|
| Lesend | `04-bdd-tests` (nur Tests, `target=dev` oder `prod`); `00-acl-apply` nur mit `dry_run=true` (Export oder Dry-Run), nie `dry_run=false` oder `confirm=APPLY-ACL`; `05-device-approve` nur `mode=list` mit `target=dev`; `diagnose-serve` (read-only, `target` immer explizit auf `dev` oder `prod` setzen; der Workflow-Default ist `prod`) | autonom |
| DEV-Deploy | `03-baseline-deploy`, `04-service-deploy` mit `target=dev` | autonom, aber erst nach bestandenem Agenten-Review; Ergebnis danach Harald vorstellen |
| Owner-only | alles mit `target=prod` oder `target=both` (außer den lesenden Zeilen oben); `00-acl-apply` mit `dry_run=false`/`confirm`; `02-tailscale-bootstrap`; `00-generate-ssh-key`; `01-tailscale-terraform` Apply (`apply=true`; läuft zusätzlich automatisch bei Push auf `main` mit `terraform/**`: ein Merge solcher Änderungen löst den Apply aus, Merge-Gate beachten); `05-device-approve` (`approve`/`reject`/`remove`/`e2e`) und `05-device-remove` (Default `target=prod`!); `debug-oauth` (nutzt OAuth-Secrets) | nur Harald bzw. nur nach seiner ausdrücklichen Anweisung im Chat |

Hinweis: Die Einordnung der Klassen ist eine Setzung dieser Regel (Stand 2026-10-04) und von Harald zu bestätigen; die ACL-Governance bleibt unberührt (siehe harte Regeln).

**Docs-/Regel-PRs ohne deploybare Änderung:** Es gibt keinen DEV-Deploy; Agenten-Review, Vorstellung im Chat (fachlich erklärt, mit CI-Run) und ausdrückliche Freigabe vor dem Merge gelten unverändert.

### Checkliste vor Fertig-Meldung
Bevor ein PR als "ready" (bereit für DEV-Deploy und Vorstellung, nicht merge-bereit) gemeldet wird (Punkte 1–8; Punkt 9 gilt zusätzlich unmittelbar vor dem Merge):
1. ✅ CI-Checks alle grün
2. ✅ PR-Beschreibung: Was + Warum + Alternativen + Fehlschlag/Worst-Case + `Closes #N` bei Issue-Bezug (P3)
3. ✅ Living Docs: arc42 + AGENTS.md aktuell
4. ✅ Secrets-Check: nichts committet
5. ✅ Branch auf aktuellem `main` (ggf. rebased)
6. ✅ Kein Force-Push auf PR-Branches
7. ✅ Overclaiming-Check: jede "fertig/funktioniert/garantiert"-Aussage mit Validierungsnachweis + Test-Kontext (P1/P9)
8. ✅ Unabhängiger Agenten-Review **bestanden** (vor DEV-Deploy und vor Vorstellung) und dokumentiert: Autor ≠ Reviewer, Ergebnis (✅ Freigabe / ❌ Befunde) im PR-Thread, Befunde bearbeitet oder als Follow-up verfolgt, Beiträge mit Rollen-Signatur (`✨ Nova` / `🔍 Reviewer` / `🏗️ Architect` / `🔧 Engineer`) (Issue #37)
9. ✅ DEV-Ergebnis Harald vorgestellt (Deploy-Run-Link + Testnachweis; bei Docs-/Regel-PRs ohne Deploy: CI-Run, siehe oben) UND ausdrückliche Freigabe danach erhalten (Merge-Gate)

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
| `CLAUDE.md`, `.claude/agents/` | Claude-Code-Rollen: `reviewer` (Modell `opus`, nur lesend, Pflicht vor Fertig-Meldung/DEV-Deploy/Vorstellung), `architect` (Recherche/Konzept); Hauptsession = Engineer + Orchestrator |
| `.claude/skills/` | Claude-Code-Skills (Pocock, MIT): `/grill-me`, `/grill-with-docs`, `/tdd`, `/diagnosing-bugs`, `/setup-matt-pocock-skills` (+ `grilling`, `domain-modeling`, `codebase-design`); IaC4-Anpassungen + Herkunft: `.claude/skills/UPSTREAM.md` |
| `.roo/rules/vendor-docs-mandatory.mdc` | Vendor-Docs-Pflicht (neue APIs, Fehler, Entscheidungen) |
| `.roo/rules/ssh-restriction.mdc` | SSH-Transition (Phasen 0-2c) |

## Agent skills

### Issue tracker

GitHub Issues in `HaraldKiessling/IaC4`; in Cloud-Sessions über die GitHub-MCP-Tools, nicht `gh`. Siehe `docs/agents/issue-tracker.md`.

### Domain docs

Ein Kontext: Glossar `docs/arc42/12_glossar.md`, ADRs `docs/adr/ADR-NNN-*.md` + Tabelle in `docs/arc42/09_architekturentscheidungen.md`. Siehe `docs/agents/domain.md`.

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
