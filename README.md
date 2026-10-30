# AyurMitra 🌿

**A Terminology-Preserving Multilingual RAG System with Knowledge Graph Grounding for Ayurvedic Knowledge Retrieval**

---

## 📌 Overview

AyurMitra is an academic research system designed to evaluate whether explicit preservation and canonicalization of Ayurvedic terminology improves retrieval accuracy and evidence grounding in multilingual Question Answering (English, Hindi, Kannada, and Romanized/Code-mixed queries).

### Key Features
- **Multilingual Input Handling:** Script identification and tokenization for English, Devanagari (Hindi), Kannada, and Romanized text.
- **Terminology Protection Layer:** Prevents translation drift (e.g. *Dhatu* -> "metal", *Agni* -> "fire", *Pitta* -> "bile") via tokenized placeholders and canonical restoration.
- **Traceable Corpus Ingestion:** Ingests 968 passages across WHO Ayurveda Guidelines, NAMASTE, IMPPAT 2.0, The Ayurvedic Pharmacopoeia of India, and literature QA records.
- **Hybrid Retrieval (RRF k=60):** Fuses Okapi BM25 lexical precision with dense multilingual semantic vector space.
- **Strict Evidence Grounding & Abstention:** Mandates exact source citations and automatically abstains when evidence is missing, ambiguous, or acute.
- **Lightweight Knowledge Graph:** NetworkX directed graph encoding Doshas, principles, herbs, and educational symptom associations with provenance.
- **Interactive Web Interface:** Streamlit UI for comparing B0, B1, P1, and P2 configurations live.

---

## 🚀 Quickstart

### 1. Installation
Ensure Python 3.10+ (tested on Python 3.13) is active:
```bash
pip install -r requirements.txt
```

### 2. Ingest Corpus & Build Terminology Index
```bash
python -m app.core.terminology
python -m app.core.corpus_builder
```

### 3. Run Automated Tests
```bash
python -m pytest tests/test_ayurmitra.py -v
```

### 4. Run Research Experiments
- **Week 1 Go/No-Go Probe:**
  ```bash
  python -m app.evaluation.go_no_go_probe
  ```
- **Generate 250-Seed Evaluation Benchmark (30% Dev / 70% Test):**
  ```bash
  python -m app.evaluation.benchmark_builder
  ```
- **Execute B0 vs B1 vs P1 Comparative Evaluation:**
  ```bash
  python -m app.evaluation.evaluator
  ```

### 5. Launch Interactive Interface
```bash
streamlit run web/app.py
```

---

## 📂 Project Architecture

```
NLP-CIE3/
├── app/
│   ├── config.py                 # Centralized configuration & paths
│   ├── core/
│   │   ├── language_detect.py    # Script & language identification
│   │   ├── terminology.py        # Terminology inventory builder
│   │   ├── matcher.py            # Multilingual & inflection-aware term matcher
│   │   ├── protection.py         # Term protection & restoration
│   │   ├── corpus_builder.py     # Traceable corpus chunking & ingestion
│   │   ├── knowledge_graph.py    # NetworkX provenance graph
│   │   └── symptom_mapper.py     # Cautious educational symptom mapper
│   ├── pipeline/
│   │   ├── bm25_retriever.py     # Okapi BM25 lexical retriever
│   │   ├── dense_retriever.py    # Multilingual dense semantic retriever
│   │   ├── hybrid_retriever.py   # Reciprocal Rank Fusion (RRF k=60)
│   │   ├── translator.py         # Multilingual translation handler
│   │   ├── generator.py          # Evidence-grounded generation & abstention
│   │   └── rag_pipeline.py       # Integrated B0 / B1 / P1 / P2 pipeline
│   └── evaluation/
│       ├── go_no_go_probe.py     # Terminology corruption probe
│       ├── benchmark_builder.py  # 250-seed benchmark generator
│       └── evaluator.py          # Research evaluation & bootstrap CIs
├── data/
│   ├── processed/                # Derived corpus, indices, and graphs
│   └── evaluation/               # Seeds, splits, probe and run results
├── docs/
│   ├── data_audit_and_licensing.md
│   └── research_findings_and_experiment_report.md
├── tests/
│   └── test_ayurmitra.py         # Automated pytest suite
├── web/
│   └── app.py                    # Streamlit web UI
├── requirements.txt
└── README.md
```

---

## ⚠️ Safety & Research Disclaimer

AyurMitra is an educational Ayurveda knowledge retrieval system, not a clinical diagnostic tool. It does not provide medical prescriptions, dosages, or biomedical diagnoses. Consult a qualified medical practitioner for health concerns.

