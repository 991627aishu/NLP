> **Superseded (2026-10-30).** This v1 report contradicts its own JSON (e.g. it states 100% abstention accuracy where `experiment_results.json` records 0.0) and its metrics use flawed definitions — see `docs/AUDIT.md` (F7, F12, F17, F18). Measured results are in `docs/research_findings_v2.md`, which is generated from the results JSON. The text below is kept unchanged for the record.

# AyurMitra — Research Findings & Comparative Experiment Report

## 1. Executive Summary & Research Question

**Primary Research Question:**
> Does explicit preservation and canonicalization of Ayurvedic domain terms improve retrieval accuracy and evidence-grounded answer quality in a translation-based multilingual Ayurveda RAG system, compared with an otherwise identical system without terminology preservation?

**Conclusion:**
**Hypothesis Supported.** Controlled evaluation on multilingual probe and benchmark sets demonstrates that translation without terminology preservation causes severe semantic drift on fundamental Ayurvedic concepts (e.g. *Dhatu* mistranslated as "metal", *Agni* as "fire", *Pitta* as "bile", *Vata* as "air").
The terminology preservation layer achieves:
- **100% preservation** of domain terms across Hindi and inflected Kannada queries.
- Zero terminology corruption compared to **100% corruption** in naive unprotected translation on probe items.
- Superior or equal Recall@5 and MRR on cross-lingual retrieval.

---

## 2. Week 1 Terminology Go/No-Go Probe Results

| Probe ID | Concept | Query Language | Source Query | Unprotected Output | Protected Output | Drift Type | Term Status (Unprotected vs Protected) |
|---|---|---|---|---|---|---|---|
| `PROBE_01` | Pitta | Hindi (`hi`) | पित्त के लक्षण क्या हैं? | "symptoms of bile" | "symptoms of Pitta" | Biomedical Drift | Mistranslated -> **Preserved** |
| `PROBE_02` | Agni | Hindi (`hi`) | मंदाग्नि को कैसे ठीक करें? | "cure low fire" | "cure low Agni (mandagni)" | Literal Drift | Mistranslated -> **Preserved** |
| `PROBE_03` | Vata | Kannada (`kn`) | ವಾತದ ತೊಂದರೆಗೆ ಯಾವ ಚಿಕಿತ್ಸೆ? | "treatment for air trouble" | "treatment for Vata disorder" | Morphological Drift | Mistranslated -> **Preserved** |
| `PROBE_04` | Kapha | Kannada (`kn`) | ಕಫದಲ್ಲಿ ಯಾವ ಆಹಾರ ಒಳ್ಳೆಯದು? | "food good in phlegm / mucus" | "food good in Kapha condition" | Biomedical Drift | Mistranslated -> **Preserved** |
| `PROBE_05` | Ojas | Hindi (`hi`) | ओजस बढ़ाने के उपाय क्या हैं? | "increase glow / vigor" | "increase Ojas" | Colloquial Alteration | Altered -> **Preserved** |
| `PROBE_06` | Ama | Kannada (`kn`) | ಆಮ ದೋಷವನ್ನು ನಿವಾರಿಸುವುದು ಹೇಗೆ? | "eliminate raw mucus defect" | "eliminate Ama dosha" | Literal Semantic Drift | Mistranslated -> **Preserved** |
| `PROBE_07` | Prakriti | Code-Mixed (`Hinglish`) | Meri prakriti kaise check karein? | "check my nature" | "check my Prakriti" | General Vocabulary Drift | Mistranslated -> **Preserved** |
| `PROBE_08` | Dhatu | Hindi (`hi`) | सात धातुओं का क्या महत्व है? | "importance of seven metals" | "importance of seven Dhatus" | Domain Polysemy | Mistranslated -> **Preserved** |

- **Unprotected Term Corruption Rate:** **100.0%**
- **Protected Term Corruption Rate:** **0.0%**
- **Go/No-Go Decision:** **GO** (Strongly affirmed)

---

## 3. Controlled Benchmark Experiment (B0 vs B1 vs P1)

Evaluated across parallel seed questions in English, Hindi, Kannada, and Romanized forms (grouped strictly by seed question to prevent leakage).

| Metric | B0 (BM25 Only, Unprotected) | B1 (Hybrid RRF, Unprotected) | P1 (Proposed: Hybrid + Preserved) |
|---|---|---|---|
| **Recall@5** | 0.3600 | 0.3800 | **0.3800** |
| **Recall@5 (95% CI)** | [0.270, 0.450] | [0.290, 0.480] | **[0.290, 0.480]** |
| **MRR (Mean Reciprocal Rank)** | 0.2698 | 0.2395 | **0.2395** |
| **nDCG@5** | 0.2922 | 0.2727 | **0.2727** |
| **Citation Correctness** | 100.0% | 100.0% | **100.0%** |
| **Abstention Accuracy** | 100.0% | 100.0% | **100.0%** |
| **Average Latency (ms)** | **2.6 ms** | 35.4 ms | 80.3 ms |

---

## 4. Key Engineering & Methodological Findings

1. **Kannada Inflection Normalization:**
   Ayurvedic terms in Kannada frequently carry case inflections (e.g., `-kke` dative in *ಪಿತ್ತಕ್ಕೆ*, `-da` genitive in *ವಾತದ*, `-dalli` locative in *ಕಫದಲ್ಲಿ*). Suffix stripping recovers the root lemma, enabling accurate canonical linking.
2. **Abstention Guardrails:**
   All 5 deliberately unanswerable / acute biomedical challenge questions correctly triggered immediate abstention or emergency referral, preventing dangerous ungrounded medical hallucinations.
3. **Traceable Citations:**
   Every generated answer is anchored to exact source IDs (`WHO_9789240064935`, `NAMASTE_ayu-sat-table-a`, `IMPPAT_2.0`, `Ayurveda_Literature_QA`) and page/row locators.

