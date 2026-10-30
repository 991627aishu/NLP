# Known limitations and open items

Everything below is a *fallback that is active* or a *claim that is not yet verified*. The website's
**System status** chip shows which fallbacks are live on your machine.

## Blocked in the build environment (code written, fallback tested, real backend not executed)

The project was upgraded in a cloud workspace with **no access to PyPI, Hugging Face or npm**.
These parts therefore have real implementations whose fallback paths are tested, but whose
neural path has **never been run**. Verify them on a machine with internet access:

| Component | Install | How to verify | Fallback that ran instead |
|---|---|---|---|
| IndicTrans2 (`ai4bharat/indictrans2-indic-en-dist-200M`, `…en-indic-dist-200M`) | `.\run.ps1 -Neural`; accept the model terms on Hugging Face (the indic→en model is **gated**) and set `HF_TOKEN` in `.env` | `python -m app.evaluation.go_no_go_probe_v2 --backend indictrans2`; check `/api/health` → neural_mt live | rule-based grammar patterns + transliteration |
| Multilingual embeddings (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`) | `.\run.ps1 -Neural` (first start encodes 2,887 chunks once) | `/api/health` → embeddings live; re-run `python -m app.evaluation.evaluator_v2 --split dev` | char n-gram TF-IDF (v1 behaviour) |
| LLM writer (Anthropic API or Ollama) | set `ANTHROPIC_API_KEY` or run Ollama; choose “Language model” in Research options | ask a question; trace shows `generator_used = llm:…` | extractive writer (default; always used in experiments) |
| Server STT (faster-whisper) | `.\run.ps1 -Voice` + ffmpeg (`winget install Gyan.FFmpeg`) | `python tests/audio_samples/make_samples.py` then `pytest tests/test_phase5_6_voice_api.py` | browser Web Speech API (Chrome/Edge) |
| Server TTS (edge-tts → gTTS) | `.\run.ps1 -Voice` (needs internet) | `/api/tts` returns `backend: edge_tts` | browser `speechSynthesis` |
| PyMuPDF | `pip install pymupdf` | `python -m app.core.who_extract` reports `engine=pymupdf` | pdfplumber (used to build the shipped `who_terms.json`) |
| pyarrow (reading `hi.parquet`/`kn.parquet`) | in `requirements.txt` | translator no longer logs "parallel-QA lookup disabled" | parallel-QA exact-match lookup empty; rules/transliteration used |
| Streamlit legacy UI | in `requirements.txt` | `.\run.ps1 -Streamlit` | not run in the build environment (file unchanged; compiles; result keys unchanged) |
| Lighthouse report | Chrome DevTools → Lighthouse on `http://127.0.0.1:8000` | save the report to `docs/lighthouse/` | not produced (no Lighthouse in the build environment); Playwright smoke tests and a 360 px overflow test were run instead |
| `regex` C extension | in `indic-transliteration`'s dependencies | normal install | a `re`-based shim was used **only in the build environment**; it is not part of the project |

## Measured limitations (see `docs/research_findings_v2.md`)

- With rule-based translation, 30–40 % of Hindi/Kannada answerable questions trigger the evidence gate
  (abstain) because transliterated queries match no passage. This is a real property of the fallback.
- The safety gate blocks ~2 % of answerable dev questions (exam-style clinical vignettes that mention
  "paralysis", "chest pain", "breathlessness"). This is deliberate conservatism, measured as false abstention.
- Compound terms are missed by the matcher, e.g. मंदाग्नि (Mandagni) in Go/No-Go PROBE_02.
- Output-side restoration is a no-op in the extractive path (answers contain no placeholders, audit F24);
  it only does work when neural EN→HI/KN answer translation is available.
- The benchmark has validity problems (audit F19, F25–F27): Latin-script terms inside "Hindi"/"Kannada"
  variants, questions copied from indexed records, English text labelled as Hindi/Kannada, topic labels used
  as gold concepts. All 250 seeds are `pending_review`.

## Not verified by a human

- Hindi/Kannada UI text, safety messages and the matcher's Hindi/Kannada term map (`label_hi`, `label_kn`).
- Every `auto_matched_by_code` graph edge (e.g. Dhatu → WHO "Metal", Rasa → "Taste" are genuine polysemies, flagged).
- The 10 symptom → dosha mappings (`project_mapping_unreviewed`; their old page locators failed verification).
- The 4 old v1 relations grounded by code in WHO text (`grounded_by_code_text`).
- Licences: NAMASTE, hi/kn parquet, `qa_cleaned.csv`, IMPPAT remain "to be verified". No redistribution rights are claimed.
