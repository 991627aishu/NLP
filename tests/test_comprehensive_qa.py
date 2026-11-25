"""
Comprehensive 16-Category QA & Architecture Test Suite for AyurMitra.
Covers unseen questions across Ayurveda, General Science, CS/Tech, Academic,
Current Info, Mixed-Domain, Ambiguous/Misspelled, EN/HI/KN/Hinglish/Kanglish,
and No-Supporting-Evidence queries.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("AYUR_TRANSLATOR_BACKEND", "rules")

from app.pipeline.rag_pipeline import AyurMitraPipeline  # noqa: E402
from app.pipeline.external_retriever import ExternalKnowledgeRetriever  # noqa: E402


TEST_CASES = [
    # Original user examples
    ("Ambiguous_kapa", "What is kapa?", "UNCLEAR_QUERY", "en"),
    ("Misspelled_kapa_ayurveda", "what is kapa in ayurveda?", "AYURVEDA_DOMAIN", "en"),
    # 1. Basic Ayurveda definitions
    ("1_Ayur_Def", "What is Kapha?", "AYURVEDA_DOMAIN", "en"),
    # 2. Ayurvedic concepts & terminology
    ("2_Ayur_Concept", "Explain Prakriti and Vikriti in Ayurveda.", "AYURVEDA_DOMAIN", "en"),
    # 3. Herbs & traditional uses
    ("3_Herb_Use", "What are the traditional uses of Ashwagandha?", "AYURVEDA_DOMAIN", "en"),
    # 4. Ayurveda-related research questions
    ("4_Ayur_Research", "What do modern clinical studies say about Ashwagandha in Ayurveda?", "MIXED_DOMAIN", "en"),
    # 5. General science
    ("5_Gen_Science", "Explain how photosynthesis works in plants.", "GENERAL_KNOWLEDGE", "en"),
    # 6. Computer science & technology
    ("6_CS_Tech", "Explain neural networks in machine learning.", "GENERAL_KNOWLEDGE", "en"),
    # 7. Academic questions
    ("7_Academic", "What is backpropagation in deep learning?", "GENERAL_KNOWLEDGE", "en"),
    # 8. Current or externally sourced information
    ("8_Current_Info", "What are the latest developments in artificial intelligence?", "CURRENT_INFORMATION", "en"),
    # 9. Mixed-domain comparisons
    ("9_Mixed_Domain", "Compare Ayurvedic Agni with modern biological metabolism.", "MIXED_DOMAIN", "en"),
    # 10. Ambiguous & misspelled
    ("10_Misspelled_Ayur", "What is kushta roga in Ayurveda?", "AYURVEDA_DOMAIN", "en"),
    # 11. English
    ("11_English", "What is the role of Pitta dosha?", "AYURVEDA_DOMAIN", "en"),
    # 12. Hindi
    ("12_Hindi", "कफ क्या है?", "AYURVEDA_DOMAIN", "hi"),
    # 13. Kannada
    ("13_Kannada", "ಕಫ ಎಂದರೇನು?", "AYURVEDA_DOMAIN", "kn"),
    # 14. Hinglish
    ("14_Hinglish", "Vata dosha ke lakshan kya hain?", "AYURVEDA_DOMAIN", "hi"),
    # 15. Kanglish
    ("15_Kanglish", "Kapha andre enu?", "AYURVEDA_DOMAIN", "kn"),
    # 16. No supporting evidence
    ("16_No_Evidence", "xzqvplm987", "AYURVEDA_DOMAIN", "en"),
]


def main() -> None:
    ext = ExternalKnowledgeRetriever()
    print("=== Direct External API Smoke Check ===")
    for dom, q in [("ayurveda", "Kapha dosha Ayurveda"), ("academic", "neural networks deep learning")]:
        er = ext.retrieve(q, domain=dom, max_results=3)
        print(f"  [{dom}] success={er['success']} providers={er['providers_used']} count={len(er['passages'])}")

    print("\n=== 16-Category Pipeline Verification ===")
    pipe = AyurMitraPipeline()
    passed = 0
    for label, query, expected_route, expected_lang in TEST_CASES:
        res = pipe.process_query(query, system_mode="P2", target_lang="auto", enable_web_search=True, generator="llm")
        route = res.get("route_category")
        tlang = res.get("target_language")
        abstained = res.get("abstained")
        cits = res.get("citations") or []
        src_lbl = res.get("source_label")
        ans_preview = (res.get("answer") or "").replace("\n", " ")[:140]

        route_ok = (route == expected_route)
        lang_ok = (tlang == expected_lang)
        # For UNCLEAR_QUERY and 16_No_Evidence, abstained=True is expected; for all others, abstained=False
        expect_abstain = label in ("Ambiguous_kapa", "16_No_Evidence")
        ans_ok = (abstained == expect_abstain) and bool(res.get("answer"))
        ok = route_ok and lang_ok and ans_ok
        if ok:
            passed += 1
        print(
            f"[{'PASS' if ok else 'FAIL'}] {label} | route={route} (exp={expected_route}) | "
            f"lang={tlang} (exp={expected_lang}) | abstained={abstained} | cits={len(cits)} | "
            f"src={src_lbl} | ans={ans_preview}..."
        )
    print(f"\nSummary: {passed}/{len(TEST_CASES)} passed")
    if passed < len(TEST_CASES):
        sys.exit(1)


if __name__ == "__main__":
    main()
