# SSH-Key-Management

## Workflow: "00 – SSH-Key-Paar generieren"

Generiert ein ED25519-Key-Paar und speichert es in GH Secrets.

### Trigger
Nur `workflow_dispatch` (nie automatisch).

### Parameter

| Parameter | Default | Beschreibung |
|-----------|---------|--------------|
| `force` | `false` | Überschreibt vorhandenen Key (⚠️ Vorsicht!) |

### Sicherheit

- **Default `force=false`** – Wenn `SSH_KEY` bereits existiert, bricht der Workflow ab
- `force=true` nur bei bewusster Entscheidung (z.B. Rotation)
- Nach Generierung: **Public-Key manuell in `cloud-config.yaml` eintragen**
- Der Workflow kann das nicht automatisch (sonst Überschreibung nicht sichtbar)

### Verwendung

```bash
# Normal (schlägt fehl wenn Key existiert)
gh workflow run "00 – SSH-Key-Paar generieren"

# Key rotieren (überschreibt existierenden)
gh workflow run "00 – SSH-Key-Paar generieren" -f force=true
```

### Ablauf
1. Workflow prüft ob `SSH_KEY` in GH Secrets existiert
2. Wenn ja + `force=false` → ❌ Abbruch
3. Wenn nein ODER `force=true` → Key generieren
4. Private Key → `SSH_KEY` (GH Secret)
5. Public Key → `SSH_KEY_PUB` (GH Secret)
6. Public Key wird ausgegeben (zum Eintragen in `cloud-config.yaml`)

### Key-Format
- **Typ:** ED25519
- **Kommentar:** `iac4-deploy-key-<YYYYMMDD>`
- **Private Key:** In GH Secret (nie lokal speichern ausser temporär)
- **Public Key:** In `cloud-config.yaml` + GH Secret `SSH_KEY_PUB`
