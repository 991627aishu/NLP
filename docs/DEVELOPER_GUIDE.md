# Developer guide

## Layout
See `docs/ARCHITECTURE.md`. Rules kept throughout: raw files in `Data/` are never written (check with
`sha256sum -c docs/raw_data_hashes.sha256`); derived files go to `Data/processed/` and `Data/evaluation/`;
old behaviour stays available behind flags; experiments always use the extractive generator with web search off.

## Commands
| Task | Command |
|---|---|
| Tests (all) | `python -m pytest tests -q` |
| Original 26 tests | `python -m pytest tests/test_ayurmitra.py -q` |
| Website smoke tests (Playwright) | `python -m pytest tests/test_web_smoke.py -q` (needs `pip install playwright` + `playwright install chromium`) |
| Rebuild WHO term table | `python -m app.core.who_extract` |
| Rebuild knowledge graph v2 | `python -m app.core.kg_builder` (≈10 s) → `knowledge_graph_v2.pkl`, `kg_v2.json`, `kg_build_report.md` |
| Rebuild corpus (original) | `python -m app.core.terminology && python -m app.core.corpus_builder` |
| Evaluation (dev, then test once) | `python -m app.evaluation.evaluator_v2 --split dev` · `--split test` |
| Go/No-Go probe with real MT | `python -m app.evaluation.go_no_go_probe_v2 --backend indictrans2` |
| Regenerate the results report | `python -m app.evaluation.report_v2` → `docs/research_findings_v2.md` |
| Human-evaluation sheets | `python -m app.evaluation.human_eval_kit --n 60` · agreement: `python -m app.evaluation.kappa A.csv B.csv` |
| API only | `uvicorn api.main:app --port 8000` (OpenAPI at `/docs`) |

## Flags (`.env`, see `.env.example`)
`AYUR_TRANSLATOR_BACKEND`, `AYUR_DENSE_BACKEND`, `AYUR_GENERATOR_BACKEND`, `AYUR_KG_VERSION`, `AYUR_SAFETY_GATE`,
`AYUR_EVIDENCE_GATE`, `AYUR_EVIDENCE_MIN_COVERAGE`, `AYUR_STT_BACKEND`, `AYUR_WHISPER_MODEL`, `AYUR_TTS_BACKEND`,
`ANTHROPIC_API_KEY`, `HF_TOKEN`. `auto` picks the best installed backend and every response records what actually ran
(`backends` in the trace, `/api/health`).

## Index caching (F9)
Every pickle is stamped with library versions and the corpus hash. A mismatch backs the old file up to
`Data/processed/_v1_backup/` (once) and rebuilds. Embeddings are cached in `embeddings.npy` + `embeddings_meta.json`.

## Adding a graph source
Add a method to `KGBuilder` that creates nodes with `source_id`/`locator` and edges with
`relation, source_id, locator, review_status, confidence`. `tests/test_phase3_kg_herbs.py` enforces provenance and re-checks
locators against the real files. Never use "treats"/"cures" relation names.

## Frontend
Plain HTML/CSS/JS in `frontend/` (no build). `assets/app.js` (views), `assets/graph.js` (canvas force layout),
`assets/i18n.js` (EN/HI/KN labels), `assets/app.css` (tokens; light/dark). Served by FastAPI at `/`.
