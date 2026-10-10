# ADR-027: Agenten-Zugangsdaten über Bitwarden-Skill und OpenClaw-Freigaben (Konfigurieren statt Eigenbau)

- **Status:** Vorgeschlagen (Proposed)
- **Datum:** 2026-10-10
- **Kontext:** Issue #192. Die OC-Instanzen (oc1–oc3 auf DEV und PROD) sollen
  sich zur Laufzeit selbst bei Portalen anmelden können (Agenten-Zugangsdaten,
  Glossar K12) und dafür Einträge in einem Passwort-Manager lesen, anlegen,
  ändern und löschen. Heute bekommt jede Instanz nur `BITWARDEN_CLIENTSECRET`
  als Umgebungsvariable
  (`ansible/roles/openclaw-gateway/templates/docker-compose.yml.j2:31-33`,
  `.github/workflows/04-service-deploy.yml:123-128`) [I]. Ohne Master-Passwort
  lässt sich der Tresor damit nicht entschlüsseln [V]
  (<https://bitwarden.com/help/personal-api-key/>), der Agent kann also nichts
  lesen. Ein Skill wird heute nicht ausgerollt (kein Treffer für `skill` in
  `ansible/roles/openclaw-gateway/`) [I].

## Fachliche Vorgaben (Owner, 2026-10-10)

1. **So wenig Eigenentwicklung wie möglich:** vorhandene OpenClaw-Skills,
   Plugins und Bordmittel nutzen, nur konfigurieren und ausrollen.
2. **Store:** ein eigenes, kostenloses Bitwarden-Konto (Cloud EU), nur für die
   OC-Instanzen (Agenten-Tresor). Keine Kosten.
3. **Sichtbarkeit:** alle sechs Instanzen sehen dieselben Einträge, keine
   Trennung DEV/PROD. DEV verhält sich identisch zu PROD.
4. **Rechte:** Lesen, Anlegen, Ändern und Löschen sind erlaubt.
5. **Freigabe:** Harald bestätigt Zugriffe per Telegram am Handy.
6. **Überall verfügbar:** Der Skill wird mit dem Deploy der OC-Instanzen
   ausgerollt und steht jeder Session der Instanz zur Verfügung, unabhängig
   davon, in welchem Repo sie arbeitet. Er übersteht Recreate und Neu-Deploy.
7. **MFA:** Bei MFA-geschützten Zugängen (typisch Banken) authentifiziert sich
   Harald zusätzlich selbst; das ist gewollt.

## Entscheidungsfrage

Wie bekommen die Agenten Zugriff auf den Agenten-Tresor, mit Haralds Freigabe
am Handy, ohne eigene Software zu entwickeln?

## Optionen

### A: Konfigurieren — Bitwarden CLI + Bitwarden-Skill + OpenClaw-Exec-Freigaben — ENTSCHEIDUNG
- **Bitwarden CLI** (`bw`, offiziell von Bitwarden) als gepinnte Version
  (ADR-017) außerhalb der Volumes: Ansible legt sie auf dem Host ab und bindet
  sie schreibgeschützt in jeden OC-Container ein. Anmeldung ohne Bediener mit
  `bw login --apikey` (`BW_CLIENTID`/`BW_CLIENTSECRET`) und
  `bw unlock --passwordenv BW_PASSWORD` [V]
  (<https://bitwarden.com/help/cli/>). Ob Bitwarden ein eigenständiges
  Linux-Binary liefert oder Node nötig ist, wird beim Bau geprüft [A].
- **Skill:** ein fertiger Community-Skill, Kandidat `bitclawden` (MIT-0, `bw`,
  Lesen/Anlegen/Ändern/Erzeugen) [V]
  (<https://clawhub.ai/typhonius/bitclawden>). Er wird geprüft, als Vorlage
  in IaC4 versioniert und um das Löschen und den Hinweis auf Freigaben
  ergänzt. Nie live von ClawHub geladen, wegen bekannter bösartiger Skills
  dort [V]
  (<https://esecurityplanet.com/threats/hundreds-of-malicious-skills-found-in-openclaws-clawhub>).
- **Ausrollen:** Die OpenClaw-Rolle kopiert den Skill bei jedem Deploy in den
  Skill-Ordner der Instanz (`<state-dir>/skills`, im Container
  `/home/node/.openclaw/skills`, auf dem Host `./config/skills`). OpenClaw lädt
  diesen Ordner in jeder Session der Instanz (Ladereihenfolge Stufe 4
  „Managed / local skills“) [V]
  (<https://docs.openclaw.ai/tools/skills>).
- **Freigabe:** OpenClaw-Exec-Freigaben, als Knopf in Haralds Telegram
  (`channels.telegram.execApprovals`, Ziel DM). Bestätigen dürfen nur die
  eingetragenen Telegram-User-IDs („only resolved approvers can approve or
  deny“), Entscheidungen sind `allow-once`, `allow-always` oder `deny` [V]
  (<https://docs.openclaw.ai/tools/exec-approvals-advanced>). Ohne Antwort
  greift `askFallback: deny` [V]
  (<https://docs.openclaw.ai/tools/exec-approvals>).
- **Nur `bw` fragt nach:** OpenClaw kennt keine Nachfrage pro einzelnem Befehl
  bei sonst freier Ausführung (`ask` ist `off`, `on-miss` oder `always`) [V].
  Geplante Umsetzung: `security: allowlist`, `ask: on-miss`; die
  Allowlist erlaubt die üblichen Programmpfade, `bw` liegt in einem eigenen,
  nicht freigegebenen Pfad und löst deshalb jedes Mal eine Freigabe aus. Ob
  sich die heutige Arbeitsweise der Agenten so ohne ständige Nachfragen
  abbilden lässt, wird zuerst auf DEV nachgewiesen [A].
- Aufwand: etwa 1 bis 2 Tage Konfiguration und Tests [A].

### B: Eigener Freigabe-Dienst (Eigenbau)
- Ein eigener Dienst je VPS hält die Tresor-Zugangsdaten; Freigabe per eigenem
  Telegram-Bot, Ordner-Regeln, 30-Minuten-Fenster, Notfall-Stopp, Protokoll,
  Passwörter nur per Platzhalter-Einsetzung im Browser. Erfüllt mehr
  Sicherheitsziele, braucht aber etwa 5 bis 9 Tage und dauerhaft eigenen Code
  [A]. **Verworfen** wegen Vorgabe 1; bleibt Rückfallweg, falls die Lücken von
  Option A stören.

### C: Bitwarden MCP Server
- Für den lokalen Rechner gedacht („exclusively for local use“), enthält ein
  Lösch-Tool, keine Freigabe pro Zugriff [V]
  (<https://github.com/bitwarden/mcp-server>). Für Server ohne Bediener nicht
  vorgesehen. **Verworfen**.

### D: Bitwarden Agent Access
- Prinzip passt (Tresor bleibt beim Anbieter, Freigabe pro Anfrage am Rechner
  mit `aac listen`), aber „early alpha“, nicht für Produktivsysteme empfohlen
  [V]
  (<https://www.businesswire.com/news/home/20260324779404/en/Bitwarden-Introduces-Open-Standard-to-Secure-Agent-Credential-Access-with-the-Agent-Access-SDK>);
  letztes Release v0.11.0 vom 21.03.2026 [V]
  (<https://github.com/bitwarden/agent-access/releases>); Freigabe nicht per
  Handy, nur Lesen. **Verworfen**, Beobachtungskandidat.

### E: Kostenpflichtige Dienste (1Password u. a.)
- 1Password hat keinen Gratis-Tarif [V] (<https://1password.com/pricing>).
  **Verworfen** (Vorgabe 2).

## Entscheidung

**Option A.** Sie erfüllt Vorgabe 1 (nur Konfiguration, fertige Bausteine von
Bitwarden und OpenClaw) und deckt Freigabe per Telegram, alle Rechte und das
Ausrollen in jede Instanz ab.

## Konsequenzen

- OpenClaw-Rolle: Bitwarden CLI einbinden, Skill nach `./config/skills/`
  ausrollen, Exec-Freigaben und Telegram-Approver in `openclaw.json.j2`
  konfigurieren.
- Zugangsdaten: drei gemeinsame GH Secrets für alle Instanzen
  (`OC_BITWARDEN_CLIENTID`, `OC_BITWARDEN_CLIENTSECRET`,
  `OC_BITWARDEN_PASSWORD`) als Umgebungsvariablen `BW_CLIENTID`,
  `BW_CLIENTSECRET`, `BW_PASSWORD`. Die alte Kette
  `*_OC<n>_BITWARDEN_CLIENTSECRET` inkl. Tippfehler
  `bitwarden_clientscurect_env` wird ersetzt; `.env.example` wird
  aktualisiert. Danach rotiert Harald den bisherigen API-Key.
- **Schutz der Zugangsdaten (Owner-Entscheid 2026-10-10 „Ja, schützen“):** Die
  drei Secrets liegen in einem GH Environment mit Harald als Required Reviewer,
  nur von `main` [V]
  (<https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments>).
  Damit nicht jeder OC-Deploy auf Harald wartet, schreibt ein eigener,
  geschützter Job die Secret-Datei auf den Host (nur bei Ersteinrichtung oder
  Rotation); normale Deploys binden die vorhandene Datei nur ein. Die
  Regel-Änderung (Owner-only) folgt als eigener Regel-PR (AGENTS.md + `.roo`).
- Tests auf DEV: Lesen, Anlegen, Ändern, Löschen je mit Telegram-Freigabe;
  Ablehnung und Zeitablauf führen zu keiner Ausführung; der Skill ist in einer
  Session außerhalb des IaC4-Workspace verfügbar; nach Recreate ist alles
  wieder da.
- arc42 K5/K7/K11 werden mit der Umsetzung aktualisiert.

## Bewusst getragene Rest-Risiken (Owner akzeptiert)

- **Keine harte Grenze:** Tresor-Zugangsdaten liegen im Agenten-Container.
  OpenClaw: Freigaben sind „not a per-user auth boundary“ [V]
  (<https://docs.openclaw.ai/tools/exec-approvals>). Ein durch Prompt-Injection
  gesteuerter Agent kann die Freigabe umgehen, z. B. über einen freigegebenen
  Befehl, der die Umgebungsvariablen ausliest.
- **Passwörter beim KI-Anbieter:** Gelesene Passwörter stehen im Verlauf des
  Agenten und gehen an den Modell-Anbieter.
- **Weniger Steuerung als im Grill zunächst festgelegt:** keine Ordner-Regel
  `Bestätigung`/`Frei`, kein 30-Minuten-Fenster (nur einmal oder dauerhaft),
  kein Notfall-Stopp per Befehl, kein eigenes Protokoll; Haralds
  Telegram-Freigaben sind das Protokoll. `allow-always` sollte für `bw` nicht
  genutzt werden, sonst entfällt die Nachfrage für diesen Befehl.
- **Löschen erlaubt:** Ein freigegebenes Löschen entfernt den Eintrag;
  gelöschte Einträge liegen 30 Tage im Papierkorb [A]. Überschriebene
  Passwörter: Bitwarden speichert „the last five saved passwords for each
  login item“ [V]
  (<https://bitwarden.com/help/password-and-generator-history/>).
- **DEV = PROD:** Ein Fehler auf DEV trifft dieselben Daten wie PROD.
- **Fremder Skill:** Inhalt eines Community-Skills; Gegenmaßnahme: geprüfte
  Kopie in IaC4, keine automatische Aktualisierung von ClawHub.

## Worst-Case / Rollback

- **Agent umgeht die Freigabe oder Zugangsdaten gelangen nach außen:**
  Master-Passwort und API-Key rotieren, betroffene Zielpasswörter ändern,
  Bitwarden-Secrets aus dem Deploy nehmen (Agenten haben dann keinen Zugriff).
- **Ständige Nachfragen behindern die Agenten:** Allowlist nachschärfen oder
  `bw`-Einbindung per Flag deaktivieren; OpenClaw läuft ohne Bitwarden weiter.
- **Master-Passwort verloren:** Konto lässt sich ohne Master-Passwort nicht
  entschlüsseln [A]; Harald verwahrt ein Emergency Kit offline.
- **Lockout-Risiko:** keines (keine Ports, keine ACL-/UFW-Änderung).
- **Rollback:** Skill, Bitwarden CLI und Exec-Freigabe-Konfiguration per Flag
  in der Rolle abschalten und neu deployen. Die alte
  `BITWARDEN_CLIENTSECRET`-Kette wird nicht zurückgeholt.

## Referenzen

- <https://bitwarden.com/help/cli/>
- <https://bitwarden.com/help/personal-api-key/>
- <https://bitwarden.com/help/password-and-generator-history/>
- <https://docs.openclaw.ai/tools/skills>
- <https://docs.openclaw.ai/tools/exec-approvals>
- <https://docs.openclaw.ai/tools/exec-approvals-advanced>
- <https://clawhub.ai/typhonius/bitclawden>
- <https://esecurityplanet.com/threats/hundreds-of-malicious-skills-found-in-openclaws-clawhub>
- <https://github.com/bitwarden/mcp-server>
- <https://github.com/bitwarden/agent-access/releases>
- <https://www.businesswire.com/news/home/20260324779404/en/Bitwarden-Introduces-Open-Standard-to-Secure-Agent-Credential-Access-with-the-Agent-Access-SDK>
- <https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments>
- <https://1password.com/pricing>
