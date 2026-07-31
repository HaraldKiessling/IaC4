# ADR-024: Service-Deployment-Workflow (ein Workflow mit Selektion vs. pro Service)

- **Status:** Vorgeschlagen (Proposed)
- **Datum:** 2026-07-31
- **Kontext:** Migrationsplan Phase 6: `04-service-deploy` (neu) für docker, traefik, ollama – später qdrant, code-server, openclaw-gateway. IaC3 nutzte ein `deploy.yml` mit Playbook-Selektion. GitHub-Actions-Evidenz: bei vielen Services empfiehlt sich Orchestrator + Reusable Workflows; bei wenigen genügt ein einzelner Workflow.

## Entscheidungsfrage
Wie strukturiert IaC4 den Service-Deploy-Workflow?

## Optionen

### A: Ein `04-service-deploy.yml` mit `workflow_dispatch`-Input `playbook` (docker|traefik|ollama|…) — EMPFEHLUNG
- **Fachliche Auswirkungen:** Ein Einstiegspunkt (konsistent mit IaC3-Erfahrung), geteilte Vorbereitung (Tailscale-Connect, Ansible-Setup, Tagging) einmal implementiert; UI-Formular mit Choice-Input; Ablauf: Tailscale-Connect → `ansible-playbook` mit `inputs.playbook` → Git-Tag. Nachteil: Datei wächst mit jedem Service (Conditionals), Änderungen betreffen den gemeinsamen Workflow.
- **Zukunft:** Tragfähig bis ~5-6 Playbooks; danach auf C migrieren (Schwellwert dokumentieren).

### B: Separater Workflow pro Service (`04-deploy-docker.yml`, `04-deploy-traefik.yml`, …)
- **Fachliche Auswirkungen:** Kleine, fokussierte Dateien; aber Duplikation der Infrastruktur-Schritte (Tailscale-Connect, Runner-Auth, Ansible-Install, Tagging) – genau die Fehlerquelle, die IaC4 vermeiden will; Cross-Service-Reihenfolge (docker vor traefik) liegt beim Operator.
- **Zukunft:** Bei Service-Team-Grenzen sinnvoll – hier Single-Operator, kein Vorteil.

### C: Orchestrator + Reusable Workflows (GH-Actions-Muster)
- **Fachliche Auswirkungen:** Ein Einstiegspunkt, der per `uses:` service-spezifische Reusable Workflows (`workflow_call`) aufruft; beste Skalierung und Entkopplung; aber: mehr Dateien, `workflow_call`-Komplexität (Input-Weitergabe, Fehler-Debugging), aktuell für 3 Services Overhead.
- **Zukunft:** Migrationsziel, sobald Services eigene Pre/Post-Schritte brauchen oder >5 Playbooks.

## Evidenz
- GitHub-Doku: `workflow_dispatch` mit Choice-Inputs; Reusable Workflows (`workflow_call`) für gemeinsame Orchestrierung
- Community-Konsens (GitHub-Community-Diskussionen zu single-vs-multiple workflows): Orchestrator+Reusable bei vielen Services; einzelner Workflow bei wenigen Services völlig ausreichend; Duplikation in separaten Workflows als Anti-Pattern
- IaC3-Praxis: `deploy.yml` mit Playbook-Selektion bewährt (BDD-validiert)

## Empfehlung
**Option A** – ein `04-service-deploy.yml` mit `inputs.playbook`-Selektion. **Migrationsregel:** ab 5 Playbooks oder sobald Services eigene Vor-/Nachschritte benötigen → Umstieg auf C (Orchestrator + Reusable), dokumentiert als Tech-Debt-Item.

## Worst-Case / Rollback
- **Worst-Case 1:** Fehlerhafter Playbook-Stand deployed auf DEV (z.B. Traefik-Config kaputt) → Service unerreichbar.
  - **Rollback:** letzten bekannten guten Commit identifizieren (`git log`), per Hotfix-PR zurücksetzen, Workflow erneut ausführen; Container-Rollback via Image-Tag (ADR-017).
- **Worst-Case 2:** Workflow-Selektion deployt falsches Playbook (Operator-Fehler).
  - **Rollback:** betroffenen Service zurücksetzen; Reihenfolge-Abhängigkeiten (docker → traefik → ollama) werden durch BDD-Checks („Voraussetzung erfüllt?") abgesichert.
- **Gegenmaßnahme:** Post-Deploy-Verifikation (BDD, Phase 7-Skript `scripts/verify-deployment.sh`); Choice-Input statt Freitext (Tippfehler-Schutz); DEV-only-Deploy-Policy (PROD nur mit Freigabe).

## Konsequenzen
- Eine Workflow-Datei, ein Wartungspunkt; Services ergänzen je einen `if`-Zweig + Playbook
- Reihenfolge-Verantwortung beim Operator (docker → traefik → ollama), Verifikation über Post-Deploy-Checks
- Migrationsschwelle in den Workflow-Kommentar schreiben

## Referenzen
- <https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions>
- <https://docs.github.com/actions/sharing-automations/reusing-workflows>
- <https://github.com/orgs/community/discussions/8774>
