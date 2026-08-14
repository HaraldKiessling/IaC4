# BDD – Pilot Familien-Instanz oc4 (GH #126)

Ausführbare Checks zu `familie_pilot.feature` (K1–K9, 15 Szenarien; Referenz-Konzept: `docs/arc42/07_verteilungssicht.md` (Abschnitt „OpenClaw oc4 – Familien-Instanz“, GH #126); alte Konzept-Datei `iac4-pilot/konzept-pilot-oc1-dev.md` (§7) historisch, Zielinstanz **oc4**).
Jede Datei `k<N>_*.sh` bildet genau ein Abnahmekriterium ab.

## Lauf

```bash
# Lokal (ohne VPS-Zugriff): Struktur-, Secret-, Doku- und Git-Checks
./run-all.sh

# Mit Remote-Deploy-Checks (read-only SSH, z.B. vom GH-Runner im Tailnet)
VPS_HOST=vps-dev.tailcfea8a.ts.net ./run-all.sh
```

Variablen (Platzhalter, per Env überschreibbar): `PILOT_BRANCH`, `INSTANCE` (oc4),
`PORT` (18792), `PERSONS` (`person1 person2`), `DEFAULT_ACCOUNT`, `VPS_HOST`, `VPS_USER`.

## Mapping Kriterium → Skript → Messmethode (Konzept §7)

| K | Skript | Messmethode | Lokal? |
|---|--------|-------------|--------|
| K1 | `k1_health.sh` | `GET /health` → 200, Container healthy, `tailscale serve`-Route | nur remote |
| K2 | `k2_bots_persona.sh` | `accounts` (person1/person2) + `defaultAccount` + `bindings` im Template/Config-Dump; Live-DM-Persona-Test = Abnahme | Struktur lokal, Rest remote |
| K3 | `k3_storage_separation.sh` | getrennte `workspace`/`agentDir`/Sessions-Pfade (Konstruktion + Host-Dirs) | Struktur lokal, Rest remote |
| K4 | `k4_shared_llm_keys.sh` | `apiKey` als SecretRef `${ENV}`, kein Plaintext im Config-Dump; Env-Durchreichung im Compose | Struktur lokal, Rest remote |
| K5 | `k5_secrets_not_in_git.sh` | `git grep` Secret-Muster, `.gitignore` (`.env*`), nur `.env.example` committet | **voll lokal** |
| K6 | `k6_update_backup_restart.sh` | Doku: Pin-Update + Deploy, Backup-Pfade `/srv/openclaw/oc4/{config,workspace}`, Restart-Kommando | **voll lokal** |
| K7 | `k7_review.sh` | Review-Konvention (Autor ≠ Reviewer) im Repo; PR-Status via `gh` (falls vorhanden) | **voll lokal** |
| K8 | `k8_no_merge.sh` | Branch == Feature-Branch, keine Merge-Commits `main..HEAD`, Branch auf origin | **voll lokal** |
| K9 | `k9_workflow05.sh` | `05-device-approve.yml`: oc4-E2E-case (18792) + `DEV_OC4_GATEWAY_TOKEN`, Multi-Bot-`--account` (belegt: OpenClaw-Doku `pairing.md`), Whitelist `TELEGRAM_APPROVE_USERS_<ACCOUNT>` | **voll lokal** |

## Hinweise

- **Q3 (Konzept §9, beantwortet 2026-08-13):** Personen-IDs `person1`/`person2` sind
  gekennzeichnete Platzhalter; echte Namen + BotFather-Tokens sind nachlieferbar.
  Accounts und Bindings werden nur gerendert, wenn das jeweilige Token-Env
  (GH-Secret `DEV_OC4_TELEGRAM_BOT_PERSON1/PERSON2`) gesetzt ist – bis dahin sind die
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
- **Multi-Account-Beleg (K9):** `openclaw pairing list/approve telegram` akzeptiert
  `--account <id>` bei Multi-Account-Kanälen (OpenClaw-Doku `channels/pairing.md`:
  „Multi-account channels take `--account <id>`“). Umsetzung: Workflow-Input
  `account` → `approve.py --account` → `discovery.py` (remote + lokal) →
  Whitelist `TELEGRAM_APPROVE_USERS_<ACCOUNT>` mit Fallback.
