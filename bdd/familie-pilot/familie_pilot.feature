# language: de
# BDD-Feature: Familien-Instanz auf oc4 (dev) — Pilot (GH Issue #126)
# Referenz-Konzept: iac4-pilot/konzept-pilot-oc1-dev.md (Dateiname historisch, Zielinstanz oc4)
# Syntax: Feature/Scenario/Given/When/Then — deutsch, technisch umsetzbar.
# Jedes Szenario bildet genau ein Abnahmekriterium (K1–K9) aus #126 ab.
# Szenario-Anzahl: 15 (K1: 1, K2: 2, K3: 3, K4: 2, K5: 2, K6: 2, K7: 1, K8: 1, K9: 1).
# Hinweis: Die Personen-IDs "person1"/"person2" sind Platzhalter (Beispielwerte). Q3 ist
# beantwortet (Personen + BotFather-Tokens nachlieferbar); die Platzhalter werden nach
# Klärung der echten Namen ersetzt.

Funktionalität: Familien-Instanz auf oc4 (dev)
  Als Betreiber (Harald) möchte ich EINE OpenClaw-Instanz (oc4, dev) betreiben,
  die mehrere Familienmitglieder mit geteilten LLM-Keys, getrenntem Speicher
  und je einem eigenen Telegram-Bot versorgt, damit die Familie gemeinsam
  Infrastruktur nutzt, aber getrennt arbeitet.
  (Die bestehende Instanz oc1 bleibt als Vanilla-/Benchmark-Baseline unangetastet.)

  Hintergrund:
    Angenommen die Instanz "oc4" ist per Feature-Branch "feature/pilot-familie-oc4-dev"
    auf dem dev-VPS "vps-dev.tailcfea8a.ts.net" deployt
    Und das Gateway ist über Tailscale Serve unter Port 18792 erreichbar
    Und die Personen "person1" und "person2" sind als Agents in "agents.list" konfiguriert
    Und die Telegram-Accounts "person1" und "person2" existieren in "channels.telegram.accounts"

  # ---------------------------------------------------------------------------
  # K1: Instanz läuft auf oc4 (dev), Gateway erreichbar
  # ---------------------------------------------------------------------------
  Szenario: Gateway der Familien-Instanz ist auf oc4 erreichbar
    Angenommen der Docker-Container "openclaw-oc4" läuft auf "vps-dev.tailcfea8a.ts.net"
    Wenn ich den Health-Endpunkt "https://vps-dev.tailcfea8a.ts.net:18792/health" aufrufe
    Dann ist der HTTP-Status 200
    Und der Container-Status von "openclaw-oc4" ist "healthy"
    Und "tailscale serve status" enthält eine Route "18792 → localhost:18792"

  # ---------------------------------------------------------------------------
  # K2: ≥2 Personen je eigener Bot, geroutet auf eigene Persona
  # ---------------------------------------------------------------------------
  Szenario: Jeder Personen-Bot routet auf die eigene Agent-Persona
    Angenommen der Telegram-Bot für "person1" hat den Token aus "DEV_OC4_TELEGRAM_BOT_PERSON1"
    Und der Telegram-Bot für "person2" hat den Token aus "DEV_OC4_TELEGRAM_BOT_PERSON2"
    Wenn eine DM an den Bot von "person1" gesendet wird
    Dann wird die Nachricht an den Agent "person1" geroutet
    Und die Antwort trägt die Identity von Agent "person1"
    Wenn eine DM an den Bot von "person2" gesendet wird
    Dann wird die Nachricht an den Agent "person2" geroutet
    Und die Antwort trägt die Identity von Agent "person2"

  Szenario: Bindings routen deterministisch pro Telegram-Account
    Angenommen "bindings" enthält
      | agentId | channel  | accountId |
      | person1  | telegram | person1    |
      | person2    | telegram | person2      |
    Wenn "channels.telegram.accounts" genau die AccountIds "person1" und "person2" definiert
    Dann matcht die Binding für Account "person1" auf Agent "person1"
    Und die Binding für Account "person2" auf Agent "person2"
    Und "channels.telegram.defaultAccount" ist explizit gesetzt

  # ---------------------------------------------------------------------------
  # K3: Speicher getrennt (Workspace/Sessions von A nicht in B sichtbar)
  # ---------------------------------------------------------------------------
  Szenario: Workspaces der Personen sind getrennt
    Angenommen Agent "person1" hat "workspace" "/home/node/.openclaw/workspace/person1"
    Und Agent "person2" hat "workspace" "/home/node/.openclaw/workspace/person2"
    Dann sind die Workspace-Pfade von "person1" und "person2" verschieden
    Und eine in Workspace "person1" angelegte Datei liegt nicht unter Workspace "person2"

  Szenario: Session-Stores der Personen sind getrennt
    Angenommen Agent "person1" nutzt "agentDir" "/home/node/.openclaw/agents/person1/agent"
    Und Agent "person2" nutzt "agentDir" "/home/node/.openclaw/agents/person2/agent"
    Wenn eine Session für Agent "person1" angelegt wird
    Dann liegt sie unter "/home/node/.openclaw/agents/person1/sessions"
    Und kein Session-Eintrag von "person1" erscheint unter "/home/node/.openclaw/agents/person2/sessions"

  Szenario: Cross-Session-Recall ist auf die eigene Person begrenzt
    Angenommen Agent "person1" führt eine Session durch
    Wenn Agent "person2" "sessions_history" für den eigenen Agent ausführt
    Dann werden keine Session-Transkripte von Agent "person1" zurückgegeben

  # ---------------------------------------------------------------------------
  # K4: Geteilte LLM-Keys funktionieren für alle Agents
  # ---------------------------------------------------------------------------
  Szenario: Beide Agents lösen denselben geteilten Provider-Key auf
    Angenommen "models.providers.deepseek.apiKey" ist als SecretRef "${DEV_DEEPSEEK_API_KEY}" konfiguriert
    Und die Container-Umgebung von "openclaw-oc4" enthält "DEV_DEEPSEEK_API_KEY"
    Wenn Agent "person1" einen LLM-Call über den Provider "deepseek" ausführt
    Dann ist der Call erfolgreich (HTTP 200 des Providers)
    Und im Config-Dump von "openclaw.json" erscheint kein Plaintext-API-Key

  Szenario: SecretRef wird zur Laufzeit aufgelöst und nicht persistiert
    Angenommen das gerenderte "openclaw.json" von oc4 enthält nur den SecretRef "${DEV_DEEPSEEK_API_KEY}"
    Und die Container-Umgebung von "openclaw-oc4" enthält "DEV_DEEPSEEK_API_KEY"
    Wenn der Gateway-Prozess startet oder reloadt
    Dann wird der SecretRef "${DEV_DEEPSEEK_API_KEY}" aus der Prozess-Umgebung aufgelöst
    Und ein Reload erfolgt als "atomic swap" (belegtes Verhalten laut secrets.md)
    # Zu verifizieren (vor Umsetzung am echten Gateway): Bei NICHT auflösbarem SecretRef ist
    # das Verhalten aus secrets.md nicht belegbar. Zu prüfen: Fehlerprotokollierung ODER
    # Weiterverwendung von last-known-good — Verhalten vor Umsetzung am echten Gateway klären.

  # ---------------------------------------------------------------------------
  # K5: Secrets liegen nicht in Git
  # ---------------------------------------------------------------------------
  Szenario: Keine Secret-Werte im committeten Repository
    Angenommen der Feature-Branch "feature/pilot-familie-oc4-dev" ist gepusht
    Wenn ich den Branch auf Secret-Muster durchsuche ("sk-", Bot-Token-Format, API-Keys)
    Dann gibt es keinen Treffer für echte Secret-Werte
    Und die Datei ".env" ist via ".gitignore" ausgeschlossen
    Und nur die Datei ".env.example" (Platzhalter) ist committet

  Szenario: Secret-Scan im CI ist sauber
    Angenommen der CI-Workflow "ci.yml" läuft auf dem Feature-Branch
    Wenn ein Secret-Scan (gitleaks oder äquivalent) ausgeführt wird
    Dann meldet der Scan keine Befunde
    Und "openclaw secrets audit --check" auf oc4 ist sauber

  # ---------------------------------------------------------------------------
  # K6: Update-/Backup-/Restart-Prozedur dokumentiert
  # ---------------------------------------------------------------------------
  Szenario: Update-Prozedur ist dokumentiert und reproduzierbar
    Angenommen die Doku (arc42/ADR/README) beschreibt das OpenClaw-Update
    Wenn ein Update durchgeführt wird (Image-Pin ändern → "04-service-deploy" mit "pull: always")
    Dann ist der Ablauf schriftlich mit Rollback-Pfad (alten Pin wiederherstellen) dokumentiert

  Szenario: Backup- und Restart-Prozedur ist dokumentiert
    Angenommen die Doku benennt die zu sichernden Pfade "/srv/openclaw/oc4/config" und "/srv/openclaw/oc4/workspace"
    Wenn ein Backup durchgeführt wird
    Dann ist ein Wiederherstellungsweg (Restore der Volumes + Secrets) dokumentiert
    Und der Restart-Weg ("docker compose restart openclaw-oc4") ist dokumentiert

  # ---------------------------------------------------------------------------
  # K7: Review durchgeführt (Autor ≠ Reviewer), Befund dokumentiert
  # ---------------------------------------------------------------------------
  Szenario: Unabhängiger Review mit dokumentiertem Befund
    Angenommen der Pilot ist auf dem Feature-Branch "feature/pilot-familie-oc4-dev" umgesetzt
    Wenn ein Pull Request erstellt wird
    Dann ist der Review-Autor verschieden vom Implementierungs-Autor
    Und der Review-Befund ist im PR (Kommentar oder "iac4-design"-Dokument) dokumentiert
    Und die CI-Checks des PR sind grün, bevor der Pilot als "erfolgreich" gemeldet wird

  # ---------------------------------------------------------------------------
  # K8: Kein Merge nach main während des Pilots
  # ---------------------------------------------------------------------------
  Szenario: Kein Merge nach main während des Pilots
    Angenommen der Feature-Branch "feature/pilot-familie-oc4-dev" ist der Deploy-Branch
    Wenn der Pilot aktiv läuft
    Dann ist die PR-Basis des Pilot-PRs "main"
    Und es existiert kein Merge-Commit und kein Merge-Event auf "main" für den Feature-Branch
    Und der Feature-Branch "feature/pilot-familie-oc4-dev" bleibt bestehen
    Und Deploys nach dev erfolgen ausschließlich vom Feature-Branch

  # ---------------------------------------------------------------------------
  # K9: Workflow 05 erweitert — Device-Pairing + mehrere Telegram-Bots (Multi-Account)
  # ---------------------------------------------------------------------------
  Szenario: Workflow 05 genehmigt Device-Pairing und mehrere Telegram-Bots auf oc4
    Angenommen Workflow "05-device-approve.yml" kennt die Instanz "oc4" mit Port 18792
    Und das Secret "DEV_OC4_GATEWAY_TOKEN" ist im Workflow als E2E-Gateway-Token hinterlegt
    Wenn ein Device-Pairing-Request für den Container "openclaw-oc4" eingeht
    Dann kann der Request per "openclaw devices approve <ID>" freigegeben werden
    Und der E2E-Modus des Workflows löst für "oc4" den Port 18792 und das Gateway-Token auf
    Wenn ein Telegram-Pairing-Request für den Bot "person1" und einer für den Bot "person2" eingehen
    Dann kann die Freigabe je Account ("person1" und "person2") erfolgen
    Und die Genehmigungs-Whitelist "TELEGRAM_APPROVE_USERS" ist pro Bot/Account abbildbar
    Und der CI-Workflow "ci-device-approve.yml" läuft auf dem Feature-Branch grün
