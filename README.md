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

## Results — read this before citing numbers

The measured results are in **`docs/research_findings_v2.md`** and the clean uncontaminated benchmark in **`Data/evaluation/experiment_results_clean.json`**.
- On an uncontaminated held-out benchmark (100 seeds × 4 language variants = 400 questions strictly disjoint from indexed corpus chunks), **P1 achieves 56.32% Recall@5 and 0.4423 MRR**, outperforming the hybrid baseline B1 (54.12% Recall@5, 0.3897 MRR) by **+2.20 percentage points** [0.00, +4.67].
- Safety gate abstention on unanswerable/emergency/toxic queries achieves **100% accuracy** (8/8) across all configurations.
- Controlled candidate count evaluation confirmed **K = 20 candidates per branch** (+1.15 pts over K=10), reconciling with paper §5.5 (`candidate_count_comparison.json`).
- The draft paper's ungrounded metrics (P1 72 %, P2 85.4 %, MRR 0.8102, 8,782 chunks, 172 seeds) were derived from an earlier unverified report with 80% test-corpus leakage; see `docs/PAPER_RECONCILIATION.md` and `docs/paper_suggested_edits.md` for complete reconciliation and line-by-line paper corrections.

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
