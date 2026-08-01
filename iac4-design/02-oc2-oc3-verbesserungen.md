# Design: Benchmark-Fairness für OC2 vs. OC3 (Auftragsbezug)

- **Status:** Vorgeschlagen (Review ausstehend) — Fokus-Überarbeitung nach Harald (2026-08-01 18:29/18:32)
- **Datum:** 2026-08-01
- **Autor:** ✨ Nova (Orchestrator)
- **Bezug:** Design 01-oc2-oc3-benchmark (freigegeben), Harald-Entscheidungen F2–F5, PR #64 (OC3-Vervollständigung)
- **Auftrag:** Vergleich zweier Agentenmodelle (OC2 Kontrollgruppe vs. OC3 Best-Practice) — **beide müssen die gleiche Chance haben, vervollständigt zu werden** (Fairness-Anforderung an den Orchestrator).

---

## 1. Scope-Disziplin (Harald 2026-08-01)

Dieses Dokument enthält **nur** Änderungen mit direktem Bezug zum Benchmark-Auftrag.
Betriebsverbesserungen (auch mit harter Evidenz) sind **bewusst ausgegliedert** in Issue #68
— sie sind benchmark-neutral, aber kein Modell-Thema.

**Evidenz-Klassen (harte Evidenz-Pflicht):**
- **A** Repo-Fakt (im IaC4-Repo verifizierbar) · **B** freigegebene Entscheidung (Design 01, Harald) · **C** Vendor-Doku/Mechanik · **D** IaC3-Analogie ohne IaC4-Beleg → fliegt raus

---

## 2. Benchmark-relevante Defizite (IST gegen IaC4-main, geprüft 2026-08-01)

| # | Defizit | Beleg (IaC4) | Evidenz | Verbesserung |
|---|---|---|---|---|
| D12 | Ressourcen-Interferenz: 3 Instanzen parallel auf 6 vCore/8 GB verrauschen die Zykluszeit-/Qualitäts-Metriken des OC2/OC3-Vergleichs — ohne Messung ist nicht unterscheidbar, ob ein Ergebnis „besser" oder nur „mehr CPU" war | Design 01 Kap. 6.1/6.3 (Architect MINOR-4, Review R1) | **B** (deine Entscheidung F4) + A (BDD-Log existiert, Erweiterung nötig) | **V5: CPU/RAM-Kovariate** |

---

## 3. Verbesserung

### V5 – CPU/RAM-Kovariate im BDD-Log (Benchmark-Fairness)
- **Problem:** Ohne Ressourcen-Messung ist der OC2/OC3-Vergleich nicht fair interpretierbar: Ein Assistent, der zufällig mehr CPU hatte, produziert bessere Zykluszeiten — das Ergebnis wäre Artefakt statt Modell-Eigenschaft.
- **Lösung:** BDD-Lauf (O1-Block, `openclaw.bdd.ps1`) um `docker stats --no-stream` je Instanz erweitern → CPU/RAM-Werte landen im Log als Kovariate für die Benchmark-Auswertung (Design 01 Kap. 6.3, Metrik „Ressourcen").
- **Beleg:** Design 01 Kap. 6.1 („Konstant gehalten: …"), 6.3 (Metrik-Tabelle), Harald-Entscheidung F4 (2026-08-01: „alle drei parallel, Auslastung mitschreiben").
- **Auswirkung:** Benchmark-Ergebnisse interpretierbar; Ressourcen-Engpass sichtbar statt stiller Verfälschung. Aufwand: klein (BDD-Erweiterung, `04-bdd-tests.yml` — Overlap mit PR #64 → nach #64-Merge).
- **Risiko:** `docker stats`-Ausgabeformat stabil; kein Funktionsrisiko (additiv, `changed_when: false`-Analogie).

---

## 4. Ausgegliedert (Issue #68, Betrieb — NICHT Benchmark-Scope)

Folgende Punkte haben harte Evidenz (A/B/C), aber **keinen** Bezug zum Agentenvergleich.
Sie sind in [Issue #68](https://github.com/HaraldKiessling/IaC4/issues/68) als Betriebs-Backlog dokumentiert
und werden **vor T1-Start nur dann** umgesetzt, wenn sie beide Instanzen symmetrisch betreffen (Fairness-Regel):

| Punkt | Evidenz | Kurzbegründung |
|---|---|---|
| V1 Selbstheilung bei Hänger | A+C (kein healthcheck im IaC4-Compose; Docker-Restart nur bei Exit) | Betriebs-Härtung, optional |
| V2 Token-Divergenz ENV vs. SSoT | A+C (Duplikation im IaC4-Template verifiziert; ENV gewinnt laut Doku) | Config-Konsistenz |
| V3 Teardown-Task | A+B (kein Teardown in Rolle; Design 01 fordert Rollback-Pfad) | Operations/Rollback |

**Gestrichen (Evidenz D):** V4 (BDD-Provider-Smoke — nur IaC3-Analogie, IaC4 hat Assert+Validator), V6 (Backup — theoretisches Risiko ohne Beleg).

---

## 5. Empfehlung

1. **PR #64 mergen** (OC3-Vervollständigung — der eigentliche Auftrags-Baustein)
2. **V5 als kleines PR** nach #64-Merge umsetzen (benchmark-kritisch, vor T1-Start)
3. **Issue #68 (V1–V3)** unabhängig vom Benchmark behandeln; Umsetzung nur symmetrisch für OC2+OC3

---

## 6. Offene Frage

1. V5-Umfang: nur `docker stats`-Log im BDD, oder zusätzlich pro Task ein Snapshot (dann je T1-Lauf ein Wertepaar)? — Empfehlung: pro BDD-Lauf reicht für die Kovariate.

---

## 7. Referenzen & Evidenz

- Design 01-oc2-oc3-benchmark (Kap. 6.1/6.3, freigegeben) — Entscheidungen F2–F5
- PR #64 (OC3-Umsetzung, HEAD `dac8bcd`) — Overlap-Analyse V5 ↔ `04-bdd-tests.yml`
- PR #56/#64-Reviews (Befund-Historie; IaC3-Vorfälle nur als Kontext, kein Beleg — Evidenz-Klassen-Regel)
- Docker-Doku (restart/healthcheck-Mechanik, für V1-Kontext in Issue #68)
