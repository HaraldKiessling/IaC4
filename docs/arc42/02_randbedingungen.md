# 2. Randbedingungen

## Technisch
- **VPS:** Ubuntu 24.04 LTS (x86_64)
- **VPS-User:** `deploy-user` (sudo + SSH-Key)
- **Automation:** GitHub Actions + Ansible
- **Netzwerk:** Public-IP initial, dann Tailscale (Mesh-VPN, dauerhaft)
- **Container:** Docker + Compose
- **CI/CD:** GitHub Actions (Ubuntu-latest Runner)

## Organisatorisch
- **Ein-Personen-Projekt** (Harald)
- **DEV + PROD:** Ein VPS pro Stage
- **Budget:** Keine kostenpflichtigen Dienste (außer VPS-Hosting)
- **Zugriff:** Initial Public-IP SSH (Bootstrap), nach Phase 2b nur Tailscale
- **IaC3-Abgrenzung:** Kein Petrus, keine RFCs, arc42-light

## Konventions-Übersicht
- **Branching:** Feature/BugFix → PR → DEV → PR → MAIN; Worktree-Sessions: `session-*/<topic>` → PR (Issue #29)
- **Commits:** Conventional Commits
- **Dokumentation:** arc42-light in docs/arc42/ (Deutsch)
- **Repo:** Monorepo für IaC4; separate Repos für home-assistant und openclaw-config
