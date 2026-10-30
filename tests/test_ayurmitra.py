"""
Automated Test Suite for AyurMitra
====================================
Validates all pipeline stages:
  1. Multilingual Language Identification (EN, HI, KN, Romanized)
  2. Terminology matching, Kannada suffix handling, and term protection
  3. Hybrid BM25 & Dense retrieval
  4. End-to-end English query -> English answer
  5. End-to-end Hindi query -> Hindi answer with Devanagari term preservation
  6. End-to-end Kannada query -> Kannada answer with Kannada term preservation
  7. Translation failure / fallback transparent reporting
  8. Knowledge graph & symptom emergency safety guardrails
"""

import pytest
from app.core.language_detect import detect, classify_input_type
from app.core.matcher import TerminologyMatcher
from app.core.protection import TerminologyProtector
from app.pipeline.hybrid_retriever import HybridRetriever
from app.pipeline.rag_pipeline import AyurMitraPipeline
from app.core.knowledge_graph import AyurKnowledgeGraph
from app.core.symptom_mapper import EducationalSymptomMapper
from app.pipeline.translator import MultilingualTranslator


def test_language_detection():
    # Exact UI queries
    en_det = detect("What is the role of Agni in digestion according to Ayurveda?")
    assert en_det["lang"] == "en"
    assert not en_det["is_romanized"]

    hi_det = detect("पित्त दोष के कार्य क्या हैं?")
    assert hi_det["lang"] == "hi"
    assert hi_det["script"] == "devanagari"
    assert not hi_det["is_romanized"]

    kn_det = detect("ಪಿತ್ತಕ್ಕೆ ಸಂಬಂಧಿಸಿದ ಲಕ್ಷಣಗಳು ಯಾವುವು?")
    assert kn_det["lang"] == "kn"
    assert kn_det["script"] == "kannada"
    assert not kn_det["is_romanized"]

    # Romanized variations
    hi_rom = detect("Pitta dosha ke lakshan kya hai?")
    assert hi_rom["lang"] == "hi"
    assert hi_rom["is_romanized"]

    kn_rom = detect("Pitta doshada lakshanagalu yavuvu?")
    assert kn_rom["lang"] == "kn"
    assert kn_rom["is_romanized"]

    assert detect("")["lang"] == "unknown"


def test_terminology_matcher_multilingual():
    matcher = TerminologyMatcher()

    # English
    en_terms = matcher.find_terms("What is the function of Pitta Dosha?")
    canon_terms = [t["canonical_term"] for t in en_terms]
    assert "Pitta Dosha" in canon_terms or "Pitta" in canon_terms

    # Hindi
    hi_terms = matcher.find_terms("अग्नि और कफ के क्या संबंध हैं?")
    hi_canons = [t["canonical_term"] for t in hi_terms]
    assert "Agni" in hi_canons
    assert "Kapha" in hi_canons

    # Kannada inflected suffix (-kke dative)
    kn_terms = matcher.find_terms("ಪಿತ್ತಕ್ಕೆ ಪರಿಹಾರವೇನು?")
    kn_canons = [t["canonical_term"] for t in kn_terms]
    assert "Pitta" in kn_canons

    # Multiple terms
    multi_terms = matcher.find_terms("How do Vata and Kapha interact with Agni?")
    multi_canons = [t["canonical_term"] for t in multi_terms]
    assert "Vata" in multi_canons
    assert "Kapha" in multi_canons
    assert "Agni" in multi_canons


def test_terminology_protection_and_restoration():
    protector = TerminologyProtector()
    query = "वात के बढ़ने से क्या होता है?"
    protected, p_map = protector.protect(query)

    assert "__AYURTERM_" in protected
    assert len(p_map) > 0

    # Test canonical restoration (English)
    restored_en = protector.restore_canonical(protected, p_map)
    assert "Vata" in restored_en

    # Test restoration to Hindi (Devanagari)
    restored_hi = protector.restore_to_language(protected, p_map, target_lang="hi")
    assert "वात" in restored_hi

    # Test restoration to Kannada script
    restored_kn = protector.restore_to_language(protected, p_map, target_lang="kn")
    assert "ವಾತ" in restored_kn


def test_hybrid_retriever():
    retriever = HybridRetriever()
    results = retriever.retrieve("Vata dosha symptoms", top_k=3, use_bm25=True, use_dense=True)

    assert len(results) > 0
    assert "chunk_id" in results[0]
    assert "source_id" in results[0]
    assert "rrf_score" in results[0]


def test_end_to_end_english_query_and_answer():
    pipe = AyurMitraPipeline()
    res = pipe.process_query("What is the role of Agni in digestion according to Ayurveda?", system_mode="P1")

    assert res["detected_language"] == "en"
    assert res["target_language"] == "en"
    assert not res["abstained"]
    assert len(res["retrieved_passages"]) > 0
    assert len(res["citations"]) > 0
    assert "Based on curated Ayurvedic literature" in res["answer"]
    assert "Agni" in [t["canonical_term"] for t in res["detected_terms"]]


def test_end_to_end_hindi_query_and_answer():
    pipe = AyurMitraPipeline()
    # Exact Hindi example query from UI
    res = pipe.process_query("पित्त दोष के कार्य क्या हैं?", system_mode="P1")

    assert res["detected_language"] == "hi"
    assert res["target_language"] == "hi"
    assert not res["abstained"]
    assert len(res["retrieved_passages"]) > 0
    assert len(res["citations"]) > 0

    # Answer must be in Hindi
    assert "प्रमाणित आयुर्वेदिक साहित्य के अनुसार" in res["answer"]
    # Preserved Hindi term
    assert "पित्त" in res["answer"]
    assert "दोष" in res["answer"]
    assert "उद्धृत स्रोत" in res["answer"]


def test_end_to_end_kannada_query_and_answer():
    pipe = AyurMitraPipeline()
    # Exact Kannada example query from UI
    res = pipe.process_query("ಪಿತ್ತಕ್ಕೆ ಸಂಬಂಧಿಸಿದ ಲಕ್ಷಣಗಳು ಯಾವುವು?", system_mode="P1")

    assert res["detected_language"] == "kn"
    assert res["target_language"] == "kn"
    assert not res["abstained"]
    assert len(res["retrieved_passages"]) > 0
    assert len(res["citations"]) > 0

    # Answer must be in Kannada
    assert "ಪ್ರಾಮಾಣಿಕ ಆಯುರ್ವೇದ ಸಾಹಿತ್ಯದ ಪ್ರಕಾರ" in res["answer"]
    # Preserved Kannada term
    assert "ಪಿತ್ತ" in res["answer"]
    assert "ಉಲ್ಲೇಖಿಸಿದ ಮೂಲಗಳು" in res["answer"]


def test_translation_fallback_and_transparency():
    translator = MultilingualTranslator()

    # Empty query
    empty_res = translator.translate_to_english("", source_lang="hi")
    assert empty_res["success"]

    # Unknown dialect word transliterates with explicit warning note
    fallback_res = translator.translate_to_english("अजीब सा रोग", source_lang="hi")
    assert fallback_res["target_lang"] == "en"
    assert fallback_res["warning"] is not None

    # Passthrough check
    pass_res = translator.translate_from_english("Hello", target_lang="es")
    assert not pass_res["success"]


def test_knowledge_graph_provenance():
    kg = AyurKnowledgeGraph()
    info = kg.query_concept("Pitta")
    assert info["found"]
    assert info["attributes"]["source_id"] == "NAMASTE_ayu-sat-table-a"
    assert len(info["connections"]) > 0
    assert "source_id" in info["connections"][0]


def test_system_modes_differentiation():
    pipe = AyurMitraPipeline()
    query = "What is the function of Pitta?"

    res_b0 = pipe.process_query(query, system_mode="B0")
    assert not res_b0["active_components"]["terminology_protection"]
    assert not res_b0["active_components"]["dense_semantic"]
    assert not res_b0["active_components"]["kg_grounding"]
    assert res_b0["system_mode"] == "B0"

    res_b1 = pipe.process_query(query, system_mode="B1")
    assert not res_b1["active_components"]["terminology_protection"]
    assert res_b1["active_components"]["dense_semantic"]
    assert not res_b1["active_components"]["kg_grounding"]
    assert res_b1["system_mode"] == "B1"

    res_p1 = pipe.process_query(query, system_mode="P1")
    assert res_p1["active_components"]["terminology_protection"]
    assert res_p1["active_components"]["dense_semantic"]
    assert not res_p1["active_components"]["kg_grounding"]
    assert res_p1["system_mode"] == "P1"

    res_p2 = pipe.process_query(query, system_mode="P2")
    assert res_p2["active_components"]["terminology_protection"]
    assert res_p2["active_components"]["dense_semantic"]
    assert res_p2["active_components"]["kg_grounding"]
    assert res_p2["system_mode"] == "P2"
    assert "Knowledge Graph Grounding" in res_p2["answer"]


def test_symptom_mapper_safety_and_emergency():
    mapper = EducationalSymptomMapper()

    # Normal symptom
    res = mapper.analyze_symptoms("I have severe dry skin and joint stiffness")
    assert not res["abstained"]
    assert "Vata" in res["primary_conceptual_tendency"]

    # Ambiguous symptom MUST trigger abstention
    ambig_res = mapper.analyze_symptoms("I feel a little strange today")
    assert ambig_res["abstained"]
    assert ambig_res["reason"] in ("insufficient_symptom_detail", "no_supported_symptom_recognized")

    # Emergency symptom MUST trigger emergency abstention
    emerg_res = mapper.analyze_symptoms("Patient has sudden severe chest pain and difficulty breathing")
    assert emerg_res["abstained"]
    assert emerg_res["reason"] == "emergency_symptom_detected"


def test_exact_screenshot_case_severe_headache_and_multilingual_emergencies():
    mapper = EducationalSymptomMapper()

    # Exact screenshot case from user: "I have severe headache"
    res_en = mapper.analyze_symptoms("I have severe headache")
    assert res_en["abstained"]
    assert res_en["reason"] == "emergency_symptom_detected"
    assert "URGENT HEALTH ADVISORY" in res_en["emergency_alert"]
    # MUST NOT assign to any dosha
    assert "primary_conceptual_tendency" not in res_en or res_en["primary_conceptual_tendency"] is None

    # Hindi emergency equivalent
    res_hi = mapper.analyze_symptoms("मुझे बहुत तेज सिरदर्द है")
    assert res_hi["abstained"]
    assert res_hi["reason"] == "emergency_symptom_detected"
    assert "तत्काल स्वास्थ्य परामर्श चेतावनी" in res_hi["emergency_alert"]

    # Kannada emergency equivalent
    res_kn = mapper.analyze_symptoms("ನನಗೆ ತೀವ್ರ ತಲೆನೋವು ಇದೆ")
    assert res_kn["abstained"]
    assert res_kn["reason"] == "emergency_symptom_detected"
    assert "ತುರ್ತು ಆರೋಗ್ಯ ಸಲಹಾ ಎಚ್ಚರಿಕೆ" in res_kn["emergency_alert"]

    # Hinglish emergency equivalent
    res_hing = mapper.analyze_symptoms("mujhe tez sirdard ho raha hai")
    assert res_hing["abstained"]
    assert res_hing["reason"] == "emergency_symptom_detected"
    assert "URGENT HEALTH ADVISORY" in res_hing["emergency_alert"]

    # Kanglish emergency equivalent
    res_kang = mapper.analyze_symptoms("nanage tumba tale novu ide")
    assert res_kang["abstained"]
    assert res_kang["reason"] == "emergency_symptom_detected"
    assert "URGENT HEALTH ADVISORY" in res_kang["emergency_alert"]


def test_symptom_mapper_multilingual_and_romanized():
    mapper = EducationalSymptomMapper()

    # 1. English
    res_en = mapper.analyze_symptoms("I have dry skin and joint stiffness after cold weather.")
    assert not res_en["abstained"]
    assert "Vata" in res_en["primary_conceptual_tendency"]
    assert res_en["detected_language"] == "en"
    assert len(res_en["mappings"]) >= 2
    assert "WHO_9789240064935" in res_en["mappings"][0]["source_id"]

    # 2. Hindi Devanagari
    res_hi = mapper.analyze_symptoms("मेरी त्वचा बहुत सूखी है और जोड़ों में दर्द रहता है।")
    assert not res_hi["abstained"]
    assert "वात" in res_hi["primary_conceptual_tendency"]
    assert res_hi["detected_language"] == "hi"
    assert "शैक्षिक विश्लेषण" in res_hi["summary"]

    # 3. Kannada script
    res_kn = mapper.analyze_symptoms("ನನ್ನ ಚರ್ಮ ಒಣಗಿದೆ ಮತ್ತು ಕೀಲುಗಳಲ್ಲಿ ನೋವು ಇದೆ.")
    assert not res_kn["abstained"]
    assert "ವಾತ" in res_kn["primary_conceptual_tendency"]
    assert res_kn["detected_language"] == "kn"
    assert "ಶೈಕ್ಷಣಿಕ ವಿಶ್ಲೇಷಣೆ" in res_kn["summary"]

    # 4. Hinglish (Romanized Hindi)
    res_hing = mapper.analyze_symptoms("mujhe severe dry skin aur joint pain hai.")
    assert not res_hing["abstained"]
    assert "Vata" in res_hing["primary_conceptual_tendency"]
    assert res_hing["is_romanized"]

    # 5. Kanglish (Romanized Kannada)
    res_kang = mapper.analyze_symptoms("nanna charma dry ide matte keelu novu ide.")
    assert not res_kang["abstained"]
    assert "Vata" in res_kang["primary_conceptual_tendency"]
    assert res_kang["is_romanized"]


def test_english_with_ayurvedic_terms_not_misclassified():
    # Sentences with domain Ayurvedic terms (Pitta, Agni, Vata, Dosha, etc.) must NOT be classified as Hindi
    q1 = "What are the qualities and functions of Pitta Dosha in digestion?"
    det1 = detect(q1)
    assert det1["lang"] == "en"
    assert not det1["is_romanized"]

    q2 = "Explain the classical role of Agni and Ama in Ayurvedic pathology."
    det2 = detect(q2)
    assert det2["lang"] == "en"
    assert not det2["is_romanized"]

    s1 = "I experience dry skin and cold hands linked to Vata Dosha."
    mapper = EducationalSymptomMapper()
    res1 = mapper.analyze_symptoms(s1)
    assert res1["detected_language"] == "en"
    assert not res1["is_romanized"]
    assert "Vata" in res1["primary_conceptual_tendency"]


def test_unsupported_symptoms_multilingual_abstention():
    mapper = EducationalSymptomMapper()

    # English vague input
    res_en = mapper.analyze_symptoms("I feel slightly weird and unusual today.")
    assert res_en["abstained"]
    assert res_en["reason"] == "no_supported_symptom_recognized"
    assert "Abstention:" in res_en["message"]

    # Hindi vague input
    res_hi = mapper.analyze_symptoms("आज मुझे कुछ अजीब और अलग सा लग रहा है।")
    assert res_hi["abstained"]
    assert res_hi["reason"] == "no_supported_symptom_recognized"
    assert "अस्वीकरण" in res_hi["message"]

    # Kannada vague input
    res_kn = mapper.analyze_symptoms("ನನಗೆ ಇಂದು ಏನೋ ವಿಚಿತ್ರ ಅನುಭವವಾಗುತ್ತಿದೆ.")
    assert res_kn["abstained"]
    assert res_kn["reason"] == "no_supported_symptom_recognized"
    assert "ತಿರಸ್ಕಾರ ಸೂಚನೆ" in res_kn["message"]


def test_all_workspace_datasets_ingested_and_searchable():
    from app.core.corpus_builder import build_corpus
    chunks = build_corpus()

    source_ids = {c["source_id"] for c in chunks}
    # Must include all 7 workspace sources
    assert "WHO_9789240064935" in source_ids
    assert "NAMASTE_ayu-sat-table-a" in source_ids
    assert "IMPPAT_2.0" in source_ids
    assert "API_SingleHerbalFormulations" in source_ids
    assert "Ayurveda_Literature_QA" in source_ids
    assert "AyurQA_Hindi_Parquet" in source_ids
    assert "AyurQA_Kannada_Parquet" in source_ids

    # Total corpus size
    assert len(chunks) >= 1200


def test_controlled_web_search_fallback():
    from app.pipeline.web_search import WebSearchFallback
    web = WebSearchFallback(timeout=6)

    # Search EuropePMC / Wikipedia
    res = web.search("Ashwagandha clinical trials", max_results=3)
    if res["success"]:
        assert len(res["passages"]) > 0
        p0 = res["passages"][0]
        assert "title" in p0
        assert "url" in p0
        assert p0["url"].startswith("http")
        assert "snippet" in p0

    # Test pipeline integration and reproducible toggle
    pipe = AyurMitraPipeline()

    # With web search enabled on external/modern question
    res_with_web = pipe.process_query(
        "What are modern clinical trials on Ashwagandha?",
        system_mode="P1",
        enable_web_search=True
    )
    assert not res_with_web["abstained"]

    # With web search disabled (controlled research evaluation mode)
    res_no_web = pipe.process_query(
        "What are modern clinical trials on Ashwagandha?",
        system_mode="P1",
        enable_web_search=False
    )
    assert not res_no_web["active_components"]["web_search_fallback"]
    assert len(res_no_web["web_passages"]) == 0


def test_broad_multilingual_natural_language_queries():
    pipe = AyurMitraPipeline()

    # 1. Medicinal plant / IMPPAT query
    res_plant = pipe.process_query("What information is available about medicinal plant Ashwagandha in IMPPAT?", system_mode="P1")
    assert not res_plant["abstained"]
    assert len(res_plant["citations"]) > 0

    # 2. Hindi natural language query (non-preset)
    res_hi = pipe.process_query("आयुर्वेद में त्रिदोष और अग्नि का क्या महत्व है?", system_mode="P1")
    assert res_hi["detected_language"] == "hi"
    assert not res_hi["abstained"]
    assert "प्रमाणित आयुर्वेदिक साहित्य" in res_hi["answer"]

    # 3. Kannada natural language query (non-preset)
    res_kn = pipe.process_query("ಆಯುರ್ವೇದದಲ್ಲಿ ತ್ರಿದೋಷಗಳ ಪಾತ್ರವೇನು?", system_mode="P1")
    assert res_kn["detected_language"] == "kn"
    assert not res_kn["abstained"]
    assert "ಪ್ರಾಮಾಣಿಕ ಆಯುರ್ವೇದ ಸಾಹಿತ್ಯದ ಪ್ರಕಾರ" in res_kn["answer"]


def test_codemixed_multilingual_segment_detection():
    # 1. English + Hindi (Devanagari)
    q_en_hi = "What are the primary symptoms of कफ वृद्धि in human body?"
    det_en_hi = detect(q_en_hi)
    assert det_en_hi["is_code_mixed"]
    assert "en" in det_en_hi["detected_languages"]
    assert "hi" in det_en_hi["detected_languages"]
    assert len(det_en_hi["segments"]) >= 2

    # 2. English + Kannada script
    q_en_kn = "Explain the concept of ಪಿತ್ತ ಪ್ರಕೋಪ and its relation to body heat."
    det_en_kn = detect(q_en_kn)
    assert det_en_kn["is_code_mixed"]
    assert "en" in det_en_kn["detected_languages"]
    assert "kn" in det_en_kn["detected_languages"]
    assert len(det_en_kn["segments"]) >= 2

    # 3. Trilingual mixed: Hindi + English + Kannada
    q_tri = "वात दोष (Vata) and ಪಿತ್ತಕ್ಕೆ ಸಂಬಂಧಿಸಿದ lakshana kya hai?"
    det_tri = detect(q_tri)
    assert det_tri["is_code_mixed"]
    assert det_tri["code_mix_type"] == "trilingual_mixed"
    assert len(det_tri["segments"]) >= 3


def test_explicit_output_language_selection():
    pipe = AyurMitraPipeline()
    query = "What is the function of Pitta and Agni in digestion?"

    # Explicit Hindi output
    res_hi = pipe.process_query(query, target_lang="hi", system_mode="P1")
    assert res_hi["target_language"] == "hi"
    assert "प्रमाणित आयुर्वेदिक साहित्य" in res_hi["answer"]

    # Explicit Kannada output
    res_kn = pipe.process_query(query, target_lang="kn", system_mode="P1")
    assert res_kn["target_language"] == "kn"
    assert "ಪ್ರಾಮಾಣಿಕ ಆಯುರ್ವೇದ ಸಾಹಿತ್ಯದ ಪ್ರಕಾರ" in res_kn["answer"]

    # Explicit English output from Hindi query
    res_en = pipe.process_query("पित्त दोष के कार्य क्या हैं?", target_lang="en", system_mode="P1")
    assert res_en["target_language"] == "en"
    assert "Based on curated Ayurvedic literature" in res_en["answer"]


def test_ayurvedic_spelling_variants_normalization():
    matcher = TerminologyMatcher()

    # Transliteration variations
    terms_vatha = matcher.find_terms("How does vatha imbalance cause joint ache?")
    assert any(t["canonical_term"] == "Vata" for t in terms_vatha)

    terms_pitha = matcher.find_terms("Patient has pitha heat and acid reflux")
    assert any(t["canonical_term"] == "Pitta" for t in terms_pitha)

    terms_prakruthi = matcher.find_terms("What is my prakruthi type according to doshas?")
    assert any(t["canonical_term"] == "Prakriti" for t in terms_prakruthi)

    terms_aagnee = matcher.find_terms("How to balance weak aagnee?")
    assert any(t["canonical_term"] == "Agni" for t in terms_aagnee)


def test_codemixed_evaluation_dataset_integrity():
    from pathlib import Path
    import json
    from app.config import DATA_EVAL  # F8 fix: resolves Data/ vs data/ on case-sensitive filesystems
    eval_file = DATA_EVAL / "codemixed_multilingual_eval.json"
    assert eval_file.exists()

    with open(eval_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) >= 20
    for item in data:
        assert "id" in item
        assert "query" in item
        assert "dominant_language" in item
        assert "expected_output_language" in item
        assert "expected_behavior" in item
        assert "review_status" in item


def test_ashwagandha_retrieval_relevance_and_no_hallucinations():
    pipe = AyurMitraPipeline()
    res = pipe.process_query(
        "What information does the available evidence provide about Ashwagandha (Withania somnifera)?",
        system_mode="P1"
    )
    assert not res["abstained"]
    assert len(res["retrieved_passages"]) > 0

    top_chunk_texts = [p.get("text", "").lower() for p in res["retrieved_passages"][:2]]
    # Top results must specifically match Withania somnifera / Ashwagandha
    assert any("withania somnifera" in t or "ashwagandha" in t or "asvagandha" in t for t in top_chunk_texts)

    # Citations must reflect IMPPAT or API formulations, not diabetes passages
    citation_titles = [c.get("title", "").lower() for c in res["citations"]]
    assert any("imppat" in t or "pharmacopoeia" in t for t in citation_titles)

    # Generated answer must contain the structured template
    ans = res["answer"]
    assert "**Answer:**" in ans
    assert "**Explanation:**" in ans
    assert "**Ayurvedic terms:**" in ans
    assert "**Sources:**" in ans
    assert "**Evidence limitation:**" in ans


def test_structured_answer_multilingual_formatting():
    pipe = AyurMitraPipeline()

    # Hindi structured answer test
    res_hi = pipe.process_query("पित्त दोष के कार्य क्या हैं?", system_mode="P1", target_lang="hi")
    ans_hi = res_hi["answer"]
    assert "**Answer:**" in ans_hi
    assert "**Explanation:**" in ans_hi
    assert "**Ayurvedic terms:**" in ans_hi
    assert "**Sources:**" in ans_hi
    assert "**Evidence limitation:**" in ans_hi
    assert "प्रमाणित आयुर्वेदिक साहित्य के अनुसार" in ans_hi

    # Kannada structured answer test
    res_kn = pipe.process_query("ಪಿತ್ತಕ್ಕೆ ಸಂಬಂಧಿಸಿದ ಲಕ್ಷಣಗಳು ಯಾವುವು?", system_mode="P1", target_lang="kn")
    ans_kn = res_kn["answer"]
    assert "**Answer:**" in ans_kn
    assert "**Explanation:**" in ans_kn
    assert "**Ayurvedic terms:**" in ans_kn
    assert "**Sources:**" in ans_kn
    assert "**Evidence limitation:**" in ans_kn
    assert "ಪ್ರಾಮಾಣಿಕ ಆಯುರ್ವೇದ ಸಾಹಿತ್ಯದ ಪ್ರಕಾರ" in ans_kn


def test_web_search_status_transitions_and_mock():
    from unittest.mock import MagicMock
    pipe = AyurMitraPipeline()

    # 1. Disabled
    res_dis = pipe.process_query("What is Agni?", system_mode="P1", enable_web_search=False)
    assert res_dis["active_components"]["web_search_status"] == "disabled"
    assert not res_dis["active_components"]["web_search_triggered"]

    # 2. Not needed (local evidence is strong for standard concept)
    res_nn = pipe.process_query("What is Agni in digestion?", system_mode="P1", enable_web_search=True)
    assert res_nn["active_components"]["web_search_status"] == "not_needed"
    assert not res_nn["active_components"]["web_search_triggered"]

    # 3. Triggered and success (mocked)
    pipe.web_search.search = MagicMock(return_value={
        "success": True,
        "passages": [{
            "source_type": "peer_reviewed_academic",
            "title": "Clinical Efficacy of Ashwagandha",
            "url": "https://doi.org/10.1016/sample",
            "publisher": "Journal of Ethnopharmacology",
            "year": "2023",
            "snippet": "Randomized controlled trial demonstrating efficacy.",
            "provenance": "[EuropePMC Peer-Reviewed]"
        }]
    })
    res_trig = pipe.process_query("What are modern clinical trial findings?", system_mode="P1", enable_web_search=True)
    assert res_trig["active_components"]["web_search_status"] == "success"
    assert res_trig["active_components"]["web_search_triggered"]
    assert len(res_trig["web_passages"]) == 1

    # 4. Error state handled gracefully (mocked)
    pipe.web_search.search = MagicMock(side_effect=RuntimeError("Network unreachable"))
    res_err = pipe.process_query("What are modern clinical trial findings?", system_mode="P1", enable_web_search=True)
    assert res_err["active_components"]["web_search_status"] == "error"


def test_multi_symptom_decomposition_and_provenance():
    mapper = EducationalSymptomMapper()

    # Multi-symptom input: dry skin AND joint pain
    res = mapper.analyze_symptoms("I have severe dry skin and stiff joints after cold season.")
    assert not res["abstained"]
    assert len(res["mappings"]) >= 2

    # Check each symptom has explicit provenance
    for m in res["mappings"]:
        assert "symptom_phrase" in m
        assert "associated_dosha" in m
        assert "provenance" in m
        assert "source_id" in m
        assert "WHO" in m["provenance"] or "NAMASTE" in m["provenance"]


def test_terminology_does_not_falsely_match_everyday_words():
    """Verify that everyday English and Hindi/Kannada grammatical words are never matched as domain terms."""
    matcher = TerminologyMatcher()

    # 1. Hindi verb 'karta' in Hinglish phrase must not match technical term kartA
    hinglish_q = "Agni digestion mein kya role play karta hai?"
    terms_hi = [t["canonical_term"] for t in matcher.find_terms(hinglish_q)]
    assert terms_hi == ["Agni"]
    assert "kartA" not in terms_hi

    # 2. Kanglish phrase
    kanglish_q = "Agni digestion alli enu role ide?"
    terms_kn = [t["canonical_term"] for t in matcher.find_terms(kanglish_q)]
    assert terms_kn == ["Agni"]

    # 3. Everyday English words (time, five, box, deep, cough, blood, pulse)
    en_q1 = "What is the best time to take Triphala after five days?"
    terms_en1 = [t["canonical_term"] for t in matcher.find_terms(en_q1)]
    assert terms_en1 == ["Triphala"]
    assert "Time" not in terms_en1
    assert "Five" not in terms_en1

    en_q2 = "I have a cough and want to check my pulse rate."
    terms_en2 = [t["canonical_term"] for t in matcher.find_terms(en_q2)]
    assert "Kapha" not in terms_en2
    assert "Nadi" not in terms_en2

    # 4. Verified genuine Ayurvedic terms must remain detected
    v_terms = [t["canonical_term"] for t in matcher.find_terms("What is the difference between Vata and Pitta?")]
    assert "Vata" in v_terms
    assert "Pitta" in v_terms


def test_four_key_ayurvedic_queries_end_to_end():
    """Verify the four required test queries produce clean canonical queries and valid citations."""
    from app.pipeline.rag_pipeline import AyurMitraPipeline
    pipe = AyurMitraPipeline()

    # 1. Hinglish query
    r1 = pipe.process_query("Agni digestion mein kya role play karta hai?", system_mode="P1")
    assert r1["canonical_query"] == "What is the role of Agni in digestion?"
    assert [t["canonical_term"] for t in r1["detected_terms"]] == ["Agni"]
    assert not r1["abstained"]
    assert len(r1["citations"]) > 0

    # 2. Kanglish query
    r2 = pipe.process_query("Agni digestion alli enu role ide?", system_mode="P1")
    assert r2["canonical_query"] == "What is the role of Agni in digestion?"
    assert [t["canonical_term"] for t in r2["detected_terms"]] == ["Agni"]
    assert not r2["abstained"]
    assert len(r2["citations"]) > 0

    # 3. English query
    r3 = pipe.process_query("What is the role of Agni in digestion?", system_mode="P1")
    assert r3["canonical_query"] == "What is the role of Agni in digestion?"
    assert [t["canonical_term"] for t in r3["detected_terms"]] == ["Agni"]
    assert not r3["abstained"]
    assert len(r3["citations"]) > 0

    # 4. Dual term query
    r4 = pipe.process_query("What is the difference between Vata and Pitta?", system_mode="P1")
    assert "Vata" in [t["canonical_term"] for t in r4["detected_terms"]]
    assert "Pitta" in [t["canonical_term"] for t in r4["detected_terms"]]
    assert not r4["abstained"]
    assert len(r4["citations"]) > 0
