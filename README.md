# AyurMitra

**A Terminology-Preserving Multilingual RAG System with Knowledge Graph Grounding for Ayurvedic Knowledge Retrieval**
RV University · Team 3 — Mansi Jain, Monisha T, N S Aishwarya, Prajna N Rao · Guide: Prof. Khusboo Pandey

AyurMitra answers educational questions about Ayurveda in English, Hindi, Kannada and code-mixed input (Hinglish/Kanglish),
by voice or text, from WHO, NAMASTE and IMPPAT sources — showing every source. Ayurvedic terms are detected, protected through
translation and restored. It refuses doses, prescriptions and diagnoses and refers emergencies to medical care.

> Educational tool only — not medical advice.

## Quick start

Windows PowerShell (Python 3.13):
```powershell
.\run.ps1                      # installs into .venv, builds the graph if needed, serves http://127.0.0.1:8000
.\run.ps1 -Neural -Voice       # + IndicTrans2, multilingual embeddings, faster-whisper, edge-tts (see docs/KNOWN_LIMITATIONS.md)
.\run.ps1 -Test                # full test suite
.\run.ps1 -Streamlit           # legacy Streamlit interface (unchanged)
```
Linux/macOS: `./run.sh`, `./run.sh --neural --voice`, `./run.sh --test`, `./run.sh --streamlit`.

## What's inside

| | |
|---|---|
| **Website** (`frontend/`, served by `api/main.py`) | Ask (text + voice, spoken answers), Knowledge-graph explorer, Symptom guidance, Herbs & lifestyle, Research lab, About/Sources/Safety · EN/HI/KN interface · light/dark |
| **Pipeline** (`app/`) | language ID → term detection (NAMASTE/WHO, aliases, Kannada suffixes) → protection → translation (IndicTrans2 or rules) → BM25 + dense RRF (k=60) → optional graph → grounded answer or abstention → restoration |
| **Safety** | pre-retrieval gate (emergency, dose/prescription, toxic ingestion, cure claims) in every configuration; evidence gate; disclaimer everywhere |
| **Knowledge graph v2** | 9,530 nodes / 72,341 edges built by code from NAMASTE (319), WHO (2,973 terms), IMPPAT plants (4,154), plant-use rows (94,261), API formulations (541); every edge carries source, locator, and review status |
| **Corpus** | 2,887 indexed chunks (IMPPAT 1,328 · API formulations 541 · QA 350 · Hindi QA 250 · Kannada QA 250 · WHO 128 · NAMASTE 40) |
| **Evaluation** | B0 / B1 / P1 / P2 with K=20 candidates per branch (reconciled with paper §5.5), gold-passage metrics, seed-level bootstrap CIs, uncontaminated zero-leakage benchmark, Go/No-Go probe, two-rater kit |

## Core Capabilities & 3-Tier Hybrid RAG Architecture

AyurMitra operates a resilient **3-Tier Evidence Cascade** ensuring high-quality, authentic Ayurvedic and health answers:

```
                  USER QUERY (Text / Voice in EN, HI, KN, Hinglish, Kanglish)
                                              │
                                              ▼
                        LANGUAGE DETECTION & SCRIPT IDENTIFICATION
                                              │
                                              ▼
                         SAFETY & RED-FLAG MEDICAL RISK GATE
                                              │
                                              ▼
                        TERMINOLOGY DETECTION & CANONICAL MAPPING
                                              │
                                              ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ LEVEL 1: LOCAL AYURMITRA KNOWLEDGE BASE RETRIEVAL                                     │
│ • Hybrid Retrieval: BM25 Lexical + 3,072-dim Gemini Vector Embeddings (RRF k=60)        │
│ • Knowledge Graph Grounding (NetworkX v2: 9,530 nodes, 72,341 edges)                   │
│ • Terminology Restoration & Strict Evidence Sufficiency Check                          │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                          [Sufficient Local Evidence?]
                                  /            \
                             YES /              \ NO / Weak / Missing Entity
                                /                \
                               ▼                  ▼
                    GROUNDED LOCAL GENERATION   ┌────────────────────────────────────────┐
                    (Gemini / LLM Synthesizer)  │ LEVEL 2: LIVE WEB RESEARCH FALLBACK    │
                                                │ • Automatic Web Search & Grounding     │
                                                │ • DuckDuckGo, EuropePMC, Wikipedia     │
                                                │ • Clean HTML Text Extraction           │
                                                │ • Real Clickable Citations & URLs      │
                                                └───────────────────┬────────────────────┘
                                                                    │
                                                  [Web Research Successful?]
                                                          /            \
                                                     YES /              \ NO / Offline
                                                        /                \
                                                       ▼                  ▼
                                            GROUNDED WEB PASSAGES   ┌────────────────────┐
                                            (Gemini Multilingual)   │ LEVEL 3: GEMINI    │
                                                                    │ FOUNDATIONAL       │
                                                                    │ KNOWLEDGE FALLBACK │
                                                                    │ (Clearly labeled,  │
                                                                    │ no fake citations) │
                                                                    └─────────┬──────────┘
                                                                              │
                                                                              ▼
                                                                FINAL VERIFIED ANSWER
                                                                (Zero raw chunk codes,
                                                                 native script, audio TTS)
```

### 1. Enterprise Google Gemini Integration
- **Official SDK:** Fully powered by the Google GenAI SDK (`google-genai` v3.6.1+).
- **Active Model Cascade:** Configured with `gemini-3.5-flash-lite`, with seamless failover across `gemini-3.1-flash-lite` and `gemini-3.5-flash` to handle demand spikes and rate limits.
- **Multilingual Embeddings:** Document and query vector indexing powered by `gemini-embedding-001` (3,072-dimensional space).
- **Telemetry & Grounding:** Live tracking of prompt tokens, candidate tokens, total tokens, and request latency.

### 2. Live Web Research Fallback Engine
- When local evidence does not directly address the query's primary entity (e.g. specialized medical queries, newly published literature), AyurMitra **automatically** launches live internet research.
- Searches authoritative sources (EuropePMC, PubMed research indexes, Wikipedia medical portals, open health literature).
- Extracts clean readability text using BeautifulSoup4 and returns verified passage context to Gemini with real, clickable external citations.

### 3. Sanskrit & Indic Entity Resolution
- Single-word regional queries (e.g., `ಕಾಮಣಿ`, `ಕಾಮಾಲೆ` for Kamala/Jaundice, `ಜ್ವರ` for Jwara, `ಪಾಂಡು` for Pandu) are automatically resolved without requesting premature clarification.
- Raw internal chunk identifiers (e.g., `[CLASSIC_CHUNK_...]`, `[WHO_CHUNK_...]`, `[CI.ASSIC...]`) are scrubbed from user-facing answers by multi-pass regex cleaners on both backend and frontend.

### 4. Multilingual Neural Speech Interface
- **Speech-to-Text (STT):** Local faster-whisper neural transcription with browser Web Speech API fallback.
- **Text-to-Speech (TTS):** Edge-TTS high-fidelity neural voices (`kn-IN-GaganNeural`, `hi-IN-MadhurNeural`, `en-IN-NeerjaNeural`) with instant audio playback, speed control, replay, and browser speech synthesis fallback.

## Results — read this before citing numbers

The measured results are in **`docs/research_findings_v2.md`** and the clean uncontaminated benchmark in **`Data/evaluation/experiment_results_clean.json`**.
- On an uncontaminated held-out benchmark (100 seeds × 4 language variants = 400 questions strictly disjoint from indexed corpus chunks), **P1 achieves 56.32% Recall@5 and 0.4423 MRR**, outperforming the hybrid baseline B1 (54.12% Recall@5, 0.3897 MRR) by **+2.20 percentage points** [0.00, +4.67].
- Safety gate abstention on unanswerable/emergency/toxic queries achieves **100% accuracy** (8/8) across all configurations.
- Controlled candidate count evaluation confirmed **K = 20 candidates per branch** (+1.15 pts over K=10), reconciling with paper §5.5 (`candidate_count_comparison.json`).
- Automated 150-query semantic regression benchmark achieves **98.00% intent routing accuracy**, **98.67% language detection accuracy**, **95.73% Recall@5**, and **100% safety guardrail recall** (`semantic_regression_results.json`).

## Architecture & Production Deliverables
- `AYURMITRA_MASTER_ARCHITECTURE.md` — Full 16-part production engineering architecture specification.
- `AYURMITRA_DATA_INGESTION_REPORT.md` — Multi-format enterprise data ingestion benchmark (PDF, DOCX, XLSX, CSV, JSON, HTML).
- `AYURMITRA_RETRIEVAL_EVALUATION.md` — Comparative evaluation of B0, B1, P1, P2 across 700 runs with bootstrap CIs.
- `AYURMITRA_MULTILINGUAL_EVALUATION.md` — Cross-lingual language & script fidelity report (EN, HI, KN, Hinglish, Kanglish).
- `AYURMITRA_SYSTEM_QA_REPORT.md` — Complete system QA report with browser Playwright visual audit and CSS fix proof.
- `scripts/run_enterprise_ingestion.py` — Reproducible multi-format ingestion runner.
- `tests/semantic_regression_benchmark.py` — Automated 150-query multi-domain regression harness.
- `tests/test_mandatory_13.py` — 13 mandatory regression test cases across English, Hindi, and Kannada.

## Documentation
- `docs/AUDIT.md` — Phase-0 audit (F1–F27) · `docs/FEATURE_COMPLETENESS.md` — every feature with evidence
- `docs/USER_GUIDE.md` · `docs/DEVELOPER_GUIDE.md` · `docs/ARCHITECTURE.md` · `CHANGELOG.md`
- `docs/data_audit_and_licensing.md` — sources and licence status (several still "to be verified"; no redistribution rights claimed)
- `docs/human_eval/` — rubric and blank sheets for two independent raters
- `docs/reference/` — the research paper and project plan (scope source of truth; unmodified)

## Layout
```
api/            FastAPI app (website + JSON API)
app/            config, core (terminology, safety, graph, herbs), pipeline, voice, evaluation
frontend/       website (HTML/CSS/JS, no build step)
web/app.py      legacy Streamlit UI (unchanged)
Data/           raw sources (never modified) + processed/ + evaluation/
docs/           audit, results, reconciliation, guides
tests/          pytest suites (original 26 tests unchanged in substance) + Playwright smoke tests
```
