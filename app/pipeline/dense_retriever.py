"""
AyurMitra — Multilingual Dense Semantic Retriever
===================================================
Two interchangeable backends behind ``config.DENSE_BACKEND``:

* ``sentence_transformers`` — real multilingual sentence embeddings
  (default model: ``sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2``),
  embeddings cached at ``Data/processed/embeddings.npy`` (+ ``embeddings_meta.json``),
  exact cosine search with numpy (2,887 chunks — FAISS is unnecessary at this size).
* ``tfidf`` — the ORIGINAL v1 behaviour: character n-gram (3–5, ``char_wb``)
  TF-IDF with cosine similarity. This is *not* a neural dense model; it is kept
  as the fallback and so that v1 results stay reproducible.

``auto`` tries sentence-transformers and silently falls back to TF-IDF.
``self.backend_used`` and each result's ``dense_backend`` record what really ran.
"""

from __future__ import annotations

import json
import logging
import pickle
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import (
    CORPUS_JSONL, DENSE_INDEX_PKL, DENSE_TOP_K, DENSE_BACKEND, DENSE_MODEL_NAME, EMBEDDINGS_NPY,
    GEMINI_API_KEY, GEMINI_EMBEDDING_MODEL
)
from app.pipeline.bm25_retriever import QUESTION_STOPWORDS
from app.pipeline.index_cache import make_stamp, stamp_matches, backup_once
from app.pipeline.gemini_provider import GeminiProvider

log = logging.getLogger("ayurmitra.dense")

EMBEDDINGS_META = EMBEDDINGS_NPY.with_name("embeddings_meta.json")


class DenseRetriever:
    """Multilingual dense semantic retriever (sentence-transformers or TF-IDF fallback)."""

    def __init__(self, corpus_path: Path = CORPUS_JSONL, index_path: Path = DENSE_INDEX_PKL,
                 backend: Optional[str] = None):
        self.corpus_path = corpus_path
        self.index_path = index_path
        self.chunks: List[Dict[str, Any]] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.doc_matrix = None
        self.requested_backend = (backend or DENSE_BACKEND or "tfidf").lower()
        self.backend_used = "tfidf"
        self.backend_warning: Optional[str] = None
        self._st_model = None
        self._embeddings: Optional[np.ndarray] = None
        from app.pipeline.gemini_provider import get_gemini_provider
        self.gemini_provider = get_gemini_provider()

        # The TF-IDF index is always available (fallback + v1 reproducibility).
        self._load_or_build()
        if self.requested_backend in ("gemini", "gemini_embeddings") or (self.requested_backend == "auto" and self.gemini_provider.is_available()):
            self._try_init_gemini_embeddings()
        elif self.requested_backend in ("auto", "sentence_transformers"):
            self._try_init_sentence_transformers()

    # ── TF-IDF (v1) ──────────────────────────────────────────────────────────
    def _load_or_build(self) -> None:
        if self.index_path.exists():
            try:
                with open(self.index_path, "rb") as f:
                    data = pickle.load(f)
                if stamp_matches(data.get("_stamp"), self.corpus_path):
                    self.vectorizer = data["vectorizer"]
                    self.doc_matrix = data["doc_matrix"]
                    self.chunks = data["chunks"]
                    return
                log.warning("Dense TF-IDF index stamp missing/mismatched (F9) — rebuilding.")
            except Exception as e:
                log.warning("Could not load dense index (%s) — rebuilding.", e)
            backup_once(self.index_path)

        self._build_index()

    def _read_chunks(self) -> List[Dict[str, Any]]:
        chunks = []
        if self.corpus_path.exists():
            with open(self.corpus_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        chunks.append(json.loads(line))
        return chunks

    def _build_index(self) -> None:
        self.chunks = self._read_chunks()
        if not self.chunks:
            return
        corpus_texts = [c["text"] for c in self.chunks]
        # Multi-script character & word n-grams capture subwords, suffixes, and cross-script terms
        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            max_features=25000,
            sublinear_tf=True
        )
        self.doc_matrix = self.vectorizer.fit_transform(corpus_texts)

        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "wb") as f:
            pickle.dump({
                "vectorizer": self.vectorizer,
                "doc_matrix": self.doc_matrix,
                "chunks": self.chunks,
                "_stamp": make_stamp(self.corpus_path),
            }, f)

    # ── sentence-transformers (v2) ────────────────────────────────────────────
    def _try_init_sentence_transformers(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception:
            self.backend_warning = "sentence-transformers not installed — using char-n-gram TF-IDF fallback"
            return
        try:
            self._st_model = SentenceTransformer(DENSE_MODEL_NAME)
            corpus_sha = make_stamp(self.corpus_path)["corpus_sha256"]
            meta = {}
            if EMBEDDINGS_META.exists():
                meta = json.loads(EMBEDDINGS_META.read_text(encoding="utf-8"))
            if (EMBEDDINGS_NPY.exists() and meta.get("model") == DENSE_MODEL_NAME
                    and meta.get("corpus_sha256") == corpus_sha and meta.get("n") == len(self.chunks)):
                self._embeddings = np.load(EMBEDDINGS_NPY)
            else:
                log.warning("Encoding %d chunks with %s (one-time)...", len(self.chunks), DENSE_MODEL_NAME)
                emb = self._st_model.encode([c["text"] for c in self.chunks], batch_size=64,
                                            show_progress_bar=False, normalize_embeddings=True)
                self._embeddings = np.asarray(emb, dtype=np.float32)
                EMBEDDINGS_NPY.parent.mkdir(parents=True, exist_ok=True)
                np.save(EMBEDDINGS_NPY, self._embeddings)
                import sentence_transformers as _st
                EMBEDDINGS_META.write_text(json.dumps({
                    "model": DENSE_MODEL_NAME, "corpus_sha256": corpus_sha, "n": len(self.chunks),
                    "dim": int(self._embeddings.shape[1]), "sentence_transformers": _st.__version__,
                    "normalized": True,
                }, indent=1), encoding="utf-8")
            self.backend_used = "sentence_transformers"
            self.backend_warning = None
        except Exception as e:  # model download blocked, OOM, etc.
            self._st_model = None
            self._embeddings = None
            self.backend_warning = f"Embedding model unavailable ({type(e).__name__}) — using TF-IDF fallback"
            log.warning(self.backend_warning)

    # ── Gemini Embeddings (Section 6) ─────────────────────────────────────────
    def _try_init_gemini_embeddings(self) -> None:
        if not self.gemini_provider.is_available():
            self.backend_warning = "Gemini API key not configured — using TF-IDF fallback"
            return
        try:
            from app.config import resolve_data_file, GEMINI_EMBEDDINGS_NPY, GEMINI_EMBEDDINGS_META
            gemini_npy = resolve_data_file(GEMINI_EMBEDDINGS_NPY)
            gemini_meta = resolve_data_file(GEMINI_EMBEDDINGS_META)
            corpus_sha = make_stamp(self.corpus_path)["corpus_sha256"]
            if gemini_npy.exists() and gemini_meta.exists():
                meta = json.loads(gemini_meta.read_text(encoding="utf-8"))
                if (meta.get("model") == self.gemini_provider.embedding_model and
                        meta.get("corpus_sha256") == corpus_sha and meta.get("n") == len(self.chunks)):
                    self._embeddings = np.load(gemini_npy)
                    self.backend_used = "gemini_embeddings"
                    self.backend_warning = None
                    return
            self.backend_used = "gemini_embeddings"
            self.backend_warning = None
        except Exception as e:
            self.backend_warning = f"Gemini embeddings error ({e}) — using TF-IDF fallback"
            log.warning(self.backend_warning)

    @property
    def model_name(self) -> str:
        if self.backend_used == "gemini_embeddings":
            return self.gemini_provider.embedding_model
        return DENSE_MODEL_NAME if self.backend_used == "sentence_transformers" else "tfidf_char_wb_3-5"

    def retrieve(self, query: str, top_k: int = DENSE_TOP_K) -> List[Dict[str, Any]]:
        """
        Retrieve top_k semantic passages using cosine similarity in dense space.
        Returns list of chunks with 'dense_score', 'rank' and 'dense_backend'.
        """
        if not self.chunks or not query or not query.strip():
            return []

        if self.backend_used == "gemini_embeddings" and self.gemini_provider.is_available():
            try:
                q_emb = self.gemini_provider.embed_text(query, task_type="RETRIEVAL_QUERY")
                if q_emb and self._embeddings is not None:
                    q_arr = np.asarray(q_emb, dtype=np.float32)
                    q_norm = q_arr / (np.linalg.norm(q_arr) + 1e-9)
                    scores = (self._embeddings @ q_norm).astype(float)
                    min_score = 0.05
                else:
                    raise ValueError("Document embeddings not preloaded")
            except Exception:
                tokens = [w for w in re.findall(r"\b[a-zA-Z0-9_ऀ-ॿಀ-೿\-]{2,}\b", query.lower())
                          if w not in QUESTION_STOPWORDS]
                clean_query = " ".join(tokens) if tokens else query
                q_vec = self.vectorizer.transform([clean_query])
                scores = cosine_similarity(q_vec, self.doc_matrix).flatten()
                min_score = 0.01
        elif self.backend_used == "sentence_transformers" and self._embeddings is not None:
            q = self._st_model.encode([query], normalize_embeddings=True, show_progress_bar=False)
            scores = (self._embeddings @ np.asarray(q, dtype=np.float32)[0]).astype(float)
            min_score = 0.05
        else:
            if self.vectorizer is None or self.doc_matrix is None:
                return []
            # Filter out generic question/filler words for semantic scoring
            tokens = [w for w in re.findall(r"\b[a-zA-Z0-9_ऀ-ॿಀ-೿\-]{2,}\b", query.lower())
                      if w not in QUESTION_STOPWORDS]
            clean_query = " ".join(tokens) if tokens else query
            q_vec = self.vectorizer.transform([clean_query])
            scores = cosine_similarity(q_vec, self.doc_matrix).flatten()
            min_score = 0.01

        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for rank, idx in enumerate(top_indices, start=1):
            score = float(scores[idx])
            if score <= min_score:
                continue
            chunk = dict(self.chunks[idx])
            chunk["dense_score"] = score
            chunk["rank"] = rank
            chunk["dense_backend"] = self.backend_used
            results.append(chunk)
        return results
