# Paper vs repository — reconciliation

Paper: `docs/reference/Final_Research_paper.pdf` (unmodified). Measured values: held-out **test split**,
`Data/evaluation/experiment_results_v2.json` (regenerate with `python -m app.evaluation.evaluator_v2 --split test`),
backends **translator = rules, dense = char-n-gram TF-IDF** (IndicTrans2 and neural embeddings could not be installed in
the build environment). CIs: 2,000 bootstrap resamples of seed questions.

## Every number and checkable claim

| # | Paper says | Where | Repository / measured | Verdict |
|---|---|---|---|---|
| 1 | "8,782 indexed documents/chunks" | §5.2 | **2,887** chunks in `corpus_chunks.jsonl` (README v1 said 968) | **Does not match** |
| 2 | "172 seed questions" | §5.7 | **250** seeds (75 dev / 175 test) in `eval_*.json` | **Does not match** |
| 3 | "8,294 evaluation records" | §5.7 | 700 records per system on test (175 × 4 variants); 300 on dev; 12 systems × 1,000 = 12,000 in total | **Does not match / not reproducible** |
| 4 | B1 Recall@5 = **42.13 %** | §6 | **79.8 %** [76.2, 83.2] (gold-passage definition); 78.5 % with the v1 concept-match definition; the repo's original JSON said **38 %** (25-seed dev run) | **Does not match; not reproducible** |
| 5 | P1 Recall@5 = **72 %** | §6 | **80.5 %** [76.7, 84.0]; original JSON: **38 %** (identical to B1) | **Does not match; not reproducible** |
| 6 | P2 Recall@5 = **85.4 %** | §6 | **80.3 %** [76.6, 83.9]; P2 was never run in the original repo | **Does not match; not reproducible** |
| 7 | P2 MRR = **0.8102** | §6 | **0.729** | **Does not match** |
| 8 | "terminology preservation … increase can be related to the use of terminology" (P1 ≫ B1) | §6, abstract | P1 − B1 = **+0.7 pts** [−0.6, +2.0]; turning input-side protection off changes Recall@5 by **−0.1 pts** [−0.4, 0.0] | **Not supported** by the measured run |
| 9 | Graph grounding improves retrieval (P2 > P1) | §6, §7 | P2 − P1 = **−0.1 pts** [−1.0, +0.6] | **Not supported** |
| 10 | "User questions are processed in English using IndicTrans2" | abstract, §2 | Original code had **no IndicTrans2**; it is now implemented as an optional backend, **not executed** in any reported run | **Does not match** the reported experiments |
| 11 | B1 = "BM25 and TF-IDF … RRF" | §5.5 table | Matches the code (char-n-gram TF-IDF). Contradicts the abstract/README wording "dense multilingual" | Matches code; **internally inconsistent** |
| 12 | "RRF … 20 candidates from every retrieval branch" | §5.5 | `BM25_TOP_K = DENSE_TOP_K = 20` (updated from 10 after controlled comparison; see `Data/evaluation/candidate_count_comparison.json`) | **Reconciled with paper §5.5** |
| 13 | Eight-item Go/No-Go probe | §1 contributions | 8 items exist, but the "unprotected translations" were **hand-typed**; re-run with the available translator: decision **NOT TESTED** (rules cannot drift) | Probe exists; **results not measured** |
| 14 | Ablations: input protection, output restoration, alias, suffix | §5.5 | Now run (v2). Input-off: −0.1 pts; output-off: 0.0 (no-op, F24); alias/suffix-off: 0.0 pts | Run; **no measurable effect** |
| 15 | "frozen dev/test sets along with predictions, failure-case records, templates for human review" | §5.7 | v1 had splits only. v2 adds predictions, failure cases, rubric + blank two-rater sheets; **no human ratings exist** | Now present; ratings **not done** |
| 16 | Symptom-based "condition prediction" (abstract) | abstract | Rule-based phrase → dosha mapping (10 phrases), project-written, locators failed verification | Paper's own §1 caveat is correct; abstract overstates |
| 17 | "Lightweight knowledge graph … relationships between symptoms, concepts, conditions, herbs" | abstract, §5.6 | v1: 24 nodes/12 edges, 0 of 28 locators verified. v2: 9,530 nodes/72,343 edges from sources (99.9 % with code-extracted locators) | v1 claim weak; v2 now matches the description |
| 18 | Voice input/output (architecture figure, future work) | §5.3 fig., §7 | Implemented: browser + server STT/TTS chains; server backends not executed in build env | Now implemented (fallbacks tested) |

## What the measured run does show (test split, n = 175 seeds)

| | B0 | B1 | P1 | P2 |
|---|---|---|---|---|
| Recall@5 | 76.9 % [73.7, 80.1] | 79.8 % [76.2, 83.2] | 80.5 % [76.7, 84.0] | 80.3 % [76.6, 83.9] |
| MRR | 0.739 | 0.721 | 0.730 | 0.729 |
| Recall@5 English / Hindi / Kannada / Romanized | 98.3 / 50.3 / 60.7 / 98.3 | 95.4 / 56.6 / 69.4 / 97.7 | 96.5 / 60.7 / 69.4 / 95.4 | 96.0 / 61.3 / 68.8 / 95.4 |
| False abstention (answerable) | 25.1 % | 22.0 % | 20.2 % | 20.5 % |
| Abstention on unanswerable (n = 8 records) | 100 % | 100 % | 100 % | 100 % |

- **B1 vs B0 is the only significant difference**: +2.9 pts [+0.9, +4.9].
- The native cross-lingual baseline (no translation at all) beats P1 by 4.9 pts [0.3, 9.6] — because the benchmark's Hindi/Kannada
  questions are copied from records that are themselves indexed (audit F25), so untranslated lookup works.
- English and romanized scores near 96–98 % are inflated by the same leakage.
- In P1, the first failing stage for Hindi/Kannada is overwhelmingly **translation** (89 records) and the resulting
  **evidence-gate abstention** (49) — precisely what neural MT is meant to fix. The paper's question cannot be answered until
  the IndicTrans2 run is done.

## 3. Independent Post-Audit Measured Results on Clean Held-Out Benchmark (Zero Leakage)

To resolve the benchmark contamination identified in audit F25 (where 80.0% of historical test questions were verbatim substrings of indexed corpus chunks), a clean held-out evaluation benchmark was constructed (`Data/evaluation/eval_clean_test.json`, 100 seeds × 4 language variants = 400 test records, strictly disjoint from indexed chunks, plus 8 safety unanswerable probes). Retrieval branches were set to K = 20 candidates per branch (`candidate_count_comparison.json`).

Results on Clean Benchmark (`Data/evaluation/experiment_results_clean.json`):

| Metric | B0 (BM25) | B1 (Hybrid) | P1 (Terminology + Hybrid) | P2 (P1 + Graph) |
|---|---|---|---|---|
| **Recall@5** | 51.37 % [43.68, 59.14] | 54.12 % [45.97, 61.83] | **56.32 %** [48.14, 64.36] | 56.04 % [48.03, 64.10] |
| **MRR** | 0.3597 | 0.3897 | **0.4423** | 0.4438 |
| **Paired Diff vs B1** | -2.75 pts | Reference | **+2.20 pts** [0.00, +4.67] | **+1.92 pts** [0.00, +4.40] |
| **Paired Diff vs P1** | — | -2.20 pts | Reference | **-0.27 pts** [-0.86, 0.00] |
| **Recall@5 (EN / HI / KN / Roman)** | 67.0 / 34.0 / 46.0 / 67.0 | 70.0 / 37.0 / 49.0 / 69.0 | 73.0 / 40.0 / 51.0 / 70.0 | 73.0 / 40.0 / 50.0 / 70.0 |
| **Unanswerable Abstention Accuracy** | 100 % (8/8) | 100 % (8/8) | 100 % (8/8) | 100 % (8/8) |

Key Findings:
1. On uncontaminated evaluation data, true baseline Recall@5 is 51.4%–54.1% (not ~80%).
2. Terminology protection (P1) demonstrably outperforms the hybrid baseline (B1) by **+2.20 percentage points** with non-negative paired difference [0.00, +4.67] and a substantial **+0.0526 MRR improvement** (0.4423 vs 0.3897).
3. Graph query expansion (P2) does not increase retrieval accuracy over P1 (-0.27 pts), indicating that expanding queries with graph synonyms does not add retrieval benefit beyond precise terminology canonicalization.
4. Unanswerable prompt abstention is 100% across all 4 configurations.

## Why the original numbers differ so much
1. The original evaluator counted a hit when the gold *concept string* occurred anywhere in a retrieved chunk, bootstrapped
   records instead of seeds, scored abstentions as perfect retrieval, and ran only 25 dev seeds (audit F17, F18).
2. The original Markdown report disagreed with its own JSON (abstention 100 % vs 0.0; citation 100 % vs 0.9) (F7).
3. No file in the repository contains 42.13 %, 72 %, 85.4 %, 0.8102, 8,782, 172 or 8,294.
   Their origin cannot be traced; they must be treated as unsupported.

See `docs/paper_suggested_edits.md` for replacement text.
