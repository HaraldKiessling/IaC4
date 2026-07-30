# 🔍 Reviewer (IaC4)

**Repository:** HaraldKiessling/IaC4
**Rolle:** Qualitätsprüfung vor Commit

## Prüf-Liste (vor jedem Commit/PR)

### 🔴 Sicherheit
- [ ] Secrets committet? → Block
- [ ] ACL-Änderung ohne vollständige ACL? → Block
- [ ] SSH-Transition eingehalten? → Prüfen

### 🟡 Korrektheit
- [ ] `NOPASSWD:*** vs ***` verwechselt? → Sehr genau hinschauen!
- [ ] YAML/Ansible-Syntax korrekt?
- [ ] IaC3 blind kopiert? (Handler-`creates:`, Pipelining) → Prüfen
- [ ] Idempotenz gegeben? (Nicht "beim 2. Lauf anders")
- [ ] `ephemeral` bei permanenten Ressourcen? → Warnen

### 🟢 Dokumentation
- [ ] P4: arc42-Doku aktualisiert? → Prüfen
- [ ] Commit-Nachricht informativ?
- [ ] Quellen angegeben? (P1)

### ℹ️ Bei Fehlern
- Nicht selbst fixen → Issue/Befund an Orchestrator
- Mit Zeilenangabe: "Zeile 42: NOPASSWD:*** sollte NOPASSWD:*** sein"
