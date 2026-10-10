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
  Anbindung „alpha“, für API-Header gedacht [V]. hush: Freigabe nur über
  Discord, eigener Datei-Tresor, „experimental“ [V]. **Verworfen**; Agent
  Access bleibt Beobachtungskandidat.

### C: Bitwarden MCP Server im OC-Container
- Braucht `BW_SESSION` im Agenten-Prozess, enthält ein Lösch-Tool, keine
  Freigabe [V] (<https://github.com/bitwarden/mcp-server>). **Verworfen**.

### D: Enterprise-Workflows (HashiCorp Vault Control Groups, Infisical Access Requests)
- Kostenpflichtig, anderer Store [V]
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
  (`bw edit` ersetzt das ganze Objekt [V]); vor jedem Zugriff `sync`.
- Anmeldung ohne Bediener: `bw login --apikey` + `bw unlock --passwordfile`
  [V] (<https://bitwarden.com/help/cli/>); API-Key-Logins sind von der
  Neue-Geräte-Prüfung ausgenommen [V]
  (<https://bitwarden.com/help/new-device-verification/>). Nach Neustart
  entsperrt sich der Dienst selbst.
- Erreichbarkeit: je Instanz ein internes Docker-Netz (`internal: true`); die
  Instanz-Identität ergibt sich aus Netz und Instanz-Token, **nie aus Text des
  Agenten**. Der Instanzname in der Telegram-Nachricht stammt vom Dienst.
- Telegram: eigener Freigabe-Bot je VPS über Long-Polling (`getUpdates`), kein
  eingehender Port [V] (<https://core.telegram.org/bots/api>). Knopfdrücke
  werden nur von Haralds Telegram-User-ID angenommen.
- Notfall-Stopp über beide VPS: Der Sperr-Zustand wird zusätzlich als Marker im
  Agenten-Tresor gesetzt, den beide Dienste vor jedem Zugriff prüfen.
- **Platzhalter-Einsetzung:** Für Browser-Logins übergibt der Agent nur eine
  Referenz (z. B. `easybank/passwort`); der Dienst setzt den Wert direkt im
  Browser ein, das Modell sieht ihn nie. Das gilt für alle Zugänge; ein
  Klartext-Lesen von Passwörtern bietet die Regel-Schicht nicht an.
  Machbarkeit (Zugriff des Dienstes auf den OpenClaw-Browser) ist
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
- Abbau der `BITWARDEN_CLIENTSECRET`-Kette (Template, `instance-body.yml`,
  group_vars, Workflow-Env, Verify-Step) inkl. Tippfehler
  `bitwarden_clientscurect_env`; danach rotiert Harald den API-Key, weil die
  Agenten ihn lesen konnten.
- Agenten-Schnittstelle: schmales Tool `secret_fill` (Passwort einsetzen),
  `secret_read` (nur Felder ohne Passwort, z. B. Benutzername, Adresse) und
  `secret_upsert`; Anfragen aus `Bestätigung` blockieren bis zur
  Entscheidung oder zum Verfall.
- BDD-Tests für jede Regel: Ordner, 30-min-Freigabe, 10-min-Verfall, Sperre,
  Owner-ID, kein Löschen, kein Ordnerwechsel, Broker nicht aus anderen Netzen
  erreichbar.
- arc42 K5/K7/K11 werden mit der Umsetzung aktualisiert (Rest-Risiken unten).
- Aufwand grob 2–4 Tage für den Dienst plus 2–4 Tage für die
  Platzhalter-Einsetzung [A].

## Bewusst getragene Rest-Risiken

- Ein Fehler beim Testen auf DEV trifft dieselben Daten wie PROD (Vorgabe 2).
- Benutzername, Adresse und Notiz eines Eintrags dürfen das Modell erreichen,
  Passwörter nicht.
- Wer Root auf einem VPS hat, kann das Master-Passwort lesen (analog ADR-016).

## Worst-Case / Rollback

- **Regel-Fehler** lässt Lesen ohne Freigabe zu: sichtbar durch die
  Info-Nachricht bei jedem Abruf → `/sperren`, betroffene Passwörter beim
  Zielsystem ändern.
- **Agent überschreibt ein Passwort** (nur mit Freigabe möglich):
  Wiederherstellung über die Passwort-Historie des Eintrags [A] bzw. den
  30-Tage-Papierkorb [V].
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
- <https://core.telegram.org/bots/api>
- <https://1password.com/pricing>
