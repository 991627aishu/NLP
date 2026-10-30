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
4. **§5.5** — "20 candidates from every retrieval branch" → "10 candidates from each branch, fused with RRF (k = 60), top 5 kept".
   Also state that B1's "dense" branch is character n-gram TF-IDF in this pilot, not a neural embedding model.
5. **§5.7** — "172 seed questions and 8294 evaluation records" → "250 seed questions (75 development, 175 held-out test), each with
   English, Hindi, Kannada and romanized variants (700 test records per system)". Add that all seeds are pending review and that
   ~40 % of Hindi/Kannada variants keep the term in Latin script.
6. **§6, all numbers** — 42.13 %, 72 %, 85.4 % and MRR 0.8102 cannot be reproduced from the project; remove them.
7. **§6 / §7 claims** — "terminology preservation is useful", "results are impressive", "the use of both techniques has improved
   the efficiency" and "the experimentation shows positive outcomes" are not supported by the measured run; replace as below.
8. **§1 contribution (3)** — the Go/No-Go probe outputs were hand-written; say the probe "is defined" and that its measurement
   with IndicTrans2 is pending (or report the real run once done).

## Replacement text for §6 (Experimental results and discussion)

> We evaluated four configurations on a held-out test split of 175 seed questions, each in English, Hindi, Kannada and romanized
> form (700 records per configuration). Relevance was judged against gold source passages identified from each seed's source record.
> Confidence intervals are 95 % percentile bootstrap intervals over seed questions (2,000 resamples). Translation used a rule-based
> fallback and the "dense" branch used character n-gram TF-IDF; IndicTrans2 and neural multilingual embeddings were not used in
> this run.
>
> Recall@5 was 76.9 % [73.7, 80.1] for B0, 79.8 % [76.2, 83.2] for B1, 80.5 % [76.7, 84.0] for the terminology-preserving P1 and
> 80.3 % [76.6, 83.9] for P2 (MRR 0.739, 0.721, 0.730, 0.729). Hybrid retrieval improved on BM25 alone (+2.9 points
> [+0.9, +4.9]). The terminology-preserving configuration did **not** differ clearly from the unprotected hybrid baseline
> (P1 − B1 = +0.7 points [−0.6, +2.0]), and graph grounding did not change retrieval (P2 − P1 = −0.1 points [−1.0, +0.6]).
> Ablations confirm this: disabling input-side protection changed Recall@5 by −0.1 points, and disabling alias/suffix
> normalisation by 0.0 points. Output-side restoration had no effect because the extractive generator does not pass answer text
> through translation.
>
> Performance differed sharply by language: P1 reached 96.5 % (English) and 95.4 % (romanized) but only 60.7 % (Hindi) and
> 69.4 % (Kannada). Stage-wise error analysis attributes most Hindi and Kannada failures to the translation step (the rule-based
> translator transliterates rather than translates) and to evidence-based abstention that follows from it. A baseline that
> skipped translation entirely scored higher (85.4 %), which we attribute to benchmark construction: many questions are drawn from
> records that are themselves indexed. English results are inflated for the same reason.
>
> All 8 unanswerable test records (prescription, toxic-substance, out-of-domain, biomedical and unsupported-claim prompts) were
> declined in every configuration. False abstention on answerable questions was 20–25 %, concentrated in Hindi and Kannada.
>
> These results do not test the central hypothesis under the intended translation model. The decisive next experiment is the same
> evaluation with IndicTrans2, together with a reviewed benchmark in which Hindi and Kannada questions are written natively and are
> not copies of indexed records.

## Replacement for §7 (first paragraph)

> AyurMitra implements a multilingual, terminology-aware retrieval pipeline with source-linked answers, a provenance-tracked
> knowledge graph built from WHO, NAMASTE and IMPPAT data, safety-first abstention and voice input/output. In this pilot, with a
> rule-based translator, terminology protection did not measurably improve retrieval over an unprotected hybrid baseline, and graph
> grounding did not improve retrieval. The dominant error source for Hindi and Kannada queries was translation.

## Additions recommended
- A limitations paragraph listing: pilot size; fallback translator; TF-IDF in place of neural embeddings; benchmark leakage and
  Latin-script terms in Hindi/Kannada variants; no human ratings yet; unverified licences for several sources.
- A short note that the knowledge-graph claims (v2) refer to code-extracted relations whose expert review is pending.
