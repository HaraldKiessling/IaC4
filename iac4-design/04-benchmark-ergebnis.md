# Design 04 — T1-Benchmark-Ergebnis (OC1/OC2/OC3, Zwischenstand)

**Status:** Zwischenstand nach 15 T1-Läufen (45 Runs) am 2026-08-02 · Basis: Design 01 (01-oc2-oc3-benchmark.md), Design 02, Design 03 (03-benchmark-durchfuehrung.md)

## 1. Durchführung

- **Arme:** OC1 (Vanilla/Creator, `main`, flash), OC2 (Team-Ist, 4 Agents, flash-Orchestrator), OC3 (Best-Practice, 4 Agents, pro-Orchestrator, Modell-Invertierung)
- **Umfang:** Pilot (S1) + 12 automatisierte Loop-Läufe (t4–t15), Rotationen R4–R15, je Lauf 3 Instanzen = 45 Runs
- **Auswertungsquelle:** vollständige Session-Transkripte der 3 Instanzen via Gateway-RPC (`sessions.get`), nicht die überschriebenen Artefakt-Dateien (Design-03-Mechanik: Artefakte instanzfremd, Zuordnung nur im Task-Log)
- **Datenintegrität:** t10 wurde 2× gelaufen (Loop-Abbruch 04:14 + Resume 06:56); OC3-t10-alt aborted (0B, `benchmark-t1-81286dc2`); gewertet wurde der Resume-Lauf. 1 von 45 Runs aborted — Ursache Loop-Prozess-Abbruch, nicht Instanz-Defekt.

## 2. Ergebnisse

### 2.1 Qualität (Ground-Truth-Adjudikation, S1 = Hauptdefekt, S2 = Zweitdefekt)

| Instanz | S1-Treffer | S2-Treffer | Ø Antwort | Modell-Kosten (15 Läufe) |
|---|---|---|---|---|
| OC1 (Vanilla) | 15/15 (100%) | 6/15 (40%) | 1.4 kB | ~€0.03 |
| OC2 (Team-Ist) | 15/15 (100%) | 10/15 (67%) | 2.0 kB | ~€0.06–0.08 |
| OC3 (Best-Practice) | 15/15 (100%) | 8/15 (53%) | 1.5 kB | ~€0.10–0.11 |

**Muster:**
1. S1 (Blocker/Major im Diff) finden alle 3 Arme immer — keine Differenz auf Hauptdefekt-Ebene.
2. S2 ist der Differenzierer, abhängig von der Defekt-Klasse: **Minor-S2 übersehen alle 3 Arme komplett (0/5)**, Major-S2 findet OC2 immer (4/4), OC3 die Hälfte, OC1 nie.
3. OC1 scheitert ausschließlich an Kontext-Defekten (Defekt in Zusatzinfo „nachfolgende Tasks, nicht gezeigt" statt in Diff-Zeilen) — alle 4 verpassten Major-S2 sind dieser Klasse.
4. OC3 (pro-Orchestrator, 4× Kosten) schlägt OC1 nur bei t6 — der pro-Vorteil zeigt sich nicht in S2-Findung, nur in Antwort-Tiefe.

### 2.2 Kosten

- Gesamt bisher: ~€0.20 für 45 Runs (DeepSeek V4 Promo, ohne Cache; mit KV-Cache eher 30–50 % niedriger)
- OC3 ist trotz weniger Tokens der teuerste Arm (pro-Orchestrator), OC2 der Token-intensivste (Team-Delegation erzeugt 64.7k Reasoning-Tokens), OC1 am günstigsten

### 2.3 Latenz (Ø je Lauf)

| Instanz | Ø Dauer | Thinking-Zeichen | Reasoning-Tokens |
|---|---|---|---|
| OC1 | 25s | 78k | 15.8k |
| OC2 | 51s | 307k | 64.7k |
| OC3 | 38s | 109k | 25.5k |

## 3. Kernbefund: Sub-Agent-Nutzung = 0

**Analyse aller 46 Transkripte auf Tool-Calls:**

| Instanz | Tool-Calls | davon Spawns | read | exec | memory_search |
|---|---|---|---|---|---|
| OC1 | 0 | 0 | 0 | 0 | 0 |
| OC2 | 9 | **0** | 2 | 6 | 1 |
| OC3 | 25 | **0** | 12 | 12 | 1 |

- **Kein einziger `sessions_spawn`/Delegations-Call** in 46 Sessions — weder OC2 (`delegationMode: suggest`) noch OC3 (`prefer`).
- Tool-Calls sind ausschließlich Doku-Recherche (`read`/`exec` in `/app/docs/`, `memory_search`).
- Delegations-Grübeln im Thinking vorhanden (OC2 4×, OC3 7×), aber nie ausgeführt.
- **Interpretation:** Die Arme verhalten sich faktisch als „Single-Agent mit unterschiedlichen Modellen + Tool-Freigaben". Die Qualitäts-Differenz kommt aus Tool-Nutzung + Denk-Tiefe, nicht aus Team-Delegation. Der konfigurierte Team-Vorteil wurde im T1 nie aktiviert.

## 4. Root-Cause-Analyse OC2-Latenz

1. **Primär — Reasoning-Explosion:** OC2 erzeugt 2.5× mehr Reasoning-Tokens als OC3 (64.7k vs 25.5k). Reasoning wird sequenziell generiert → direkter Latenz-Treiber. Der flash-Orchestrator kompensiert Unsicherheit mit langen Selbst-Verifikationsschleifen (22k-Zeichen-Blöcke, 17 Selbst-Rückfragen).
2. **Sekundär — BOOTSTRAP.md-Ablenkung (Setup-Artefakt):** OC2-Workspace enthält BOOTSTRAP.md; der Agent verliert in 5 Turns Zeit mit „soll ich dem Bootstrap-Flow folgen?" — task-fremd, bei OC1/OC3 nicht vorhanden.
3. **Tertiär — Ineffiziente Doku-Verifikation:** OC2 liest in Chunks (read mit offset) und wiederholt greps; OC3 recherchiert gezielter.
4. **Gegenprobe:** Token-Rate bei allen ~6–7.5k tok/s — OC2 ist nicht langsamer pro Token, er erzeugt ~60% mehr Tokens (v.a. Reasoning).

**Fazit:** OC2-Latenz = Preis für Denk-Tiefe (beste S2-Quote) + BOOTSTRAP-Ablenkung. Der Team-Modus hat weder geholfen (0 Spawns) noch geschadet.

## 5. Folge-Themen (für Harald anzulegen, kein Fixes/Closes)

- **T1: Delegation-Aktivierung prüfen** — warum spawnen OC2/OC3 bei Review-Tasks nie Sub-Agents? (suggest/prefer-Konfiguration wirkt nicht wie erwartet; ggf. Task-Design anpassen, damit T3/T4-Tasks Delegation provozieren, oder Erwartung korrigieren)
- **T2: BOOTSTRAP.md-Cleanup in Instanz-Workspaces** — frische Workspaces enthalten BOOTSTRAP.md, das Benchmark-Sessions ablenkt; für Benchmark-Instanzen entfernen oder deaktivieren
- **T3: Artefakt-Ablage Design-03-Fix** — instanzfremde Artefakt-Dateien werden überschrieben (nur letzter Schreiber sichtbar); künftig pro Instanz getrennte Dateien mit Blind-Zuordnung nur im Task-Log
- **T4: Voll-Adjudikation t5–t15 gegen Design-01-Kriterien** — Adjudikation hier automatisiert (Keyword-basiert); Harald-Adjudikation 100% T1 laut Design 03 steht aus

## 6. Referenzen

- Design 01: `01-oc2-oc3-benchmark.md` (gemergt, refs PR #64/#70/#72)
- Design 02: `02-oc2-oc3-verbesserungen.md` (refs Issue #68)
- Design 03: `03-benchmark-durchfuehrung.md` (PR #73)
- ADR-025 (Multi-Instanz), ADR-016 (Least-Privilege deploy-user), ADR-017 (Pinning)
- Lokale Artefakte: `benchmark/out/` (Task-Logs, Ground Truths, qualitaetsauswertung.md) — nicht im Repo
