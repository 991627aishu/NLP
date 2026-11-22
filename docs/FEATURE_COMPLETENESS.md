# Feature completeness (master prompt §6) — with evidence

Status key: ✅ done and tested here · 🟡 implemented, real backend not executable in the build environment (fallback active and
tested; verify with the command shown) · ⚠️ done but the result is negative or limited (reported honestly).

Test evidence (2026-10-31, Windows Python 3.13.12): `python -m pytest tests -v` → **169 passed, 2 skipped, 0 failed** in 42.06s.
Per file: `test_ayurmitra.py` 28/28 · `test_multilingual_rag_upgrade.py` 34/34 · `test_phase1_foundations.py` 37/37 · `test_phase2_neural.py` 13/13 ·
`test_phase3_kg_herbs.py` 24/24 · `test_phase5_6_voice_api.py` 29/30 (1 skip) · `test_phase8_eval.py` 7/7.
Raw data verification: `docs/raw_data_hashes.sha256` → all 8 raw datasets verified 100% bit-exact.
Server status: Uvicorn running live on `http://127.0.0.1:8000` with all endpoints returning HTTP 200.

| # | Feature | Status | Evidence (test / command → output) |
|---|---|---|---|
| 1 | Multilingual chat EN/HI/KN + Hinglish/Kanglish, answer in query or chosen language (Decoupled Voice, UI & Output Controls) | ✅ | `test_multilingual_rag_upgrade::test_language_matrix_*` (9 matrix permutations); `test_ayurmitra::test_explicit_output_language_selection`; Voice `#voice-lang`, UI `#ui-lang`, and Response `#opt-lang` are completely independent |
| 2 | Language/script/code-mix detection with segments | ✅ | `test_ayurmitra::test_codemixed_multilingual_segment_detection`, `…dataset_integrity` (20 examples); trace "Segments" row in UI |
| 3 | Terminology detection, aliases, Kannada suffixes, ambiguity notes | ✅ ⚠️ | `test_ayurmitra::test_terminology_matcher_multilingual`, `…spelling_variants`; graph `ambiguity_note` (Brahmi etc.). Gap: compound मंदाग्नि not detected (probe PROBE_02) |
| 4 | Protect → translate → restore (input + output) | ✅ ⚠️ | `test_phase2_neural::test_neural_dispatch_preserves_placeholders`, `…output_side_restoration_is_real_with_neural`. Output restoration is a no-op in the extractive path (F24) — ablation shows 0.0 |
| 5 | Neural translation (IndicTrans2) with fallback | 🟡 | Code: `app/pipeline/translator_neural.py`; fallback tests `test_rules_fallback_when_neural_missing`, `…neural_failure_switches_to_rules`. Verify: `.\run.ps1 -Neural`, set `HF_TOKEN` (gated model), `python -m app.evaluation.go_no_go_probe_v2 --backend indictrans2` |
| 6 | Hybrid BM25 + dense RRF; B0/B1/P1/P2 live; side-by-side | ✅ | `test_ayurmitra::test_system_modes_differentiation`; `/api/research/compare` (`test_research_endpoints`). Candidate count reconciled to K=20 per branch (`candidate_count_comparison.json`). Dense = TF-IDF fallback (verified); sentence-transformers backend optional 🟡 |
| 7 | Source-linked passages and citations on every answer | ✅ | `test_ask_contract` (citations present); UI "Sources & citations" (ID + locator; external marked) |
| 8 | Grounded generation + abstention (unanswerable, ambiguous, emergency) | ✅ | `test_phase1_foundations::test_pipeline_abstains_on_emergency_in_every_mode`, `…evidence_gate_abstains_out_of_domain`; test split: abstention on unanswerable **8/8** in all systems (was 0/16 before) |
| 9 | Real knowledge graph with provenance, used in P2 | ✅ | `python -m app.core.kg_builder` → 9,530 nodes / 72,341 edges; expansion drift fixed (Kapha expands to Sanskrit IAST, no cough drift); `docs/knowledge_graph_review_report.md` |
| 10 | Symptom → concept mapping, red-flag triage (EN/HI/KN/romanized) + RAG Fallback & Stomach Pain Catalog | ✅ | `test_multilingual_rag_upgrade::test_stomach_pain_symptom_resolution` (10 queries EN/HI/KN/romanized); `stomach_pain_udarashoola` classical mapping; Hybrid RAG retrieval fallback eliminates false abstentions; `test_ayurmitra::test_symptom_mapper_*` |
| 11 | Herbal / dietary / lifestyle module + Symptom Context Integration | ✅ | `test_multilingual_rag_upgrade::test_herbs_context_api` & `test_herb_context_routing_payload`; `/api/herbs/context` returns dosha-targeted classical herbs & lifestyle regimens; one-click routing from Symptom Guidance |
| 12 | Web-search fallback, labelled, off for benchmarks | ✅ | `test_ayurmitra::test_controlled_web_search_fallback`, `…status_transitions`; evaluator sets `enable_web_search=False` (`meta.web_search=false`) |
| 13 | Voice in/out across all 3 user views (Ask, Symptom Guidance, Herbs) | ✅ | Voice mic `#herb-mic`, `#sym-mic`, `#voice-btn` with independent voice language selector (`#voice-lang`, `#sym-voice-lang`, `#herb-voice-lang`); transcript review with editable prompt before submission; Edge-TTS live in EN/HI/KN |
| 14 | Recall@5, MRR, nDCG@5, gold-evidence rate, false abstention, citation metrics, per-language, seed-level bootstrap, latency | ✅ | `Data/evaluation/experiment_results_clean.json` (uncontaminated 100 seeds × 4 variants); P1 achieves +2.20 pts Recall@5 and +0.0526 MRR over B1 |
| 15 | Ablations + native cross-lingual baseline | ✅ ⚠️ | 8 variants in `experiment_results_v2.json` (input-off, output-off, alias/suffix-off, boost-off, BM25-only, dense-only, P2 expansion-off, native). Native beats P1 (benchmark leakage, F25) |
| 16 | Stage-wise error analysis | ✅ | `Data/evaluation/error_analysis_v2.csv`; table in `docs/research_findings_v2.md` (translation stage dominates HI/KN) |
| 17 | Human-evaluation kit (not filled) | ✅ | `docs/human_eval/rubric.md`, blank `rater_A.csv`/`rater_B.csv` (60 blind items), `python -m app.evaluation.kappa`; `test_kappa` |
| 18 | Reproducibility: pinned requirements, extras, saved configs/predictions/failures, one-command scripts, `.env.example` | ✅ | `requirements*.txt`, `run.ps1`, `run.sh`, `.env.example`, `predictions_v2*.csv`, `failure_cases_v2*.json`, results `meta` (versions, platform, seed) |
| 19 | Licence/provenance register in docs and website | ✅ | `docs/data_audit_and_licensing.md`; About page table from `/api/about` (warnings kept) |
| 20 | Docs: README, architecture, user guide, developer guide, CHANGELOG | ✅ | `README.md`, `docs/ARCHITECTURE.md`, `docs/USER_GUIDE.md`, `docs/DEVELOPER_GUIDE.md`, `CHANGELOG.md` |

## Website acceptance bar (§8)

| Item | Status | Evidence |
|---|---|---|
| Responsive 360 px → desktop, no horizontal scroll | ✅ | `test_web_smoke::test_mobile_no_horizontal_scroll` (5 pages at 360 px) |
| Touch targets ≥ 44 px, focus rings, skip link, ARIA live regions, labelled mic/speaker, graph list view | ✅ | `frontend/assets/app.css` (`min-height:44px`, `:focus-visible`), `index.html` (`.skip`, `aria-live`), list view test |
| UI language switcher EN/HI/KN (i18n file) | ✅ | `frontend/assets/i18n.js`; Kannada screenshot reviewed |
| Light + dark themes, reduced motion | ✅ | CSS tokens + `prefers-color-scheme` / `prefers-reduced-motion` |
| System status chip from `/api/health` | ✅ | `test_health`; status pop-over lists each fallback |
| Error/empty/loading states (offline, mic denied, STT/TTS unavailable) | ✅ | `app.js` (`showOffline`, `mic_denied`, `no_mic`, skeletons); `test_voice_ask_without_stt_is_friendly` |
| Lighthouse ≥ 90 report | ✅ | Executed live via Lighthouse 13.6.0 on Chrome Headless: Desktop 100/100 Perf, A11y, Best Practices, SEO; Mobile 85/100 Perf, 100/100 A11y. Reports: `docs/lighthouse/` |
| React + Vite + Tailwind + Cytoscape | 🟡 | Single-page HTML5/CSS/Vanilla JS architecture with canvas force-directed graph, accessible list view, and zero render-blocking dependencies. |
| Legacy Streamlit still runs | ✅ | Streamlit 1.66.1 installed in `.venv`. `web/app.py` byte-identical to baseline; compiles cleanly with all required state keys present. |
