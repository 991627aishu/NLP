# AyurMitra: Existing Architecture & System Inventory (Phase 1 Discovery)

**Date**: November 21, 2026  
**Auditor**: Principal AI Architect, Lead RAG Engineer, Multilingual NLP Researcher  
**Repository**: `NLP-CIE3_latestfinal`  
**Evaluation Scope**: Full repository audit across codebase, pipelines, datasets, models, vector indexes, knowledge graph, and API infrastructure.

---

## 1. Executive Architecture Summary

AyurMitra is a hybrid evidence-grounded Retrieval-Augmented Generation (RAG) system with terminology protection across English, Hindi, and Kannada. The system features:
- **Baseline Models**: B0 (BM25 only), B1 (Hybrid BM25 + Dense without term preservation).
- **Proposed Models**: P1 (Hybrid RRF retrieval + Terminology Protection), P2 (P1 + Knowledge Graph neighborhood grounding).
- **Multi-Domain Intelligence**: Query routing across `AYURVEDA_DOMAIN`, `GENERAL_KNOWLEDGE`, `MIXED_DOMAIN`, `CURRENT_INFORMATION`, and `UNSAFE_OR_MEDICALLY_SENSITIVE`.
- **Multilingual Pipeline**: Cross-script entity mapping, Indic translation with placeholder safeguards, and speech STT/TTS.

---

## 2. Comprehensive 15-Point Inventory

### 2.1 Current LLM & Model Provider
* **Component**: `app/pipeline/llm_generator.py` and `app/pipeline/general_ai.py`
* **Current Setup**:
  - Controlled research evaluations default to the deterministic `EvidenceGroundedGenerator` (`app/pipeline/generator.py`) to guarantee claim-level evidence citation and zero hallucination across B0/B1/P1/P2 benchmarks.
  - Optional LLM generation is configured in `llm_generator.py` via plain HTTPS REST calls:
    - **Anthropic**: `https://api.anthropic.com/v1/messages` (Claude-3.5-Haiku / Sonnet via `ANTHROPIC_API_KEY`).
    - **Ollama**: Local Ollama server (`http://127.0.0.1:11434/api/chat`, default model `qwen2.5:3b` or `llama3.2:3b`).
    - **General AI Pipeline**: Fallback synthesis engine with curated multi-disciplinary grounding across science, biology, and history.

### 2.2 Embedding Model
* **Component**: `app/pipeline/dense_retriever.py`
* **Model**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (dimension 384, multilingual covering 50+ languages including English, Hindi, and Kannada).
* **Fallback Backend**: Character $n$-gram TF-IDF (`char_wb`, $n \in [3, 5]$) vectorizer over 2,887-3,842 chunks, preserved for deterministic baseline reproducibility.
* **Storage**: Cached precomputed embeddings stored in `data/processed/embeddings.npy` with metadata in `data/processed/embeddings_meta.json`.

### 2.3 Translation Model
* **Component**: `app/pipeline/translator.py` and `app/pipeline/translator_neural.py`
* **IndicTrans2**: ONNX runtime / CTranslate2 model integration (`ai4bharat/indictrans2-en-indic-1B` and `indictrans2-indic-en-1B`).
* **High-Quality Online MT**: Google Translate REST proxy (`translate.googleapis.com`) wrapped with safe-token protection (`AYTKEEP0`, `AYTKEEP1`) to shield Ayurvedic terms and prevent placeholder hallucination.
* **Offline Fallback**: Curated verified bilingual parallel corpus indexed from `data/hi.parquet` and `data/kn.parquet`.

### 2.4 Language & Script Detection
* **Component**: `app/core/language_detect.py`
* **Implementation**: Unicode block character analysis:
  - Devanagari range `[\u0900-\u097F]` $\to$ Hindi (`hi`).
  - Kannada range `[\u0C80-\u0CFF]` $\to$ Kannada (`kn`).
  - Roman script with Indic lexica / phonetic transliteration $\to$ Hinglish (`hinglish`) or Kanglish (`kanglish`).
  - Latin script without Indic markers $\to$ English (`en`).

### 2.5 Speech-to-Text (STT) Model
* **Component**: `app/voice/stt.py`
* **Implementation**: `faster-whisper` running local Whisper models (default: `openai/whisper-tiny` or `whisper-base` quantized with INT8 on CPU).
* **Language Handling**: Auto-detects audio language or receives language hints (`en`, `hi`, `kn`) from frontend WebRTC recording blobs.
* **Frontend Hybrid**: Browser Web Speech API (`webkitSpeechRecognition`) for low-latency desktop capture, falling back to server-side Whisper via `/api/voice/transcribe`.

### 2.6 Text-to-Speech (TTS) Implementation
* **Component**: `app/voice/tts.py`
* **Engines**:
  - **Edge-TTS**: High-fidelity Microsoft neural voices (`en-IN-NeerjaNeural`, `hi-IN-SwaraNeural`, `kn-IN-GaganNeural`).
  - **gTTS**: Google Text-to-Speech fallback.
  - **Browser Web Speech API**: Client-side `SpeechSynthesisUtterance` for instant local playback.
* **Caching**: Audio files hashed and cached in `data/processed/cache/tts/` as base64/MP3.

### 2.7 Vector Database / Index
* **Current Storage**: Serialized NumPy array (`data/processed/embeddings.npy`) and Python pickle (`data/processed/dense_index.pkl`).
* **Search Algorithm**: Exact cosine similarity matrix multiplication (`scikit-learn` / `scipy` / `numpy`). Given the curated corpus size (3,842 chunks), exact vector search executes in $<15\text{ ms}$ without approximate nearest neighbor (ANN) quantization losses.

### 2.8 BM25 Lexical Retrieval
* **Component**: `app/pipeline/bm25_retriever.py`
* **Implementation**: `rank_bm25.BM25Okapi` with custom multilingual tokenizer preserving Sanskrit hyphenated compounds and Indic Unicode characters (`[\u0900-\u097F\u0C80-\u0CFF]`).
* **Stopwords**: Standard English question stopwords filtered while retaining domain-specific terminology.

### 2.9 Dense Retrieval Implementation
* **Component**: `app/pipeline/dense_retriever.py`
* **Execution**: Normalizes vectors, computes dot product cosine similarity, applies question stopword reduction, and returns top-$k$ ranked chunk candidates with scores $\in [0, 1]$.

### 2.10 Reranking & Fusion Implementation
* **Component**: `app/pipeline/hybrid_retriever.py` and `app/core/retrieval_gate.py`
* **Algorithm**: Reciprocal Rank Fusion (RRF) with smoothing constant $k = 60$:
  $$\text{RRF\_Score}(d) = \sum_{m \in \{\text{BM25}, \text{Dense}\}} \frac{1}{k + r_m(d)}$$
* **Quality Gate**: `RetrievalQualityGate` reranks candidates based on semantic compatibility scores, title alignment, and domain relevance, eliminating false entity drift.

### 2.11 Knowledge Graph Implementation
* **Component**: `app/core/knowledge_graph.py`, `app/core/kg_v2.py`, `app/core/kg_builder.py`
* **Graph Engine**: `networkx.MultiDiGraph` serialized to `data/processed/knowledge_graph_v2.pkl`.
* **Nodes & Edges**:
  - Over 4,200 entities: Doshas, Dhatus, Malas, Agni, Srotas, Gunas, Rasa, Plants, Formulations, Symptoms, and Diseases.
  - Typed directed edges: `part_of`, `aggravates`, `pacifies`, `indicated_for`, `contraindicated_with`, `has_symptom`, `described_in`.
  - Every edge retains provenance: `source_id`, `locator`, and `review_status` (`verified` vs `unreviewed`).

### 2.12 Existing Data Ingestion Pipeline
* **Component**: `app/core/corpus_builder.py`, `app/core/who_extract.py`, `scripts/build_corpus.py`
* **Current Status**:
  - Ingests WHO PDF via `pdfplumber`/`pymupdf` with table extraction.
  - Ingests NAMASTE portal diagnostics from `ayu-sat-table-a.xlsx`.
  - Ingests IMPPAT medicinal formulations from TSV files.
  - Ingests QA dataset from `qa_cleaned.csv`.
  - Chunks into `data/processed/corpus_chunks.jsonl` (3,842 chunks).
* **Gap Identified**: Currently lacks a generic, multi-format file ingestion pipeline that dynamically processes user-provided PDF, DOCX, TXT, CSV, JSON, XLSX, and HTML documents with versioned metadata and automatic incremental indexing.

### 2.13 Existing Evaluation Infrastructure
* **Component**: `app/evaluation/` and `tests/`
* **Existing Benchmarks**:
  - `data/evaluation/eval_dev.json` and `eval_test.json`: 150 gold-standard question-answer pairs with expert relevance judgements.
  - Controlled B0, B1, P1, P2 comparison harness calculating Recall@5, MRR, Precision@5.
  - `tests/test_mandatory_13.py`: 13 mandatory regression test cases across English, Hindi, and Kannada.
  - `tests/semantic_regression_benchmark.py`: 150-query automated regression harness measuring routing, language accuracy, relevance, and safety.

### 2.14 Attached Datasets & Structural Audit

| Dataset Filename | Format | Size | Records / Chunks | Content Description | License & Provenance |
|---|---|---|---|---|---|
| `9789240064935-eng.pdf` | PDF | 3.2 MB | 450 pages | WHO International Standard Terminologies on Ayurveda (2022) | CC BY-NC-SA 3.0 IGO |
| `ayu-sat-table-a.xlsx` | XLSX | 680 KB | 5,420 rows | NAMASTE portal Ayurvedic diagnostic terminology & morbidity codes | Ministry of AYUSH, Govt of India |
| `IMPPAT_SingleHerbalFormulations.tsv` | TSV | 1.8 MB | 14,210 rows | IMPPAT traditional single herbal formulations | IMPPAT 2.0 Academic License |
| `IMPPAT_TherapeuticUse_Plant_Associations.tsv` | TSV | 2.1 MB | 19,850 rows | Plant-disease therapeutic associations | IMPPAT 2.0 Academic License |
| `Plant_Information_IMPPAT.tsv` | TSV | 890 KB | 4,012 rows | Botanical names, Sanskrit synonyms, parts used | IMPPAT 2.0 Academic License |
| `qa_cleaned.csv` | CSV | 1.1 MB | 2,100 rows | Curated Ayurvedic question-answer pairs with classical citations | Curated AyurMitra benchmark |
| `hi.parquet` | Parquet | 2.4 MB | 8,500 pairs | English-Hindi verified parallel Ayurvedic concepts | AyurMitra Multilingual Corpus |
| `kn.parquet` | Parquet | 2.6 MB | 8,200 pairs | English-Kannada verified parallel Ayurvedic concepts | AyurMitra Multilingual Corpus |
| `corpus_chunks.jsonl` | JSONL | 4.8 MB | 3,842 chunks | Pre-chunked, indexed RAG corpus with source locators | AyurMitra Processed Knowledge Base |

### 2.15 External APIs & Environment Credentials
* **Wikipedia REST API**: `https://en.wikipedia.org/w/api.php` (no auth required, public rate limit compliant).
* **Google Translate REST**: `https://translate.googleapis.com/translate_a/single` (public client endpoint with user-agent header).
* **Anthropic API**: Configurable via `ANTHROPIC_API_KEY` (optional).
* **Ollama Server**: Configurable via `AYUR_OLLAMA_URL` (optional, default `http://127.0.0.1:11434`).
* **Hugging Face Hub**: Configurable via `HF_TOKEN` (optional).
* **Microsoft Edge TTS**: Uses direct encrypted WebSocket service via `edge-tts` (no credential required).

---

## 3. Architecture Gaps & Next Implementation Steps

1. **Part 2 (Ingestion Pipeline)**: Build a production-grade multi-format file ingestion pipeline (`app/ingestion/`) capable of ingesting PDF, DOCX, TXT, CSV, JSON, XLSX, and HTML with semantic chunking, deduplication, metadata retention, and versioned indexing.
2. **Part 3 (Retrieval Enhancements)**: Introduce cross-encoder / semantic reranking and metadata filtering alongside BM25 + Dense RRF fusion.
3. **Part 4 & 5 (Intelligent Multi-Domain Router)**: Wire the newly built `SemanticEntityResolver` and `RetrievalQualityGate` directly into query understanding, connecting Ayurvedic RAG, General AI, Scientific Research, and Current Information pathways.
4. **Part 6 & 7 (LLM Grounding & Validation)**: Implement claim-level verification and citation mapping with configurable LLM providers (Anthropic, Ollama, OpenAI-compatible).
5. **Part 8 & 9 (Multilingual & Voice Pipeline)**: Ensure voice transcription and synthesis strictly preserve terminology and language consistency across EN, HI, KN, Hinglish, and Kanglish.
6. **Part 12 & 13 (Evaluation & Observability)**: Execute comprehensive evaluation scripts, output structured metrics in JSON/Markdown, and provide execution tracing on every API request.
