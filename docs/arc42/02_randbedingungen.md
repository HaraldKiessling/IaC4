# 2. Randbedingungen

## Technisch
- **VPS:** Ubuntu 24.04 LTS (x86_64)
- **Automation:** GitHub Actions + Ansible
- **Netzwerk:** Tailscale (Mesh-VPN)
- **Container:** Docker + Compose
- **CI/CD:** GitHub Actions (Ubuntu-latest Runner)

## Organisatorisch
- **Ein-Personen-Projekt** (Harald)
- **DEV + PROD:** Ein VPS pro Stage
- **Budget:** Keine kostenpflichtigen Dienste (außer VPS-Hosting)
- **Zugriff:** Nur via Tailscale (keine öffentlichen Ports außer Traefik)

## Konventions-Übersicht
- **Branching:** Feature/BugFix → PR → DEV → PR → MAIN
- **Commits:** Conventional Commits
- **Dokumentation:** arc42-light in docs/arc42/ (Deutsch)
- **Repo:** Monorepo für Entwicklungstools, separate Repos für Projekte
