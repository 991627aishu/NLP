# AyurMitra — measured results (test split)

> This file is generated automatically by `python -m app.evaluation.report_v2` from `Data/evaluation/experiment_results_v2.json` (2026-10-30). Do not edit by hand.

## Setup

- Seeds: **175** (173 answerable, gold passages resolved by code for 173) × 4 variants (english, hindi, kannada, romanized).
- Gold-passage methods: question_text_in_chunk (36), namaste_code_in_chunk (32), parallel_question_text_in_chunk (105), unanswerable (2).
- Backends: translator **rules**, dense **tfidf** (`tfidf_char_wb_3-5`), generator extractive (fixed across systems), graph v2; web search off.
- Confidence intervals: percentile bootstrap, 2000 resamples of seed questions (all language variants together) (seed 20261030).
- Runtime 567.9 s on Linux-6.18.44-fc-v185-x86_64-with-glibc2.39, Python 3.13.18.

## Main systems

| System | Recall@5 [95% CI] | MRR [95% CI] | nDCG@5 | Answer with gold evidence | False abstention | Abstention accuracy (unanswerable) | Mean latency |
|---|---|---|---|---|---|---|---|
| B0 | 76.9% [73.7%, 80.1%] | 0.739 [0.707, 0.771] | 0.738 | 69.7% | 25.1% | 100.0% (n=8) | 4 ms |
| B1 | 79.8% [76.2%, 83.2%] | 0.721 [0.682, 0.759] | 0.729 | 69.5% | 22.0% | 100.0% (n=8) | 57 ms |
| P1 | 80.5% [76.7%, 84.0%] | 0.730 [0.688, 0.767] | 0.734 | 71.4% | 20.2% | 100.0% (n=8) | 85 ms |
| P2 | 80.3% [76.6%, 83.9%] | 0.729 [0.688, 0.767] | 0.733 | 71.2% | 20.5% | 100.0% (n=8) | 86 ms |

## Paired differences (same seed resamples)

| Comparison | ΔRecall@5 [95% CI] | ΔMRR [95% CI] | ΔFalse abstention | Verdict |
|---|---|---|---|---|
| P1 vs B1 | +0.7 pts [-0.6, +2.0] | +0.008 [-0.005, +0.021] | -1.7 pts | no clear difference (CI includes 0) |
| B1 vs B0 | +2.9 pts [+0.9, +4.9] | -0.017 [-0.043, +0.006] | -3.2 pts | improves (CI excludes 0) |
| P2 vs P1 | -0.1 pts [-1.0, +0.6] | -0.000 [-0.006, +0.005] | +0.3 pts | no clear difference (CI includes 0) |
| P1 vs P1-grounding-boost-off | +0.9 pts [-0.4, +2.2] | +0.010 [-0.003, +0.023] | -0.1 pts | no clear difference (CI includes 0) |
| P1 vs P1-input-protection-off | -0.1 pts [-0.4, +0.0] | -0.003 [-0.007, +0.000] | +0.0 pts | no clear difference (CI includes 0) |
| P1 vs P1-alias-suffix-off | +0.0 pts [+0.0, +0.0] | -0.001 [-0.004, +0.000] | -0.1 pts | no clear difference (CI includes 0) |
| P1 vs native-crosslingual | -4.9 pts [-9.6, -0.3] | -0.048 [-0.092, -0.004] | +12.0 pts | worse (CI excludes 0) |

## Recall@5 by language

| System | english | hindi | kannada | romanized |
|---|---|---|---|---|
| B0 | 98.3% | 50.3% | 60.7% | 98.3% |
| B1 | 95.4% | 56.6% | 69.4% | 97.7% |
| P1 | 96.5% | 60.7% | 69.4% | 95.4% |
| P2 | 96.0% | 61.3% | 68.8% | 95.4% |

## Ablations and baselines

| Configuration | What changes | Recall@5 [95% CI] | MRR | False abstention |
|---|---|---|---|---|
| P1-input-protection-off | terms detected (boost kept) but query text NOT replaced by placeholders/canonical terms | 80.6% [76.9%, 84.1%] | 0.733 | 20.2% |
| P1-output-restoration-off | answer-side restore_to_language disabled (a no-op in the extractive path, audit F24) | 80.5% [76.7%, 84.0%] | 0.730 | 20.2% |
| P1-alias-suffix-off | only exact canonical / exact native forms detected (no aliases, no Kannada suffix stripping) | 80.5% [76.7%, 84.0%] | 0.731 | 20.4% |
| P1-grounding-boost-off | term protection kept, but the +0.05/term RRF re-ranking boost removed (isolates protection) | 79.6% [76.0%, 83.1%] | 0.719 | 20.4% |
| P1-bm25-only | P1 with the dense branch off | 76.6% [73.3%, 79.9%] | 0.737 | 23.7% |
| P1-dense-only | P1 with the BM25 branch off | 73.0% [68.4%, 77.4%] | 0.650 | 22.8% |
| P2-expansion-off | P2 graph facts kept, query expansion removed | 80.5% [76.7%, 84.0%] | 0.730 | 20.2% |
| native-crosslingual | no translation, no term handling: dense retrieval directly on the untranslated query | 85.4% [81.0%, 89.4%] | 0.777 | 8.2% |

## Comparison with the v1 metric definition

The v1 evaluator counted a hit when the gold *concept string* appeared in any retrieved chunk. With that definition the same runs give:

| System | v1-style concept-match Recall@5 | v2 gold-passage Recall@5 |
|---|---|---|
| B0 | 74.7% | 76.9% |
| B1 | 78.5% | 79.8% |
| P1 | 78.9% | 80.5% |
| P2 | 78.8% | 80.3% |

## Stage-wise error analysis (P1, first failing stage per record)

| Stage | english | hindi | kannada | romanized | Total | Example |
|---|---|---|---|---|---|---|
| safety_gate | 3 | 2 | 1 | 3 | 9 | [english] Dose of VIT K is → not_run_safety_gate:  |
| language_id | 0 | 0 | 0 | 1 | 1 | [romanized] Ayurveda mein: Tobacco is……poison. → identity: Ayurveda mein: Tobacco is……poison. |
| term_detection | 0 | 4 | 5 | 0 | 9 | [hindi] जनसांख्यिकीय चक्र के किस चरण में भारत हाल ही में प्रवेश किया है? → indic_transliteration_fallback: janasAMkhyikI |
| suffix_normalization | 0 | 0 | 1 | 0 | 1 | [kannada] ಎರಡು ಸ್ನೆಹಗಳ ಸಂಯೋಜನೆಯನ್ನು ಹೀಗೆ ಕರೆಯಲಾಗುತ್ತದೆ → indic_transliteration_fallback: èraDu snèhagaLa saMyojanèyannu  |
| translation | 0 | 40 | 45 | 4 | 89 | [hindi] नाल की वह लंबाई जिसे काटा जाना है, वह 4 अंगुल होगी। → indic_transliteration_fallback: nAla kI vaha laMbAI jise k |
| retrieval | 3 | 22 | 1 | 0 | 26 | [hindi] ekAntaH की परिभाषा और आयुर्वेदिक महत्व क्या है? → ayurvedic_grammar_pattern_rule: What is ekAntaH की परिभाषा और  |
| graph | 0 | 0 | 0 | 0 | 0 | P1 has no graph stage; see P2 vs P1 paired difference |
| generation_abstained | 0 | 25 | 24 | 0 | 49 | [hindi] विसर्प को आंतरिक रूप से विकसित किया गया है --------- → indic_transliteration_fallback: visarpa ko AMtarika rUpa  |
| generation_citation | 4 | 4 | 4 | 2 | 14 | [kannada] ಕರ್ಮಕಾತವನ ಪ್ರಕಾರ, ಆಚಾರ್ಯ ಸುಶ್ರುತರು ಹೇಳಿದಂತೆ, ಅಲ್ಲಿ ... ಸ್ಥಾವರ ಸ್ನೇಹಸಾಯವಿದೆ. → indic_transliteration_fallback:  |
| restoration | 0 | 0 | 0 | 0 | 0 | extractive answers contain no placeholders, so output restoration cannot fail (audit F24); measured only with neural ans |
| success | 163 | 76 | 92 | 163 | 494 |  |

## Go/No-Go terminology probe (v2, real translator output)

Translator: **rules** · decision: **NOT TESTED**

The translator in this run was the rule-based fallback (no IndicTrans2). It transliterates rather than translates, so it cannot produce semantic drift such as Pitta→bile; this run therefore does NOT test the research premise. Re-run with --backend indictrans2 on a machine that can load the model. The v1 '100% corruption' figure was hand-typed and is not a measurement.

| Probe | Query | Unprotected output | Status | Protected output | Status |
|---|---|---|---|---|---|
| PROBE_01 (Pitta) | पित्त के लक्षण क्या हैं? | What are the symptoms and signs of पित्त? | untranslated | What are the symptoms and signs of Pitta? | preserved |
| PROBE_02 (Agni) | मंदाग्नि को कैसे ठीक करें? | How to balance and treat मंदाग्नि? | untranslated | How to balance and treat मंदाग्नि? | untranslated |
| PROBE_03 (Vata) | ವಾತದ ತೊಂದರೆಗೆ ಯಾವ ಚಿಕಿತ್ಸೆ? | vAtada tòMdarègè yAva chikitsè? | preserved | Vata tòMdarègè yAva chikitsè? | preserved |
| PROBE_04 (Kapha) | ಕಫದಲ್ಲಿ ಯಾವ ಆಹಾರ ಒಳ್ಳೆಯದು? | kaphadalli yAva AhAra òLLèyadu? | preserved | kaphadalli yAva AhAra òLLèyadu? | preserved |
| PROBE_05 (Ojas) | ओजस बढ़ाने के उपाय क्या हैं? | What is ओजस बढ़ाने के उपाय? | untranslated | What is Ojas बढ़ाने के उपाय? | preserved |
| PROBE_06 (Ama) | ಆಮ ದೋಷವನ್ನು ನಿವಾರಿಸುವುದು ಹೇಗೆ? | Ama doShavannu nivArisuvudu hegè? | preserved | Ama Dosha nivArisuvudu hegè? | preserved |
| PROBE_07 (Prakriti) | Meri prakriti kaise check karein? | Meri prakriti kaise check karein? | preserved | Meri Prakriti kaise check karein? | preserved |
| PROBE_08 (Dhatu) | सात धातुओं का क्या महत्व है? | sAta dhAtuoM kA kyA mahatva hai? | preserved | sAta DhatuoM kA kyA mahatva hai? | preserved |

## Development split (for reference; used for inspection only — nothing was tuned on test)

| System | Recall@5 [95% CI] |
|---|---|
| B0 | 75.3% [69.9%, 80.4%] |
| B1 | 78.1% [72.6%, 83.1%] |
| P1 | 79.9% [74.3%, 84.9%] |
| P2 | 79.9% [74.3%, 84.9%] |

## Limitations

- Pilot scale: 175 seed questions on the test split; CIs are wide.
- Translation backend in this run: rules. IndicTrans2 was NOT available, so Hindi/Kannada queries were translated by rules/transliteration; results do not test the paper's IndicTrans2 pipeline.
- Dense backend in this run: tfidf (tfidf_char_wb_3-5). This is character n-gram TF-IDF, not a neural embedding model.
- 68 Hindi and 71 Kannada variants contain the Ayurvedic term in Latin script, so they do not exercise native-script term protection (audit F19).
- Many benchmark questions are taken from records that are themselves in the indexed corpus (QA rows, BhashaBench rows), so English retrieval is close to a lookup (audit F25).
- Some 'Hindi'/'Kannada' variants are English text with a short native-script prefix (audit F26); several gold_concept values are topic labels such as 'General' (audit F27). All 250 seeds are still review_status=pending_review.
- No human ratings exist yet; answer quality and citation faithfulness need the two-rater kit in docs/human_eval/.

## Files

- `Data/evaluation/predictions_v2*.csv` — every record: query, retrieved IDs, cited IDs, gold IDs, scores
- `Data/evaluation/error_analysis_v2*.csv` — first failing stage per P1 record
- `Data/evaluation/failure_cases_v2*.json` — retrieval/abstention failures and missed abstentions
- `Data/evaluation/experiment_results.json` — the ORIGINAL v1 results, kept unchanged (see docs/AUDIT.md F7/F17/F18)
