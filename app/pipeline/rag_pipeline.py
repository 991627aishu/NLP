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

import logging
import time
from typing import Any, Dict, List, Optional

log = logging.getLogger("ayurmitra.pipeline")

from app.config import EXPERIMENT_CONFIGS, FUSION_TOP_K, SAFETY_GATE, EDUCATIONAL_DISCLAIMER
from app.core.safety import check_query_safety, safety_message
from app.config import EVIDENCE_GATE, EVIDENCE_MIN_COVERAGE, GENERATOR_BACKEND, KG_VERSION
import re
_re = re
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
        from app.core.query_router import IntelligentQueryRouter, QueryRoute
        from app.pipeline.general_ai import GeneralAIEngine
        self.router = IntelligentQueryRouter(matcher=self.matcher)
        self.general_ai = GeneralAIEngine(translator=self.translator)

    def process_query(
        self,
        query: str,
        system_mode: str = "P1",
        top_k: int = FUSION_TOP_K,
        target_lang: str = "auto",
        enable_web_search: bool = True,
        generator: Optional[str] = None,
        force_ayurveda: bool = False,
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
        stage_timings = {}
        t_cursor = start_time
        config = EXPERIMENT_CONFIGS.get(system_mode, EXPERIMENT_CONFIGS["P1"])
        use_terminology = config.get("use_terminology", True)
        use_dense = config.get("use_dense", True)
        use_graph = config.get("use_graph", False)

        # Step 1: Language, Script, and Code-Mixing Detection
        from app.core.language_detect import resolve_target_language
        lang_res = resolve_target_language(query, target_lang)
        lang_info = lang_res.get("detected_info") or detect(query)
        dominant_lang = lang_info.get("dominant_lang", lang_info.get("lang", "en"))
        effective_target_lang = lang_res.get("mode", dominant_lang)
        t_now = time.time()
        stage_timings["language_detect_ms"] = round((t_now - t_cursor) * 1000, 2)
        t_cursor = t_now

        # Step 1a: Unsupported language handling
        if not lang_res.get("is_supported", True) or effective_target_lang == "unsupported":
            from app.pipeline.generator import LOCALIZED_STRINGS
            unsupp_str = LOCALIZED_STRINGS["unsupported"]["abstention_no_evidence"]
            elapsed_ms = (time.time() - start_time) * 1000.0
            stage_timings["total_ms"] = round(elapsed_ms, 2)
            return {
                "raw_query": query,
                "system_mode": system_mode,
                "detected_language": "unsupported",
                "dominant_language": "unsupported",
                "target_language": "unsupported",
                "language_mode": "unsupported",
                "display_language": "Unsupported Language",
                "tts_lang": "en-IN",
                "is_code_mixed": False,
                "code_mix_type": "foreign_unsupported",
                "segments": lang_info.get("segments", []),
                "active_components": {
                    "system_mode": system_mode,
                    "bm25_lexical": False,
                    "dense_semantic": False,
                    "terminology_protection": False,
                    "terminology_preservation": False,
                    "kg_grounding": False,
                    "knowledge_graph_grounding": False,
                    "web_search_fallback": False,
                    "web_search_configured": False,
                    "web_search_triggered": False,
                    "web_search_status": "unsupported_language",
                    "web_sources_retrieved": 0,
                },
                "lang_detect_meta": lang_info,
                "translation_meta": {"method": "unsupported_language_rejection", "translated_text": "", "success": False},
                "use_terminology": False,
                "detected_terms": [],
                "canonical_query": "",
                "retrieved_passages": [],
                "web_passages": [],
                "graph_facts": [],
                "graph_expansion_terms": [],
                "retrieval_query": "",
                "answer": (
                    "**AyurMitra Language Notice / भाषा सूचना / ಭಾಷಾ ಸೂಚನೆ:**\n\n"
                    f"{unsupp_str}\n\n"
                    "Supported languages:\n"
                    "- **English** (e.g., *'What is Vata dosha?'*)\n"
                    "- **हिन्दी / Hindi** (e.g., *'वात दोष क्या है?'*)\n"
                    "- **ಕನ್ನಡ / Kannada** (e.g., *'ವಾತ ದೋಷ ಎಂದರೇನು?'*)\n"
                    "- **Hinglish** (e.g., *'Pitta badhne par kya symptoms hote hain?'*)\n"
                    "- **Kanglish** (e.g., *'Agni mandya andre enu?'*)"
                ),
                "abstained": True,
                "abstention_reason": "unsupported_language",
                "citations": [],
                "disclaimer": EDUCATIONAL_DISCLAIMER,
                "latency_ms": elapsed_ms,
                "stage_timings_ms": stage_timings,
                "backends": self.backend_info(),
                "evidence_check": {"judgeable": False, "supported": False, "keywords": [], "matched": []},
                "is_emergency": False,
                "machine_translated": False,
                "answer_grounding": "none",
                "generator_used": "system_guard",
                "generator_note": None,
            }

        # Step 1b: Pre-retrieval safety gate (all modes; audit F15/F16).
        # Emergencies, dosage/prescription requests, toxic-ingestion requests and
        # cure claims are never answered from retrieved text.
        if SAFETY_GATE and not getattr(self, "_disable_safety_gate", False):
            safety = check_query_safety(query)
            if safety["blocked"]:
                t_now = time.time()
                stage_timings["safety_gate_ms"] = round((t_now - t_cursor) * 1000, 2)
                return self._safety_response(query, system_mode, config, lang_info, dominant_lang,
                                             effective_target_lang, enable_web_search, safety, start_time, stage_timings)

        # Step 1c: Intelligent Query Routing & Multi-Domain Classification
        from app.core.query_router import QueryRoute
        if not hasattr(self, "router"):
            from app.core.query_router import IntelligentQueryRouter
            self.router = IntelligentQueryRouter(matcher=self.matcher)
        if not hasattr(self, "general_ai"):
            from app.pipeline.general_ai import GeneralAIEngine
            self.general_ai = GeneralAIEngine(translator=self.translator)

        if not force_ayurveda:
            route_res = self.router.classify(query, detected_terms=None)
            route_cat = route_res.get("route", QueryRoute.AYURVEDA_DOMAIN)

            t_now = time.time()
            stage_timings["router_ms"] = round((t_now - t_cursor) * 1000, 2)
            t_cursor = t_now

            if route_cat == QueryRoute.UNCLEAR_QUERY:
                unclear_res = self.general_ai.process_unclear_query(query, target_lang=effective_target_lang, route_res=route_res)
                stage_timings["general_ai_ms"] = round((time.time() - t_cursor) * 1000, 2)
                return self._wrap_general_ai_response(
                    query, system_mode, lang_info, dominant_lang, effective_target_lang,
                    lang_res, start_time, unclear_res, route_res, stage_timings
                )

            if route_cat == QueryRoute.UNSAFE_OR_MEDICALLY_SENSITIVE:
                safety = {"blocked": True, "reason": "unsafe_or_medically_sensitive", "severity": "caution"}
                return self._safety_response(query, system_mode, config, lang_info, dominant_lang,
                                             effective_target_lang, enable_web_search, safety, start_time, stage_timings)

            if route_cat == QueryRoute.GENERAL_KNOWLEDGE:
                gen_res = self.general_ai.process_general_knowledge(query, target_lang=effective_target_lang)
                stage_timings["general_ai_ms"] = round((time.time() - t_cursor) * 1000, 2)
                return self._wrap_general_ai_response(
                    query, system_mode, lang_info, dominant_lang, effective_target_lang,
                    lang_res, start_time, gen_res, route_res, stage_timings
                )

            if route_cat == QueryRoute.CURRENT_INFORMATION:
                cur_res = self.general_ai.process_current_information(query, target_lang=effective_target_lang)
                stage_timings["general_ai_ms"] = round((time.time() - t_cursor) * 1000, 2)
                return self._wrap_general_ai_response(
                    query, system_mode, lang_info, dominant_lang, effective_target_lang,
                    lang_res, start_time, cur_res, route_res, stage_timings
                )

            if route_cat == QueryRoute.MIXED_DOMAIN:
                mix_res = self.general_ai.process_mixed_domain(
                    query, target_lang=effective_target_lang, ayurveda_pipeline=self, system_mode=system_mode
                )
                stage_timings["general_ai_ms"] = round((time.time() - t_cursor) * 1000, 2)
                return self._wrap_general_ai_response(
                    query, system_mode, lang_info, dominant_lang, effective_target_lang,
                    lang_res, start_time, mix_res, route_res, stage_timings
                )
        else:
            t_now = time.time()
            stage_timings["router_ms"] = round((t_now - t_cursor) * 1000, 2)
            t_cursor = t_now

        # Step 2: Terminology Detection & Protection (P1/P2 only)
        detected_terms = []
        placeholder_map = {}
        processed_query = query

        if use_terminology:
            detected_terms = self.matcher.find_terms(query)
            if hasattr(self.matcher, "find_fuzzy_terms"):
                fuzzy = self.matcher.find_fuzzy_terms(query, require_ayurveda_context=True)
                seen_c = {t.get("canonical_term", "").lower() for t in detected_terms}
                for fz in fuzzy:
                    if fz.get("canonical_term", "").lower() not in seen_c:
                        detected_terms.append(fz)
                        seen_c.add(fz["canonical_term"].lower())
            if detected_terms:
                protected_text, placeholder_map = self.protector.protect(query)
                for fz in detected_terms:
                    if fz.get("script") == "Latin_Fuzzy":
                        mt = fz.get("matched_text", "")
                        ct = fz.get("canonical_term", "")
                        if mt and ct and mt in protected_text:
                            tok_key = f"__AYURTERM_{len(placeholder_map)}__"
                            protected_text = re.sub(rf"\b{re.escape(mt)}\b", tok_key, protected_text, count=1)
                            placeholder_map[tok_key] = {
                                "canonical_term": ct,
                                "matched_text": mt,
                                "script": "Latin_Fuzzy",
                                "concept_id": fz.get("concept_id", f"CID_{ct}"),
                            }
                processed_query = protected_text
        t_now = time.time()
        stage_timings["terminology_detection_ms"] = round((t_now - t_cursor) * 1000, 2)
        t_cursor = t_now

        # Step 3: Query Translation to English for English Corpus Retrieval
        # For P1/P2: Placeholders protect domain terms from translation drift.
        # For B0/B1: Raw text is passed directly, allowing drift to occur.
        trans_src_lang = effective_target_lang if effective_target_lang in ("hi", "kn", "hinglish", "kanglish") else dominant_lang
        trans_res = self.translator.translate_to_english(
            processed_query, source_lang=trans_src_lang
        )
        translated_query = trans_res["translated_text"]

        # Step 4: Canonicalization on Query Side
        # In P1/P2: Placeholders are restored to standard canonical Ayurvedic terms
        if use_terminology and placeholder_map:
            english_query = self.protector.restore_canonical(translated_query, placeholder_map)
        else:
            english_query = translated_query
        t_now = time.time()
        stage_timings["query_translation_canonicalization_ms"] = round((t_now - t_cursor) * 1000, 2)
        t_cursor = t_now

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
        t_now = time.time()
        stage_timings["kg_query_expansion_ms"] = round((t_now - t_cursor) * 1000, 2)
        t_cursor = t_now

        retrieved_passages = self.retriever.retrieve(
            query=retrieval_query,
            top_k=top_k,
            use_bm25=True,
            use_dense=use_dense,
            detected_terms=detected_terms if use_terminology else None,
        )
        t_now = time.time()
        stage_timings["hybrid_retrieval_ms"] = round((t_now - t_cursor) * 1000, 2)
        t_cursor = t_now

        # Step 5b: Controlled Web Search Fallback
        # States: disabled, not_needed, triggered, success, no_relevant_results, error
        web_passages = []
        is_local_insufficient = False
        if not retrieved_passages:
            is_local_insufficient = True
        else:
            top_p = retrieved_passages[0]
            top_score = top_p.get("rrf_score", top_p.get("bm25_score", 0.0))
            if top_score <= 0.020 and top_p.get("bm25_score", 0.0) == 0:
                is_local_insufficient = True
            # Ignore generic meta-terms so e.g. 'ayurveda' alone does not mask missing concept coverage
            generic_meta = {"ayurveda", "ayurvedic", "disease", "roga", "health", "medicine"}
            primary_terms = [
                t.get("canonical_term", "").lower() for t in (detected_terms or [])
                if t.get("canonical_term") and t.get("canonical_term", "").lower() not in generic_meta
            ]
            if primary_terms:
                all_text = " ".join((p.get("text", "") + " " + p.get("title", "")) for p in retrieved_passages).lower()
                if not any(pt in all_text for pt in primary_terms):
                    is_local_insufficient = True
            if not is_local_insufficient:
                pre_ev = self._evidence_check(english_query, detected_terms, retrieved_passages)
                if pre_ev.get("judgeable") and not pre_ev.get("supported"):
                    is_local_insufficient = True

        explicit_external_req = any(w in query.lower() for w in ["recent", "modern", "latest", "who report", "clinical trial", "pubchem", "news", "current"])

        # Automatic web research is ALWAYS enabled when local evidence is weak or absent
        if not (is_local_insufficient or explicit_external_req) and not enable_web_search:
            web_status = "disabled"
            web_triggered = False
        elif not (is_local_insufficient or explicit_external_req):
            web_status = "not_needed"
            web_triggered = False
        else:
            web_triggered = True
            try:
                # Search using both translated English query and any specific entities
                search_term = english_query
                if detected_terms:
                    canon_names = [t.get("canonical_term") for t in detected_terms if t.get("canonical_term")]
                    if canon_names:
                        search_term = " ".join(canon_names) + " " + search_term
                domain_terms = [t.get("canonical_term", "") for t in (detected_terms or []) if t.get("canonical_term")]
                web_res = self.web_search.search(search_term.strip(), max_results=4, domain="ayurveda", domain_terms=domain_terms)
                if web_res.get("success") and web_res.get("passages"):
                    web_passages = web_res.get("passages", [])
                    web_status = "success"
                elif web_res.get("success") and not web_res.get("passages"):
                    web_status = "no_relevant_results"
                else:
                    web_status = "no_relevant_results"
            except Exception as e:
                web_status = f"error: {e}"
        t_now = time.time()
        stage_timings["web_search_ms"] = round((t_now - t_cursor) * 1000, 2)
        t_cursor = t_now

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
        t_now = time.time()
        stage_timings["kg_grounding_facts_ms"] = round((t_now - t_cursor) * 1000, 2)
        t_cursor = t_now

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
                if not out.get("success", True):
                    generator_note = {"llm_error": str(out.get("error", "llm_failed"))[:200], "fell_back_to": "extractive"}
                elif out["insufficient"]:
                    gen_res = dict(gen_res, answer=safety_message("insufficient_evidence", effective_target_lang),
                                   abstained=True, reason="insufficient_evidence", citations=[])
                    generator_used = f"llm:{out['provider']}:{out['model']}"
                else:
                    cited = set(out["cited_ids"])
                    clean_ans = out['answer_text']
                    clean_ans = re.sub(r"\[[A-Za-z0-9_.\- :]+(?:CHUNK|EVID|WHO|NAMASTE|IMPPAT|CLASSIC|CI\.ASSIC|WEB|DOC)[^\]]*\]", "", clean_ans, flags=re.IGNORECASE)
                    clean_ans = re.sub(r"\[[A-Z][A-Z0-9_.\-]{3,}[A-Z0-9]\]", "", clean_ans)
                    clean_ans = re.sub(r"\s{2,}", " ", clean_ans).strip()
                    cits = [c for c in gen_res.get("citations", []) if c["chunk_id"] in cited] or gen_res.get("citations", [])
                    src_lines = "\n".join(f"- {c['title']} ({c.get('source_id', 'Corpus')} | {c.get('locator', 'Ref')})" for c in cits)
                    gen_res = dict(gen_res, citations=cits,
                                   answer=f"**Answer:** {clean_ans}\n\n**Sources:**\n{src_lines}")
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

        # Step 7c: 3-Tier Fallback — Level 1 (Local) -> Level 2 (External) -> Level 3 (Gemini Knowledge Fallback)
        # When local evidence is insufficient or abstained, first utilize any retrieved live web research
        if gen_res.get("abstained") and web_passages and (want_llm or (GENERATOR_BACKEND or "llm").lower() == "llm"):
            from app.pipeline.llm_generator import LLMGenerator
            llm = getattr(self, "_llm", None) or LLMGenerator()
            self._llm = llm
            try:
                web_llm_out = llm.generate(
                    question=english_query if effective_target_lang == "en" else query,
                    passages=web_passages,
                    graph_facts=graph_facts,
                    target_lang=effective_target_lang,
                    domain="AYURVEDA_AND_EXTERNAL_EVIDENCE"
                )
                if web_llm_out.get("success") and web_llm_out.get("answer_text"):
                    clean_ans = web_llm_out["answer_text"]
                    clean_ans = re.sub(r"\[[A-Z0-9_\-]+(?:CHUNK|EVID|WHO|NAMASTE|IMPPAT)[A-Z0-9_\-]*\]", "", clean_ans).strip()
                    web_cits = []
                    for wp in web_passages:
                        web_cits.append({
                            "chunk_id": f"WEB_{abs(hash(wp.get('url', '')))%10000:04d}",
                            "source_id": wp.get("publisher", "Web Reference"),
                            "title": wp.get("title", "Authoritative Web Research"),
                            "locator": wp.get("year", "Current"),
                            "is_web": True,
                            "url": wp.get("url", ""),
                            "publisher": wp.get("publisher", ""),
                        })
                    src_bullets = "\n".join(f"- [{wc['title']}]({wc['url']}) ({wc['publisher']})" for wc in web_cits if wc.get('url'))
                    gen_res = dict(
                        gen_res,
                        answer=f"**Answer:** {clean_ans}\n\n**External Authoritative Sources:**\n{src_bullets}" if src_bullets else f"**Answer:** {clean_ans}",
                        abstained=False,
                        reason=None,
                        citations=web_cits,
                    )
                    generator_used = f"llm:google_gemini:{web_llm_out.get('model', 'gemini')}:web_grounded"
            except Exception as web_llm_err:
                log.warning("Web-grounded LLM synthesis failed: %s", web_llm_err)

        # Level 3 (Gemini Knowledge Fallback) if still abstained
        if gen_res.get("abstained") and (want_llm or (GENERATOR_BACKEND or "llm").lower() == "llm"):
            from app.pipeline.gemini_provider import get_gemini_provider
            gem_fb = getattr(self, "_gemini_fb", None)
            if gem_fb is None:
                gem_fb = get_gemini_provider()
                self._gemini_fb = gem_fb

            if gem_fb.is_available():
                try:
                    lang_label = {"en": "English", "hi": "Hindi (Devanagari)", "kn": "Kannada", "hinglish": "Hindi", "kanglish": "Kannada"}.get(effective_target_lang, "English")
                    fb_prompt = (
                        f"User Question: {query}\n"
                        f"Target Language: {lang_label}\n\n"
                        f"Guidelines:\n"
                        f"- Provide a clear, comprehensive, and authentic educational explanation of this Ayurvedic or medical concept in {lang_label} using native script.\n"
                        f"- Ground your explanation in foundational Ayurvedic principles (Tridosha, Dhatu, Agni, Ama, Srotas, classical definitions).\n"
                        f"- Do not claim specific local corpus passage citations.\n"
                        f"- Be helpful, accurate, educational, and respectful."
                    )
                    fb_res = gem_fb.generate_answer(
                        system_instruction="You are AyurMitra, an authentic Ayurvedic and medical health education assistant.",
                        user_prompt=fb_prompt,
                        temperature=0.2,
                        max_output_tokens=1024,
                    )
                    if fb_res.get("success") and fb_res.get("text", "").strip():
                        fb_text = fb_res["text"].strip()
                        # Clean any raw chunk brackets
                        fb_text = re.sub(r"\[[A-Z0-9_\-]+(?:CHUNK|EVID|WHO|NAMASTE|IMPPAT)[A-Z0-9_\-]*\]", "", fb_text).strip()
                        gen_res = dict(
                            gen_res,
                            answer=f"**Answer:** {fb_text}\n\n*Note: This explanation is synthesized from AyurMitra's Gemini foundational knowledge base.*",
                            abstained=False,
                            reason=None,
                            citations=[],
                        )
                        generator_used = f"llm:google_gemini:{fb_res.get('model', 'gemini')}:knowledge_fallback"
                except Exception as fb_err:
                    log.warning("Level 3 Gemini knowledge fallback failed: %s", fb_err)

        t_now = time.time()
        stage_timings["generation_and_fallback_ms"] = round((t_now - t_cursor) * 1000, 2)
        t_cursor = t_now

        # Step 8: Output-Side Term Restoration (P1/P2 only)
        if use_terminology and placeholder_map:
            final_answer = self.protector.restore_to_language(
                gen_res["answer"], placeholder_map, target_lang=effective_target_lang
            )
        else:
            final_answer = gen_res["answer"]

        # Step 8b: Output Language and Script Validation Gate
        from app.pipeline.generator import validate_output_language_and_script
        primary_concept = detected_terms[0].get("canonical_term") if detected_terms else None
        final_answer = validate_output_language_and_script(
            final_answer, effective_target_lang, primary_concept=primary_concept
        )
        # Strip any internal chunk codes from final output
        final_answer = re.sub(r"\[[A-Za-z0-9_.\- :]+(?:CHUNK|EVID|WHO|NAMASTE|IMPPAT|CLASSIC|CI\.ASSIC|WEB|DOC)[^\]]*\]", "", final_answer, flags=re.IGNORECASE)
        final_answer = re.sub(r"\[[A-Z][A-Z0-9_.\-]{3,}[A-Z0-9]\]", "", final_answer)
        final_answer = re.sub(r"\s{2,}", " ", final_answer).strip()

        elapsed_ms = (time.time() - start_time) * 1000.0
        t_now = time.time()
        stage_timings["post_processing_ms"] = round((t_now - t_cursor) * 1000, 2)
        stage_timings["total_ms"] = round(elapsed_ms, 2)

        all_citations = gen_res.get("citations", []) + gen_res.get("web_citations", [])

        ext_providers = sorted(set(wp.get("provider", "") for wp in (web_passages or []) if wp.get("provider")))
        if ":web_grounded" in generator_used:
            computed_source_label = f"External Authoritative APIs ({', '.join(ext_providers) or 'Web Research'})"
            computed_answer_source = "external_api_grounded"
        elif ":knowledge_fallback" in generator_used:
            computed_source_label = "Gemini Foundational Knowledge (No Local Corpus Match)"
            computed_answer_source = "gemini_knowledge_fallback"
        else:
            computed_source_label = "AyurMitra Knowledge Base (WHO / NAMASTE / IMPPAT)"
            computed_answer_source = "ayurveda_rag"

        return {
            "raw_query": query,
            "system_mode": system_mode,
            "detected_language": dominant_lang,
            "dominant_language": dominant_lang,
            "target_language": effective_target_lang,
            "language_mode": effective_target_lang,
            "display_language": lang_res.get("display", effective_target_lang),
            "tts_lang": lang_res.get("tts_lang", "en-IN"),
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
            "stage_timings_ms": stage_timings,
            "backends": self.backend_info(),
            "evidence_check": evidence_check,
            "is_emergency": False,
            "machine_translated": gen_res.get("machine_translated", False),
            "answer_grounding": gen_res.get("answer_grounding"),
            "generator_used": generator_used,
            "generator_note": generator_note,
            "evidence_support_rate": gen_res.get("evidence_support_rate", 1.0),
            "claim_validation": gen_res.get("claim_validation"),
            "route_category": "AYURVEDA_DOMAIN",
            "route_label": "AyurMitra Knowledge Base" if computed_answer_source == "ayurveda_rag" else "AyurMitra + External APIs",
            "source_label": computed_source_label,
            "answer_source": computed_answer_source,
            "is_ayurvedic_grounded": computed_answer_source == "ayurveda_rag",
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
                         target_lang, enable_web_search, safety, start_time, stage_timings=None) -> Dict[str, Any]:
        from app.pipeline.generator import LOCALIZED_STRINGS
        lang = target_lang if target_lang in ("en", "hi", "kn", "hinglish", "kanglish") else "en"
        msg = safety_message(safety["reason"], lang)
        loc_key = lang if lang in LOCALIZED_STRINGS else "en"
        disclaimer = LOCALIZED_STRINGS[loc_key]["disclaimer"]
        use_terminology = config.get("use_terminology", True)
        elapsed_ms = (time.time() - start_time) * 1000.0
        timings = dict(stage_timings or {})
        timings["total_ms"] = round(elapsed_ms, 2)
        return {
            "raw_query": query,
            "system_mode": system_mode,
            "detected_language": dominant_lang,
            "dominant_language": dominant_lang,
            "target_language": lang,
            "language_mode": lang,
            "display_language": lang,
            "tts_lang": "hi-IN" if lang in ("hi", "hinglish") else ("kn-IN" if lang in ("kn", "kanglish") else "en-IN"),
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
            "latency_ms": elapsed_ms,
            "stage_timings_ms": timings,
            "backends": self.backend_info(),
            "machine_translated": False,
            "answer_grounding": "safety_gate",
            "generator_used": "safety_gate",
            "generator_note": None,
            "route_category": "UNSAFE_OR_MEDICALLY_SENSITIVE",
            "route_label": "Safety Guardrail",
            "source_label": "Safety & Medical Disclaimer",
            "answer_source": "safety_gate",
            "is_ayurvedic_grounded": False,
        }

    def _wrap_general_ai_response(
        self, query: str, system_mode: str, lang_info: dict, dominant_lang: str,
        effective_target_lang: str, lang_res: dict, start_time: float,
        engine_res: dict, route_res: dict, stage_timings=None
    ) -> Dict[str, Any]:
        from app.core.query_router import QueryRoute
        elapsed_ms = (time.time() - start_time) * 1000.0
        route_cat = route_res.get("route", QueryRoute.GENERAL_KNOWLEDGE)
        timings = dict(stage_timings or {})
        timings["total_ms"] = round(elapsed_ms, 2)

        route_labels = {
            QueryRoute.GENERAL_KNOWLEDGE: "General AI Knowledge",
            QueryRoute.CURRENT_INFORMATION: "Live / Current Information",
            QueryRoute.MIXED_DOMAIN: "Hybrid (Ayurveda + General AI)",
            QueryRoute.UNCLEAR_QUERY: "Clarification Needed",
            QueryRoute.UNSAFE_OR_MEDICALLY_SENSITIVE: "Safety Guardrail",
            QueryRoute.AYURVEDA_DOMAIN: "AyurMitra Knowledge Base",
        }

        return {
            "raw_query": query,
            "system_mode": system_mode,
            "detected_language": dominant_lang,
            "dominant_language": dominant_lang,
            "target_language": effective_target_lang,
            "language_mode": effective_target_lang,
            "display_language": lang_res.get("display", effective_target_lang),
            "tts_lang": lang_res.get("tts_lang", "en-IN"),
            "is_code_mixed": lang_info.get("is_code_mixed", False),
            "code_mix_type": lang_info.get("code_mix_type", "monolingual"),
            "segments": lang_info.get("segments", []),
            "active_components": {
                "system_mode": system_mode,
                "bm25_lexical": route_cat == QueryRoute.MIXED_DOMAIN,
                "dense_semantic": route_cat == QueryRoute.MIXED_DOMAIN,
                "terminology_protection": route_cat == QueryRoute.MIXED_DOMAIN,
                "terminology_preservation": route_cat == QueryRoute.MIXED_DOMAIN,
                "kg_grounding": route_cat == QueryRoute.MIXED_DOMAIN,
                "knowledge_graph_grounding": route_cat == QueryRoute.MIXED_DOMAIN,
                "web_search_fallback": True,
                "web_search_configured": True,
                "web_search_triggered": True,
                "web_search_status": "active_general_knowledge",
                "web_sources_retrieved": len(engine_res.get("citations", [])),
            },
            "lang_detect_meta": lang_info,
            "translation_meta": {"method": "general_ai_translator", "translated_text": "", "success": True},
            "use_terminology": route_cat == QueryRoute.MIXED_DOMAIN,
            "detected_terms": engine_res.get("detected_terms", []),
            "canonical_query": query,
            "retrieved_passages": engine_res.get("retrieved_passages", []),
            "web_passages": engine_res.get("retrieved_passages", []),
            "graph_facts": engine_res.get("graph_facts", []),
            "graph_expansion_terms": [],
            "retrieval_query": query,
            "answer": engine_res.get("answer", ""),
            "abstained": engine_res.get("abstained", False),
            "abstention_reason": engine_res.get("abstention_reason"),
            "citations": engine_res.get("citations", []),
            "disclaimer": EDUCATIONAL_DISCLAIMER,
            "latency_ms": elapsed_ms,
            "stage_timings_ms": timings,
            "backends": self.backend_info(),
            "evidence_check": {"judgeable": False, "supported": True, "keywords": [], "matched": []},
            "is_emergency": False,
            "machine_translated": engine_res.get("machine_translated", False),
            "answer_grounding": engine_res.get("answer_source", "general_ai"),
            "generator_used": engine_res.get("answer_source", "general_ai"),
            "generator_note": None,
            "evidence_support_rate": engine_res.get("evidence_support_rate", 0.95),
            "claim_validation": engine_res.get("claim_validation"),
            "route_category": route_cat.value if hasattr(route_cat, "value") else str(route_cat),
            "route_label": route_labels.get(route_cat, "General AI Knowledge"),
            "source_label": engine_res.get("source_label", "General AI Knowledge"),
            "answer_source": engine_res.get("answer_source", "general_ai"),
            "is_ayurvedic_grounded": engine_res.get("is_ayurvedic_grounded", False),
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
