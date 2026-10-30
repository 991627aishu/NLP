"""
AyurMitra — End-to-End Multilingual RAG Pipeline
==================================================
Orchestrates the complete AyurMitra architecture supporting:
  - B0: Translation-only query + BM25 only, without terminology preservation
  - B1: Translation-only query + BM25 & Dense hybrid (RRF), without terminology preservation
  - P1: Terminology detection, protection, canonicalization, hybrid retrieval, restoration
  - P2: P1 + Knowledge Graph concept grounding (NetworkX)
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.config import EXPERIMENT_CONFIGS, FUSION_TOP_K
from app.core.language_detect import detect
from app.core.matcher import TerminologyMatcher
from app.core.protection import TerminologyProtector
from app.core.knowledge_graph import AyurKnowledgeGraph
from app.pipeline.hybrid_retriever import HybridRetriever
from app.pipeline.translator import MultilingualTranslator
from app.pipeline.generator import EvidenceGroundedGenerator
from app.pipeline.web_search import WebSearchFallback


class AyurMitraPipeline:
    """Integrated Multilingual Ayurvedic RAG System with Controlled Web Fallback."""

    def __init__(self):
        self.matcher = TerminologyMatcher()
        self.protector = TerminologyProtector(matcher=self.matcher)
        self.translator = MultilingualTranslator()
        self.retriever = HybridRetriever()
        self.generator = EvidenceGroundedGenerator()
        self.kg = AyurKnowledgeGraph()
        self.web_search = WebSearchFallback()

    def process_query(
        self,
        query: str,
        system_mode: str = "P1",
        top_k: int = FUSION_TOP_K,
        target_lang: str = "auto",
        enable_web_search: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes a query through the chosen pipeline configuration.

        Args:
            query: Raw user query in English, Hindi, Kannada, or Romanized/code-mixed form.
            system_mode: One of "B0", "B1", "P1", "P2".
            top_k: Number of retrieved passages to return.
            target_lang: Output language ("auto", "en", "hi", "kn"). Defaults to "auto"
                         (uses dominant detected language).
            enable_web_search: If True, falls back to EuropePMC/Wikipedia when local evidence is weak.
                               Set to False during research benchmark evaluations.

        Returns:
            Dict containing query metadata, language detection, detected terms,
            active components, retrieval results, generated answer, and execution trace.
        """
        start_time = time.time()
        config = EXPERIMENT_CONFIGS.get(system_mode, EXPERIMENT_CONFIGS["P1"])
        use_terminology = config.get("use_terminology", True)
        use_dense = config.get("use_dense", True)
        use_graph = config.get("use_graph", False)

        # Step 1: Language, Script, and Code-Mixing Detection
        lang_info = detect(query)
        dominant_lang = lang_info.get("dominant_lang", lang_info.get("lang", "en"))

        # Resolve effective target language (Auto vs Explicit user choice)
        if target_lang and target_lang.lower() in ("en", "hi", "kn"):
            effective_target_lang = target_lang.lower()
        else:
            effective_target_lang = dominant_lang if dominant_lang in ("en", "hi", "kn") else "en"

        # Step 2: Terminology Detection & Protection (P1/P2 only)
        detected_terms = []
        placeholder_map = {}
        processed_query = query

        if use_terminology:
            detected_terms = self.matcher.find_terms(query)
            if detected_terms:
                protected_text, placeholder_map = self.protector.protect(query)
                processed_query = protected_text

        # Step 3: Query Translation to English for English Corpus Retrieval
        # For P1/P2: Placeholders protect domain terms from translation drift.
        # For B0/B1: Raw text is passed directly, allowing drift to occur.
        trans_res = self.translator.translate_to_english(
            processed_query, source_lang=dominant_lang
        )
        translated_query = trans_res["translated_text"]

        # Step 4: Canonicalization on Query Side
        # In P1/P2: Placeholders are restored to standard canonical Ayurvedic terms
        if use_terminology and placeholder_map:
            english_query = self.protector.restore_canonical(translated_query, placeholder_map)
        else:
            english_query = translated_query

        # Step 5: Retrieval (BM25 only for B0; Hybrid RRF for B1, P1, P2)
        # In P1/P2: Grounded ranking utilizes detected Ayurvedic terms
        retrieved_passages = self.retriever.retrieve(
            query=english_query,
            top_k=top_k,
            use_bm25=True,
            use_dense=use_dense,
            detected_terms=detected_terms if use_terminology else None,
        )

        # Step 5b: Controlled Web Search Fallback
        # States: disabled, not_needed, triggered, success, no_relevant_results, error
        web_passages = []
        is_local_insufficient = False
        if not retrieved_passages:
            is_local_insufficient = True
        else:
            top_p = retrieved_passages[0]
            top_score = top_p.get("rrf_score", top_p.get("bm25_score", 0.0))
            if top_score <= 0.005 and top_p.get("bm25_score", 0.0) == 0:
                is_local_insufficient = True

        explicit_external_req = any(w in query.lower() for w in ["recent", "modern", "latest", "who report", "clinical trial", "pubchem"])

        if not enable_web_search:
            web_status = "disabled"
            web_triggered = False
        elif not (is_local_insufficient or explicit_external_req):
            web_status = "not_needed"
            web_triggered = False
        else:
            web_triggered = True
            try:
                web_res = self.web_search.search(english_query, max_results=3)
                if web_res.get("success") and web_res.get("passages"):
                    web_passages = web_res.get("passages", [])
                    web_status = "success"
                elif web_res.get("success") and not web_res.get("passages"):
                    web_status = "no_relevant_results"
                else:
                    web_status = "no_relevant_results"
            except Exception:
                web_status = "error"

        # Step 6: Knowledge Graph Grounding (P2 only)
        graph_facts = []
        if use_graph and detected_terms:
            for t in detected_terms:
                canon = t.get("canonical_term")
                if not canon:
                    continue
                kg_info = self.kg.query_concept(canon)
                if kg_info.get("found"):
                    for conn in kg_info.get("connections", []):
                        graph_facts.append({
                            "concept": canon,
                            "relation": conn.get("relation", "related_to"),
                            "target": conn.get("target") or conn.get("source"),
                            "source_id": conn.get("source_id", "NAMASTE"),
                            "locator": conn.get("locator", ""),
                        })

        # Step 7: Evidence-Grounded Answer Generation in User's Target Language
        gen_res = self.generator.generate_answer(
            query=english_query,
            retrieved_passages=retrieved_passages,
            detected_terms=detected_terms,
            target_lang=effective_target_lang,
            graph_facts=graph_facts,
            web_passages=web_passages,
        )

        # Step 8: Output-Side Term Restoration (P1/P2 only)
        if use_terminology and placeholder_map:
            final_answer = self.protector.restore_to_language(
                gen_res["answer"], placeholder_map, target_lang=effective_target_lang
            )
        else:
            final_answer = gen_res["answer"]

        elapsed_ms = (time.time() - start_time) * 1000.0

        all_citations = gen_res.get("citations", []) + gen_res.get("web_citations", [])

        return {
            "raw_query": query,
            "system_mode": system_mode,
            "detected_language": dominant_lang,
            "dominant_language": dominant_lang,
            "target_language": effective_target_lang,
            "is_code_mixed": lang_info.get("is_code_mixed", False),
            "code_mix_type": lang_info.get("code_mix_type", "monolingual"),
            "segments": lang_info.get("segments", []),
            "active_components": {
                "system_mode": system_mode,
                "bm25_lexical": True,
                "dense_semantic": use_dense,
                "terminology_protection": use_terminology,
                "terminology_preservation": use_terminology,
                "kg_grounding": use_graph,
                "knowledge_graph_grounding": use_graph,
                "web_search_fallback": enable_web_search,
                "web_search_configured": enable_web_search,
                "web_search_triggered": web_triggered,
                "web_search_status": web_status,
                "web_sources_retrieved": len(web_passages),
            },
            "lang_detect_meta": lang_info,
            "translation_meta": trans_res,
            "use_terminology": use_terminology,
            "detected_terms": detected_terms,
            "canonical_query": english_query,
            "retrieved_passages": retrieved_passages,
            "web_passages": web_passages,
            "graph_facts": graph_facts,
            "answer": final_answer,
            "abstained": gen_res["abstained"],
            "abstention_reason": gen_res["reason"],
            "citations": all_citations,
            "disclaimer": gen_res["disclaimer"],
            "latency_ms": elapsed_ms,
        }
