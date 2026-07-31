# ADR-016: Docker-Zugriff für `deploy-user` (docker-Gruppe vs. sudo)

- **Status:** Vorgeschlagen (Proposed)
- **Datum:** 2026-07-31
- **Kontext:** IaC3 fügte den VPS-User zur docker-Gruppe hinzu. IaC4 läuft mit `deploy-user`, der laut `cloud-config.yaml` bereits `sudo: ALL=(ALL) NOPASSWD:ALL` besitzt. Ansible-Tasks laufen via `become: true` als root und benötigen keine Gruppen-Mitgliedschaft. **IST-Widerspruch:** `ansible/roles/docker/tasks/main.yml` enthält den Task „deploy-user-User zur Docker-Gruppe hinzufügen" → wird bei Phase-3-Umsetzung entfernt (diese ADR entscheidet gegen die Gruppe).

## Entscheidungsfrage
Braucht `deploy-user` Mitgliedschaft in der docker-Gruppe, oder läuft Docker-Administration über sudo?

## Optionen

### A: `deploy-user` in docker-Gruppe (IaC3-Muster)
- **Fachliche Auswirkungen:** Bequem (direkt `docker ps` in SSH-Session), aber docker-Gruppe = **root-Äquivalent** (Daemon läuft als root; Socket-Zugriff erlaubt Host-Dateisystem-Mounts, privileged Container). Keine Audit-Trail, Aktionen erscheinen nicht in sudo-Logs.
- **Zukunft:** Jede Kompromittierung des Accounts = voller Host-Zugriff ohne Spuren; bei zusätzlichen Usern skaliert das Risiko.

### B: Keine Gruppen-Mitgliedschaft; Docker via sudo (NOPASSWD) — EMPFEHLUNG
- **Fachliche Auswirkungen:** `deploy-user` hat bereits NOPASSWD-sudo → faktisch gleiche Privilegien, aber **auditierbar** (sudo-Logs), Policy steuerbar; Prinzip „ein Weg zu root" bleibt sauber. Ansible braucht keine Änderung (become: root). **Ehrliche Einordnung:** eine engere sudoers-Regel (`NOPASSWD: /usr/bin/docker …`) ist erst wirksam, wenn `cloud-config.yaml`/vps-baseline `ALL=(ALL) NOPASSWD:ALL` auf spezifische Regeln reduziert (sudoers-Vereinigungs-Semantik) → dokumentierte Phase-3-Verschärfung, kein Sofort-Effekt.
- **Zukunft:** Zusätzliche User bekommen kontrollierten Zugriff via sudoers, nicht via Gruppe; Docker-Socket bleibt root-only.

### C: Rootless Docker (echtes Least-Privilege)
- **Fachliche Auswirkungen:** Daemon als unprivilegierter User, deutlich kleinere Angriffsfläche. Aber: Port 80/443-Bindung (Traefik) kollidiert mit Privileged-Ports, Docker-Socket-Pfad weicht ab, Ansible-Integration komplexer.
- **Zukunft:** Interessant bei Multi-User-Betrieb; für Single-Admin-VPS aktuell Overhead ohne fachlichen Mehrwert (deploy-user ist ohnehin sudo-fähig).

## Evidenz
- Docker-Doku: „The docker group grants privileges equivalent to the root user"
- Sicherheitsanalysen (u.a. securitum.com, Stack Overflow/Unix.SE-Konsens): docker-Gruppe = root-Äquivalent, Empfehlung: sudo-basiert mit Logging statt Gruppe
- Docker-Doku: Rootless-Modus als Härtungsoption, aber mit Einschränkungen (Privileged-Ports)

## Empfehlung
**Option B** – `deploy-user` NICHT in docker-Gruppe. Docker-Kommandos via sudo (auditierbar), Ansible läuft als root. Security-Gewinn bei gleicher Bequemlichkeit, da NOPASSWD-sudo bereits existiert. Der IST-Task „deploy-user in docker-Gruppe" wird bei Phase-3-Umsetzung **entfernt**.

## Worst-Case / Rollback (Pflicht: Expositions-/Privilegien-Entscheidung)
- **Worst-Case:** Kompromittierung von `deploy-user` → voller Host-Zugriff (bestehendes Risiko durch `NOPASSWD:ALL`, **nicht** durch docker-Gruppe erhöht; ohne Gruppe zusätzlich ohne Docker-Socket-Angriffsvektor).
- **Rollback:** SSH-Keys + sudoers rotieren; Gruppen-Mitgliedschaft wird nie vergeben (nichts zu entfernen).
- **Gegenmaßnahme:** sudo-Log-Monitoring (`/var/log/auth.log`), Phase-3-Verschärfung `NOPASSWD:ALL` → spezifische Regeln, BDD-Check „deploy-user nicht in docker-Gruppe" (`id deploy-user`).

## Konsequenzen
- Docker-Rolle erstellt KEINE Gruppen-Mitgliedschaft (abweichend von IaC3)
- Phase-3-Umsetzung: Task in `roles/docker/tasks/main.yml` entfernen + BDD-Check ergänzen
- Operative Anweisung: Docker-Wartung via `sudo docker …`; sudoers-Verschärfung als eigenes Task (vps-baseline)

## Referenzen
- https://docs.docker.com/engine/install/linux-postinstall/
- https://www.securitum.com/privilege_escalation_through_docker_group_membership_and_sudo_backdoor.html
- https://unix.stackexchange.com/questions/743501/is-installing-docker-itself-risky-the-possibility-of-creating-docker-groups
