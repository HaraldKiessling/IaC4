// ia4-vault-approval – Freigabe nur fuer Tresor-Zugriffe (ADR-027, Fix 2026-10-11).
// Von Ansible abgelegt, root-eigen und read-only in den Container gemountet.
// Jeder Tool-Aufruf, dessen Parameter den Agenten-Tresor beruehren (ia4-bw, Bitwarden CLI,
// BW_*-Variablen), wartet auf Haralds Freigabe in Telegram (allow-once/deny).
// Eine Freigabe gilt danach WINDOW_MS lang NUR fuer den freigegebenen Eintrag (Suchbegriff, ID,
// Name) und nur zum Lesen (get, list --search), fuer alle Agenten dieser Instanz (auch Sub-Agenten).
// Alles andere (anderer Eintrag, list ohne Suche, create/edit/delete, direkte bw-/BW_*-/
// Umgebungs-Zugriffe) fragt jedes Mal
// (Owner-Entscheide 2026-10-11: "10 Minuten", "nur fuer einen Eintrag").
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

// Freigaben je Eintrag, nur im Speicher des Gateway-Prozesses (eine Instanz); ein Neustart
// beendet sie. Monotone Uhr, damit ein Zeitsprung kein Fenster verlaengert.
const WINDOW_MS = 10 * 60_000;
const APPROVAL_TIMEOUT_MS = 600_000;
const approved = new Map<string, number>(); // Eintrag -> gueltig bis
const pending = new Map<string, { since: number; id: number }>(); // Eintrag -> offene Anfrage
const resolveAfterCall = new Map<string, boolean>(); // freigegebener Aufruf -> Ergebnis auswerten
let nextId = 1;
const now = () => performance.now();

function paramsText(params: unknown): string {
  try {
    return JSON.stringify(params) ?? "";
  } catch {
    return String(params);
  }
}

// Einfache Shell-Zerlegung des ia4-bw-Aufrufs (Woerter, Quotes), endet bei | ; & ) oder Zeilenende.
function ia4bwArgs(command: string): string[] | undefined {
  const m = command.match(/ia4-bw\b([^|;&)\n]*)/);
  if (!m || /[`$]/.test(m[1])) return undefined;
  const words: string[] = [];
  for (const w of m[1].matchAll(/"([^"]*)"|'([^']*)'|([^\s"'<>]+)/g)) {
    words.push(w[1] ?? w[2] ?? w[3]);
  }
  return words;
}

// Schluessel des Eintrags, auf den sich der Aufruf bezieht; undefined = jedes Mal fragen.
function entryKey(command: string): string | undefined {
  const occurrences = command.match(/ia4-bw\b/g)?.length ?? 0;
  if (occurrences !== 1) return undefined;
  // Ausserhalb des ia4-bw-Aufrufs darf nichts anderes den Tresor beruehren.
  const rest = command.replace(/[^\s|;&(]*ia4-bw\b[^|;&)\n]*/, " ");
  if (VAULT.test(rest) || ENV_DUMP.test(rest)) return undefined;
  const a = ia4bwArgs(command);
  if (!a) return undefined;
  const norm = (v: string | undefined) => (v ?? "").trim().toLowerCase();
  if (a[0] === "list" && a[1] === "items") {
    const i = a.indexOf("--search");
    return i > 0 && a[i + 1] ? `search:${norm(a[i + 1])}` : undefined;
  }
  // Nur Lesen nutzt das Fenster; create/edit/delete fragen immer.
  if (a[0] === "get" && a[1] && a[2] && !a[2].startsWith("-")) {
    return `entry:${norm(a[2])}`;
  }
  return undefined;
}

// Liefert die Ergebnis-Ausgabe genau EINEN Eintrag, gilt die Freigabe auch fuer seine ID und
// seinen Namen (Suche -> get item <id> fragt nicht erneut). Mehrere Treffer: keine Erweiterung.
function entriesFromResult(result: unknown): string[] {
  const text = typeof result === "string" ? result : paramsText(result);
  const ids = [...text.matchAll(/\\?"id\\?"\s*:\s*\\?"([0-9a-f-]{36})\\?"/gi)].map((m) => m[1].toLowerCase());
  if (new Set(ids).size !== 1) return [];
  const keys = [`entry:${ids[0]}`];
  const afterId = text.slice(text.search(/\\?"id\\?"\s*:/));
  const name = afterId.match(/\\?"name\\?"\s*:\s*\\?"((?:[^"\\]|\\(?!")[\s\S])*)\\?"/);
  if (name) keys.push(`entry:${name[1].trim().toLowerCase()}`);
  return keys;
}

function callKey(event: { toolCallId?: string; params?: unknown }): string {
  return event.toolCallId ?? paramsText(event.params);
}

export default definePluginEntry({
  id: "ia4-vault-approval",
  name: "IaC4 Tresor-Freigabe",
  description: "Fragt vor Zugriffen auf den Agenten-Tresor (Bitwarden) per Telegram nach; eine Freigabe gilt 10 Minuten fuer einen Eintrag.",
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
        const key = typeof raw === "string" ? entryKey(raw) : undefined;
        const t = now();
        if (key && (approved.get(key) ?? 0) > t) {
          resolveAfterCall.set(callKey(event), true);
          return;
        }
        if (key) {
          const open = pending.get(key);
          if (open && t - open.since < APPROVAL_TIMEOUT_MS) {
            return {
              block: true,
              blockReason:
                "Fuer diesen Tresor-Eintrag ist gerade eine Freigabe bei Harald angefragt. Rufe ihn erst wieder auf, nachdem der laufende Aufruf ein Ergebnis geliefert hat.",
            };
          }
        }
        const id = nextId++;
        if (key) pending.set(key, { since: t, id });
        const scope = key ? "Gilt 10 Min. nur fuer diesen Eintrag." : "Gilt nur fuer diesen Aufruf.";
        return {
          requireApproval: {
            title: "Zugriff auf den Agenten-Tresor",
            // Passwort-Felder im Befehl (z. B. JSON fuer create/edit) nicht in den Chat geben.
            description: `${scope} ${ctx.agentId ?? "agent"} (${event.toolName}): ${command}`
              .replace(SECRET, "$1***")
              .slice(0, 500),
            severity: "warning",
            allowedDecisions: ["allow-once", "deny"],
            timeoutMs: APPROVAL_TIMEOUT_MS,
            onResolution(decision) {
              if (!key) return;
              // Nur die eigene Anfrage abschliessen (eine aeltere Antwort setzt nichts Neueres zurueck).
              if (pending.get(key)?.id === id) pending.delete(key);
              if (decision === "allow-once") {
                approved.set(key, now() + WINDOW_MS);
                resolveAfterCall.set(callKey(event), true);
              }
            },
          },
        };
      },
      { priority: 100 },
    );
    api.on("after_tool_call", (event) => {
      const k = callKey(event);
      if (!resolveAfterCall.delete(k) || event.error) return;
      const until = now() + WINDOW_MS;
      for (const entry of entriesFromResult(event.result)) {
        if ((approved.get(entry) ?? 0) < until) approved.set(entry, until);
      }
    });
  },
});
