# AyurMitra Project Status — Revision 5 (Final Research-Grade Implementation)

## Delivered in this Revision
- **Complete Test Suite (33/33 Passed)**:
  - 8 core normalization & dataset adapter tests (`test_core.py`)
  - 3 download link & regex parsing tests (`test_downloaders.py`)
  - 13 service, RAG abstention, citation indexing, and hybrid retrieval tests (`test_service.py`)
  - 9 NLP, multilingual understanding, ML classifier, emergency triage, and API tests (`test_nlp_and_evaluation.py`)
- **Offline Ollama Non-Blocking Socket Probe (`app/rag.py`)**:
  - Implemented `_is_ollama_alive(timeout=0.2)` to eliminate 120s Windows hanging when Ollama is offline.
  - Dynamically extracts citations (`[E1]`, `[E2]`) from grounded evidence.
  - Abstains safely on incomplete definitions and PDF table fragments.
- **Multilingual NLP & Ayurvedic Concept Preservation (`app/nlp.py`)**:
  - Comprehensive canonical Ayurvedic glossary across English, Sanskrit (IAST), Devanagari, and Kannada.
  - Botanical cross-reference mapping common and vernacular aliases (e.g., Tulsi -> *Ocimum tenuiflorum*, Ashwagandha -> *Withania somnifera*).
  - Colloquial Hinglish and Kanglish symptom mapping (e.g., "sir dard", "thale novu" -> headache; "bukhar", "kemmu" -> fever/cough).
  - Red-flag emergency triage detecting acute cardiovascular, neurological, respiratory, and crisis symptoms.
- **Academic Condition Classifier Baseline (`app/classifier.py`)**:
  - TF-IDF (1-2 n-grams) + Multinomial Naive Bayes trained on Columbia Disease-Symptom KB.
  - 1,119 samples across 134 conditions; 80/20 holdout evaluation.
  - Empirical metrics: Accuracy = 54.64%, Top-3 Accuracy = 70.71%, Top-5 Accuracy = 76.07%, Macro-F1 = 0.5373.
  - Calibrated confidence thresholding (0.08) and safe abstention on insufficient symptoms.
- **Explainable AI (XAI) Condition Scoring (`app/core.py`)**:
  - Transparent candidate scoring with matched symptoms list, query coverage %, and justification breakdown.
- **Empirical Retrieval Ablation Benchmark (`data/evaluation/gold_queries.jsonl`, `scripts/evaluate_retrieval.py`)**:
  - 18 multi-domain gold queries evaluated across 18,473 candidate passages.
  - Proposed System achieved P@1 = 0.2353, R@5 = 0.2059, MRR = 0.3402, nDCG@5 = 0.1965 (+24.4% MRR over BM25).
  - Successfully abstains on out-of-domain queries (1/1).
- **Web UI Overhaul & Live Browser Validation (`web/`)**:
  - Emerald-slate Ayurvedic visual identity with Google Outfit and Plus Jakarta Sans typography.
  - Live dataset status indicators, interactive quick-search chips, clickable citation anchoring (`[E1]`), XAI candidate cards with progress bars, and empirical benchmark monitor.
  - Validated via automated browser subagent on `http://127.0.0.1:8000` with recorded WebP session and captured screenshots.

## Local Data Verified & Usable
- **WHO Ayurveda Terminology PDF**: Present (608 pages, 1,023 chunks).
- **NAMASTE SAT-Combined**: Present (14,968 standardized terms).
- **IMPPAT 2.0**: Present (94,261 plant-part/therapeutic-use rows, 4,154 plants).
- **Columbia Disease-Symptom KB**: Present (1,898 disease-symptom pairs, 134 conditions).
- **AYUSH Evidence Register**: Present (file schema and draft template ready).

## Validation Instructions
```powershell
.venv\Scripts\activate
python -m unittest discover -s tests -v
python scripts\audit_datasets.py
python scripts\evaluate_retrieval.py
python -m uvicorn app.web_app:app --host 127.0.0.1 --port 8000
```
