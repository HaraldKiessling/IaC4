// ia4-vault-approval – Freigabe nur fuer Tresor-Zugriffe (ADR-027, Fix 2026-10-11).
// Von Ansible abgelegt, root-eigen und read-only in den Container gemountet.
// Jeder Tool-Aufruf, dessen Parameter den Agenten-Tresor beruehren (ia4-bw, Bitwarden CLI,
// BW_*-Variablen), wartet auf Haralds Freigabe in Telegram (allow-once/deny).
// Suche (list items --search) fragt jedes Mal einmal; der Wrapper zeigt dabei nur ID und Name.
// Eine Freigabe gilt danach WINDOW_MS lang NUR zum Lesen (get) des freigegebenen Eintrags (ID,
// Name), fuer alle Agenten dieser Instanz (auch Sub-Agenten).
// Alles andere (anderer Eintrag, list ohne Suche, create/edit/delete, direkte bw-/BW_*-/
// Umgebungs-Zugriffe) fragt jedes Mal
// (Owner-Entscheide 2026-10-11: "10 Minuten", "nur fuer einen Eintrag", "Suche fragt").
// Alle anderen Befehle laufen ohne Nachfrage wie vor ADR-027.
// Grundlage [V]: docs/plugins/hooks/tool-policy.md (before_tool_call, requireApproval),
// docs/plugins/plugin-permission-requests.md (Entscheidungen, Timeout, fail-closed).
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

// Treffer = Nachfrage. Bewusst breit (Tresor-Befehl, CLI-Paket, Zugangsdaten-Variablen, Prozess-
// Umgebung), aber ohne gaengige Befehle wie cd, git, python3 oder bash-Skripte.
// Keine harte Grenze: ein Skript, das diese Woerter nicht enthaelt, faellt nicht auf (ADR-027, Restrisiko).
// Shell-Befehle (Tool-Parameter "command"): Tresor-Aufruf, CLI, Zugangsdaten, Prozess-Umgebung.
// Der Skill-Ordner "ia4-bitwarden" allein ist kein Zugriff (Anleitung lesen fragt nicht, DEV-Test 2026-10-11).
const VAULT =
  /ia4-bw|\/opt\/ia4-bitwarden\/cli|@bitwarden\/cli|\bbw\b|BW_(CLIENTID|CLIENTSECRET|PASSWORD|SESSION)|\/proc\/[^/\s]*\/environ|\bprintenv\b|process\.env/;
// Auftrag an einen Sub-Agenten (sessions_spawn): nur echte Zugriffe auf Zugangsdaten oder
// Prozess-Umgebung. Erwaehnt der Auftrag nur ia4-bw, fragt erst der Sub-Agent beim Ausfuehren.
// Alle anderen Tools (write/edit/process ...) behalten die volle Pruefung, sonst liesse
// sich ia4-bw ueber ein geschriebenes Skript oder eine laufende Shell ohne Karte starten (Review).
const VAULT_TEXT = /BW_(CLIENTID|CLIENTSECRET|PASSWORD|SESSION)|\/proc\/[^/\s]*\/environ|\bprintenv\b|process\.env/;
// Ausgabe der ganzen Prozess-Umgebung (enthaelt die BW_*-Zugangsdaten): nur am Shell-Befehl selbst
// geprueft, weil "env" als JSON-Feldname vorkommt. "env FOO=1 cmd" bleibt frei.
// Code-Modus-Zelle (aeusseres exec mit JavaScript): der Host kennzeichnet sie verbindlich mit
// toolKind "code_mode_exec" [V] (docs/plugins/hooks/tool-policy.md); "code" und "command" tragen dort
// denselben JS-Text. Jeder verschachtelte Tool-Aufruf laeuft erneut durch before_tool_call [V]
// (docs/tools/code-mode/internals.md, "Nested tool execution").
// Die Zelle selbst fragt deshalb nur bei Zugangsdaten-/Umgebungs-Text oder wenn sie Tresor-Text mit
// Wegen aus dem Gast heraus (process., require, import, constructor ...) kombiniert (Node-Executor ist
// keine Sicherheitsgrenze [V], docs/tools/code-mode/executors.md).
const CELL_ESCAPE = /\bprocess\s*[.\[]|\brequire\b|\bimport\b|constructor|child_process|globalThis|\bFunction\b|\beval\b/;
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
const resolveAfterCall = new Map<string, { until: number }>(); // Aufruf -> Ergebnis auswerten, Fenster-Ende erben
let nextId = 1;
const now = () => performance.now();

function paramsText(params: unknown): string {
  try {
    return JSON.stringify(params) ?? "";
  } catch {
    return String(params);
  }
}

// Lese-Fenster (get) bzw. Suchkarte (list --search) nur fuer Befehle, die GENAU dieser Form entsprechen
// (Allowlist, sonst jedes Mal fragen mit allgemeiner Karte):
//   [/opt/ia4-bitwarden/]ia4-bw list items --search <begriff> [--pretty]
//   [/opt/ia4-bitwarden/]ia4-bw get item|username|password|uri|totp|notes <name-oder-id> [--raw|--pretty]
// Woerter: ohne Sonderzeichen oder vollstaendig in '...'/"..." ohne Quotes, $, `, \ darin.
// Keine Pipes, Umleitungen, Variablen-Praefixe, Subshells, zweiten Befehle (Review 2026-10-11).
const WORD = /^(?:[A-Za-z0-9._@:\/+,%=-]+|"[^"'$`\\]*"|'[^"'$`\\]*')$/;
const GET_OBJECTS = new Set(["item", "username", "password", "uri", "totp", "notes"]);
// "title"/"timeoutSeconds": Anzeige-Titel und Laufzeit des exec-Tools [V] (bash-tools.schemas, 2026.9.8);
// Code-Modus setzte "title" bei jedem Shell-Aufruf [I] (DEV-Test 2026-10-11).
const EXEC_KEYS = new Set([
  "command", "workdir", "cwd", "timeout", "timeoutMs", "timeoutSeconds", "yieldMs", "background", "description", "title",
]);

function strictWords(command: string): string[] | undefined {
  const parts = command.trim().split(/\s+/);
  if (!parts.every((w) => WORD.test(w))) return undefined;
  return parts.map((w) => (/^["']/.test(w) ? w.slice(1, -1) : w));
}

// Schluessel des Eintrags fuer das Fenster; undefined = jedes Mal fragen.
function entryKey(params: Record<string, unknown>): { key: string; kind: "search" | "get-item" | "get" } | undefined {
  if (typeof params.command !== "string") return undefined;
  if (!Object.keys(params).every((k) => EXEC_KEYS.has(k))) return undefined;
  const w = strictWords(params.command);
  if (!w || !["ia4-bw", "/opt/ia4-bitwarden/ia4-bw"].includes(w[0])) return undefined;
  const a = w.slice(1);
  const norm = (v: string) => v.trim().toLowerCase();
  if (a[0] === "list" && a[1] === "items" && a[2] === "--search" && a[3] && !a[3].startsWith("-")) {
    if (a.slice(4).every((f) => f === "--pretty")) return { key: `search:${norm(a[3])}`, kind: "search" };
    return undefined;
  }
  if (a[0] === "get" && GET_OBJECTS.has(a[1]) && a[2] && !a[2].startsWith("-")) {
    if (a.slice(3).every((f) => f === "--raw" || f === "--pretty")) {
      return { key: `entry:${norm(a[2])}`, kind: a[1] === "item" ? "get-item" : "get" };
    }
  }
  return undefined;
}

// Genau EIN Bitwarden-Eintrag im Ergebnis (geparstes JSON mit object "item") -> dessen ID und Name.
// Nur nach "get item"; Mehrfachtreffer oder kein JSON: keine Erweiterung.
function entriesFromResult(result: unknown): string[] {
  const items = new Map<string, string>();
  const visit = (v: unknown, depth: number) => {
    if (depth > 6 || v == null) return;
    if (typeof v === "string") {
      const t = v.trim();
      if (!/^[\[{]/.test(t)) return;
      try {
        visit(JSON.parse(t), depth + 1);
      } catch {
        return;
      }
      return;
    }
    if (Array.isArray(v)) {
      const bwItems = v.filter((x) => x && typeof x === "object" && (x as Record<string, unknown>).object === "item");
      if (bwItems.length > 1) items.set("multi", "multi");
      v.forEach((x) => visit(x, depth + 1));
      return;
    }
    if (typeof v === "object") {
      const o = v as Record<string, unknown>;
      if (o.object === "item" && typeof o.id === "string") {
        items.set(o.id.toLowerCase(), typeof o.name === "string" ? o.name : "");
        return;
      }
      Object.values(o).forEach((x) => visit(x, depth + 1));
    }
  };
  visit(result, 0);
  if (items.size !== 1 || items.has("multi")) return [];
  const [[id, name]] = [...items.entries()];
  return name ? [`entry:${id}`, `entry:${name.trim().toLowerCase()}`] : [`entry:${id}`];
}

function callKey(event: { toolCallId?: string; params?: unknown }): string {
  return event.toolCallId ?? paramsText(event.params);
}

function purge(t: number) {
  for (const [k, until] of approved) if (until <= t) approved.delete(k);
  for (const [k, v] of resolveAfterCall) if (v.until <= t) resolveAfterCall.delete(k);
}

export default definePluginEntry({
  id: "ia4-vault-approval",
  name: "IaC4 Tresor-Freigabe",
  description: "Fragt vor Zugriffen auf den Agenten-Tresor (Bitwarden) per Telegram nach; jede Suche fragt, eine Lese-Freigabe gilt 10 Minuten fuer einen Eintrag.",
  register(api) {
    api.on(
      "before_tool_call",
      (event, ctx) => {
        const text = paramsText(event.params);
        const raw = (event.params as Record<string, unknown> | undefined)?.command;
        const command = typeof raw === "string" ? raw : text;
        // Shell: Rohbefehl und JSON pruefen (im JSON wird ein Zeilenumbruch zu "\n", kein Wortrand vor "bw").
        const kind = (event as { toolKind?: unknown }).toolKind ?? (ctx as { toolKind?: unknown }).toolKind;
        const codeCell = kind === "code_mode_exec";
        const hit =
          event.toolName === "sessions_spawn"
            ? VAULT_TEXT.test(text)
            : codeCell
              ? VAULT_TEXT.test(text) || (VAULT.test(text) && CELL_ESCAPE.test(text))
              : VAULT.test(text) || (typeof raw === "string" && (VAULT.test(raw) || ENV_DUMP.test(raw)));
        if (!hit) {
          return;
        }
        // Fenster nur fuer Shell-Tools (Review Runde 2, Haertung).
        const shellTool = !codeCell && (event.toolName === "exec" || event.toolName === "bash");
        const entry = shellTool ? entryKey((event.params ?? {}) as Record<string, unknown>) : undefined;
        // Suche fragt jedes Mal (Owner-Entscheid "Suche fragt", 2026-10-11), ohne Fenster.
        const search = entry?.kind === "search";
        const key = search ? undefined : entry?.key;
        const expands = entry?.kind === "get-item";
        const t = now();
        purge(t);
        const until = key ? approved.get(key) ?? 0 : 0;
        if (key && until > t) {
          // Fenster laeuft ab wie freigegeben; Erweiterung erbt dieses Ende (kein Gleiten).
          if (expands) resolveAfterCall.set(callKey(event), { until });
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
        const scope = key
          ? "Gilt 10 Min. nur fuer diesen Eintrag."
          : search
            ? "Suche (zeigt nur Namen und IDs), gilt nur fuer diesen Aufruf."
            : "Gilt nur fuer diesen Aufruf.";
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
                const end = now() + WINDOW_MS;
                approved.set(key, end);
                if (expands) resolveAfterCall.set(callKey(event), { until: end });
              }
            },
          },
        };
      },
      { priority: 100 },
    );
    api.on("after_tool_call", (event) => {
      const k = callKey(event);
      const pendingExpand = resolveAfterCall.get(k);
      resolveAfterCall.delete(k);
      if (!pendingExpand || event.error || pendingExpand.until <= now()) return;
      for (const entry of entriesFromResult(event.result)) {
        if ((approved.get(entry) ?? 0) < pendingExpand.until) approved.set(entry, pendingExpand.until);
      }
    });
  },
});
