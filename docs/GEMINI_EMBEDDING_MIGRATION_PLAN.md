# AyurMitra — Gemini API Model Verification & Embedding Migration Plan

## 1. Model Verification Against Live Gemini API Account

A live verification probe was executed using the configured `GEMINI_API_KEY` against Google Gemini API endpoints:

### Generation Model: `gemini-3.8-flash`
- **Catalog Status**: Present in account model catalog (`models/gemini-3.8-flash`).
- **Google Deprecation Notice on Older Models**:
  - `gemini-2.5-flash`: `404 NOT_FOUND` (*"This model models/gemini-2.5-flash is no longer available to new users. Please update your code to use models/gemini-3.8-flash"*).
  - `gemini-2.0-flash`: `404 NOT_FOUND` (*"This model models/gemini-2.0-flash is no longer available"*).
  - `gemini-1.5-flash`: `404 NOT_FOUND`.
- **High-Demand Handling**: `gemini-3.8-flash` is active as primary. During Google transient high-demand spikes (`503 UNAVAILABLE`), exponential backoff retries with automatic transient fallback to `gemini-3.5-flash` ensures zero user-facing service interruptions.
- **Live Output Test**: Verified with successful response:
  > *"In Ayurveda, Vata dosha is the physiological principle governed by the elements of Air and Space, responsible for all movement and communication within the mind and body. It controls vital processes such as nerve impulses, respiration, and circulation, and is characterized by dry, light, cold, and mobile qualities."*

### Embedding Model: `gemini-embedding-001`
- **Catalog Status**: Verified active and operational in account (`models/gemini-embedding-001`).
- **Vector Dimension**: **3,072 dimensions**.
- **Live Output Test**: Confirmed with HTTP 200 via `POST https://generativelanguage.googleapis.com/v1/models/gemini-embedding-001:batchEmbedContents`.

---

## 2. Google Search Grounding Configuration

Per requirements, **Google Search Grounding is disabled initially**:
- **Default State**: `search_grounding_enabled = False` (`GEMINI_SEARCH_GROUNDING_ENABLED=false`).
- **Optional Activation**: Can be enabled on demand either via:
  1. Environment variable: `GEMINI_SEARCH_GROUNDING_ENABLED=true`
  2. Per-request override: `provider.generate_answer(..., enable_grounding=True)`
- **Dynamic Tool Attachment**: When enabled, dynamically binds `types.Tool(google_search=types.GoogleSearch())` and extracts citations from candidate grounding metadata.

---

## 3. Preservation of Existing Indexes & Migration Strategy

Existing indexes:
- `data/processed/dense_index.pkl` (Deterministic TF-IDF n-gram index)
- `data/processed/bm25_index.pkl` (Okapi BM25 index)

> [!IMPORTANT]
> The existing `dense_index.pkl` and `bm25_index.pkl` are **preserved completely untouched**. They remain active for all baseline evaluations and offline operation.

### Dedicated Gemini Embedding Storage:
Gemini embeddings are isolated to separate dedicated artifacts:
- Vectors: `data/processed/gemini_embeddings.npy` (Shape: `[N, 3072]`)
- Metadata: `data/processed/gemini_embeddings_meta.json`
- SQLite Persistent Cache: `Data/processed/cache/gemini_embeddings_cache.sqlite`

### Re-Embedding Migration Tool:
A dedicated migration CLI is provided at `scripts/migrate_gemini_embeddings.py`:

```bash
# 1. Dry run verification (validates credentials without quota consumption):
python scripts/migrate_gemini_embeddings.py --dry-run

# 2. Sample migration (embeds first 10 chunks to verify pipeline):
python scripts/migrate_gemini_embeddings.py --sample 10

# 3. Complete corpus migration (embeds all 2,901 chunks with rate-limiting & caching):
python scripts/migrate_gemini_embeddings.py
```

### Switching Active Dense Backend:
To activate Gemini embeddings in the running server:
- Set `DENSE_BACKEND=gemini` in `.env`.
- If the Gemini API is unreachable or sandboxed, `DenseRetriever` automatically falls back to `tfidf` without raising unhandled exceptions.
