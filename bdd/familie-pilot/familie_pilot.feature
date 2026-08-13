# language: de
# BDD-Feature: Familien-Instanz auf oc1 (dev) — Pilot (GH Issue #126)
# Referenz-Konzept: iac4-pilot/konzept-pilot-oc1-dev.md
# Syntax: Feature/Scenario/Given/When/Then — deutsch, technisch umsetzbar.
# Jedes Szenario bildet genau ein Abnahmekriterium (K1–K8) aus #126 ab.
# Szenario-Anzahl: 14 (K1: 1, K2: 2, K3: 3, K4: 2, K5: 2, K6: 2, K7: 1, K8: 1).
# Hinweis: Die Personen-Namen "harald"/"anna" sind Platzhalter (Beispielwerte); solange
# Q3 (Pilot-Personen) offen ist, werden sie nach Klärung durch die echten Namen ersetzt.

Funktionalität: Familien-Instanz auf oc1 (dev)
  Als Betreiber (Harald) möchte ich EINE OpenClaw-Instanz (oc1, dev) betreiben,
  die mehrere Familienmitglieder mit geteilten LLM-Keys, getrenntem Speicher
  und je einem eigenen Telegram-Bot versorgt, damit die Familie gemeinsam
  Infrastruktur nutzt, aber getrennt arbeitet.

  Hintergrund:
    Angenommen die Instanz "oc1" ist per Feature-Branch "feature/pilot-familie-oc1-dev"
    auf dem dev-VPS "vps-dev.tailcfea8a.ts.net" deployt
    Und das Gateway ist über Tailscale Serve unter Port 18789 erreichbar
    Und die Personen "harald" und "anna" sind als Agents in "agents.list" konfiguriert
    Und die Telegram-Accounts "harald" und "anna" existieren in "channels.telegram.accounts"

  # ---------------------------------------------------------------------------
  # K1: Instanz läuft auf oc1 (dev), Gateway erreichbar
  # ---------------------------------------------------------------------------
  Szenario: Gateway der Familien-Instanz ist auf oc1 erreichbar
    Angenommen der Docker-Container "openclaw-oc1" läuft auf "vps-dev.tailcfea8a.ts.net"
    Wenn ich den Health-Endpunkt "https://vps-dev.tailcfea8a.ts.net:18789/health" aufrufe
    Dann ist der HTTP-Status 200
    Und der Container-Status von "openclaw-oc1" ist "healthy"
    Und "tailscale serve status" enthält eine Route "18789 → localhost:18789"

  # ---------------------------------------------------------------------------
  # K2: ≥2 Personen je eigener Bot, geroutet auf eigene Persona
  # ---------------------------------------------------------------------------
  Szenario: Jeder Personen-Bot routet auf die eigene Agent-Persona
    Angenommen der Telegram-Bot für "harald" hat den Token aus "DEV_OC1_TELEGRAM_BOT_HARALD"
    Und der Telegram-Bot für "anna" hat den Token aus "DEV_OC1_TELEGRAM_BOT_ANNA"
    Wenn eine DM an den Bot von "harald" gesendet wird
    Dann wird die Nachricht an den Agent "harald" geroutet
    Und die Antwort trägt die Identity von Agent "harald"
    Wenn eine DM an den Bot von "anna" gesendet wird
    Dann wird die Nachricht an den Agent "anna" geroutet
    Und die Antwort trägt die Identity von Agent "anna"

  Szenario: Bindings routen deterministisch pro Telegram-Account
    Angenommen "bindings" enthält
      | agentId | channel  | accountId |
      | harald  | telegram | harald    |
      | anna    | telegram | anna      |
    Wenn "channels.telegram.accounts" genau die AccountIds "harald" und "anna" definiert
    Dann matcht die Binding für Account "harald" auf Agent "harald"
    Und die Binding für Account "anna" auf Agent "anna"
    Und "channels.telegram.defaultAccount" ist explizit gesetzt

  # ---------------------------------------------------------------------------
  # K3: Speicher getrennt (Workspace/Sessions von A nicht in B sichtbar)
  # ---------------------------------------------------------------------------
  Szenario: Workspaces der Personen sind getrennt
    Angenommen Agent "harald" hat "workspace" "/home/node/.openclaw/workspace/harald"
    Und Agent "anna" hat "workspace" "/home/node/.openclaw/workspace/anna"
    Dann sind die Workspace-Pfade von "harald" und "anna" verschieden
    Und eine in Workspace "harald" angelegte Datei liegt nicht unter Workspace "anna"

  Szenario: Session-Stores der Personen sind getrennt
    Angenommen Agent "harald" nutzt "agentDir" "/home/node/.openclaw/agents/harald/agent"
    Und Agent "anna" nutzt "agentDir" "/home/node/.openclaw/agents/anna/agent"
    Wenn eine Session für Agent "harald" angelegt wird
    Dann liegt sie unter "/home/node/.openclaw/agents/harald/sessions"
    Und kein Session-Eintrag von "harald" erscheint unter "/home/node/.openclaw/agents/anna/sessions"

  Szenario: Cross-Session-Recall ist auf die eigene Person begrenzt
    Angenommen Agent "harald" führt eine Session durch
    Wenn Agent "anna" "sessions_history" für den eigenen Agent ausführt
    Dann werden keine Session-Transkripte von Agent "harald" zurückgegeben

  # ---------------------------------------------------------------------------
  # K4: Geteilte LLM-Keys funktionieren für alle Agents
  # ---------------------------------------------------------------------------
  Szenario: Beide Agents lösen denselben geteilten Provider-Key auf
    Angenommen "models.providers.deepseek.apiKey" ist als SecretRef "${DEV_DEEPSEEK_API_KEY}" konfiguriert
    Und die Container-Umgebung von "openclaw-oc1" enthält "DEV_DEEPSEEK_API_KEY"
    Wenn Agent "harald" einen LLM-Call über den Provider "deepseek" ausführt
    Dann ist der Call erfolgreich (HTTP 200 des Providers)
    Und im Config-Dump von "openclaw.json" erscheint kein Plaintext-API-Key

  Szenario: SecretRef wird zur Laufzeit aufgelöst und nicht persistiert
    Angenommen das gerenderte "openclaw.json" von oc1 enthält nur den SecretRef "${DEV_DEEPSEEK_API_KEY}"
    Und die Container-Umgebung von "openclaw-oc1" enthält "DEV_DEEPSEEK_API_KEY"
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
    Angenommen der Feature-Branch "feature/pilot-familie-oc1-dev" ist gepusht
    Wenn ich den Branch auf Secret-Muster durchsuche ("sk-", Bot-Token-Format, API-Keys)
    Dann gibt es keinen Treffer für echte Secret-Werte
    Und die Datei ".env" ist via ".gitignore" ausgeschlossen
    Und nur die Datei ".env.example" (Platzhalter) ist committet

  Szenario: Secret-Scan im CI ist sauber
    Angenommen der CI-Workflow "ci.yml" läuft auf dem Feature-Branch
    Wenn ein Secret-Scan (gitleaks oder äquivalent) ausgeführt wird
    Dann meldet der Scan keine Befunde
    Und "openclaw secrets audit --check" auf oc1 ist sauber

  # ---------------------------------------------------------------------------
  # K6: Update-/Backup-/Restart-Prozedur dokumentiert
  # ---------------------------------------------------------------------------
  Szenario: Update-Prozedur ist dokumentiert und reproduzierbar
    Angenommen die Doku (arc42/ADR/README) beschreibt das OpenClaw-Update
    Wenn ein Update durchgeführt wird (Image-Pin ändern → "04-service-deploy" mit "pull: always")
    Dann ist der Ablauf schriftlich mit Rollback-Pfad (alten Pin wiederherstellen) dokumentiert

  Szenario: Backup- und Restart-Prozedur ist dokumentiert
    Angenommen die Doku benennt die zu sichernden Pfade "/srv/openclaw/oc1/config" und "/srv/openclaw/oc1/workspace"
    Wenn ein Backup durchgeführt wird
    Dann ist ein Wiederherstellungsweg (Restore der Volumes + Secrets) dokumentiert
    Und der Restart-Weg ("docker compose restart openclaw-oc1") ist dokumentiert

  # ---------------------------------------------------------------------------
  # K7: Review durchgeführt (Autor ≠ Reviewer), Befund dokumentiert
  # ---------------------------------------------------------------------------
  Szenario: Unabhängiger Review mit dokumentiertem Befund
    Angenommen der Pilot ist auf dem Feature-Branch "feature/pilot-familie-oc1-dev" umgesetzt
    Wenn ein Pull Request erstellt wird
    Dann ist der Review-Autor verschieden vom Implementierungs-Autor
    Und der Review-Befund ist im PR (Kommentar oder "iac4-design"-Dokument) dokumentiert
    Und die CI-Checks des PR sind grün, bevor der Pilot als "erfolgreich" gemeldet wird

  # ---------------------------------------------------------------------------
  # K8: Kein Merge nach main während des Pilots
  # ---------------------------------------------------------------------------
  Szenario: Kein Merge nach main während des Pilots
    Angenommen der Feature-Branch "feature/pilot-familie-oc1-dev" ist der Deploy-Branch
    Wenn der Pilot aktiv läuft
    Dann ist die PR-Basis des Pilot-PRs "main"
    Und es existiert kein Merge-Commit und kein Merge-Event auf "main" für den Feature-Branch
    Und der Feature-Branch "feature/pilot-familie-oc1-dev" bleibt bestehen
    Und Deploys nach dev erfolgen ausschließlich vom Feature-Branch
