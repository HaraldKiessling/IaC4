# 7. Verteilungssicht

## Infrastruktur (final – ab Phase 2b)
```
[Tailnet (Tailscale Mesh 🔒 – HTTPS via Tailscale Serve 443→80)]
    │
    ▼
[VPS (Ubuntu 24.04)]
    ├── tailscale0 (100.x.y.z) – Tailscale Mesh 🔒
    ├── eth0 (Public-IP) – SSH blockiert via UFW 🔒, keine Service-Ports
    ├── docker0 (172.17.0.1)   – Docker Bridge
    │
    ├── Container: traefik      → Port 80 (Tailnet-only, UFW-CGNAT)
    ├── Container: qdrant       → Port 6333, 6334 (lokal + TS)
    ├── Container: code-server  → Port 8443 (via Traefik)
    ├── Container: openclaw-oc1 → Port 18789 (localhost-only, TS-Serve-TLS) – Default-Gateway
    ├── Container: openclaw-oc2 → Port 18790 (localhost-only, TS-Serve-TLS) – DevOps (4 Agents)
    └── Container: openclaw-oc3 → Port 18791 (aktiv, Best-Practice-Referenz)
```

## Netzwerk-Security (nach SSH-Transition)
| Service | Erreichbar via | Authentifizierung |
|---------|---------------|-------------------|
| Traefik (HTTP) | Tailscale (Port 80, UFW-CGNAT); HTTPS via Tailscale Serve | Tailscale ACL + BasicAuth (Dashboard, ADR-019) |
| SSH | NUR Tailscale (100.x.y.z:22) | SSH-Key + Tailscale ACL |
| Qdrant | localhost + Tailscale | Tailscale ACL |
| Code-Server | Tailscale (Traefik-Route) | Traefik-ForwardAuth |
| OpenClaw OC1/OC2 | Tailscale via Serve-TLS (18789/18790) | Gateway-Token + Tailscale ACL |
| OpenClaw OC3 | DEV: aktiv (Best-Practice-Referenz, Benchmark – Design 01-oc2-oc3-benchmark); PROD: aktiv (Best-Practice-Referenz, seit 2026-08-12) | Port 18791 |

## SSH-Transition (zeitlich)
| Phase | SSH-Zugriff | Via | Dauer |
|-------|-------------|-----|-------|
| 0 (cloud-config) | 🔓 Öffentliche IP | eth0:22 | Minuten (Setup) |
| 1 (Baseline) | 🔓 Öffentliche IP | eth0:22 | < 2 Min |
| 2a (Tailscale) | 🔓 Öffentliche IP | eth0:22 | < 2 Min |
| 2b (Restrict) | 🔒 Geschlossen | – | < 1 Min |
| 2c+ (Final) | 🔒 Nur Tailscale | tailscale0:22 | dauerhaft |

## OpenClaw oc4 – Familien-Instanz (Pilot, GH #126)

**Status:** Feature-Branch `feature/pilot-familie-oc4-dev` (kein Merge nach `main` während des Pilots, K8).
Zielinstanz: **oc4** (Port 18792) auf `vps-dev.tailcfea8a.ts.net` – Harald-Entscheidung 2026-08-13 15:43
(oc1/oc2/oc3 bleiben als Benchmark-Arme unangetastet; Dateiname des Konzepts ist historisch `konzept-pilot-oc1-dev.md`).
Konzept: `iac4-pilot/konzept-pilot-oc1-dev.md`. BDD: `bdd/familie-pilot/`.

### Konfigurationsmodell (Alternative A: 1 Gateway, N Agents)

Die Instanz oc4 (Port 18792) ist eine **neue** Familien-Instanz (Alternative A:
1 Gateway, N Agents) — Quelle: `ansible/group_vars/vps-dev.yml` (oc4, neuer Eintrag) +
`ansible/roles/openclaw-gateway/templates/openclaw.json.j2`:

| Mechanik | Umsetzung | Scope-Punkt |
|----------|-----------|-------------|
| Personen-Agents | `oc.person_agents` → `agents.list[]` mit je `workspace` + `agentDir` + `subagents.allowAgents: ["<person>"]` | S3 (getrennter Speicher) |
| Eigener Bot je Person | `oc.telegram_accounts` → `channels.telegram.accounts.<person>.botToken` + `defaultAccount` + `dmPolicy: "pairing"` | S4 |
| Routing | Top-Level `bindings[]`: `{agentId: <person>, match: {channel: "telegram", accountId: <person>}}` | S4 |
| Geteilte LLM-Keys | `oc.secrets_ref: true` → `models.providers.*.apiKey` als SecretRef `"${DEV_*}"`; Werte als Container-Env via `docker-compose.yml.j2` (Workflow 04 reicht GH-Secrets durch) | S2/S6 |
| Web-Search (OpenRouter) | `oc.websearch_api_key_env: "DEV_OC4_OPENROUTER_API_KEY"` → `plugins.entries.perplexity.config.webSearch.apiKey` als SecretRef `"${DEV_OC4_OPENROUTER_API_KEY}"` (+ `baseUrl`/`model` explizit); der sk-or-Key schaltet auf den OpenRouter-Chat-Completions-Pfad um (Doku: `docs/tools/perplexity-search.md` „OpenRouter/Sonar“) | Harald 2026-08-13 17:00 (#126, statt Perplexity) |
| Rollen-Pattern | `agents.defaults.subagents`: `delegationMode: "prefer"`, `maxSpawnDepth: 2` (Orchestrator-Pattern je Person, S5) | S5 |

**Platzhalter:** Personen-IDs `person1`/`person2` sind gekennzeichnete Platzhalter (Q3 beantwortet
2026-08-13 – echte Namen + BotFather-Tokens nachlieferbar); Accounts/Bindings werden nur
gerendert, wenn das jeweilige Token-Env gesetzt ist.

**Web-Search (Umstellung 2026-08-13 17:00, #126):** oc4 nutzt OpenRouter statt Perplexity
(GH-Secret `DEV_OC4_OPENROUTER_API_KEY`). Gerendert als SecretRef `"${DEV_OC4_OPENROUTER_API_KEY}"`
in `plugins.entries.perplexity.config.webSearch.apiKey` (SecretRef-faehig, Beleg:
`reference/secretref-credential-surface.md`); der sk-or-Key schaltet den Provider auf den
OpenRouter-Chat-Completions-Pfad um (Sonar-Kompatibilitaet, `docs/tools/perplexity-search.md`).
oc1/oc2/oc3 bleiben unveraendert auf Perplexity (`<T>_OC<n>_WEBSEARCH_API_KEY`).

### Pfad-Mapping Host ↔ Container (oc4)

| Zweck | Host-Pfad (`vps-dev`) | Container-Pfad |
|-------|----------------------|----------------|
| Config + Agent-State (inkl. `agents/<person>/agent`) | `/srv/openclaw/oc4/config` | `/home/node/.openclaw` |
| Workspaces (je Person) | `/srv/openclaw/oc4/workspace/<person>` | `/home/node/.openclaw/workspace/<person>` |
| Sessions | `/srv/openclaw/oc4/config/agents/<person>/sessions` | `/home/node/.openclaw/agents/<person>/sessions` |

### Expositions-Caveat `bind: "lan"` (Konzept §3, Empfehlung (a))

Der Container bindet `lan` (Docker-Bridge, `traefik-network`), weil ein container-interner
`loopback`-Bind über den publizierten Port (`127.0.0.1:18792:18792`) nicht erreichbar wäre.
Die Exposition ist trotzdem loopback-only: Host-Port bindet `127.0.0.1`, TLS-Front ist
`tailscale serve --https=18792` (ADR-025). Von außen ist das Gateway nur im Tailnet erreichbar.

### Betrieb (K6: Update / Backup / Restart)

- **Update:** Image-Pin `openclaw_image_version` ändern (SSoT `ansible/group_vars/all.yml`,
  ADR-017) → Workflow `04-service-deploy.yml` (`target: dev`, `instance: oc4`, `pull: always` +
  Recreate via `docker_compose_v2`). Rollback = alten Pin wiederherstellen + erneut deployen.
- **Backup:** Verzeichnisse `/srv/openclaw/oc4/config` und `/srv/openclaw/oc4/workspace`
  (Host-Pfade) sichern; Secrets sind SSoT in GH-Secrets (`.env`/`.env.example`-Schema: Konzept §4),
  keine Secrets im Backup nötig.
- **Restore:** Volumes aus Backup zurückkopieren (uid 1000), danach
  `docker compose -f /srv/openclaw/oc4/docker-compose.yml restart openclaw` (Container `openclaw-oc4`).
- **Restart:** `docker compose -f /srv/openclaw/oc4/docker-compose.yml restart openclaw` bzw.
  `docker restart openclaw-oc4`; Health: `GET https://vps-dev.tailcfea8a.ts.net:18792/health` → 200.
