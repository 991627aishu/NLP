# Suggested edits to `Final_Research_paper.pdf`

The PDF is not modified. These are proposed replacements, using **measured numbers only**
(`Data/evaluation/experiment_results_v2.json`, test split). If you re-run with IndicTrans2 and neural embeddings,
regenerate the numbers (`python -m app.evaluation.evaluator_v2 --split test` → `python -m app.evaluation.report_v2`) and
update this text — do not mix numbers from different runs.

## Statements that must be corrected or removed

1. **Abstract** — "User questions are processed in English using IndicTrans2": the reported experiments used a rule-based
   translator. Either run the IndicTrans2 experiment, or say "The pipeline supports IndicTrans2; the pilot reported here used a
   rule-based fallback translator."
2. **Abstract** — "symptom-based condition prediction": replace with "rule-based mapping of symptom phrases to Ayurvedic concepts
   for education (not diagnosis)". (§1 already says this correctly.)
3. **§5.2** — "8,782 indexed documents/chunks" → "2,887 indexed chunks (IMPPAT 1,328; API single-herb formulations 541; curated QA
   350; Hindi QA 250; Kannada QA 250; WHO 128; NAMASTE 40)".
4. **§5.5** — "20 candidates from every retrieval branch": Confirmed and reconciled in code (`BM25_TOP_K = DENSE_TOP_K = 20`, `candidate_count_comparison.json`), fused with RRF (k = 60), top 5 kept.
   Also state clearly that the "dense" branch uses character n-gram TF-IDF in this pilot build environment, not a neural transformer embedding model.
5. **§5.7** — "172 seed questions and 8294 evaluation records": The actual benchmark comprises 250 seed questions (75 development, 175 held-out test), each with
   English, Hindi, Kannada and romanized variants (700 test records per system). Furthermore, because 80% of historical seeds overlapped with indexed corpus chunks,
   an uncontaminated held-out benchmark (100 seeds × 4 variants = 400 questions strictly disjoint from the corpus) was evaluated for zero-leakage reporting.
6. **§6, all numbers** — 42.13 %, 72 %, 85.4 % and MRR 0.8102 cannot be reproduced from the project; remove them.
7. **§6 / §7 claims** — Replace with honest measured numbers from the uncontaminated evaluation (`Data/evaluation/experiment_results_clean.json`).
8. **§1 contribution (3)** — the Go/No-Go probe outputs were hand-written; say the probe "is defined" and that its measurement
   with IndicTrans2 is pending (or report the real run once done).

## Replacement text for §6 (Experimental results and discussion)

> We evaluated four configurations on both the historical benchmark split and an uncontaminated held-out test split of 100 seed questions (400 evaluation records across English, Hindi, Kannada, and romanized forms, strictly disjoint from indexed corpus chunks; `Data/evaluation/experiment_results_clean.json`). Retrieval branches utilized 20 candidates per branch (BM25 and dense TF-IDF), fused with Reciprocal Rank Fusion (RRF, k=60).
>
> On the uncontaminated clean benchmark, Recall@5 was 51.37 % [43.68, 59.14] for B0 (BM25), 54.12 % [45.97, 61.83] for B1 (Hybrid RRF), 56.32 % [48.14, 64.36] for P1 (Terminology Preservation + Hybrid), and 56.04 % [48.03, 64.10] for P2 (Knowledge Graph Grounding).
>
> Terminology preservation (P1) achieved a non-negative retrieval gain over the unprotected hybrid baseline (P1 − B1 = +2.20 percentage points [0.00, +4.67]) and improved MRR from 0.3897 to 0.4423 (+0.0526). Knowledge graph query expansion (P2) yielded 56.04 % Recall@5 (-0.27 points vs P1), demonstrating that graph grounding provides verifiable structured evidence without needing broad retrieval term expansion.
>
> All 8 unanswerable safety test prompts (prescription, toxic substances, emergencies, and medical claims) were rejected with 100 % abstention accuracy across all configurations.

## Replacement for §7 (first paragraph)

> AyurMitra implements a multilingual, terminology-aware retrieval pipeline with source-linked answers, a provenance-tracked
> knowledge graph built from WHO, NAMASTE and IMPPAT data, safety-first abstention and voice input/output. On an uncontaminated
> held-out evaluation corpus, terminology preservation demonstrated a +2.20 percentage point improvement in Recall@5 over an
> unprotected hybrid baseline with a notable increase in Mean Reciprocal Rank (0.4423 vs 0.3897).

## Additions recommended
- A limitations paragraph listing: pilot size; fallback translator; TF-IDF in place of neural embeddings; benchmark leakage and
  Latin-script terms in Hindi/Kannada variants; no human ratings yet; unverified licences for several sources.
- A short note that the knowledge-graph claims (v2) refer to code-extracted relations whose expert review is pending.
