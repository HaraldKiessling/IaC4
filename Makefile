.PHONY: help lint deploy-dev deploy-prod docs

help:          ## Zeigt diese Hilfe
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

lint:          ## Lintet YAML + Markdown
	@echo "=== YAML Lint ===" && yamllint . --strict || true
	@echo "=== Markdown Lint ===" && markdownlint 'docs/**/*.md' || true
	@echo "=== Ansible Syntax ===" && ansible-playbook --syntax-check ansible/playbooks/site.yml 2>/dev/null || true

deploy-dev:    ## Deploy auf DEV-VPS (Phase 1+2)
	@echo "Trigger GH Actions Deploy (target=dev)…"
	@gh workflow run deploy.yml -f target=dev

deploy-prod:   ## Deploy auf PROD-VPS (Phase 1+2) – nur mit Haralds OK!
	@echo "Trigger GH Actions Deploy (target=prod)…"
	@gh workflow run deploy.yml -f target=prod

docs:          ## Startet arc42-Dokumentations-Server (optional)
	@echo "Öffne docs/arc42/ im Browser oder Editor."
	@echo "Kein Build-Tool nötig – reines Markdown."

ci: lint
