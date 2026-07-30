# IaC4 – Plan-Management

> **Problem:** Große Themen (wie IaC3→IaC4-Migration) haben viele Unterpunkte.
> Zu viele Issues → Chaos. Keine Issues → Dinge gehen verloren.
>
> **Lösung:** Ein Plan-Dokument pro großes Thema. Keine Issue-Flut.

## Struktur

```
docs/plans/
├── README.md               ← Diese Datei
├── iac4-migration.md       ← Haupt-Migration (alle Phasen)
├── feature-xxx.md          ← Weitere große Themen
└── archive/                ← Abgeschlossene Pläne
```

## Kernidee

| Statt | Machen wir |
|-------|-----------|
| 20 Issues für Migration | 1 Plan-Dokument mit 20 Checkboxen |
| "Erinnere mich später" | `- [ ]` im Plan, nicht als Issue |
| Issue zu wenn erledigt | Checkbox abhaken (bleibt sichtbar) |
| Alles als Issue | Max 5 Issues gleichzeitig aktiv |

## Regeln

1. **1 Plan = 1 Thema** – nicht vermischen
2. **Tasks als Checkboxen** – `- [ ]` im Markdown
3. **Max 5 aktive Issues** – nur für den aktuellen Schritt
4. **Erledigt = `- [x]`** – bleibt als Historie, wird nicht gelöscht
5. **Jeder Task < 30 Min** – sonst weiter zerlegen
6. **Rückstau** → nicht als Issue, sondern in arc42 K11

## Ablauf

```
1. Neues Thema → docs/plans/thema.md
2. In Phasen zerlegen (Phase 1, Phase 2, …)
3. Jede Phase in Tasks < 30 Min zerlegen
4. Task → Architect/Engineer/Reviewer → Done
5. Nächster Task
6. Phase fertig → Phase-Checkbox abhaken
7. Thema fertig → nach docs/plans/archive/
```

## Wann Issue, wann Plan?

| Situation | Mach ein |
|-----------|----------|
| Neues, großes Thema | 🗂️ **Plan-Dokument** |
| Task aus Plan umsetzen | ❌ **Kein Issue** (Task im Plan) |
| Entscheidung von Harald nötig | 📋 **Issue** (wird nach Entscheidung geschlossen) |
| Bug gefunden | 📋 **Bug-Issue** (Template 02-bug) |
| Feature-Wunsch, kein grosses Thema | 📋 **Feature-Issue** (Template 01-feature) |
