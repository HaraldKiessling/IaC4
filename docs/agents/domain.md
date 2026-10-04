# Domain Docs

Wie die Engineering-Skills die Domänen-Dokumentation dieses Repos nutzen.

## Vor dem Erkunden lesen

- **`docs/arc42/12_glossar.md`**: Begriffstabelle (Deutsch, `Begriff | Bedeutung`)
- **`docs/arc42/09_architekturentscheidungen.md`** und **`docs/adr/ADR-NNN-*.md`**: Entscheidungen im betroffenen Bereich

Fehlt etwas, still weitermachen. `domain-modeling` legt Einträge lazy an, wenn Begriffe oder Entscheidungen geklärt sind.

## Dateistruktur (ein Kontext)

- Glossar: Zeile in `docs/arc42/12_glossar.md` (kein `GLOSSARY.md`/`GLOSSARY-MAP.md`)
- ADR: neues Detailblatt `docs/adr/ADR-NNN-<slug>.md` im bestehenden Format (Vorbild ADR-016), Nummer = höchste vorhandene + 1; zusätzlich Zeile in der Tabelle von `docs/arc42/09_architekturentscheidungen.md`

## Vokabular des Glossars nutzen

Begriffe aus dem Glossar verwenden (z. B. DEV/PROD, Phase 0–2c, deploy-user), keine Synonyme.

## ADR-Konflikte benennen

Widerspricht ein Vorschlag einer ADR, ausdrücklich nennen:

> _Widerspricht ADR-017 (Image-Pinning), aber neu bewerten, weil …_
