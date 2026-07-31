# ADR-023: Ollama-Embedding-Modell (nomic-embed-text vs. Alternativen)

- **Status:** Vorgeschlagen (Proposed)
- **Datum:** 2026-07-31
- **Kontext:** Ollama wird erster Service (Harald-Entscheidung 2026-07-31). IaC3 (RFC 0016): `nomic-embed-text` (768 Dimensionen, ~274 MB) für ZooCode/Roo-Code-Indexierung. 2026 existieren stärkere lokale Embedding-Modelle (bge-m3, mxbai-embed-large, qwen3-embedding-Familie).
- **Abgrenzung zum 3072d-Bestand (kein Supersede):** `docs/arc42/09` ADR-011 „Gemini-Embedding-001 (3072d, Cosine)" + Migrationsplan Phase 3 (Qdrant-Collection 3072d/Cosine) bleiben **unverändert gültig** – sie betreffen das OpenClaw-Memory-Backend (Cloud-Embedding, Qdrant). Diese ADR betrifft ausschließlich das **lokale Ollama-Embedding für ZooCode/Roo-Code-Codebase-Indexing** (anderer Zweck, andere Dimension). Die Dimensionen sind pro Zweck getrennt konfiguriert; ein Dimensionswechsel erzwingt jeweils Re-Index der betroffenen Daten.

## Entscheidungsfrage
Welches Embedding-Modell lädt Ollama initial?

## Optionen

### A: `nomic-embed-text` (IaC3-Muster) — EMPFEHLUNG
- **Fachliche Auswirkungen:** 274 MB, 768d, CPU-tauglich, schnell ladend (KEEP_ALIVE-kompatibel); bewährte Kompatibilität mit ZooCode/Roo-Code (RFC 0034-Konfiguration nutzt 768d); geringster Ressourcen-Fußabdruck auf kleinem VPS. Qualität: solide, aber nicht State-of-the-Art (MTEB mittel).
- **Zukunft:** Modell-Wechsel ist über Variablen vorbereitet (Name + Dimension + Index-Konfiguration) → Upgrade-Pfad ohne Redesign; Re-Index beim Wechsel dokumentiert.

### B: `mxbai-embed-large` (1024d, ~1,2 GB)
- **Fachliche Auswirkungen:** Bessere Retrieval-Qualität (besonders englisch), aber: größere Dimensionen → mehr RAM/CPU pro Request; Dimensionswechsel erzwingt **Re-Index des ZooCode-Index**; auf kleinem VPS spürbarer Overhead.
- **Zukunft:** Guter Schritt, wenn Retrieval-Qualität zum Engpass wird – dann als bewusster Migrations-PR.

### C: `bge-m3` (multilingual, flexibel 1024d)
- **Fachliche Auswirkungen:** Stärkste Retrieval-Werte in Vergleichstests, multilingual, lange Kontexte; aber schwerer (~1,2 GB+), Dimensionen 1024 → gleicher Migrationsaufwand wie B; Vorteil erst bei mehrsprachigen Codebases/Dokumenten relevant.
- **Zukunft:** Kandidat für Phase „Qualität statt Ressourcen".

### D: `qwen3-embedding:0.6b` (neu 2026)
- **Fachliche Auswirkungen:** Starke neue Familie (laut 2026-Benchmark-Zusammenfassungen MTEB multilingual ~64 für 0.6b; Quelle morphllm.com zum Reviewzeitpunkt nicht verifizierbar → als Annahme [A] behandelt); aber sehr neu (Ökosystem-Kompatibilität mit ZooCode/Roo noch nicht breit belegt); Risiko von Kompatibilitätsproblemen in Roo-Code-Integration.
- **Zukunft:** Beobachten; sobald Roo-Code-Integration belegt, ernsthafter Kandidat.

## Evidenz
- 2026-Vergleiche: nomic-embed-text bleibt Standard-Default für CPU-only RAG (ollama.com/blog/embedding-models; localaimaster 2026); mxbai-embed-large/bge-m3 als Qualitäts-Upgrades (tigerdata-Vergleich, Stand Dez 2024); qwen3-embedding-Familie mit Top-Benchmarks (Quelle morphllm [A], nicht verifizierbar)
- Ollama-Blog/Model-Library: nomic-embed-text weit verbreitet, 768d, klein
- IaC3-Betrieb: nomic + Pre-Warm produktiv validiert (0,24s nach Warm-up)

## Empfehlung
**Option A** – initial `nomic-embed-text`. Begründung: bewährte Kompatibilität, CPU-VPS-tauglich, geringstes Risiko; Qualitäts-Upgrade (B/C/D) als dokumentierter Migrationspfad über Variablen, ausgelöst durch messbare Retrieval-Probleme. **Kein Einfluss auf Qdrant-Collection (3072d, ADR-011).**

## Worst-Case / Rollback
- **Worst-Case 1:** Modellwechsel auf 1024d-Modell ohne Plan → ZooCode-Index und Embeddings inkonsistent (Dimension-Mismatch), Suche liefert keine Treffer.
  - **Rollback:** alten Modell-Namen + Dimensionswert in `group_vars` wiederherstellen, Container-Recreate, Index neu aufbauen (Re-Index).
- **Worst-Case 2:** Pre-Warm/Pull schlägt fehl (Registry/Netz) → erster Embedding-Request langsam (15-30s) statt <1s; Zoo-Indexing-Timeout möglich.
  - **Rollback:** Playbook erneut ausführen (idempotent, `ollama pull` cached); Container `restart: unless-stopped` fährt selbst hoch.
- **Gegenmaßnahme:** Pre-Warm-Entrypoint (ADR-022-Kontext), BDD-Test „Embedding-Request < 2s nach Container-Start"; Dimensions-Konfiguration als SSoT in `group_vars` (Modell + Dimension gekoppelt).

## Konsequenzen
- Rollen-Variablen: `ollama_model: nomic-embed-text`, `ollama_model_dimensions: 768`
- Pre-Warm-Entrypoint zieht Modell aus Variable (nicht hartcodiert)
- Qdrant-Collection bleibt 3072d/Cosine (arc42/09 ADR-011) – keine Änderung am Memory-Backend
- ADR-Review-Kriterium: Upgrade erst bei belegtem Bedarf (Evidence-based Engineering)

## Referenzen
- <https://ollama.com/blog/embedding-models>
- <https://ollama.com/library/nomic-embed-text>
- https://www.tigerdata.com/blog/finding-the-best-open-source-embedding-model-for-rag (Stand Dez 2024)
- https://localaimaster.com/blog/best-ollama-models (2026)
