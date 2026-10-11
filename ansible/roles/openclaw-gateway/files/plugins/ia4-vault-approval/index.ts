// ia4-vault-approval – Freigabe nur fuer Tresor-Zugriffe (ADR-027, Fix 2026-10-11).
// Von Ansible abgelegt, root-eigen und read-only in den Container gemountet.
// Jeder Tool-Aufruf, dessen Parameter den Agenten-Tresor beruehren (ia4-bw, Bitwarden CLI,
// BW_*-Variablen), wartet auf Haralds Freigabe in Telegram (allow-once/deny).
// Alle anderen Befehle laufen ohne Nachfrage wie vor ADR-027.
// Grundlage [V]: docs/plugins/hooks/tool-policy.md (before_tool_call, requireApproval),
// docs/plugins/plugin-permission-requests.md (Entscheidungen, Timeout, fail-closed).
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

// Treffer = Nachfrage. Bewusst breit (Tresor-Befehl, CLI-Paket, Zugangsdaten-Variablen, Prozess-
// Umgebung), aber ohne gaengige Befehle wie cd, git, python3 oder bash-Skripte.
// Keine harte Grenze: ein Skript, das diese Woerter nicht enthaelt, faellt nicht auf (ADR-027, Restrisiko).
const VAULT =
  /ia4-bw|ia4-bitwarden|@bitwarden\/cli|\bbw\b|BW_(CLIENTID|CLIENTSECRET|PASSWORD|SESSION)|\/proc\/[^/\s]*\/environ|\bprintenv\b/;
// Ausgabe der ganzen Prozess-Umgebung (enthaelt die BW_*-Zugangsdaten): nur am Shell-Befehl selbst
// geprueft, weil "env" als JSON-Feldname vorkommt. "env FOO=1 cmd" bleibt frei.
const ENV_DUMP = /(^|[;&|(]|\s)(env|export\s+-p|declare\s+-[a-z]*x[a-z]*)\s*($|[;&|>)])/m;
// Geheime Werte (JSON, auch escaped, oder NAME=wert) vor der Anzeige im Chat unkenntlich machen.
const SECRET =
  /((?:password|totp|BW_PASSWORD|BW_CLIENTSECRET|BW_SESSION)\\?"?\s*[:=]\s*)(\\?"(?:[^"\\]|\\(?!")[\s\S])*\\?"|[^\s"\;&|]+)/gi;

function paramsText(params: unknown): string {
  try {
    return JSON.stringify(params) ?? "";
  } catch {
    return String(params);
  }
}

export default definePluginEntry({
  id: "ia4-vault-approval",
  name: "IaC4 Tresor-Freigabe",
  description: "Fragt vor jedem Zugriff auf den Agenten-Tresor (Bitwarden) per Telegram nach.",
  register(api) {
    api.on(
      "before_tool_call",
      (event, ctx) => {
        const text = paramsText(event.params);
        const raw = (event.params as Record<string, unknown> | undefined)?.command;
        const command = typeof raw === "string" ? raw : text;
        // Rohbefehl zusaetzlich pruefen: im JSON wird ein Zeilenumbruch zu "\n" (kein Wortrand vor "bw").
        const hit = VAULT.test(text) || (typeof raw === "string" && (VAULT.test(raw) || ENV_DUMP.test(raw)));
        if (!hit) {
          return;
        }
        return {
          requireApproval: {
            title: "Zugriff auf den Agenten-Tresor",
            // Passwort-Felder im Befehl (z. B. JSON fuer create/edit) nicht in den Chat geben.
            description: `${ctx.agentId ?? "agent"} (${event.toolName}): ${command}`
              .replace(SECRET, "$1***")
              .slice(0, 500),
            severity: "warning",
            allowedDecisions: ["allow-once", "deny"],
            timeoutMs: 600_000,
          },
        };
      },
      { priority: 100 },
    );
  },
});
