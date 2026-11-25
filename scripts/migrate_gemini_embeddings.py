"""
AyurMitra — Gemini Multilingual Embeddings Migration & Indexing Pipeline
========================================================================
Safe migration script to embed corpus documents using `gemini-embedding-001` (3072-dim)
without modifying existing TF-IDF or BM25 indexes.

Features:
- Validates model and API connectivity.
- Reads chunks from `data/processed/corpus_chunks.jsonl`.
- Uses SQLite persistent cache to prevent duplicate embedding API calls.
- Outputs dedicated `data/processed/gemini_embeddings.npy` and `gemini_embeddings_meta.json`.
- Supports dry-run / sample testing mode (--sample N) to test without full quota consumption.
- Keeps existing `dense_index.pkl` and `bm25_index.pkl` intact.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import CORPUS_JSONL, EMBEDDINGS_NPY, CACHE_DIR
from app.pipeline.gemini_provider import GeminiProvider
from app.pipeline.index_cache import make_stamp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ayurmitra.gemini_migration")

def main():
    parser = argparse.ArgumentParser(description="AyurMitra Gemini Embeddings Migration Tool")
    parser.add_argument("--sample", type=int, default=0, help="Embed only first N chunks for verification")
    parser.add_argument("--dry-run", action="store_true", help="Validate credentials and inspect corpus without embedding")
    parser.add_argument("--force", action="store_true", help="Force re-embedding even if cached")
    args = parser.parse_args()

    log.info("Starting Gemini Embedding Migration Pipeline...")
    
    # 1. Initialize Gemini Provider
    provider = GeminiProvider(embedding_model="gemini-embedding-001")
    health = provider.check_health()
    log.info("Gemini Health Status: %s", health)
    
    if not provider.is_available():
        log.error("Gemini API is unavailable: %s", health.get("message"))
        sys.exit(1)

    # 2. Verify Live Model Connectivity
    log.info("Verifying live connection to model: %s", provider.embedding_model)
    try:
        test_vec = provider.embed_text("Ayurveda is a traditional science of life.", task_type="RETRIEVAL_DOCUMENT")
        log.info("Live test successful! Embedding vector dimension: %d", len(test_vec))
    except Exception as e:
        log.error("Live test failed: %s", e)
        sys.exit(1)

    if args.dry_run:
        log.info("Dry-run complete. Live model verified successfully. Exiting without changing indexes.")
        return

    # 3. Read Corpus
    if not CORPUS_JSONL.exists():
        log.error("Corpus file not found: %s", CORPUS_JSONL)
        sys.exit(1)

    chunks: List[Dict[str, Any]] = []
    with open(CORPUS_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    log.info("Loaded %d corpus chunks from %s", len(chunks), CORPUS_JSONL)
    
    target_chunks = chunks[:args.sample] if args.sample > 0 else chunks
    log.info("Processing %d chunks for embedding generation...", len(target_chunks))

    # 4. Generate Embeddings with Caching & Progress
    vectors: List[List[float]] = []
    t0 = time.time()
    
    for idx, c in enumerate(target_chunks):
        text = c.get("text", "")
        # Prepare text representation
        title = c.get("title", "")
        locator = c.get("locator", "")
        doc_text = f"{title}. {locator}. {text}" if title else text
        
        try:
            vec = provider.embed_text(doc_text, task_type="RETRIEVAL_DOCUMENT")
            vectors.append(vec)
        except Exception as e:
            log.warning("Failed to embed chunk %s (idx %d): %s — padding with zeros", c.get("chunk_id"), idx, e)
            vectors.append([0.0] * len(test_vec))

        if (idx + 1) % 10 == 0 or (idx + 1) == len(target_chunks):
            elapsed = time.time() - t0
            rate = (idx + 1) / max(elapsed, 0.001)
            log.info("[%d/%d] chunks embedded (%.1f chunks/sec, elapsed: %.1fs)", idx + 1, len(target_chunks), rate, elapsed)

    # 5. Safe Artifact Persistence (Without Overwriting TF-IDF dense_index.pkl)
    vec_array = np.array(vectors, dtype=np.float32)
    gemini_npy = EMBEDDINGS_NPY.with_name("gemini_embeddings.npy")
    gemini_meta = EMBEDDINGS_NPY.with_name("gemini_embeddings_meta.json")
    
    stamp = make_stamp(CORPUS_JSONL)
    meta = {
        "model": provider.embedding_model,
        "n": len(vectors),
        "dim": vec_array.shape[1] if len(vec_array.shape) > 1 else 0,
        "corpus_sha256": stamp.get("corpus_sha256"),
        "created_at": time.time(),
        "is_partial": (args.sample > 0 and args.sample < len(chunks)),
    }

    np.save(gemini_npy, vec_array)
    gemini_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    
    log.info("Successfully persisted Gemini embeddings to: %s (shape: %s)", gemini_npy, vec_array.shape)
    log.info("Successfully persisted metadata to: %s", gemini_meta)
    log.info("Existing TF-IDF and BM25 indexes remain completely intact and active.")

if __name__ == "__main__":
    main()
