# Issue tracker: GitHub

Issues und Specs dieses Repos liegen als GitHub-Issues in `HaraldKiessling/IaC4`.
In Cloud-Sessions gibt es kein `gh`; es gelten die GitHub-MCP-Tools.

## Konventionen

- **Anlegen:** `issue_write` (vorher `search_issues`, um Duplikate zu vermeiden). Vorlagen aus `.github/ISSUE_TEMPLATE/` (Feature/Bug/Change) verwenden (P2).
- **Lesen:** `issue_read` (inklusive Kommentare)
- **Auflisten:** `list_issues` (Filter `state`, `labels`), gezielte Suche mit `search_issues`
- **Kommentieren:** `add_issue_comment`; Beiträge mit Rollen-Signatur und Attribution-Footer (siehe `AGENTS.md`)
- **Labels / Schließen:** `issue_write` (Labels setzen, Status schließen, immer mit `state_reason`)
- **Sub-Issues:** `sub_issue_write`

Issues im Chat als Link oder als `owner/repo#nummer` nennen, nie als nacktes `#123`.

## Pull Requests als Anfragequelle

**PRs als Anfragequelle: nein.**

## Wenn ein Skill sagt "publish to the issue tracker"

Ein GitHub-Issue anlegen.

## Wenn ein Skill sagt "fetch the relevant ticket"

`issue_read` mit der Issue-Nummer.

## Wayfinding (nur falls `/wayfinder` installiert wird)

Karte = ein Issue mit Label `wayfinder:map`, Kinder als Sub-Issues (`sub_issue_write`).
Blockierende Kanten als Zeile `Blocked by: #<n>` oben im Kind-Issue
(native Abhängigkeiten sind über die MCP-Tools nicht belegt).
