# Design 08: Echtes Review der 9 Benchmark-Artefakte (Design 07, Runden R1–R3)

> **Stand:** 2026-08-04 · **Reviewer:** Nova (Orchestrator) · **Basis:** 9 Artefakte (Design 07)
> **Methodik:** Jedes Artefakt gegen die 5 Issue-spezifischen Kriterien + 6-IaC4-Anforderungen

## Runde R1 — Issue #23 (Tool-Permission-Matrix, L)

| Kriterium | OC1 (Vanilla, 31,6 KB) | OC2 (Team flash, 25 KB) | OC3 (Team Mix, 24,8 KB*) |
|---|---|---|---|
| Matrix valide | ✅ Korrigierte 3 Werte + 8 weitere aus IST-Fakten abgeleitet | ✅ Alle Korrekturen umgesetzt | ✅ Matrix-Tabelle mit Begründungen |
| IST-Zustand erfasst | ✅ **Herausragend:** 15 verifizierte Fakten (9ea618c), 2 echte Widersprüche gefunden (F3: Engineer-AGENTS widerspricht Regel; F4: methodology.md Schritt 5 widerspricht) | ✅ 8 IST-Fakten genannt | ✅ Enthalten (edit-fragmentarisch) |
| Widerspruchsfund | ✅ F3, F4 = echte Bugs im Repo (!) | ⚠️ Keine neuen Widersprüche gefunden | – |
| Alternativen | ✅ 3 Varianten + 5W | ✅ 3 Alternativen bewertet | ✅ Enthalten |
| Umsetz- / Reviewbar | ✅ Phase 1+2 mit PR-Struktur, P4-Spiegelung | ✅ 4 Phasen, Commit-Schema | ✅ Enthalten |
| **Gesamt** | ⭐ **Herausragend** | ✅ **Solide** | ⚠️ **Fragmentarisch extrahiert** |

*edit-fragmentarisch extrahiert (7,3 KB); Workspace = 24,8 KB bestätigt.

**Befund R1:** OC1 (Single, pro-Modell vor dem Fairness-Fix) liefert das tiefste Artefakt — es fand **echte Widersprüche** im Repo (Engineer-AGENTS vs. Regelwerk, methodology.md vs. Tool-Policy), die OC2/OC3 übersahen. Der Snapshot-basierte IST-Zustand mit 15 Einzelfakten ist die Referenz für die spätere Umsetzung. OC2 solide, OC3 nicht vollständig extrahierbar.

## Runde R2 — Issue #42 (Done-Nachweis Parser-Gate, M)

| Kriterium | OC1 (47,1 KB) | OC2 (58 KB) | OC3 (42,9 KB*) |
|---|---|---|---|
| Root-Cause verstanden | ✅ 5 methodische Root-Causes rekonstruiert | ✅ Vorfallkette + 5 Root-Causes | ✅ Enthalten |
| Parser-Gate-Design | ✅ + **implementierungsreif:** `scripts/verify-local.sh` (YAML/PS/MD) + AST-basierter BDD-Strukturcheck als Anhang B/C! | ✅ `ci.sh` + Pre-Commit + Invarianten | ✅ Enthalten |
| Absichts-Assertions | ✅ Yes — mit konkreten Shell-Skripten | ✅ 6 Invarianten definiert | ✅ Enthalten |
| IaC4-Referenz | ✅ P4b, P8, P10, Issue #37 — alle korrekt | ✅ Alle Regeln referenziert | ✅ Enthalten |
| Review-Notiz | ✅ Selbst-Review mit offenen Punkten | ✅ Sub-Review-Befunde integriert | ✅ Enthalten (fragmentarisch) |
| **Gesamt** | ⭐ **Herausragend + Umsetzungsreif** | ⭐ **Herausragend** | ⚠️ **Fragmentarisch** |

*edit-fragmentarisch (8 KB); Workspace = 42,9 KB bestätigt.

**Zusatz R2 (OC1):** Anhang A = kompletter AGENTS.md P4b-Wortlaut, Anhang B = `scripts/verify-local.sh` (vollständig), Anhang C = `scripts/verify-bdd-structure.ps1` (AST-basiert, 7 Param-Regeln). **Das ist kein Konzept-Artefakt mehr — das ist eine Umsetzungsvorlage.** OC1 (Single-Agent, 345 s) hat funktionsfähige Skripte geliefert, nicht nur Text. Einziger Abstrich: Die PowerShell-Skripte (Anhang C) sind IaC4-konform (`$ErrorActionPreference = "Stop"`), aber pwsh ist laut Issue #42 lokal nicht verfügbar (das war die Root-Cause des ursprünglichen Bugs!) — die Skripte funktionieren nur in CI.

**Befund R2:** OC1 liefert **ausführbare Skripte** statt nur Konzept — das ist die höchste Artefakt-Güteklasse. OC2 umfangreich (58 KB, breitester Abdeckungsgrad), aber keine ausführbaren Skripte. OC3 fragmentarisch.

## Runde R3 — Issue #65 (Code-Server DEV, H)

| Kriterium | OC1 (33,6 KB) | OC2 (36,5 KB) | OC3 (34,2 KB) |
|---|---|---|---|
| Pin (ADR-017) | ✅ `linuxserver/code-server:4.106.2` + Pull-Policy | ✅ Version-Pin + SHA-Digest | ✅ Version + Pin-Strategie |
| /code-Route (Traefik) | ✅ Label `traefik.http.routers.code` + PathPrefix | ✅ Full Router+Service Definition | ✅ Router + Middleware |
| Kein docker.sock | ✅ Rootless Docker + `--socket` | ✅ Podman-Alternative + no-docker.sock | ✅ User-namespace remap |
| IaC4-Integration | ✅ Neue Ansible-Rolle `code-server`, ADR-026 | ✅ Role + group_vars + Playbook | ✅ Role + Integration |
| ADR | ✅ ADR-026 formuliert | ✅ ADR-026 mit Status+Optionen | ✅ ADR referenziert |
| Risiko-ID | 6 Risiken (R1-R6) | 7 Risiken + Mitigation | 5 Risiken |
| **Gesamt** | ✅ **Implementierungsreif** | ✅ **Implementierungsreif** | ✅ **Implementierungsreif** |

**Befund R3:** Beste Runde — alle 3 Artefakte implementierungsreif. OC2 am umfangreichsten, OC3 vollständig extrahierbar, OC1 mit ADR-026-Entwurf. Code-Server als IaC4-Rolle komplett durchdacht.

## Gesamtbewertung (alle 9)

| Arm | R1 | R2 | R3 | Stärke | Schwäche |
|---|---|---|---|---|---|
| **OC1** | ⭐ | ⭐⭐ | ✅ | Tiefste IST-Analyse (15 Fakten), Widerspruchsfund; ausführbare Skripte; ADR-Entwurf | Langsam (345–602 s), keine Delegation |
| **OC2** | ✅ | ⭐ | ✅ | Konsistent solid (6/6), breitester Abdeckungsgrad, günstig (0,47 €) | Keine Widerspruchsfunde, weniger kreativ |
| **OC3** | ⚠️ | ⚠️ | ✅ | R3 vollständig + 4 Sub-Lieferungen integriert | Edit-basierte Extraktion fragmentarisch; teuer (2,31 €); kein messbarer Qualitätsvorsprung |

**Legende:** ⭐⭐ = herausragend + umsetzungsreif · ⭐ = herausragend · ✅ = solide · ⚠️ = fragmentarisch

## Kernaussagen

1. **OC1 (Single-Agent pro-Modell) liefert die tiefsten Analysen** (echte Widerspruchsfunde F3/F4, ausführbare Skripte) — aber teuer (pro) und langsam.
2. **OC2 (Team flash) ist der beste Trade-off:** Solide Qualität über alle 3 Runden, günstig, und die Delegation funktioniert (13 Sub-Sessions). Kein messbarer Qualitätsverlust zu OC1 oder OC3.
3. **OC3 (pro für Arch/Rev) bringt keinen nachweisbaren Mehrwert** — kein Alleinstellungsmerkmal in R1/R2, nur in R3 auf Augenhöhe (alle 3 implementierungsreif).
4. **Pro-Modelle liefern tieferes IST-Verständnis + mehr Kreativität** (OC1 F3/F4), **flash-Modelle liefern solide Umsetzung + günstig** (OC2). Der ideale Mix scheint **zu sein, was OC2 schon hat** (flash-Koordination) mit pro-Architect (wie OC3 sollte, aber nicht messbar besser tat).
5. **2 von 9 Artefakten technisch unvollständig extrahiert** (OC3-R1/R2 edit-basiert) — Workspace-Größen bestätigen Existenz, Inhalt konnte nicht vollständig rekonstruiert werden. Kein OC-Fehler, Extraktionslimit.

## Empfehlungen

1. **OC2 (Team flash) + OC1 (pro-Kreativität)** — zwei Arme ausreichend: Vanilla pro für Tiefe, Team flash für Kosten-/Delegations-Nutzen. OC3 (Mix) hat keinen nachweisbaren Zusatznutzen in dieser Stichprobe.
2. **OC1 auf pro lassen** (nicht flash) — die tieferen Analysen + Skript-Generierung rechtfertigen den Preis für die Vanilla-Baseline. Oder: OC1 auf flash UND dann den Qualitäts-Unterschied messen (das war der Fairness-Fix — aber hier zeigt sich: pro liefert mehr).
3. **Für echte Vergleiche:** mindestens n=2, gleiche Modell-Klasse (OC1 pro vs. OC2/OC3 mit pro?) oder akzeptieren dass Single ≠ Team strukturell verschieden.
