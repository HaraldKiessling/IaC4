# IaC4 Migration – Gesamtplan

> **Übergeordnetes Ziel:** IaC3-Inhalte nach IaC4 migrieren, VPS DEV via Tailscale bereitstellen.
> **Stand:** 2026-07-31 | **Methodik:** docs/workflows/methodology.md
> **Aktuell:** Phase 3 (Ansible-Rollen befüllen) — Phase 2 abgeschlossen 2026-07-31 (Workflow 02+03 grün, SSH via Tailscale bestätigt). Design-Basis: ADR-015..024 (`docs/adr/`, 2026-07-31; Ollama-Priorisierung durch Harald).
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
- [ ] qdrant: Collection-Setup (3072d/Cosine)
- [ ] code-server: Tasks implementieren
- [ ] openclaw-gateway: Tasks implementieren

## ⬜ Phase 4: Services deployen

- [ ] Docker + Traefik auf DEV deployen
- [ ] Ollama auf DEV deployen (erster Service, ADR-021..023)
- [ ] Qdrant auf DEV deployen
- [ ] Code-Server auf DEV deployen

## ⬜ Phase 5: OpenClaw Minimal

- [ ] OpenClaw-Gateways auf DEV deployen (Docker-Container, Multi-Instanz OC1/OC2, Design: ADR-025 revidiert 2026-08-01)
- [ ] Memory-Backend (Qdrant) konfigurieren
- [ ] WebSearch-Tool einrichten

## ⬜ Phase 6: CI/CD ausbauen

- [ ] 03-baseline-deploy: Vollständiger Run
- [ ] 04-service-deploy (neu): Vollständiger Run
- [ ] BDD-Szenarien aus ADR-018/019/021 konkretisieren (Serve-Status, 8080-CGNAT, 11434-Nicht-Erreichbarkeit) in `qa/bdd-testkonzept.md`
- [ ] 05-openclaw-install (neu): Vollständiger Run
- [ ] CI mit Quality-Gates

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

## 🔲 Offene Punkte (Stand 2026-07-31)

> Erfasst nach Abschluss der Regel-Härtung, BDD-Einführung, UFW-Fix, OAuth-only-Umbau und Option A (Tag-Design tag:ia4). Bewusst offen gelassen — kein Blocker für den laufenden Betrieb.

- [ ] **arc42/11-Risiko-Einträge übernehmen:** R-001 (Lockout durch SSH-Restrict-Fehler, Schwere hoch/W'keit niedrig) und R-002 (Tag-Umbruch bricht TS-SSH) aus `docs/plans/iac4-firewall-konzept.md` §6/§9.5 in `docs/arc42/11_risiken_und_technische_schulden.md` übernehmen — R-001 mit der bestehenden K11-Zeile „SSH-Lockout bei Tailscale-Ausfall" **harmonisieren, nicht duplizieren**; nach Übernahme im Firewall-Konzept §8.3 abhaken
- [ ] **Neuer Tailscale-API-Key für 01-/ACL-Runs:** Der temporäre Key ist ungültig (401 seit 2026-07-31 15:36). Workflow 01 (Terraform-Provider) und `ensure-acl-ia4.py` brauchen für echte Änderungen einen gültigen Key (Konsole → Generate API Key). Tagesbetrieb 02/03/04 ist davon unabhängig (OAuth-only).
- [ ] **Fresh-Node-Join-Verifikation:** Der Exact-Match-Auth-Key `[tag:ci, tag:ia4]` (Option A) ist erst bei der nächsten Neuprovisionierung eines VPS empirisch testbar (Join direkt mit tag:ia4, kein Re-Tag nötig) — 02-Re-Run auf dem Bestands-VPS ist nach dem SSH-Restrict nicht mehr möglich (Re-Run-Design, Firewall-Konzept §5)
- [ ] **PROD-Migration** (Migrationsplan Phase 8): weiterhin offen — VPS prod ist noch IaC3; nach erfolgreichem IaC4-dev-Betrieb migrieren (Details in Phase-8-Checkboxen unten)
- [ ] **Firewall-Konzept-Verifikationsreste** (`docs/plans/iac4-firewall-konzept.md` §8, dort geführt und abzuhaken): §8.2 Lockout-Vorfall-Rekonstruktion (Logs 2026-07-31 früh), §8.4 Vendor-Empfehlung vs. CGNAT-Allow (Entscheidung dokumentieren), §8.5 Tailscale-Version + ts-input-41641-Regel verifizieren

> **Abgrenzung:** Weitere Konzept-Reste (netfilter-mode) sind durch BDD-T4 beantwortet; die übrigen offenen Punkte des Firewall-Konzepts werden ausschließlich dort geführt — diese Liste ist der Sammelpunkt auf Migrationsplan-Ebene.
