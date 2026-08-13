# BDD – Pilot Familien-Instanz oc1 (GH #126)

Ausführbare Checks zu `familie_pilot.feature` (K1–K8, 14 Szenarien; Referenz:
`iac4-pilot/konzept-pilot-oc1-dev.md` §7). Jede Datei `k<N>_*.sh` bildet genau ein
Abnahmekriterium ab.

## Lauf

```bash
# Lokal (ohne VPS-Zugriff): Struktur-, Secret-, Doku- und Git-Checks
./run-all.sh

# Mit Remote-Deploy-Checks (read-only SSH, z.B. vom GH-Runner im Tailnet)
VPS_HOST=vps-dev.tailcfea8a.ts.net ./run-all.sh
```

Variablen (Platzhalter, per Env überschreibbar): `PILOT_BRANCH`, `INSTANCE` (oc1),
`PORT` (18789), `PERSONS` (`harald anna`), `DEFAULT_ACCOUNT`, `VPS_HOST`, `VPS_USER`.

## Mapping Kriterium → Skript → Messmethode (Konzept §7)

| K | Skript | Messmethode | Lokal? |
|---|--------|-------------|--------|
| K1 | `k1_health.sh` | `GET /health` → 200, Container healthy, `tailscale serve`-Route | nur remote |
| K2 | `k2_bots_persona.sh` | `accounts` (harald/anna) + `defaultAccount` + `bindings` im Template/Config-Dump; Live-DM-Persona-Test = Abnahme | Struktur lokal, Rest remote |
| K3 | `k3_storage_separation.sh` | getrennte `workspace`/`agentDir`/Sessions-Pfade (Konstruktion + Host-Dirs) | Struktur lokal, Rest remote |
| K4 | `k4_shared_llm_keys.sh` | `apiKey` als SecretRef `${ENV}`, kein Plaintext im Config-Dump; Env-Durchreichung im Compose | Struktur lokal, Rest remote |
| K5 | `k5_secrets_not_in_git.sh` | `git grep` Secret-Muster, `.gitignore` (`.env*`), nur `.env.example` committet | **voll lokal** |
| K6 | `k6_update_backup_restart.sh` | Doku: Pin-Update + Deploy, Backup-Pfade `/srv/openclaw/oc1/{config,workspace}`, Restart-Kommando | **voll lokal** |
| K7 | `k7_review.sh` | Review-Konvention (Autor ≠ Reviewer) im Repo; PR-Status via `gh` (falls vorhanden) | **voll lokal** |
| K8 | `k8_no_merge.sh` | Branch == Feature-Branch, keine Merge-Commits `main..HEAD`, Branch auf origin | **voll lokal** |

## Hinweise

- **Q3 offen (Konzept §9):** Personen `harald`/`anna` sind Platzhalter. Accounts und
  Bindings werden nur gerendert, wenn das jeweilige Token-Env (GH-Secret
  `DEV_OC1_TELEGRAM_BOT_HARALD/ANNA`) gesetzt ist – bis dahin sind die
  K2-Remote-Checks erwartungsgemäß rot/skip, kein Config-Fehler.
- **Kein Deploy, kein Restart, keine Schreibzugriffe:** Alle Checks sind read-only.
- **Einordnung:** Die bestehende IaC4-BDD-Suite (`scripts/bdd/*.bdd.ps1`,
  `qa/bdd-testkonzept.md`, Workflow `04-bdd-tests.yml`) bleibt unverändert; dieses
  Verzeichnis ergänzt sie um die lokal ausführbaren Pilot-Checks (Shell,
  Entscheidung engineer-pro gemäß Konzept §6). Eine Workflow-Integration kann als
  Folge-Issue folgen.
- **SecretRef-Beleg:** `channels.telegram.accounts.*.botToken` und
  `models.providers.*.apiKey` sind laut OpenClaw-Doku
  (`reference/secretref-credential-surface.md`, `gateway/secrets.md`) SecretRef-fähig;
  Auflösung erfolgt aus der Container-Umgebung (durchgereicht via
  `docker-compose.yml.j2`, Werte aus GH-Secrets).
