# IaC4 Migration – Gesamtplan

> **Übergeordnetes Ziel:** IaC3-Inhalte nach IaC4 migrieren, VPS DEV via Tailscale bereitstellen.
> **Stand:** 2026-07-31 | **Methodik:** docs/workflows/methodology.md
> **Aktuell:** Phase 3 (Ansible-Rollen befüllen) — Phase 2 abgeschlossen 2026-07-31 (Workflow 02+03 grün, SSH via Tailscale bestätigt).
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
- [x] OAuth-Client tag:ia3 hinzugefügt (für SSH-ACL-Kompatibilität)
- [x] Workflow 01 (Tailscale Terraform / rotate OAuth) erstellt (force=false)

## ✅ Phase 2: VPS DEV via Tailscale (erledigt)

- [x] Cloud-config korrigiert (NOPASSWD:***)
- [x] VPS DEV installiert (deploy-user + SSH-Key)
- [x] Workflow 02 (Tailscale Bootstrap) erstellt
- [x] Handler `creates:` gefixt (skip Bug)
- [x] Auth-Key `ephemeral: false` (permanenter Server)
- [x] Auth-Key `tag:ia3` (ACL-kompatibel)
- [x] **VPS neu installieren** (letzte cloud-config)
- [x] Workflow 02 (Tailscale Bootstrap) grün — 2026-07-31 (Join tag:ci + Re-Tag tag:ia3, UFW-Restrict mit CGNAT-Allow, Cleanup = Rename)
- [x] SSH-Zugriff via Tailscale bestätigen — 2026-07-31 (SSH-Check in Workflow 02/03 erfolgreich: deploy-user@<Tailscale-IP>)

## ⬜ Phase 3: Ansible-Rollen befüllen

- [x] vps-baseline: Tasks implementiert (Baseline-Deploy grün, 2026-07-31)
- [ ] docker: Tasks implementieren
- [ ] traefik: Tasks implementieren
- [ ] qdrant: Collection-Setup (3072d/Cosine)
- [ ] code-server: Tasks implementieren
- [ ] openclaw-gateway: Tasks implementieren

## ⬜ Phase 4: Services deployen

- [ ] Docker + Traefik auf DEV deployen
- [ ] Qdrant auf DEV deployen
- [ ] Code-Server auf DEV deployen

## ⬜ Phase 5: OpenClaw Minimal

- [ ] OpenClaw Gateway auf DEV deployen
- [ ] Memory-Backend (Qdrant) konfigurieren
- [ ] WebSearch-Tool einrichten

## ⬜ Phase 6: CI/CD ausbauen

- [ ] 03-baseline-deploy: Vollständiger Run
- [ ] 04-service-deploy (neu): Vollständiger Run
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
- [ ] Post-Deploy-Verifikation + Gap-Analyse PROD
- [ ] IaC3-Deployments auf PROD stoppen (IaC3 → Backup-Modus)

## ✅ Phase 9: IaC3 in den Backup-Modus

- [ ] IaC3-Workflows deaktivieren (keine Deploys auf dev/prod)
- [ ] IaC3-Repo als Backup-Referenz markieren (README-Hinweis)
- [ ] Finale Dokumentation: IaC4 = Single Source of Truth

## 🔴 Tech-Debt (dokumentiert in arc42 K11)

- [ ] Qdrant-Volume-Backup
- [ ] Ollama (niedrige Prio)
- [ ] Monitoring/Alerting
- [ ] Fehlende API-Secrets (Gemini, OpenRouter)
