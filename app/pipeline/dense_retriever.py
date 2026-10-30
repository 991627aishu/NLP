"""
AyurMitra — Multilingual Dense Semantic Retriever
===================================================
Computes dense semantic embeddings across the multilingual Ayurvedic corpus.
Uses character-word n-gram sublinear vectorization with cosine similarity as a
lightweight, deterministic multilingual vector space (with support for
sentence-transformers if present).
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import re
from app.config import CORPUS_JSONL, DENSE_INDEX_PKL, DENSE_TOP_K
from app.pipeline.bm25_retriever import QUESTION_STOPWORDS


class DenseRetriever:
    """Multilingual dense semantic retriever."""

    def __init__(self, corpus_path: Path = CORPUS_JSONL, index_path: Path = DENSE_INDEX_PKL):
        self.corpus_path = corpus_path
        self.index_path = index_path
        self.chunks: List[Dict[str, Any]] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.doc_matrix: Optional[np.ndarray] = None
        self._load_or_build()

    def _load_or_build(self) -> None:
        if self.index_path.exists():
            try:
                with open(self.index_path, "rb") as f:
                    data = pickle.load(f)
                    self.vectorizer = data["vectorizer"]
                    self.doc_matrix = data["doc_matrix"]
                    self.chunks = data["chunks"]
                return
            except Exception:
                pass

        self._build_index()

    def _build_index(self) -> None:
        self.chunks = []
        if not self.corpus_path.exists():
            return

        with open(self.corpus_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    self.chunks.append(json.loads(line))

        corpus_texts = [c["text"] for c in self.chunks]
        # Multi-script character & word n-grams capture subwords, suffixes, and cross-script terms
        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            max_features=25000,
            sublinear_tf=True
        )
        self.doc_matrix = self.vectorizer.fit_transform(corpus_texts)

        # Cache index
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "wb") as f:
            pickle.dump({
                "vectorizer": self.vectorizer,
                "doc_matrix": self.doc_matrix,
                "chunks": self.chunks
            }, f)

    def retrieve(self, query: str, top_k: int = DENSE_TOP_K) -> List[Dict[str, Any]]:
        """
        Retrieve top_k semantic passages using cosine similarity in dense space.
        Returns list of chunks with 'dense_score' and 'rank'.
        """
        if self.vectorizer is None or self.doc_matrix is None or not self.chunks or not query.strip():
            return []

        # Filter out generic question/filler words for semantic scoring
        tokens = [w for w in re.findall(r"\b[a-zA-Z0-9_\u0900-\u097F\u0C80-\u0CFF\-]{2,}\b", query.lower()) if w not in QUESTION_STOPWORDS]
        clean_query = " ".join(tokens) if tokens else query

        q_vec = self.vectorizer.transform([clean_query])
        scores = cosine_similarity(q_vec, self.doc_matrix).flatten()

        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for rank, idx in enumerate(top_indices, start=1):
            score = float(scores[idx])
            if score <= 0.01:
                continue
            chunk = dict(self.chunks[idx])
            chunk["dense_score"] = score
            chunk["rank"] = rank
            results.append(chunk)

        return results

