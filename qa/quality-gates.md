# Quality Gates

## Definition: "Grün"

### Für DEV-Deploy
- Ansible-Playbook erfolgreich durchgelaufen
- Health-Check bestanden (Traefik, Qdrant, OpenClaw)
- Keine Errors in GH Actions Log

### Für PR von DEV → MAIN
✅ Alle DEV-Gates
✅ CI-Pipeline (YAML-Lint, Markdown-Lint, arc42-Check)
✅ Deployment auf DEV erfolgreich (nachweisbar via Log)
✅ arc42-Dokumentation aktualisiert (P4)

### Für MAIN → PROD
✅ Alle DEV-Gates
✅ Haralds manuelles OK
✅ Grün gelaufener DEV-Deploy der getaggten Version
