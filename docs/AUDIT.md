# AyurMitra — Phase 0 Audit Report

**Date:** 2026-10-30  **Baseline:** git tag `v0-baseline` (commit `f9d2b2d`, project exactly as received in `NLP-CIE3.zip`)
**Backup:** full copy at `../NLP-CIE3_BACKUP_2026-10-30/`  **Raw-data hashes:** `docs/raw_data_hashes.sha256` (verify with `sha256sum -c docs/raw_data_hashes.sha256`)
**Reference documents:** `docs/reference/Final_Research_paper.pdf`, `docs/reference/AyurMitra_Complete_Project_and_Research_Plan_v2.pdf` (the second is byte-identical to the `... (1).pdf` copy at the repo root).

Every finding below was re-checked by running code, not by reading descriptions alone. Verdicts: **CONFIRMED** (reproduced), **CONFIRMED+** (reproduced, and worse than first reported), **NEW** (not in the original audit list).

---

## 0. Audit environment and its limits

| Item | Value |
|---|---|
| OS / Python | Linux container, Python 3.13.18 (the user's machine is Windows + Python 3.13) |
| Libraries | scikit-learn 1.9.1, numpy 2.5.3, pandas 3.0.5, networkx 3.7, pdfplumber (PyMuPDF not available) |
| Network | **PyPI, npm and Hugging Face are blocked from this workspace.** `rank_bm25`, `indic_transliteration` (+ `common_maps` data), `xlrd`, `roman` and `tqdm` were installed from their GitHub sources. `regex` (a C extension) was replaced by a `re` shim for the audit environment only. Nothing in the project depends on this shim. |
| Not available here | `pyarrow` (so `hi.parquet`/`kn.parquet` cannot be re-read live; the parallel-QA lookup in `translator.py` is empty in this environment), `streamlit`, `fastapi`, `torch`, `transformers`, `sentence-transformers`, IndicTrans2 models |

Consequence: live behaviour of the Hindi/Kannada parallel-QA lookup could not be reproduced here. Everything else in this audit was run here.

---

## 1. Test suite

| Run | Result |
|---|---|
| As received, on Linux | **18 passed, 8 failed.** All 8 failures are `data/` vs `Data/` path errors (F8). |
| Throwaway copy with a `data → Data` symlink (simulates Windows' case-insensitive FS) | **26 passed**, 22 warnings (sklearn `InconsistentVersionWarning`, pickles built with 1.7.2 → F9) |

Command: `python -m pytest tests/test_ayurmitra.py -q`

---

## 2. Findings F1–F13 (from the original audit)

| # | Verdict | What was verified (evidence) |
|---|---|---|
| **F1** Translation is not IndicTrans2 | **CONFIRMED** | Nothing under `app/`, `web/` or `tests/` imports `transformers`, `torch` or IndicTrans2. Live P1 run of `ಆಮ ದೋಷವನ್ನು ನಿವಾರಿಸುವುದು ಹೇಗೆ?` gives `translation_meta.method = "indic_transliteration_fallback"`, `translated_text = "__AYURTERM_0__ __AYURTERM_1__ nivArisuvudu hegè?"`, `canonical_query = "Ama Dosha nivArisuvudu hegè?"`. Top-3 retrieved: `WHO_CHUNK_0101/0098/0102` (WHO body-channel-dysfunction / morbidity tables). These are off-topic. |
| **F2** "Dense" retrieval is TF-IDF | **CONFIRMED** | `dense_retriever.py` builds a `TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5))`. The docstring says "with support for sentence-transformers if present", but **no such code path exists**. `DENSE_MODEL_NAME` in `config.py` is never imported. The paper's own §5.5 table also calls B1 "BM25 and TF-IDF", which contradicts its abstract/README ("dense multilingual"). |
| **F3** Generator is extractive/template | **CONFIRMED+** | `GENERATOR_MODEL = None`; `generator.py` imports `CONCEPT_EXPLANATIONS` (8 hand-written HI/KN paragraphs). In the F1 Kannada run, the **answer body is the hard-coded `CONCEPT_EXPLANATIONS["Ama"]["kn"]` text, while the cited evidence is an unrelated WHO passage** (ITA-4.8.7, body-channel dysfunction). The citation does not support the answer → see F14. |
| **F4** KG is tiny, hand-coded, locators unproven | **CONFIRMED+** | 24 nodes (8 Herb, 6 SymptomPhrase, 3 Dosha, 3 Principle, 2 Concept, 1 Discipline, 1 Therapy), 12 edges. **Every locator was checked by code** (table below). None of the 9 NAMASTE codes points to the concept it is attached to. None of the WHO page locators supports its relation under either physical-page or printed-page numbering (printed = physical − 18, determined from 64 page footers). |
| **F5** No voice I/O | **CONFIRMED** | No STT/TTS code anywhere (`grep -ri "speech|whisper|tts"` → nothing). |
| **F6** No herbal/diet/lifestyle module | **CONFIRMED** | Only the symptom mapper and 8 herb nodes. No herb directory, no formulation view. |
| **F7** Paper numbers ≠ repository | **CONFIRMED+** | See §4. In addition, the Markdown report contradicts the JSON it summarises: B0 citation 100% (JSON 0.9); abstention accuracy 100% for all systems (JSON **0.0** for all); "All 5 unanswerable questions correctly triggered abstention" (the dev run contained 1 unanswerable seed × 4 variants, and none abstained). P2 was never evaluated (`experiment_results.json` contains only B0, B1, P1). The results file stores a Windows absolute path (`C:\Users\texta\Downloads\...`). |
| **F8** `data` vs `Data` case bug | **CONFIRMED** | `config.py`: `DATA_RAW = ROOT/"Data"` but `DATA_PROC = ROOT/"data"/"processed"`, `DATA_EVAL = ROOT/"data"/"evaluation"`. Tests also hard-code `Path("data/evaluation/...")`. 8 tests fail on Linux. **Danger:** on Linux the pipeline silently rebuilds indices into a new `data/processed/` instead of failing. |
| **F9** sklearn pickle version warnings | **CONFIRMED** | Pickles were built with 1.7.2. `InconsistentVersionWarning` appears for `TfidfVectorizer`/`TfidfTransformer` under 1.9.1. `requirements.txt` uses only `>=` lower bounds (nothing pinned). |
| **F10** `query_concept()` key mismatch | **CONFIRMED** | Found → keys `found, concept, attributes, connections`. Not found → keys `found, concept, neighbors`. |
| **F11** Missing research artefacts | **CONFIRMED** | Not present anywhere: ablations (input-off / output-off / alias-suffix-off / BM25-only / dense-only / graph-off), native cross-lingual baseline, stage-wise error analysis, human-review rubric/templates, two-rater kappa script, saved failure cases. `experiment_results.json` keeps only `detailed_sample_count`, not per-item predictions. |
| **F12** Go/No-Go probe outputs | **CONFIRMED — static strings** | `go_no_go_probe.py` contains hand-typed `"unprotected_translation"` values (e.g. `"What are the symptoms of bile?"`, `"How to cure low fire?"`) and hand-assigned `term_status_unprotected`. No MT model is called. The reported "100% unprotected corruption → GO" is therefore **not a measurement**. It has to be re-run with real IndicTrans2 output. |
| **F13** Licence register "to be verified" | **CONFIRMED (+ inconsistency)** | `config.py` says the hi/kn parquet and `qa_cleaned.csv` licences are "to be confirmed". `docs/data_audit_and_licensing.md` asserts they are "BhashaBench Ayurveda parallel QA" and "Dr. Vaidya Mana Bajracharya" archive without a licence or URL. The two documents disagree. Keep the warnings. |

### F4 locator verification (machine-checked)

| Graph element | Claimed locator | What the source actually contains there |
|---|---|---|
| Vata / Pitta / Kapha nodes | NAMASTE `Code SAT-A` | `SAT-A` = *mUlaBUta-SabdaH* "fundamental terms" (section header, not the dosha) |
| Agni | NAMASTE `SAT-A.2` | *AyuH* "life; lifespan" |
| Ama | NAMASTE `SAT-A.3` | *dhAri* "that which sustains" |
| Ojas | NAMASTE `SAT-A.4` | *jIvitam* "life" |
| Prakriti | NAMASTE `SAT-A.5` | *nityaga* "incessant" |
| Rasayana | NAMASTE `SAT-A.6` | *anubandhaH* "continuity of life" |
| Panchakarma | NAMASTE `SAT-A.7` | *AyuH-prakAraH* "types of life" |
| Agni → Ama (`impaired_leads_to`) | NAMASTE `SAT-A.3` | *dhAri* (unrelated) |
| Agni → Ojas (`optimal_nourishes`) | NAMASTE `SAT-A.4` | *jIvitam* (unrelated) |
| Sluggish Digestion → Kapha | NAMASTE `SAT-A.2` | *AyuH* (unrelated) |
| Tridosha → Vata/Pitta/Kapha (`comprises`) | WHO `page 15` | Neither physical p.15 nor printed p.15 (phys. 33, ITA-1.8.x) mentions vata/pitta/tridosha |
| Dry Skin → Vata | WHO `page 45` | No "vata", no "dry" on phys. 45 or printed 45 |
| Joint Stiffness → Vata | WHO `page 46` | No "stiffness" on either page |
| Burning Sensation → Pitta | WHO `page 50` | No "pitta"/"burning" on either page |
| Acid Reflux → Pitta | WHO `page 52` | "pitta" present on phys. 52, but no "reflux"/"acid" (reflux occurs only on phys. 183, 226) |
| Excessive Mucus → Kapha | WHO `page 58` | "mucus" and "kapha" both present on phys. 58 → **plausible, needs human check** |
| 8 herb nodes, Ashwagandha → Rasayana | IMPPAT `"Plant Registry"` / `"TherapeuticUse_Plant_Association"` | File names only, not row locators; `recorded_uses` are typed strings, not IMPPAT rows |

**Result: 0 of 28 locators verified; 1 plausible; 27 incorrect or non-specific.** Phase 3 will move all of these to `review_status: "unverified"` (or correct them), and v2 will derive locators by code from WHO Term IDs (`ITA-x.y.z` + real page) and NAMASTE rows.

---

## 3. New findings (not in the original list)

| # | Severity | Finding | Evidence |
|---|---|---|---|
| **F14** | **High (grounding)** | HI/KN answers can state facts that are not in the cited passages. The body comes from `CONCEPT_EXPLANATIONS` and is attached to whatever chunk was retrieved. | F1 run: Ama explanation, citation = `WHO_CHUNK_0101` (ITA-4.8.7 body-channel dysfunction). |
| **F15** | **Critical (safety)** | **The main chat pipeline never abstains on emergencies, dosage requests or any of the 5 benchmark "unanswerable" seeds.** `generator.py` abstains only when *zero* passages are retrieved. Red-flag triage exists only in `EducationalSymptomMapper` (Symptom tab), which `rag_pipeline.py` does not call. | `process_query(..., enable_web_search=False)` with B1 and P1: "sudden severe headache and blurred vision", "मुझे अचानक तेज़ सिरदर्द…", "How many grams of Ashwagandha should I take daily?", plus all 5 `is_unanswerable` seeds (prescription, toxic substance, out-of-domain, modern biomedicine, unsupported claim) → **`abstained=False` in every case (16/16).** |
| **F16** | High (safety) | The symptom mapper misses native-script Hindi red flags. "मुझे अचानक तेज़ सिरदर्द हो रहा है" → `no_supported_symptom_recognized` (not an emergency). Kannada script, English and romanized Hindi are caught. | `analyze_symptoms()` live run |
| **F17** | High (evaluation validity) | The evaluator's metric definitions do not match their names. **Relevance** = gold-concept substring (or any >3-char word of it) appearing in a retrieved chunk, not gold passage IDs. **"citation_correctness"** = "answer has ≥1 citation". **"term_preserved"** is hard-wired to 1.0 for non-P1 modes. **Unanswerable items** score Recall/MRR/nDCG = 1.0 when the system abstains (this inflates retrieval metrics). | `evaluator.py` L80–140 |
| **F18** | High (evaluation validity) | Bootstrap CIs resample **individual records**, not seed questions, even though the docstring and the plan both say seed-level. Records from the same seed (4 language variants) are treated as independent, so the intervals come out too narrow. | `bootstrap_ci()` L52–64 |
| **F19** | High (explains B1 = P1) | Many "Hindi"/"Kannada" benchmark variants embed the term in **romanized ITRANS** inside native-script text (e.g. `uddhAraH की परिभाषा…`): 99/250 HI and 101/250 KN seeds. On these items, protection is never exercised against native-script MT, so B1 ≡ P1 is expected. All 250 seeds are `review_status: pending_review`. The dev run used the first 25 of 75 dev seeds. | `eval_*.json` |
| **F20** | Medium (reproducibility) | `ayu-sat-table-a.xlsx` is actually a legacy **OLE2 `.xls`** file. Reading it needs `xlrd`, which is **missing from `requirements.txt`**. `terminology.py` catches the error and prints a warning, so a fresh install silently builds an inventory **without NAMASTE**. | `file` → "CDFV2 Microsoft Excel"; `openpyxl` → `BadZipFile` |
| **F21** | Medium | Silent `except Exception: pass` in `translator._load_parallel_datasets()` (and elsewhere): a missing `pyarrow` makes the parallel-QA lookup empty with no warning. Translation quality then changes silently by environment. | `translator.py` |
| **F22** | Low (paper/code mismatch) | The paper says RRF takes **20 candidates per branch**. `config.py` uses `BM25_TOP_K = DENSE_TOP_K = 10`. | paper §5.5, `config.py` |
| **F23** | Low | Corpus uses only a small slice of the raw data: 350 of 82,285 `qa_cleaned.csv` rows and 250 of 14,963 rows from each parquet. That is fine for a pilot, but the paper/README should state it. WHO chunk locators use physical PDF pages (printed page = physical − 18). Citations should say which convention they use. | `corpus_chunks.jsonl` source counts |

---

## 4. Numbers: paper vs README vs repository (preliminary; full reconciliation in Phase 8)

| Quantity | Paper | README / MD report | Repository (measured) |
|---|---|---|---|
| Indexed chunks | 8,782 | 968 passages | **2,887** (IMPPAT 1,328; API formulations 541; QA 350; HI parquet 250; KN parquet 250; WHO 128; NAMASTE 40) |
| Seed questions | 172 | 250 | **250** (dev 75 / test 175); dev run used **25** |
| Evaluation records | 8,294 | — | **100** per system (25 seeds × 4 variants) |
| B1 Recall@5 | 42.13% | 0.38 | **0.38** (CI [0.29, 0.48], record-level bootstrap) |
| P1 Recall@5 | 72% | 0.38 | **0.38**, identical to B1 (MRR 0.2395 both) |
| P2 Recall@5 / MRR | 85.4% / 0.8102 | — | **never run** |
| Go/No-Go corruption | 100% | 100% | **not measured** (static strings, F12) |
| Abstention accuracy | — | 100% | **0.0** in JSON. Live check: 0/16 unsafe queries abstain (F15) |

**Plain conclusion:** none of the paper's §6 results numbers can be traced to anything in the repository. The repository's own (weakly-defined) metrics show **no difference between B1 and P1**. The paper's §6 claims ("terminology preservation is useful", "P2 … 85.4%") are currently **unsupported** and must not be repeated until Phase 8 produces real measurements.

---

## 5. What works today (keep it working)

- Script/language detection, the terminology matcher with Kannada suffix stripping (`ದೋಷವನ್ನು → Dosha` was detected correctly), placeholder protection/restoration, BM25 + char-TF-IDF RRF fusion, chunk provenance (`source_id`, `locator`, `citation_tag`), the educational disclaimer, and the symptom mapper's red-flag check for EN / romanized / Kannada.
- 26/26 tests pass once paths are resolved correctly.

## 6. Re-prioritisation recommended for Phase 1

1. **F15/F16 safety gaps should be fixed first, in Phase 1, not later.** Reuse the existing `EducationalSymptomMapper` red-flag logic plus a dosage/prescription intent check inside `rag_pipeline.process_query` before retrieval. This is additive: existing callers keep the same signature, and the result just gains `abstained=True` with a reason. Add tests for all 16 queries above.
2. F8 (case-insensitive path resolution), F9 (rebuild pickles after backing up to `Data/processed/_v1_backup/`), F10, F20 (`xlrd` in requirements), F21 (log instead of silently passing).
3. F17/F18 evaluator fixes are Phase 8 work. Keep the old evaluator as `v1` for comparison.

## 7. Blockers for later phases (in this cloud workspace)

- **Phase 2 (IndicTrans2, sentence-transformers), Phase 5 (faster-whisper, edge-tts, gTTS), Phase 6 (FastAPI) and Phase 7 (npm/Vite/React) need PyPI, Hugging Face and npm access.** All three are blocked here. Options: (a) allow `pypi.org`, `files.pythonhosted.org`, `huggingface.co`, `registry.npmjs.org` for this workspace; (b) run those phases on the user's own machine; (c) build code + fallbacks here, unverified against real models (they would be clearly labelled as such in `KNOWN_LIMITATIONS.md`).

---

## 8. Addendum — findings made during Phases 1–8

| # | Severity | Finding | Where handled |
|---|---|---|---|
| **F24** | Medium | Output-side restoration (`restore_to_language`) is a no-op: the extractive generator never puts placeholders into the answer. The "output restoration" ablation therefore cannot show an effect. | Real output-side protection added for neural EN→HI/KN answer translation (`translate_answer_text`); ablation reports 0.0 honestly |
| **F25** | High (evaluation validity) | Every answerable benchmark question's text appears inside an indexed chunk (QA rows / BhashaBench rows). English retrieval is close to a lookup, and an untranslated native-script baseline beats P1. | Reported in `docs/research_findings_v2.md`, `PAPER_RECONCILIATION.md` |
| **F26** | Medium | Some "Hindi"/"Kannada" variants are English sentences with a short native-script prefix (e.g. "आयुर्वेदिक दृष्टिकोण से: What is typically advised…"). | Reported; benchmark review needed |
| **F27** | Medium | Several `gold_concept` values are topic labels ("General", "Prasutitantra"), so the v1 concept-match metric is meaningless for them. | v2 uses gold passages derived by code |
| **F28** | Low | P1's re-ranking boost (+0.05 per matched term, ~3× a typical RRF score) is extra processing that B1 does not get; the small P1 − B1 difference comes from it, not from protection (input-protection-off ablation: −0.1 pts). | Separate `P1-grounding-boost-off` ablation |
| **F29** | Low | Compound terms such as मंदाग्नि (Mandagni) are not detected by the matcher. | Listed in `KNOWN_LIMITATIONS.md` |
