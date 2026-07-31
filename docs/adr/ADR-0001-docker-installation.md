# ADR-0001: Docker-Engine-Installation (eigene Tasks vs. Community-Rolle)

- **Status:** Vorgeschlagen (Proposed)
- **Datum:** 2026-07-31
- **Kontext:** IaC4 Phase 3 – Rolle `ansible/roles/docker` befüllen. IaC3 nutzte die Community-Collection `geerlingguy.docker`. IaC4-Prinzip: schlanke Rollen, minimale externe Abhängigkeiten, Reproduzierbarkeit (QZ1). IST-Stand auf `main`: Rolle enthält bereits Tasks (GPG-Key/Repo/Install via `apt_key`/`apt_repository` – veraltete Module, werden in Phase 3 ersetzt).

## Entscheidungsfrage
Wie installiert IaC4 die Docker Engine (inkl. Compose-Plugin) auf dem VPS?

## Optionen

### A: Community-Rolle `geerlingguy.docker` (IaC3-Muster)
- **Fachliche Auswirkungen:** Bewährtes, breit genutztes Muster; weniger eigener Code; aber externe Collection = zusätzliche Supply-Chain (Version pinnen, Update-Zyklus der Collection), Verhalten teilweise undurchsichtig, Overhead für den reinen Install-Fall.
- **Zukunft:** Collection-Updates müssen im IaC4-Update-Prozess mitgezogen werden; bei Collection-Einstellung Umstieg nötig.

### B: Eigene Tasks mit offiziellem Docker-APT-Repo (docker.com) — EMPFEHLUNG
- **Fachliche Auswirkungen:** ~15 Zeilen Ansible (Keyring `docker.asc`, `.sources`-Datei, `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-compose-plugin`); volle Transparenz und Kontrolle; keine externe Collection; offizielle Docker-Doku als SSoT. Wartung: ein Task-Block, Updates laufen über den normalen Baseline-apt-Zyklus. Hinweis: die aktuell auf `main` liegenden Tasks nutzen die **deprecated** Module `apt_key`/`apt_repository` → bei Umsetzung auf `get_url`/`copy` (Keyring) + `.sources`-Datei umstellen (Docker-Doku-Stand).
- **Zukunft:** Paket-Versionen zentral in `group_vars`; Upgrades bewusst per Versions-Bump; bei Bedarf auf Digest-Pinning der Pakete erweiterbar.

### C: Ubuntu-Distributionspaket `docker.io`
- **Fachliche Auswirkungen:** Einfachste Installation, aber Docker empfiehlt das offizielle Repo; `docker.io` ist ein Ubuntu-Backport mit Verzögerung bei Sicherheits-Updates und teils abweichendem Verhalten.
- **Zukunft:** Verpasst Docker-Features/Patches; nicht empfohlen für produktive Infrastruktur.

## Evidenz
- Docker Official Docs: Installation über offizielles APT-Repo mit `docker-ce` + `docker-compose-plugin`, neues `.sources`-Format (docs.docker.com/engine/install/ubuntu/)
- Community-Konsens: offizielles Repo für Produktion, `docker.io` nur für Minimal-Setups
- apt_key-Deprecation: Ansible-Doku (ansible.builtin.apt_key deprecated)

## Empfehlung
**Option B** – eigene Tasks mit offiziellem Docker-Repo. Passt zu IaC4 (schlank, transparent, reproduzierbar), keine Fremd-Collection, Docker-Doku verbindlich. Bestehende IST-Tasks (apt_key/apt_repository, docker-Gruppen-Task) werden bei Phase-3-Umsetzung ersetzt (siehe ADR-0002).

## Worst-Case / Rollback
- **Worst-Case:** Docker-Repo-Key/URL nicht erreichbar oder Paket-`state: present` schlägt fehl → Playbook bricht ab, VPS bleibt im letzten konsistenten Zustand (Ansible-Idempotenz).
- **Rollback:** Fehlerhafter Task-Block → alten Stand aus Git wiederherstellen und erneut deployen; Docker-Pakete sind apt-verwaltet, kein Datenverlust (Volumes/Netzwerk unberührt).
- **Gegenmaßnahme:** Playbook-Lauf in Workflow 04 (ADR-0010) mit sichtbarem Log; BDD-Check `docker --version` nach Deploy.

## Konsequenzen
- Ein Task-Block in `roles/docker/tasks/main.yml` + Variablen in `defaults/main.yml`
- Kein `ansible-galaxy`-Requirement für Docker
- Versions-Pinning der Pakete optional über `group_vars` (vgl. ADR-0003)

## Referenzen
- https://docs.docker.com/engine/install/ubuntu/
- https://docs.docker.com/engine/install/
