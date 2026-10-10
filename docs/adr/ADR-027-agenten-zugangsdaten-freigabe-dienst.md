# ADR-027: Agenten-Zugangsdaten über eigenen Freigabe-Dienst (Bitwarden + Telegram)

- **Status:** Vorgeschlagen (Proposed)
- **Datum:** 2026-10-10
- **Kontext:** Issue #192. Die OC-Instanzen (oc1–oc3 auf DEV und PROD) sollen
  sich zur Laufzeit selbst bei Portalen anmelden können (Agenten-Zugangsdaten,
  Glossar K12) und dafür Einträge lesen, anlegen und ändern. Heute bekommt jede
  Instanz nur `BITWARDEN_CLIENTSECRET` als Umgebungsvariable
  (`ansible/roles/openclaw-gateway/templates/docker-compose.yml.j2:31-33`,
  `.github/workflows/04-service-deploy.yml:123-128`) [I]. Ohne Master-Passwort
  lässt sich der Tresor damit nicht entschlüsseln [V]
  (<https://bitwarden.com/help/personal-api-key/>), der Agent kann also keine
  Zugangsdaten lesen. Gleichzeitig liegt ein Konto-Zugang heute im
  Agenten-Container und damit in Reichweite des Agenten.

## Fachliche Vorgaben (Owner-Grill 2026-10-10)

1. **Store:** ein eigenes, kostenloses Bitwarden-Konto (Cloud EU), nur für die
   OC-Instanzen (Agenten-Tresor). Keine Kosten.
2. **Sichtbarkeit:** alle sechs Instanzen sehen dieselben Einträge, keine
   Trennung DEV/PROD. DEV verhält sich identisch zu PROD.
3. **Ordner:** `Bestätigung` und `Frei`. Von Agenten angelegte Einträge landen
   immer in `Bestätigung`; nur Harald verschiebt nach `Frei`.
4. **Lesen aus `Bestätigung`:** nur nach Freigabe per Telegram-Knopf; gilt
   30 Minuten für diesen Eintrag und diese Instanz.
5. **Anlegen/Ändern:** immer mit Freigabe. Die Anfrage zeigt Instanz, Eintrag,
   neu/geändert, betroffene Felder und Grund, nie Werte. **Löschen ist
   verboten.**
6. **Information:** jeder Abruf (auch aus `Frei`) erzeugt eine Info-Nachricht.
7. **Verfall:** unbeantwortete Anfragen verfallen nach 10 Minuten.
8. **Notfall-Stopp:** `/sperren` blockiert jeden Zugriff aller Instanzen auf
   DEV und PROD, bis `/entsperren`.
9. **Protokoll:** jeder Zugriff, 90 Tage, abrufbar mit `/protokoll`; nie
   Passwörter im Protokoll.
10. **KI-Anbieter:** Passwörter erreichen das Modell nie
    (Platzhalter-Einsetzung), auch nicht bei MFA-geschützten Zugängen. Bei MFA
    authentifiziert sich Harald zusätzlich selbst; das ist gewollt.
11. **Bedienung:** einfach; je VPS ein Freigabe-Chat („OC-Freigabe DEV“,
    „OC-Freigabe PROD“).

## Entscheidungsfrage

Wie erhalten Agenten kontrollierten Zugriff auf Einträge im Agenten-Tresor,
ohne selbst Tresor-Zugangsdaten zu besitzen, mit Freigabe durch Harald am Handy?

## Optionen

### A: OpenClaw-Exec-Approvals vor `bw`-Aufrufen im Agenten-Container
- Schlüssel liegt beim Agenten. OpenClaw: Approvals sind „not a per-user auth
  boundary“ [V] (<https://docs.openclaw.ai/tools/exec-approvals>). Schützt nur
  vor Versehen. **Verworfen** (Vorgabe: harte Grenze).

### B: Fertige Lösung (Bitwarden Agent Access SDK, OneCLI, hush)
- Agent Access: „early preview“, Freigabe per lokaler CLI statt Telegram, nur
  Lesen [V] (<https://github.com/bitwarden/agent-access>). OneCLI: Bitwarden-
  Anbindung „alpha“, für API-Header gedacht [V]
  (<https://onecli.sh/blog/bitwarden-agent-access-sdk-onecli>). hush: Freigabe
  nur über Discord, eigener Datei-Tresor, „experimental“ [V]
  (<https://pkg.go.dev/github.com/mrz1836/hush@v0.2.0>). **Verworfen**; Agent
  Access bleibt Beobachtungskandidat.

### C: Bitwarden MCP Server im OC-Container
- Braucht `BW_SESSION` im Agenten-Prozess, enthält ein Lösch-Tool, keine
  Freigabe [V] (<https://github.com/bitwarden/mcp-server>). **Verworfen**.

### D: Kostenpflichtige Dienste (1Password, HashiCorp Vault Control Groups, Infisical Access Requests)
- 1Password hat keinen Gratis-Tarif, nur eine Testphase [V]
  (<https://1password.com/pricing>). Die Freigabe-Workflows von Vault und
  Infisical sind Enterprise-Funktionen mit anderem Store [V]
  (<https://developer.hashicorp.com/vault/docs/enterprise/control-groups>,
  <https://infisical.com/docs/documentation/platform/access-controls/access-requests>).
  **Verworfen** (Vorgabe: keine Kosten).

### E: Bitwarden Secrets Manager (Free) mit Zugangstoken
- Kein Master-Passwort nötig, `bws secret create/edit` [V]
  (<https://bitwarden.com/help/secrets-manager-cli/>), aber nur
  Name/Wert/Notiz, keine Login-Einträge und Ordner (Vorgabe 3). Token läge
  ohne Broker wieder beim Agenten. **Verworfen**.

### F: Eigener Freigabe-Dienst je VPS — EMPFEHLUNG
- Container `oc-secret-broker` je VPS (Image gepinnt, ADR-017). Darin:
  `bw serve` nur auf 127.0.0.1 im Container (die API hat keine eigene
  Authentifizierung und enthält `DELETE` [V], Quellcode
  `apps/cli/src/oss-serve-configurator.ts`), davor eine Regel-Schicht mit nur
  `read`/`create`/`update`.
- Regel-Schicht: Ordner nach jedem `get` selbst prüfen; neue Einträge immer in
  `Bestätigung`; `folderId` nie änderbar; Änderung als GET → Merge → PUT
  (`bw edit` ersetzt das ganze Objekt [V], <https://bitwarden.com/help/cli/>);
  vor jedem Zugriff `sync`.
- Mehrdeutige Referenzen (z. B. zwei Einträge gleichen Namens) lehnt der Dienst
  ab, statt einen Eintrag zu raten.
- `secret_read` liefert nur eine Positivliste von Feldern: Name, Benutzername,
  URI, Notiz. TOTP-Seed, Passwort und eigene Felder (auch versteckte) erreichen
  den Agenten nie. Notizen enthalten deshalb keine Geheimnisse.
- Neue oder geänderte Passwörter erzeugt der Dienst selbst (`bw generate`) und
  setzt sie per Platzhalter ins Portal ein. `secret_upsert` nimmt vom Agenten
  keine Passwort-Werte an; so sieht das Modell auch beim Registrieren oder
  Passwortwechsel kein Passwort.
- Anmeldung ohne Bediener: `bw login --apikey` + `bw unlock --passwordfile`
  [V] (<https://bitwarden.com/help/cli/>); API-Key-Logins sind von der
  Neue-Geräte-Prüfung ausgenommen [V]
  (<https://bitwarden.com/help/new-device-verification/>). Nach Neustart
  entsperrt sich der Dienst selbst.
- Erreichbarkeit: je Instanz ein internes Docker-Netz (`internal: true`); die
  Instanz-Identität ergibt sich aus Netz und Instanz-Token, **nie aus Text des
  Agenten**. Der Instanzname in der Telegram-Nachricht stammt vom Dienst. Der
  Broker hängt **nicht** im gemeinsamen Traefik-Netz `{{ docker_network }}`, in
  dem alle OC-Instanzen hängen (`docker-compose.yml.j2:49-50`) [I]; für
  Bitwarden und Telegram bekommt er ein eigenes Netz mit Internetzugang, das
  keine OC-Instanz erreicht.
- Telegram: eigener Freigabe-Bot je VPS über Long-Polling (`getUpdates`), kein
  eingehender Port [V] (<https://core.telegram.org/bots/api>). Knopfdrücke
  werden nur von Haralds Telegram-User-ID angenommen.
- Notfall-Stopp: `/sperren` in einem der beiden Freigabe-Chats reicht. Der
  empfangende Dienst sperrt sofort lokal (Zustand auf dem Host, übersteht
  Neustarts) und setzt einen Sperr-Marker im Agenten-Tresor, den beide Dienste
  vor jedem Zugriff prüfen. Der Marker wird über eine feste Item-ID erkannt,
  nie über den Namen, und ist von allen Agenten-Operationen ausgeschlossen.
  Schlägt `sync` oder das Lesen des Markers fehl, gilt „gesperrt“ (fail
  closed).
- Protokoll: je VPS eine Datenbank auf dem Host außerhalb von
  `/srv/openclaw/`, Einträge 90 Tage, ohne Werte. `/protokoll` im jeweiligen
  Freigabe-Chat zeigt die Zugriffe dieses VPS.
- **Platzhalter-Einsetzung:** Für Browser-Logins übergibt der Agent nur eine
  Referenz (z. B. `easybank/passwort`); der Dienst setzt den Wert direkt im
  Browser ein. **Ziel** ist, dass das Modell ihn nie sieht; das gilt für alle
  Zugänge, ein Klartext-Lesen von Passwörtern bietet die Regel-Schicht nicht
  an. Damit das Ziel hält, gelten zwei Pflicht-Regeln: (1) Einsetzen nur, wenn
  die Adresse der Seite zur gespeicherten URI des Eintrags passt (Schutz gegen
  eine durch Prompt-Injection untergeschobene fremde Seite); (2) Einsetzen und
  Absenden in einem Schritt, oder das Zurücklesen des Feldinhalts durch den
  Agenten wird technisch verhindert. Was davon nicht umsetzbar ist, wird
  Rest-Risiko. Machbarkeit (Zugriff des Dienstes auf den OpenClaw-Browser) ist
  **nicht geprüft** [A] und wird zuerst auf DEV nachgewiesen; Rückfall, falls
  sie bei einem Portal nicht geht: manuelle Anmeldung im persistenten Browser-Profil, wie
  OpenClaw sie empfiehlt [V] (<https://docs.openclaw.ai/tools/browser-login>,
  Issue #172).

## Empfehlung

**Option F.** Keine fertige, kostenlose Lösung erfüllt die Vorgaben (B–E). Die
Bausteine sind dokumentiert und kostenlos, es gibt keinen eingehenden Port und
keine Änderung an Tailscale-ACL oder UFW, und die Regel-Schicht ist klein und
vollständig testbar.

## Konsequenzen

- Neue Ansible-Rolle und Compose-Template für `oc-secret-broker`; Master-
  Passwort, API-Key und Freigabe-Bot-Token nur dort (GH Secrets → Datei mit
  Modus 0400), nie in OC-Containern und nie unter `/srv/openclaw/<name>/`
  (dort gemountete Config ist für Agenten lesbar, `docker-compose.yml.j2:42`).
- **Bereitstellungsweg absichern:** Die Workflows nutzen heute keine GH
  Environments [I] (kein `environment:` in `.github/workflows/`), und der
  DEV-Deploy ist für Agenten autonom (AGENTS.md). Ein Agent könnte so
  geänderten Broker- oder Workflow-Code auf DEV bringen und wegen Vorgabe 2 den
  gemeinsamen Tresor ohne Freigabe lesen. Empfehlung: die drei Broker-Secrets
  in ein GH Environment mit Harald als Required Reviewer legen (im öffentlichen
  Repo verfügbar [V],
  <https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments>)
  und Deploys der Broker-Rolle als Owner-only einstufen. Die Regel-Änderung
  folgt als eigener Regel-PR (AGENTS.md + `.roo`). **Owner-Entscheid offen.**
- Abbau der `BITWARDEN_CLIENTSECRET`-Kette (Template, `instance-body.yml`,
  group_vars, Workflow-Env, Verify-Step) inkl. Tippfehler
  `bitwarden_clientscurect_env` als erster Umsetzungsschritt; danach rotiert
  Harald den API-Key, weil die Agenten ihn lesen konnten.
- Agenten-Schnittstelle: schmales Tool `secret_fill` (Passwort einsetzen),
  `secret_read` (Positivliste, siehe Option F) und `secret_upsert` (ohne
  Passwort-Werte); Anfragen aus `Bestätigung` blockieren bis zur
  Entscheidung oder zum Verfall.
- BDD-Tests für jede Regel: Ordner, 30-min-Freigabe, 10-min-Verfall, Sperre
  inkl. fail closed, Owner-ID, kein Löschen, kein Ordnerwechsel, Feld-
  Positivliste, URI-Matching, keine Passwort-Werte in `secret_upsert`, Broker
  nicht aus anderen Netzen erreichbar.
- arc42 K5/K7/K11 werden mit der Umsetzung aktualisiert (Rest-Risiken unten).
- Aufwand grob 2–4 Tage für den Dienst plus 2–4 Tage für die
  Platzhalter-Einsetzung [A].

## Bewusst getragene Rest-Risiken

- Ein Fehler beim Testen auf DEV trifft dieselben Daten wie PROD (Vorgabe 2).
- Name, Benutzername, URI und Notiz eines Eintrags erreichen das Modell und
  damit den KI-Anbieter, Passwörter nicht.
- Wer Root auf einem VPS hat, kann das Master-Passwort lesen (analog ADR-016).

## Worst-Case / Rollback

- **Regel-Fehler** lässt Lesen ohne Freigabe zu: sichtbar durch die
  Info-Nachricht bei jedem Abruf → `/sperren`, betroffene Passwörter beim
  Zielsystem ändern.
- **Agent überschreibt ein Passwort** (nur mit Freigabe möglich):
  Wiederherstellung über die Passwort-Historie; Bitwarden speichert „the last
  five saved passwords for each login item“ [V]
  (<https://bitwarden.com/help/password-and-generator-history/>).
- **Master-Passwort verloren:** Das Konto lässt sich ohne Master-Passwort nicht
  entschlüsseln [A]. Gegenmaßnahme: Harald verwahrt ein Emergency Kit
  (Master-Passwort offline); im schlimmsten Fall wird das dedizierte Konto neu
  angelegt und die Einträge neu erfasst.
- **Host kompromittiert:** Agenten-Tresor offen; Schaden auf das dedizierte
  Konto begrenzt → Master-Passwort und API-Key rotieren, Zielpasswörter ändern.
- **Dienst gesperrt oder abgemeldet:** Agenten erhalten keine Zugangsdaten
  (fail closed); OpenClaw selbst läuft weiter.
- **Lockout-Risiko:** keines (keine eingehenden Ports, keine ACL-/UFW-Änderung).
- **Rollback:** Broker-Container und -Netze entfernen (Rolle per Flag
  deaktivieren); OC-Instanzen laufen unverändert. Der Abbau der alten
  `BITWARDEN_CLIENTSECRET`-Kette wird nicht zurückgerollt.

## Referenzen

- <https://bitwarden.com/help/cli/>
- <https://bitwarden.com/help/personal-api-key/>
- <https://bitwarden.com/help/new-device-verification/>
- <https://bitwarden.com/help/secrets-manager-cli/>
- <https://github.com/bitwarden/clients/blob/main/apps/cli/src/oss-serve-configurator.ts>
- <https://github.com/bitwarden/agent-access>
- <https://github.com/bitwarden/mcp-server>
- <https://docs.openclaw.ai/tools/exec-approvals>
- <https://docs.openclaw.ai/tools/browser-login>
- <https://bitwarden.com/help/password-and-generator-history/>
- <https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments>
- <https://onecli.sh/blog/bitwarden-agent-access-sdk-onecli>
- <https://pkg.go.dev/github.com/mrz1836/hush@v0.2.0>
- <https://core.telegram.org/bots/api>
- <https://1password.com/pricing>
