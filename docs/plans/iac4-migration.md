# IaC4 Migration – Gesamtplan

> **Übergeordnetes Ziel:** IaC3-Inhalte nach IaC4 migrieren, VPS DEV via Tailscale bereitstellen.
> **Stand:** 2026-08-04 | **Methodik:** docs/workflows/methodology.md
> **Aktuell:** Phase 3–5 abgeschlossen (DEV) — code-server deployed + abgenommen 2026-08-04, Update-/Rollback-Prozess via Pin-Bump verifiziert (ADR-017). Offen: Phase-6-Reste, Phase 7–9. Design-Basis: ADR-015..024 (`docs/adr/`, 2026-07-31; Ollama-Priorisierung durch Harald).
> **Workflow-Nummern = Ausführungsreihenfolge:** 02 (Bootstrap) → 03 (Baseline) → Services (docs/workflows/deploy-stages.md)

## ✅ Phase 0: Grundstruktur (erledigt)

- [x] Repo-Struktur entworfen und gepusht (58 Dateien)
- [x] arc42-Dokumentation (12 Kapitel DE) angelegt
- [x] Issue-Templates (Feature/Bug/Change) hinterlegt
- [x] SSH-Key-Paar generiert + GH Secrets gesetzt
- [x] Cloud-config mit deploy-user + SSH-Key erstellt
- [x] `.roo/rules/` für Zoo Code angelegt
- [x] `.openclaw/agents/` mit Rollen angelegt
- [x] Arbeitsmethodik dokumentiert (8-Schritte)
- [x] Plan-Management dokumentiert (docs/plans/)

## ✅ Phase 1: Tailscale OAuth (erledigt)

- [x] Terraform OAuth-Client erzeugt (IaC4 GH Secrets gespeichert)
- [x] OAuth-Client tag:ia3 hinzugefügt (für SSH-ACL-Kompatibilität) — *historisch, ersetzt durch Option A (tag:ia4, 2026-07-31)*
- [x] Workflow 01 (Tailscale Terraform / rotate OAuth) erstellt (force=false)

## ✅ Phase 2: VPS DEV via Tailscale (erledigt)

- [x] Cloud-config korrigiert (NOPASSWD:***)
- [x] VPS DEV installiert (deploy-user + SSH-Key)
- [x] Workflow 02 (Tailscale Bootstrap) erstellt
- [x] Handler `creates:` gefixt (skip Bug)
- [x] Auth-Key `ephemeral: false` (permanenter Server)
- [x] Auth-Key `tag:ia3` (ACL-kompatibel) — *historisch, ersetzt durch Exact-Match `[tag:ci, tag:ia4]` (Option A)*
- [x] **VPS neu installieren** (letzte cloud-config)
- [x] Workflow 02 (Tailscale Bootstrap) grün — 2026-07-31 (Join tag:ci + Re-Tag tag:ia3, UFW-Restrict mit CGNAT-Allow, Cleanup = Rename) — *hist. Stand; seit Option A: Join direkt tag:ia4*
- [x] **Option A (2026-07-31):** OAuth-Client `[tag:ci, tag:ia4]` (IaC3-Muster, Exact-Match), Auth-Key `[tag:ci, tag:ia4]`, Runner-Join `tag:ci,tag:ia4`, vps-dev → `tag:ia4`; ACL additiv um ia4 erweitert (`scripts/ensure-acl-ia4.py`, Workflow 01, Backup+Rollback); BDD-Lauf 4 komplett grün
- [x] SSH-Zugriff via Tailscale bestätigen — 2026-07-31 (SSH-Check in Workflow 02/03 erfolgreich: deploy-user@<Tailscale-IP>)

## ⬜ Phase 3: Ansible-Rollen befüllen

- [x] vps-baseline: Tasks implementiert (Baseline-Deploy grün, 2026-07-31)
- [x] docker: Tasks implementieren (2026-07-31, ADR-015/016/017)
- [x] traefik: Tasks implementieren (2026-07-31, ADR-017..020)
- [x] ollama: Tasks implementieren (Rolle NEU, 2026-07-31; ADR-021..023)
- [x] LE-Reste entfernen (ADR-018 P4-Delta): group_vars `traefik_acme_email` ✅, Template-Port 443 ✅, `.env.example` ✅ (2026-07-31)
- [x] qdrant: Collection-Setup (zoocode-3072d, 3072d/Cosine) — deployed 2026-08-01, BDD Q4 grün
- [x] code-server: Tasks implementieren — umgesetzt + **abgenommen** (2026-08-04, Issue #65; PR #94/#95; Abnahme Harald: Update-Test + ZooCode/Qdrant-Gemini produktiv)
- [x] openclaw-gateway: Tasks implementieren — deployed 2026-08-01 (Container-Multi-Instanz OC1/OC2, ADR-025 revidiert)

## ✅ Phase 4: Services deployen (DEV abgeschlossen 2026-08-04 — inkl. code-server)

- [x] Docker + Traefik auf DEV deployen — 2026-08-01 (Dashboard via Serve-HTTPS, BDD D1-D10 grün)
- [x] Ollama auf DEV deployen (erster Service, ADR-021..023) — 2026-08-01, BDD O1-O3 grün
- [x] Qdrant auf DEV deployen — 2026-08-01 (TS-TLS 6333 + TCP 6334), BDD Q1-Q5 grün
- [x] Code-Server auf DEV deployen — deployed + **abgenommen** (2026-08-04, Issue #65; Update-/Rollback-Prozess verifiziert: 4.131.0→4.130.0→4.131.0, Persistenz via Volume bestätigt)

## ✅ Phase 5: OpenClaw (DEV abgeschlossen 2026-08-01)

- [x] OpenClaw-Gateways auf DEV deployen (Docker-Container, Multi-Instanz OC1/OC2, Design: ADR-025 revidiert) — 2026-08-01, BDD O1-O4 grün (62/62 Gesamtlauf)
- [x] Memory: Default-Backend (qmd) je Instanz aktiv; Qdrant-Backend als spätere Option (bewusst, Reviewer B11)
- [x] WebSearch-Tool einrichten — Perplexity-Plugin mit OpenRouter-Key (Legacy-Pfad, offiziell unterstützt)

## ⬜ Phase 6: CI/CD ausbauen

- [x] 03-baseline-deploy: Vollständiger Run — grün (2026-07-31, Phase 2; SSH via Tailscale bestätigt)
- [x] 04-service-deploy (neu): Vollständiger Run — grün (mehrfach, u.a. 2026-08-04 Update-Test: 4× success)
- [x] BDD-Szenarien aus ADR-018/019/021 konkretisieren (Serve-Status, 8080-CGNAT, 11434-Nicht-Erreichbarkeit) in `qa/bdd-testkonzept.md` — enthalten (2026-08-04) + code-server C1–C5 ergänzt
- [x] 05-openclaw-install (neu): Vollständiger Run — via 04-service-deploy playbook=openclaw deployed (2026-08-01, BDD O1–O4 grün; erneute Runs 2026-08-04)
- [x] CI mit Quality-Gates — ci.yml (Lint + Quality Gate) grün bei PRs #94/#95 (2026-08-04)

## ⬜ Phase 7: Post-Deploy + Security

- [ ] Post-Deploy-Verifikation (scripts/verify-deployment.sh)
- [ ] arc42 living docs updaten (P4)
- [ ] Gap-Analyse (P5)
- [ ] Tech-Debt in K11 aktualisieren

## ⬜ Phase 8: VPS PROD nach IaC4 migrieren (nach erfolgreichem DEV-Betrieb)

> **Voraussetzung:** Phase 2-7 auf DEV vollständig grün (Tailscale, Baseline, Services, OpenClaw, CI/CD).

- [ ] VPS PROD mit IaC4-Cloud-Config neu installieren (deploy-user + IaC4-SSH-Key)
- [ ] Workflow 02 (Tailscale Bootstrap) auf `target=prod` ausführen
- [ ] SSH-Zugriff via Tailscale auf PROD bestätigen
- [ ] Baseline + Services + OpenClaw auf PROD deployen (Workflows 03, 04, 05)
- [ ] Post-Deploy-Verifikation + Gap-Analyse PROD (inkl. BDD-Lauf 04 auf `target=prod`)
- [ ] `VPS_PROD_PUBLIC_IP`-Secret setzen (vor Workflow 02 auf prod)
- [ ] IaC3-Deployments auf PROD stoppen (IaC3 → Backup-Modus)

## ✅ Phase 9: IaC3 in den Backup-Modus

- [ ] IaC3-Workflows deaktivieren (keine Deploys auf dev/prod)
- [ ] IaC3-Repo als Backup-Referenz markieren (README-Hinweis)
- [ ] Finale Dokumentation: IaC4 = Single Source of Truth

## 🔴 Tech-Debt (dokumentiert in arc42 K11)

- [ ] Idempotenz-Kosmetik: Swap/Zeitzone-Tasks in vps-baseline ohne `changed_when` → Ansible meldet „changed“ trotz no-op (2026-07-31, LOW)
- [ ] Qdrant-Volume-Backup
- [x] ~~Ollama (niedrige Prio)~~ → **erledigt 2026-07-31:** Ollama wird migriert (erster Service, ADR-021..023)
- [ ] Monitoring/Alerting
- [ ] Fehlende API-Secrets (Gemini, OpenRouter)

## 🔲 Offene Punkte (Stand 2026-08-04)

> Erfasst nach Abschluss der Regel-Härtung, BDD-Einführung, UFW-Fix, OAuth-only-Umbau, Option A (Tag-Design tag:ia4) und der code-server-Abnahme (2026-08-04). Bewusst offen gelassen — kein Blocker für den laufenden DEV-Betrieb.

- [ ] **arc42/11-Risiko-Einträge übernehmen:** R-001 (Lockout durch SSH-Restrict-Fehler, Schwere hoch/W'keit niedrig) und R-002 (Tag-Umbruch bricht TS-SSH) aus `docs/plans/iac4-firewall-konzept.md` §6/§9.5 in `docs/arc42/11_risiken_und_technische_schulden.md` übernehmen — R-001 mit der bestehenden K11-Zeile „SSH-Lockout bei Tailscale-Ausfall" **harmonisieren, nicht duplizieren**; nach Übernahme im Firewall-Konzept §8.3 abhaken
- [ ] **Neuer Tailscale-API-Key für 01-/ACL-Runs:** Der temporäre Key ist ungültig (401 seit 2026-07-31 15:36). Workflow 01 (Terraform-Provider) und `ensure-acl-ia4.py` brauchen für echte Änderungen einen gültigen Key (Konsole → Generate API Key). Tagesbetrieb 02/03/04 ist davon unabhängig (OAuth-only).
- [ ] **Fresh-Node-Join-Verifikation:** Der Exact-Match-Auth-Key `[tag:ci, tag:ia4]` (Option A) ist erst bei der nächsten Neuprovisionierung eines VPS empirisch testbar (Join direkt mit tag:ia4, kein Re-Tag nötig) — 02-Re-Run auf dem Bestands-VPS ist nach dem SSH-Restrict nicht mehr möglich (Re-Run-Design, Firewall-Konzept §5)
- [ ] **PROD-Migration** (Migrationsplan Phase 8): weiterhin offen — VPS prod ist noch IaC3; nach erfolgreichem IaC4-dev-Betrieb migrieren (Details in Phase-8-Checkboxen unten)
- [ ] **code-server-Follow-ups (PR #94/#95):** K4-3: `/workspace`-Task chown't bei jedem Lauf auch ein bestehendes Verzeichnis auf 1000:1000 → bei PROD-Migration (Phase 8) nur bei Abwesenheit anlegen oder explizit dokumentieren; K5-3: BDD-C2 stderr-Rauschen (kosmetisch)
- [ ] **Firewall-Konzept-Verifikationsreste** (`docs/plans/iac4-firewall-konzept.md` §8, dort geführt und abzuhaken): §8.2 Lockout-Vorfall-Rekonstruktion (Logs 2026-07-31 früh), §8.4 Vendor-Empfehlung vs. CGNAT-Allow (Entscheidung dokumentieren), §8.5 Tailscale-Version + ts-input-41641-Regel verifizieren

> **Abgrenzung:** Weitere Konzept-Reste (netfilter-mode) sind durch BDD-T4 beantwortet; die übrigen offenen Punkte des Firewall-Konzepts werden ausschließlich dort geführt — diese Liste ist der Sammelpunkt auf Migrationsplan-Ebene.
