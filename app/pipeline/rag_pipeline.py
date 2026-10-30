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

from app.config import EXPERIMENT_CONFIGS, FUSION_TOP_K, SAFETY_GATE, EDUCATIONAL_DISCLAIMER
from app.core.safety import check_query_safety, safety_message
from app.config import EVIDENCE_GATE, EVIDENCE_MIN_COVERAGE, GENERATOR_BACKEND, KG_VERSION
import re as _re
from app.pipeline.bm25_retriever import QUESTION_STOPWORDS

# Words too generic to show that a passage addresses the question.
_GENERIC_DOMAIN_WORDS = {
    "ayurveda", "ayurvedic", "ancient", "traditional", "classical", "texts", "text", "role", "importance",
    "describe", "described", "body", "health", "healthy", "human", "people", "person", "system", "systems",
    "method", "methods", "way", "ways", "use", "used", "uses", "benefit", "benefits", "help", "helps", "good",
    "bad", "know", "mean", "means", "meaning", "definition", "define", "significance", "related", "relation",
    "concept", "concepts", "principle", "principles", "function", "functions", "type", "types", "kind",
    "list", "main", "important", "work", "works", "affect", "affects", "different", "between", "hospital",
    "hospitals", "patient", "patients", "india", "indian", "modern", "today", "daily", "life",
}
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
        self.generator.translator = self.translator
        self.generator.protector = self.protector
        self.kg_v1 = AyurKnowledgeGraph()
        self.kg = self.kg_v1
        self.kg.version = "v1"
        if KG_VERSION in ("auto", "v2"):
            try:
                from app.core.kg_v2 import load_kg_v2
                kg2 = load_kg_v2()
                if kg2 is not None:
                    self.kg = kg2
            except Exception as e:  # missing/corrupt v2 graph -> keep v1
                import logging
                logging.getLogger("ayurmitra.pipeline").warning("KG v2 unavailable (%s); using v1", e)
        self.web_search = WebSearchFallback()

    def process_query(
        self,
        query: str,
        system_mode: str = "P1",
        top_k: int = FUSION_TOP_K,
        target_lang: str = "auto",
        enable_web_search: bool = True,
        generator: Optional[str] = None,
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

        # Step 1b: Pre-retrieval safety gate (all modes; audit F15/F16).
        # Emergencies, dosage/prescription requests, toxic-ingestion requests and
        # cure claims are never answered from retrieved text.
        if SAFETY_GATE and not getattr(self, "_disable_safety_gate", False):
            safety = check_query_safety(query)
            if safety["blocked"]:
                return self._safety_response(query, system_mode, config, lang_info, dominant_lang,
                                             effective_target_lang, enable_web_search, safety, start_time)

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
        # Step 5a (P2 only): bounded graph query expansion (≤5 terms, appended once => lower weight)
        graph_expansion_terms: List[str] = []
        retrieval_query = english_query
        if use_graph and detected_terms and hasattr(self.kg, "expansion_terms"):
            for t in detected_terms:
                for x in self.kg.expansion_terms(t.get("canonical_term", ""), k=5):
                    if x not in graph_expansion_terms and len(graph_expansion_terms) < 5:
                        graph_expansion_terms.append(x)
            if graph_expansion_terms:
                retrieval_query = english_query + " " + " ".join(graph_expansion_terms)

        retrieved_passages = self.retriever.retrieve(
            query=retrieval_query,
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
        if use_graph and detected_terms and hasattr(self.kg, "facts_for_term"):
            seen_f = set()
            for t in detected_terms:
                for f in self.kg.facts_for_term(t.get("canonical_term", ""), limit=6):
                    key = (f["query_concept"], f["relation"], f["target_id"])
                    if key not in seen_f:
                        seen_f.add(key)
                        graph_facts.append(f)
        elif use_graph and detected_terms:
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

        # Step 7a: Optional evidence-only LLM generator (never used in benchmarks)
        generator_used = "extractive"
        generator_note = None
        want_llm = (generator or GENERATOR_BACKEND or "extractive").lower() == "llm"
        if want_llm and not gen_res["abstained"] and retrieved_passages:
            try:
                from app.pipeline.llm_generator import LLMGenerator
                llm = getattr(self, "_llm", None) or LLMGenerator()
                self._llm = llm
                out = llm.generate(english_query if effective_target_lang == "en" else query,
                                   retrieved_passages, graph_facts, target_lang=effective_target_lang)
                if out["insufficient"]:
                    gen_res = dict(gen_res, answer=safety_message("insufficient_evidence", effective_target_lang),
                                   abstained=True, reason="insufficient_evidence", citations=[])
                else:
                    cited = set(out["cited_ids"])
                    cits = [c for c in gen_res.get("citations", []) if c["chunk_id"] in cited] or gen_res.get("citations", [])
                    src_lines = "\n".join(f"- {c['title']} (`{c['source_id']}` | {c['locator']}) [{c['chunk_id']}]" for c in cits)
                    gen_res = dict(gen_res, citations=cits,
                                   answer=f"**Answer:** {out['answer_text']}\n\n**Sources:**\n{src_lines}")
                generator_used = f"llm:{out['provider']}:{out['model']}"
                generator_note = {"dropped_sentences": out["dropped_sentences"]}
            except Exception as e:
                generator_note = {"llm_error": f"{type(e).__name__}: {e}"[:300], "fell_back_to": "extractive"}

        # Step 7b: Evidence gate — abstain instead of answering from passages that
        # share no content word with the question (e.g. out-of-domain queries).
        # Retrieved passages are still returned so retrieval metrics are unaffected.
        evidence_check = self._evidence_check(english_query, detected_terms, retrieved_passages)
        if (EVIDENCE_GATE and not gen_res["abstained"] and not web_passages
                and evidence_check["judgeable"] and not evidence_check["supported"]):
            gen_res = dict(gen_res)
            gen_res["answer"] = safety_message("insufficient_evidence", effective_target_lang)
            gen_res["abstained"] = True
            gen_res["reason"] = "insufficient_evidence"
            gen_res["citations"] = []

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
            "graph_expansion_terms": graph_expansion_terms,
            "retrieval_query": retrieval_query,
            "answer": final_answer,
            "abstained": gen_res["abstained"],
            "abstention_reason": gen_res["reason"],
            "citations": all_citations,
            "disclaimer": gen_res["disclaimer"],
            "latency_ms": elapsed_ms,
            "backends": self.backend_info(),
            "evidence_check": evidence_check,
            "is_emergency": False,
            "machine_translated": gen_res.get("machine_translated", False),
            "answer_grounding": gen_res.get("answer_grounding"),
            "generator_used": generator_used,
            "generator_note": generator_note,
        }

    @staticmethod
    def _evidence_check(english_query: str, detected_terms, passages) -> Dict[str, Any]:
        kws = set()
        for t in detected_terms or []:
            for k in (t.get("canonical_term"), t.get("matched_text")):
                if k and len(k) >= 3:
                    kws.add(k.lower())
        for w in _re.findall(r"[a-zA-Z\u0900-\u097F\u0C80-\u0CFF]{3,}", (english_query or "").lower()):
            if w not in QUESTION_STOPWORDS and w not in _GENERIC_DOMAIN_WORDS and "ayurterm" not in w:
                kws.add(w)
        if not kws:
            return {"judgeable": False, "supported": True, "keywords": [], "matched": []}
        matched = set()
        for p in passages or []:
            blob = (p.get("text", "") + " " + p.get("title", "")).lower()
            for k in kws:
                stem = k[:5] if len(k) > 5 and k.isascii() else k
                if stem in blob:
                    matched.add(k)
        term_kws = {k.lower() for t in (detected_terms or []) for k in (t.get("canonical_term"), t.get("matched_text")) if k}
        coverage = len(matched) / len(kws)
        supported = bool(matched & term_kws) or coverage >= EVIDENCE_MIN_COVERAGE
        return {"judgeable": True, "supported": supported, "coverage": round(coverage, 3),
                "keywords": sorted(kws), "matched": sorted(matched)}

    # ── Safety-gate response (same keys as a normal response) ────────────────
    def _safety_response(self, query, system_mode, config, lang_info, dominant_lang,
                         target_lang, enable_web_search, safety, start_time) -> Dict[str, Any]:
        from app.pipeline.generator import LOCALIZED_STRINGS
        lang = target_lang if target_lang in ("en", "hi", "kn") else "en"
        msg = safety_message(safety["reason"], lang)
        disclaimer = LOCALIZED_STRINGS.get(lang, LOCALIZED_STRINGS["en"])["disclaimer"]
        use_terminology = config.get("use_terminology", True)
        return {
            "raw_query": query,
            "system_mode": system_mode,
            "detected_language": dominant_lang,
            "dominant_language": dominant_lang,
            "target_language": lang,
            "is_code_mixed": lang_info.get("is_code_mixed", False),
            "code_mix_type": lang_info.get("code_mix_type", "monolingual"),
            "segments": lang_info.get("segments", []),
            "active_components": {
                "system_mode": system_mode,
                "bm25_lexical": True,
                "dense_semantic": config.get("use_dense", True),
                "terminology_protection": use_terminology,
                "terminology_preservation": use_terminology,
                "kg_grounding": config.get("use_graph", False),
                "knowledge_graph_grounding": config.get("use_graph", False),
                "web_search_fallback": enable_web_search,
                "web_search_configured": enable_web_search,
                "web_search_triggered": False,
                "web_search_status": "blocked_by_safety_gate",
                "web_sources_retrieved": 0,
                "safety_gate": True,
            },
            "lang_detect_meta": lang_info,
            "translation_meta": {"method": "not_run_safety_gate", "translated_text": "", "success": True},
            "use_terminology": use_terminology,
            "detected_terms": [],
            "canonical_query": "",
            "retrieved_passages": [],
            "web_passages": [],
            "graph_facts": [],
            "graph_expansion_terms": [],
            "retrieval_query": "",
            "answer": msg,
            "abstained": True,
            "abstention_reason": safety["reason"],
            "safety": safety,
            "is_emergency": safety["severity"] == "emergency",
            "citations": [],
            "disclaimer": disclaimer,
            "latency_ms": (time.time() - start_time) * 1000.0,
            "backends": self.backend_info(),
            "machine_translated": False,
            "answer_grounding": "safety_gate",
            "generator_used": "safety_gate",
            "generator_note": None,
        }

    def backend_info(self) -> Dict[str, Any]:
        """Which backends are actually live (recorded in every trace)."""
        dense = getattr(self.retriever, "dense", None)
        return {
            "translator": getattr(self.translator, "backend_used", "rules"),
            "translator_warning": getattr(self.translator, "backend_warning", None),
            "dense": getattr(dense, "backend_used", "tfidf"),
            "dense_model": getattr(dense, "model_name", "tfidf_char_wb_3-5"),
            "dense_warning": getattr(dense, "backend_warning", None),
            "generator": getattr(self.generator, "backend_used", "extractive"),
            "kg_version": getattr(self.kg, "version", "v1"),
            "safety_gate": bool(SAFETY_GATE),
        }
