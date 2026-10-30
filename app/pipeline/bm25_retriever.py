"""
AyurMitra — BM25 Lexical Retriever
===================================
Lexical search across the curated Ayurvedic corpus using Okapi BM25.
Tokenization handles punctuation, case-folding, and preserves Ayurvedic tokens.
"""

from __future__ import annotations

import json
import pickle
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rank_bm25 import BM25Okapi

from app.config import BM25_INDEX_PKL, CORPUS_JSONL, BM25_TOP_K


QUESTION_STOPWORDS = {
    "what", "which", "who", "whom", "whose", "where", "when", "why", "how",
    "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "doing",
    "have", "has", "had", "having",
    "can", "could", "would", "should", "will", "shall", "may", "might", "must",
    "a", "an", "the", "and", "or", "but", "if", "because", "as", "until", "while",
    "of", "at", "by", "for", "with", "about", "against", "between", "into", "through",
    "during", "before", "after", "above", "below", "to", "from", "up", "down", "in", "out",
    "on", "off", "over", "under", "again", "further", "then", "once", "here", "there",
    "all", "any", "both", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "now", "tell", "explain", "give", "please", "according", "provide",
    "provides", "provided", "information", "available", "evidence", "detail", "details",
    "describe", "discuss", "mention", "know", "mean", "meaning"
}


def tokenize_for_bm25(text: str) -> List[str]:
    """Tokenize query or document for lexical matching."""
    if not text:
        return []
    # Lowercase and split on non-alphanumeric (preserves hyphens inside words)
    tokens = re.findall(r"\b[a-zA-Z0-9_\u0900-\u097F\u0C80-\u0CFF\-]{2,}\b", text.lower())
    return tokens


class BM25Retriever:
    """Okapi BM25 index and query retriever for the Ayurvedic corpus."""

    def __init__(self, corpus_path: Path = CORPUS_JSONL, index_path: Path = BM25_INDEX_PKL):
        self.corpus_path = corpus_path
        self.index_path = index_path
        self.chunks: List[Dict[str, Any]] = []
        self.bm25: BM25Okapi = None
        self._load_or_build()

    def _load_or_build(self) -> None:
        if self.index_path.exists():
            try:
                with open(self.index_path, "rb") as f:
                    data = pickle.load(f)
                    self.bm25 = data["bm25"]
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

        tokenized_corpus = [tokenize_for_bm25(c["text"]) for c in self.chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)

        # Cache index
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "wb") as f:
            pickle.dump({"bm25": self.bm25, "chunks": self.chunks}, f)

    def retrieve(self, query: str, top_k: int = BM25_TOP_K) -> List[Dict[str, Any]]:
        """
        Retrieve top_k most relevant passages for the query using BM25.
        Returns list of chunk dicts augmented with 'bm25_score' and 'rank'.
        """
        if not self.bm25 or not self.chunks or not query.strip():
            return []

        tokenized_query = tokenize_for_bm25(query)
        if not tokenized_query:
            return []

        # Filter out generic question/filler words for lexical scoring
        filtered_tokens = [t for t in tokenized_query if t not in QUESTION_STOPWORDS]
        scoring_tokens = filtered_tokens if filtered_tokens else tokenized_query

        scores = self.bm25.get_scores(scoring_tokens)
        # Pair with indices
        scored_indices = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for rank, (idx, score) in enumerate(scored_indices, start=1):
            if score <= 0:
                continue
            chunk = dict(self.chunks[idx])
            chunk["bm25_score"] = float(score)
            chunk["rank"] = rank
            results.append(chunk)

        return results

