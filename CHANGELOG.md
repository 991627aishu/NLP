# Changelog

## v1-complete — 2026-10-30
Starting point: tag `v0-baseline` (project as received). Raw `Data/` files unchanged (SHA-256 in `docs/raw_data_hashes.sha256`).

### Phase 0 — audit
- `docs/AUDIT.md`: F1–F13 verified by running code; new findings F14–F27, including the critical **F15**
  (the chat pipeline never abstained on emergencies, dosage requests or unanswerable questions: 0/16).

### Phase 1 — foundations & safety
- Case-insensitive `Data/` paths (F8); version-stamped indices with backup + rebuild (F9); consistent `query_concept` keys (F10).
- Pre-retrieval **safety gate** in all modes (emergency, dosage/prescription, toxic ingestion, cure claims; nukta-normalised Hindi).
- Evidence gate (abstain when retrieved passages cover < 40 % of the question's content words).
- Feature flags, `.env`, pinned requirements, `xlrd` added (NAMASTE is a legacy `.xls`, F20), parquet failures logged (F21).
- One test line changed: `Path("data/evaluation/…")` → `DATA_EVAL / …` (same assertion; fixes Linux).

### Phase 2 — NLP backends
- IndicTrans2 backend (gated model, `HF_TOKEN`), SQLite cache, placeholder survival check + re-injection; rules kept as fallback.
- sentence-transformers dense backend with cached embeddings; TF-IDF kept (v1).
- HI/KN answers now lead with the cited evidence sentence (F3/F14); `CONCEPT_EXPLANATIONS` only as a labelled glossary note.
- Real output-side term protection for EN→HI/KN answer MT (F24). Optional evidence-only LLM writer with citation post-check.

### Phase 3–4 — knowledge graph v2 & herbs
- 2,973 WHO terms + 195 sections extracted by code with real pages; graph v2: 9,530 nodes, 72,343 edges, 99.9 % with source locators.
- Old v1 locators re-verified (0/28 held up; 4 relations re-grounded in WHO text, others marked unverified).
- P2 uses the graph for bounded query expansion and provenance-carrying facts.
- Herb directory/detail (IMPPAT + Ayurvedic Pharmacopoeia) and lifestyle topics from the corpus.

### Phase 5–6 — voice & API
- STT chain (browser → faster-whisper + ffmpeg) with context-gated term normalisation; TTS chain (edge-tts → gTTS → browser).
- FastAPI layer: ask, voice/ask, tts, symptoms, graph, herbs, lifestyle, research, health, about, feedback.

### Phase 7 — website
- Single-page site served by FastAPI (chat + voice, graph explorer, symptoms, herbs & lifestyle, research lab, about), EN/HI/KN UI, light/dark, accessibility; Playwright smoke tests.

### Phase 8 — evaluation & honesty
- `evaluator_v2`: gold-passage relevance, seed-level bootstrap, paired differences, 8 ablations/baselines, stage-wise error analysis.
- Go/No-Go probe v2 with real translator output (v1 outputs were hand-typed, F12).
- `docs/research_findings_v2.md` generated from JSON; `docs/PAPER_RECONCILIATION.md`; `docs/paper_suggested_edits.md`; human-evaluation kit.

### Phase 9 — release
- `run.ps1`/`run.sh`, README, user & developer guides, `docs/FEATURE_COMPLETENESS.md`, `docs/KNOWN_LIMITATIONS.md`.
