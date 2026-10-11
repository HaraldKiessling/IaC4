# ADR-027: Agenten-Zugangsdaten über Bitwarden-Skill und OpenClaw-Freigaben (Konfigurieren statt Eigenbau)

- **Status:** Vorgeschlagen (Proposed); Owner-Richtung 2026-10-10, angenommen
  mit dem Merge
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

## Änderung 2026-10-11: Nachfrage nur beim Tresor (Plugin statt Exec-Allowlist)

- **Befund [I]:** Mit `tools.exec.mode: "ask"` und Allowlist fragte PROD oc3
  fast jeden Befehl ab (`cd … && git …`, `python3 <Skript>`,
  `bash <Skript>`), und Cron-Läufe (`sync-anlagen.sh`) wurden mit
  `approval-scope-closed` abgebrochen, weil dort niemand bestätigen kann
  (Freigabe-Protokoll von Harald, 2026-10-11).
- **Owner-Vorgabe:** „nur Tresor-Befehle fragen, alles andere läuft wie
  vorher“.
- **Umsetzung:** Kein Exec-Modus und kein Freigabe-Dokument mehr von IaC4
  (Standard `full`, wie vor ADR-027). Ein eigenes Plugin
  `ia4-vault-approval` (rund 60 Zeilen,
  `ansible/roles/openclaw-gateway/files/plugins/`, root-eigen und
  schreibgeschützt eingebunden, geladen über `plugins.load.paths`) prüft per
  `before_tool_call` jeden Tool-Aufruf. Enthalten die Parameter einen
  Tresor-Bezug (`ia4-bw`, `@bitwarden/cli`, `bw`, `BW_*`-Variablen,
  `/proc/*/environ`, `printenv`, ein bloßes `env`, `export -p`), verlangt es
  eine Freigabe mit nur
  `allow-once` oder `deny`, Zeitlimit 10 Minuten; Zeitablauf, fehlende
  Oberfläche und Abbruch blockieren [V]
  (<https://docs.openclaw.ai/plugins/hooks/tool-policy>,
  <https://docs.openclaw.ai/plugins/plugin-permission-requests>). Die
  Anfrage geht per `approvals.plugin` (Ziel Telegram, Haralds User-ID) an
  Haralds Telegram [V]
  (<https://docs.openclaw.ai/tools/exec-approvals-advanced>). Passwort-Felder
  im Befehl werden in der Anfrage durch `***` ersetzt.
- **Freigabe je Eintrag (Owner-Entscheide 2026-10-11, „10 Minuten“, „nur für
  einen Eintrag“):** Im DEV-Test brauchte eine einzige Tresor-Abfrage fünf
  Freigaben (Orchestrator und Sub-Agent, je Suche/Lesen ein Aufruf). Nach
  einem `allow-once` darf deshalb 10 Minuten lang derselbe Eintrag ohne neue
  Frage gelesen werden, von allen Agenten der Instanz (auch Sub-Agenten).
  „Derselbe Eintrag“ heißt: derselbe Suchbegriff (`list items --search`),
  derselbe Name oder dieselbe ID (`get …`); liefert eine freigegebene Suche
  genau einen Treffer, gelten auch dessen ID und Name. Jedes Mal fragen
  weiterhin: andere Einträge, Suchen mit mehreren Treffern beim Folgezugriff,
  `list items` ohne Suche, `create`/`edit`/`delete`, direkte `bw`-, `BW_*`-
  und Umgebungs-Zugriffe, Befehle mit mehreren Tresor-Aufrufen oder `$(…)`.
  Läuft für denselben Eintrag schon eine Anfrage, wird ein weiterer Zugriff
  ohne neue Frage abgewiesen (Hinweis an den Agenten, nach dem Ergebnis
  erneut aufzurufen). Die Karte in Telegram nennt den Umfang. Die Freigaben
  liegen nur im Speicher des Plugins (`onResolution`, `after_tool_call`, [V]
  <https://docs.openclaw.ai/plugins/hooks/tool-policy>); Neustart, `deny`
  und Zeitablauf beenden sie. Folge: Innerhalb der 10 Minuten kann jeder
  Agent der Instanz, auch ein Cron-Lauf, diesen einen Eintrag ohne Rückfrage
  lesen.
- **Warum Eigenentwicklung trotz Vorgabe 1:** OpenClaw fragt Exec-Befehle nur
  über die Allowlist ab (Treffer läuft, alles andere fragt) [V]
  (<https://docs.openclaw.ai/tools/exec-approvals>); ein Bordmittel „nur
  bei Befehl X fragen“ gibt es nicht. Allowlist und Owner-Vorgabe „alles
  andere läuft wie vorher“ schließen sich deshalb aus. Der dokumentierte Weg
  für eigene Regeln ist ein Plugin mit `before_tool_call` [V]; das kleinste
  davon ist dieses.
- **Absicherung gegen stilles Fehlen:** Lädt das Plugin nicht, gäbe es keine
  Nachfrage. Die Rolle prüft deshalb nach dem Start mit
  `openclaw plugins inspect ia4-vault-approval --runtime --json`, dass der
  Hook registriert ist, und bricht sonst ab; der Verify-Schritt in Workflow 04
  macht den Run ebenfalls rot. Grenze: Die Prüfung lädt das Plugin im
  CLI-Prozess, nicht im laufenden Gateway, und ein roter Lauf baut nichts
  zurück; der Container läuft dann mit Zugangsdaten und ohne Nachfrage
  weiter. Handlungsweg: Workflow 04 mit `bitwarden_secret=delete` (entfernt
  die Zugangsdaten). Der eigentliche Nachweis bleibt der Test „`ia4-bw`
  fragt nach“ auf DEV.
- **Folge:** Cron-Jobs und normale Befehle laufen ohne Nachfrage; nur
  Tresor-Zugriffe fragen. Ein Tresor-Zugriff aus einem Cron-Lauf wird
  blockiert (niemand kann bestätigen), außer er liest einen Eintrag, der
  gerade freigegeben ist (siehe Freigabe je Eintrag).
- **Restrisiko unverändert (keine harte Grenze), Erkennung jetzt über Text:**
  Ein Skript, das die Tresor-Wörter nicht im Aufruf trägt, fällt nicht auf
  (z. B. eigenes Skript, das die Umgebung liest, oder ein bloßes `set`, das
  bewusst nicht erkannt wird, weil das Wort in fast jedem Tool-Aufruf vorkommt,
  ebenso `env -0`, `env 2>&1` oder `node -e "console.log(process.env)"`).
  Das entspricht dem schon
  akzeptierten Risiko „Zugangsdaten als Umgebungsvariablen im Container“.
- **Rückbau der früheren Allowlist:** Wo der Marker `exec-policy-ia4` liegt,
  setzt die Rolle das Freigabe-Dokument auf `full`/`off` zurück, prüft das
  Ergebnis mit `openclaw approvals get --gateway --json` und entfernt den
  Marker erst danach; ein Fehlschlag macht den Lauf rot.
- Die Abschnitte unten zu Allowlist und `ask: on-miss` beschreiben den Stand
  vom 2026-10-10 und gelten nicht mehr.

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
  (ADR-017, npm-Paket `@bitwarden/cli`): Ansible installiert sie bei jedem
  Deploy als root in einen eigenen Pfad im Container (`/opt/ia4-bitwarden/cli`,
  nicht auf dem PATH, vom Agenten nicht änderbar). Anmeldung ohne Bediener mit
  `bw login --apikey` (`BW_CLIENTID`/`BW_CLIENTSECRET`) und
  `bw unlock --passwordenv BW_PASSWORD` [V]
  (<https://bitwarden.com/help/cli/>).
- **Aufruf-Hülle `ia4-bw`** (einziger eigener Code, rund 50 Zeilen Shell): meldet
  sich an, entsperrt, synchronisiert und reicht alle Argumente an `bw` weiter.
  So kostet jeder Vorgang genau eine Freigabe statt drei (Login, Unlock,
  Befehl), und die Freigabe zeigt den eigentlichen Befehl. Read-only
  eingebunden unter `/opt/ia4-bitwarden/ia4-bw`.
- **Skill:** ein fertiger Community-Skill, Kandidat `bitclawden` (MIT, `bw`,
  Lesen/Anlegen/Ändern/Erzeugen) [V]
  (<https://clawhub.ai/typhonius/bitclawden>). Er wird geprüft, als Vorlage
  in IaC4 versioniert und um das Löschen und den Hinweis auf Freigaben
  ergänzt. Nie live von ClawHub geladen, wegen bekannter bösartiger Skills
  dort [V]
  (<https://esecurityplanet.com/threats/hundreds-of-malicious-skills-found-in-openclaws-clawhub>).
- **Ausrollen:** Die OpenClaw-Rolle legt den Skill bei jedem Deploy vollständig
  neu ab (gleiches Ergebnis bei jedem Lauf) und bindet ihn schreibgeschützt in
  den Skill-Ordner der Instanz ein (`<state-dir>/skills`, im Container
  `/home/node/.openclaw/skills`, eigener `:ro`-Mount über dem sonst
  beschreibbaren `./config`). OpenClaw lädt diesen Ordner in jeder Session der
  Instanz (Ladereihenfolge Stufe 4 „Managed / local skills“) [V]
  (<https://docs.openclaw.ai/tools/skills>). Workspace-Skills haben Vorrang
  („the highest source wins“) [V]; der Skill bekommt deshalb einen eindeutigen
  Namen (`ia4-bitwarden`), damit ihn kein Repo zufällig überdeckt.
- **Freigabe:** OpenClaw-Exec-Freigaben, als Knopf in Haralds Telegram
  (`channels.telegram.execApprovals`, Ziel DM). Bestätigen dürfen nur die
  eingetragenen Telegram-User-IDs („only resolved approvers can approve or
  deny“), Entscheidungen sind `allow-once`, `allow-always` oder `deny` [V]
  (<https://docs.openclaw.ai/tools/exec-approvals-advanced>). Ohne
  erreichbare Oberfläche oder bei Zeitablauf greift `askFallback: deny`
  („no UI is reachable (or the prompt times out)“) [V]
  (<https://docs.openclaw.ai/tools/exec-approvals>); offene Anfragen verfallen
  standardmäßig nach 30 Minuten [V].
- **Nur `bw` fragt nach:** OpenClaw kennt keine Nachfrage pro einzelnem Befehl
  bei sonst freier Ausführung (`ask` ist `off`, `on-miss` oder `always`) [V].
  Geplante Umsetzung: `security: allowlist`, `ask: on-miss`,
  `tools.exec.strictInlineEval: true`; die Allowlist erlaubt die üblichen
  Programmpfade, `bw` liegt in einem eigenen, nicht freigegebenen Pfad. Bei
  Ketten muss jedes Segment der Allowlist genügen [V]; `sh -c`-Wrapper und
  Inline-Code (`node -e`, `python -c`) gehen den Weg der menschlichen Freigabe
  [V] (<https://docs.openclaw.ai/tools/exec-approvals-advanced>). Dass damit
  **jeder** `bw`-Aufruf nachfragt und die heutige Arbeitsweise der Agenten
  ohne ständige Nachfragen läuft, ist nicht belegt [A] und wird zuerst auf DEV
  nachgewiesen (Testfälle unter Konsequenzen).
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

- OpenClaw-Rolle: Bitwarden CLI einbinden, Skill aus `./bitwarden/skills/`
  schreibgeschützt nach `/home/node/.openclaw/skills/ia4-bitwarden` einbinden, Exec-Freigaben und Telegram-Approver
  konfigurieren. OpenClaw speichert Freigaben und Allowlist in der
  State-Datenbank (`$OPENCLAW_STATE_DIR/state/openclaw.sqlite`) [V]
  (<https://docs.openclaw.ai/tools/exec-approvals>); die Rolle setzt die
  Vorgaben bei jedem Deploy neu und entfernt dabei `allow-always`-Einträge für
  `bw` (Weg über Konfiguration oder CLI noch unbelegt [A], DEV-Testfall).
- Zugangsdaten: drei gemeinsame Environment-Secrets für alle Instanzen
  (`BW_CLIENTID`, `BW_CLIENTSECRET`, `BW_PASSWORD`, Namen von Harald
  gewählt), gleichnamig als Umgebungsvariablen im Container. Repo-Secrets
  mit diesen Namen darf es nicht geben, weil sie bei fehlendem
  Environment-Secret greifen würden. Die alte Kette
  `*_OC<n>_BITWARDEN_CLIENTSECRET` inkl. Tippfehler
  `bitwarden_clientscurect_env` wird ersetzt; `.env.example` wird
  aktualisiert. Danach rotiert Harald den bisherigen API-Key.
- **Schutz der Zugangsdaten (Owner-Entscheid 2026-10-10 „Ja, schützen“):** Die
  drei Secrets liegen in GH Environments mit Harald als Required Reviewer
  (`oc-bitwarden-dev`, `oc-bitwarden-prod`; PROD nur von `main`) [V]
  (<https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments>).
  Damit nicht jeder OC-Deploy auf Harald wartet, schreibt ein eigener,
  geschützter Job (`bitwarden-secret` in Workflow 04, nur mit
  `bitwarden_secret=write`/`delete`, Owner-only) die Secret-Datei
  auf den Host (nur bei Ersteinrichtung, Rotation oder Rückbau); normale
  Deploys binden die vorhandene Datei nur ein. Die Datei
  (`/etc/ia4/oc-bitwarden.env`) liegt außerhalb von `./config` und
  `./workspace`, gehört root, Rechte
  `0600`, und wird von Docker Compose beim Start als Umgebung gelesen. Fehlt
  sie, läuft der Deploy ohne Bitwarden weiter und bricht nicht ab.
- **Reihenfolge der Umsetzung (Owner 2026-10-10: erst DEV, dann Merge):**
  Ein Environment „nur `main`“ gibt Branch-Läufen keine Secrets, die Tests auf
  DEV laufen aber vor dem Merge vom Branch (P7). Deshalb erlaubt
  `oc-bitwarden-dev` den Branch, jeder Lauf wartet weiter auf Haralds Klick;
  `oc-bitwarden-prod` bleibt auf `main` beschränkt. Der Job liegt in Workflow
  04, weil der Knopf „Run workflow“ nur für Workflows erscheint, die auf
  `main` existieren („present if the workflow file exists on the default
  branch“) [V]
  (<https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch>);
  ein neuer Workflow wäre vom Branch aus nicht startbar. Umsetzung, Regel-Zeile
  (Owner-only für `bitwarden_secret`) und Doku liegen im selben PR wie dieses ADR.
- Tests auf DEV: Lesen, Anlegen, Ändern, Löschen je mit Telegram-Freigabe;
  Ablehnung und Zeitablauf führen zu keiner Ausführung; `bw` über `sh -c`,
  über `node` und ein direkter Aufruf der Bitwarden-API mit den
  Umgebungsvariablen (z. B. `curl`), `sh /opt/ia4-bitwarden/ia4-bw …`
  (Script-Datei über eine freigegebene Shell), ein eigenes Script des Agenten,
  das `ia4-bw` aufruft, sowie `env` und `cat /proc/1/environ` lösen eine
  Nachfrage aus oder sind gesperrt (Ergebnis wird dokumentiert und Harald vor
  der Freigabe gezeigt); parallele `ia4-bw`-Aufrufe einer Instanz stören sich
  nicht gegenseitig [A]; der Skill ist in einer Session
  außerhalb des IaC4-Workspace verfügbar und lässt sich vom Agenten nicht
  ändern; ein `allow-always`-Eintrag für `bw` ist nach erneutem Deploy weg;
  nach Recreate und zweitem Deploy ist alles unverändert da.
- arc42 K5/K7/K11 werden mit der Umsetzung aktualisiert.

## Bewusst getragene Rest-Risiken (Owner akzeptiert)

- **Keine harte Grenze:** Tresor-Zugangsdaten liegen im Agenten-Container.
  OpenClaw: Freigaben sind „not a per-user auth boundary“ [V]
  (<https://docs.openclaw.ai/tools/exec-approvals>). Die Zugangsdaten stehen
  als Umgebungsvariablen im Container, und der Exec-Snapshot schließt sie
  bewusst nicht aus (`OPENCLAW_EXEC_SHELL_SNAPSHOT=0`,
  `docker-compose.yml.j2:21-23`) [I]. Jedes freigegebene Programm, das die
  Umgebung liest oder die Bitwarden-API direkt anspricht, kommt ohne Nachfrage
  an den Tresor (z. B. `env`, `cat /proc/1/environ`). Ob eine freigegebene
  Shell die Hülle als Script-Datei ohne Nachfrage startet
  (`sh /opt/ia4-bitwarden/ia4-bw …`), ist offen [A]. Das kann auch ohne böse
  Absicht bei normaler Arbeit passieren (z. B. `npx @bitwarden/cli` statt des
  eingebundenen `bw`), nicht nur durch Prompt-Injection. Ordner, in die der
  Agent selbst schreiben kann (`~/.local/bin`, `~/.npm-global/bin`), stehen
  deshalb nicht in der Allowlist.
- **Agent kann eigene Freigaben ändern:** `./config` ist beschreibbar
  eingebunden [I], dort liegt die State-Datenbank mit Allowlist und
  `allow-always`-Einträgen [V]. Ein Agent könnte sie verändern oder eigene
  Skills neben den geprüften legen. Gegenmaßnahme: der Skill-Ordner ist
  schreibgeschützt, die Rolle setzt die Freigabe-Vorgaben bei jedem Deploy neu;
  zwischen zwei Deploys bleibt das Risiko.
- **Passwörter beim KI-Anbieter:** Gelesene Passwörter stehen im Verlauf des
  Agenten und gehen an den Modell-Anbieter.
- **Weniger Steuerung als im Grill zunächst festgelegt:** keine Ordner-Regel
  `Bestätigung`/`Frei`, kein 30-Minuten-Fenster (nur einmal oder dauerhaft),
  kein Notfall-Stopp per Befehl, kein eigenes Protokoll; Haralds
  Telegram-Freigaben sind das Protokoll. `allow-always` sollte für `bw` nicht
  genutzt werden, sonst entfällt die Nachfrage für diesen Befehl.
- **Löschen erlaubt:** Ein freigegebenes Löschen entfernt den Eintrag;
  gelöschte Einträge liegen 30 Tage im Papierkorb [A, Primärquelle
  nicht abrufbar]. Überschriebene
  Passwörter: Bitwarden speichert „the last five saved passwords for each
  login item“ [V]
  (<https://bitwarden.com/help/password-and-generator-history/>).
- **DEV = PROD:** Ein Fehler auf DEV trifft dieselben Daten wie PROD.
- **Fremder Skill:** Inhalt eines Community-Skills; Gegenmaßnahme: geprüfte
  Kopie in IaC4, schreibgeschützt ausgerollt, keine automatische
  Aktualisierung von ClawHub.

## Worst-Case / Rollback

- **Agent umgeht die Freigabe oder Zugangsdaten gelangen nach außen:**
  Master-Passwort und API-Key rotieren, betroffene Zielpasswörter ändern,
  Workflow 04 mit `bitwarden_secret=delete` und `playbook=openclaw` auf DEV und
  PROD: löscht die Secret-Datei und erstellt die Container ohne Zugangsdaten
  neu; erst dann haben die Agenten keinen Zugriff mehr.
- **Ständige Nachfragen behindern die Agenten:** Allowlist nachschärfen oder
  Bitwarden per Rollback abschalten; OpenClaw läuft ohne Bitwarden weiter.
- **Master-Passwort verloren:** Konto lässt sich ohne Master-Passwort nicht
  entschlüsseln [A]; Harald verwahrt ein Emergency Kit offline.
- **Lockout-Risiko:** keines (keine Ports, keine ACL-/UFW-Änderung).
- **Rollback:** Secret-Datei löschen (siehe oben) oder
  `openclaw_bitwarden_enabled: false` setzen und neu deployen. Die Rolle
  entfernt dann Skill und Hülle aus dem Container und setzt die
  Exec-Freigaben auf das vorherige Verhalten ohne Nachfrage zurück. Die alte
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
