"""
AyurMitra — Hybrid Retriever with Reciprocal Rank Fusion (RRF)
================================================================
Combines BM25 lexical ranking and dense semantic ranking using standard
Reciprocal Rank Fusion (RRF) with constant k = 60.

Fair-comparison principle:
The fusion algorithm and parameter k are fixed across baseline (B1) and
proposed (P1) configurations.
"""

from __future__ import annotations

import concurrent.futures
from typing import Any, Dict, List, Optional

from app.config import RRF_K, FUSION_TOP_K, BM25_TOP_K, DENSE_TOP_K
from app.pipeline.bm25_retriever import BM25Retriever
from app.pipeline.dense_retriever import DenseRetriever

_RET_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4)


class HybridRetriever:
    """Fuses BM25 and Dense retrieval via Reciprocal Rank Fusion."""

    def __init__(
        self,
        bm25_retriever: Optional[BM25Retriever] = None,
        dense_retriever: Optional[DenseRetriever] = None,
        rrf_k: int = RRF_K,
    ):
        self.bm25 = bm25_retriever or BM25Retriever()
        self.dense = dense_retriever or DenseRetriever()
        self.rrf_k = rrf_k

    def retrieve(
        self,
        query: str,
        top_k: int = FUSION_TOP_K,
        use_bm25: bool = True,
        use_dense: bool = True,
        detected_terms: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute hybrid retrieval on query.

        If use_bm25=True and use_dense=False: returns BM25-only (B0 baseline).
        If use_bm25=True and use_dense=True: fuses both via RRF (B1 baseline / P1 proposed).
        Pass detected_terms to ground ranking against identified Ayurvedic entities.
        """
        if not query or not query.strip():
            return []

        if use_bm25 and use_dense:
            f_bm25 = _RET_POOL.submit(self.bm25.retrieve, query, top_k=BM25_TOP_K)
            f_dense = _RET_POOL.submit(self.dense.retrieve, query, top_k=DENSE_TOP_K)
            bm25_results = f_bm25.result()
            dense_results = f_dense.result()
        else:
            bm25_results = self.bm25.retrieve(query, top_k=BM25_TOP_K) if use_bm25 else []
            dense_results = self.dense.retrieve(query, top_k=DENSE_TOP_K) if use_dense else []

        if use_bm25 and not use_dense:
            # BM25-only (e.g. B0)
            return bm25_results[:top_k]

        if use_dense and not use_bm25:
            # Dense-only
            return dense_results[:top_k]

        # Reciprocal Rank Fusion
        rrf_scores: Dict[str, float] = {}
        chunk_lookup: Dict[str, Dict[str, Any]] = {}
        bm25_ranks: Dict[str, int] = {}
        dense_ranks: Dict[str, int] = {}

        for rank, item in enumerate(bm25_results, start=1):
            cid = item["chunk_id"]
            chunk_lookup[cid] = item
            bm25_ranks[cid] = rank
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (self.rrf_k + rank))

        for rank, item in enumerate(dense_results, start=1):
            cid = item["chunk_id"]
            chunk_lookup[cid] = item
            dense_ranks[cid] = rank
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (self.rrf_k + rank))

        # Grounding boost for detected Ayurvedic concepts
        if detected_terms:
            target_keywords = set()
            for t in detected_terms:
                if t.get("canonical_term"):
                    target_keywords.add(t["canonical_term"].lower())
                if t.get("matched_text"):
                    target_keywords.add(t["matched_text"].lower())

            is_definitional = any(q_word in query.lower() for q_word in ["what is", "define", "meaning", "definition", "concept"])

            for cid, chunk in chunk_lookup.items():
                chunk_str = (chunk.get("text", "") + " " + chunk.get("title", "")).lower()
                matched_count = sum(1 for kw in target_keywords if len(kw) >= 3 and kw in chunk_str)
                if matched_count > 0:
                    rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (0.05 * matched_count)
                    # Authoritative definition boost for WHO / NAMASTE standardized compendia
                    src = str(chunk.get("source_id", "")).lower()
                    if is_definitional and ("who" in src or "namaste" in src):
                        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 0.08

        sorted_cids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:top_k]

        fused_results = []
        for rank, cid in enumerate(sorted_cids, start=1):
            chunk = dict(chunk_lookup[cid])
            chunk["fused_rank"] = rank
            chunk["rrf_score"] = float(rrf_scores[cid])
            chunk["bm25_rank"] = bm25_ranks.get(cid, None)
            chunk["dense_rank"] = dense_ranks.get(cid, None)
            fused_results.append(chunk)

        return fused_results

