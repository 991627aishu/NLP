"""
Detailed stage-by-stage timer profiler for AyurMitra RAG
"""
import time
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from app.pipeline.rag_pipeline import AyurMitraPipeline
pipe = AyurMitraPipeline()

def timed_run(q, lang="en"):
    print(f"\n==========================================")
    print(f"QUERY: '{q}' (lang={lang})")
    print(f"==========================================")
    
    t_start = time.perf_counter()
    
    # Stage 1: Language detection
    t0 = time.perf_counter()
    from app.core.language_detect import resolve_target_language, detect
    lang_res = resolve_target_language(q, lang)
    lang_info = lang_res.get("detected_info") or detect(q)
    dominant_lang = lang_info.get("dominant_lang", lang_info.get("lang", "en"))
    effective_target_lang = lang_res.get("mode", dominant_lang)
    t_lang = (time.perf_counter() - t0) * 1000
    print(f"  [1] Language Detect:          {t_lang:8.2f} ms ({dominant_lang} -> {effective_target_lang})")
    
    # Stage 2: Routing
    t0 = time.perf_counter()
    route_res = pipe.router.classify(q)
    t_route = (time.perf_counter() - t0) * 1000
    print(f"  [2] Query Router:             {t_route:8.2f} ms ({route_res.get('route')})")
    
    # Stage 3: Terminology detection & protection
    t0 = time.perf_counter()
    detected_terms = pipe.matcher.find_terms(q)
    protected_text, placeholder_map = pipe.protector.protect(q) if detected_terms else (q, {})
    t_terms = (time.perf_counter() - t0) * 1000
    print(f"  [3] Terminology Protection:   {t_terms:8.2f} ms ({len(detected_terms)} terms detected)")
    
    # Stage 4: Translation to English
    t0 = time.perf_counter()
    trans_src_lang = effective_target_lang if effective_target_lang in ("hi", "kn", "hinglish", "kanglish") else dominant_lang
    trans_res = pipe.translator.translate_to_english(protected_text, source_lang=trans_src_lang)
    translated_query = trans_res["translated_text"]
    english_query = pipe.protector.restore_canonical(translated_query, placeholder_map) if placeholder_map else translated_query
    t_trans = (time.perf_counter() - t0) * 1000
    print(f"  [4] Translation & Canon:      {t_trans:8.2f} ms -> '{english_query}'")
    
    # Stage 5: Graph expansion
    t0 = time.perf_counter()
    graph_expansion_terms = []
    if detected_terms and hasattr(pipe.kg, "expansion_terms"):
        for t in detected_terms:
            for x in pipe.kg.expansion_terms(t.get("canonical_term", ""), k=5):
                if x not in graph_expansion_terms and len(graph_expansion_terms) < 5:
                    graph_expansion_terms.append(x)
    retrieval_query = english_query + (" " + " ".join(graph_expansion_terms) if graph_expansion_terms else "")
    t_graph_exp = (time.perf_counter() - t0) * 1000
    print(f"  [5] KG Expansion:             {t_graph_exp:8.2f} ms ({len(graph_expansion_terms)} terms)")
    
    # Stage 6: BM25 retrieval
    t0 = time.perf_counter()
    bm25_res = pipe.retriever.bm25.retrieve(retrieval_query, top_k=5)
    t_bm25 = (time.perf_counter() - t0) * 1000
    print(f"  [6] BM25 Retrieval:           {t_bm25:8.2f} ms ({len(bm25_res)} chunks)")
    
    # Stage 7: Dense retrieval (Gemini embedding)
    t0 = time.perf_counter()
    dense_res = pipe.retriever.dense.retrieve(retrieval_query, top_k=5)
    t_dense = (time.perf_counter() - t0) * 1000
    print(f"  [7] Dense (Gemini) Retrieval: {t_dense:8.2f} ms ({len(dense_res)} chunks)")
    
    # Stage 8: Hybrid RRF Fusion
    t0 = time.perf_counter()
    hybrid_res = pipe.retriever.retrieve(retrieval_query, top_k=5, use_bm25=True, use_dense=True, detected_terms=detected_terms)
    t_rrf = (time.perf_counter() - t0) * 1000
    print(f"  [8] Full Hybrid RRF Fusion:   {t_rrf:8.2f} ms ({len(hybrid_res)} chunks)")
    
    # Stage 9: Graph facts
    t0 = time.perf_counter()
    graph_facts = []
    if detected_terms and hasattr(pipe.kg, "facts_for_term"):
        seen_f = set()
        for t in detected_terms:
            for f in pipe.kg.facts_for_term(t.get("canonical_term", ""), limit=6):
                key = (f["query_concept"], f["relation"], f["target_id"])
                if key not in seen_f:
                    seen_f.add(key)
                    graph_facts.append(f)
    t_facts = (time.perf_counter() - t0) * 1000
    print(f"  [9] KG Facts Gathering:       {t_facts:8.2f} ms ({len(graph_facts)} facts)")
    
    # Stage 10: Gemini Generation
    t0 = time.perf_counter()
    from app.pipeline.llm_generator import LLMGenerator
    llm = LLMGenerator()
    llm_out = llm.generate(english_query if effective_target_lang == "en" else q,
                           hybrid_res, graph_facts, target_lang=effective_target_lang)
    t_gen = (time.perf_counter() - t0) * 1000
    print(f"  [10] Gemini Answer Generation: {t_gen:8.2f} ms (model: {llm_out.get('model')})")
    
    t_total = (time.perf_counter() - t_start) * 1000
    print(f"  ==> TOTAL PIPELINE TIME:      {t_total:8.2f} ms ({t_total/1000:.2f} s)")

timed_run("What is Vata dosha?", "en")
timed_run("ಕಾಮಣಿ", "kn")
