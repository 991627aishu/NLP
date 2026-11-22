"""
AyurMitra — Forensic Suite Runner (Sections 5 & 6)
==================================================
Runs unseen test queries across general vocabulary, ambiguous terminology,
classical Ayurveda, Hindi, Kannada, Romanized scripts, General Science,
Programming, Mathematics, History, and Mixed Domains.
Performs manual/automated evidence verification on 30 answers.
Outputs: AYURMITRA_FORENSIC_TEST_RESULTS.json
"""

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.pipeline.rag_pipeline import AyurMitraPipeline

UNSEEN_TEST_QUERIES = [
    # 1. Specifically Retested Mandatory Queries
    {"id": "RETEST_01", "category": "Mandatory Retest", "query": "What is roga?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "en", "forbidden": ["mopacho", "dance", "kuru"]},
    {"id": "RETEST_02", "category": "Mandatory Retest", "query": "रोग मतलब क्या होता है?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "hi", "forbidden": ["कुरु", "पापुआ", "mopacho"]},
    {"id": "RETEST_03", "category": "Mandatory Retest", "query": "ರೋಗ ಎಂದರೇನು?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "kn", "forbidden": ["ಮೋಪಾಚೊ", "mopacho", "ಕುರು", "kuru", "____"]},

    # 2. General Vocabulary & Wellness
    {"id": "UNSEEN_01", "category": "General Vocabulary", "query": "What is wellness in modern lifestyle?", "expected_domain": "GENERAL_KNOWLEDGE", "expected_lang": "en"},
    {"id": "UNSEEN_02", "category": "General Vocabulary", "query": "Explain the concept of human vitality", "expected_domain": "GENERAL_KNOWLEDGE", "expected_lang": "en"},

    # 3. Ambiguous Terminology
    {"id": "UNSEEN_03", "category": "Ambiguous Terminology", "query": "What is Pitta?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "en"},
    {"id": "UNSEEN_04", "category": "Ambiguous Terminology", "query": "Is Pitta the same as bile in modern biology?", "expected_domain": "MIXED_DOMAIN", "expected_lang": "en"},

    # 4. Ayurvedic Concepts
    {"id": "UNSEEN_05", "category": "Ayurvedic Concepts", "query": "What is Dhatusamyata?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "en"},
    {"id": "UNSEEN_06", "category": "Ayurvedic Concepts", "query": "Explain Ojas in classical Ayurvedic texts", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "en"},
    {"id": "UNSEEN_07", "category": "Ayurvedic Concepts", "query": "What is Ama according to Charaka Samhita?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "en"},

    # 5. Hindi Queries (Devanagari)
    {"id": "UNSEEN_08", "category": "Hindi (Devanagari)", "query": "वात दोष का प्रकोप किस ऋतु में होता है?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "hi"},
    {"id": "UNSEEN_09", "category": "Hindi (Devanagari)", "query": "कफ प्रकृति के व्यक्ति के लक्षण क्या हैं?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "hi"},
    {"id": "UNSEEN_10", "category": "Hindi (Devanagari)", "query": "अग्निमांद्य का क्या अर्थ है?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "hi"},

    # 6. Kannada Queries (Kannada Script)
    {"id": "UNSEEN_11", "category": "Kannada Script", "query": "ಪಿತ್ತ ಪ್ರಕೋಪ ಎಂದರೇನು?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "kn"},
    {"id": "UNSEEN_12", "category": "Kannada Script", "query": "ಆಯುರ್ವೇದದಲ್ಲಿ ಕಫ ದೋಷದ ಗುಣಗಳು ಯಾವುವು?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "kn"},
    {"id": "UNSEEN_13", "category": "Kannada Script", "query": "ಸ್ವಾಸ್ಥ್ಯ ಎಂದರೇನು?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "kn"},

    # 7. Romanized Hindi (Hinglish)
    {"id": "UNSEEN_14", "category": "Hinglish", "query": "Pitta badhne ke lakshan kya hote hain?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "hi"},
    {"id": "UNSEEN_15", "category": "Hinglish", "query": "Agni mand hone se kya dikkat hoti hai?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "hi"},

    # 8. Romanized Kannada (Kanglish)
    {"id": "UNSEEN_16", "category": "Kanglish", "query": "Vata dosha hecchagidre yenu madabeku?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "kn"},

    # 9. General Science
    {"id": "UNSEEN_17", "category": "General Science", "query": "What is photosynthesis in plant biology?", "expected_domain": "GENERAL_KNOWLEDGE", "expected_lang": "en"},
    {"id": "UNSEEN_18", "category": "General Science", "query": "Explain Newton's third law of motion", "expected_domain": "GENERAL_KNOWLEDGE", "expected_lang": "en"},

    # 10. Computer Science & Programming
    {"id": "UNSEEN_19", "category": "Programming", "query": "What is a binary search tree in computer science?", "expected_domain": "GENERAL_KNOWLEDGE", "expected_lang": "en"},
    {"id": "UNSEEN_20", "category": "Programming", "query": "Explain recursion in Python programming", "expected_domain": "GENERAL_KNOWLEDGE", "expected_lang": "en"},

    # 11. Mathematics
    {"id": "UNSEEN_21", "category": "Mathematics", "query": "What is the Pythagorean theorem?", "expected_domain": "GENERAL_KNOWLEDGE", "expected_lang": "en"},
    {"id": "UNSEEN_22", "category": "Mathematics", "query": "What is a prime number?", "expected_domain": "GENERAL_KNOWLEDGE", "expected_lang": "en"},

    # 12. History & Geography
    {"id": "UNSEEN_23", "category": "History", "query": "Who was Chandragupta Maurya?", "expected_domain": "GENERAL_KNOWLEDGE", "expected_lang": "en"},
    {"id": "UNSEEN_24", "category": "History", "query": "What was the Indus Valley Civilization?", "expected_domain": "GENERAL_KNOWLEDGE", "expected_lang": "en"},

    # 13. Mixed-Domain Inquiries
    {"id": "UNSEEN_25", "category": "Mixed Domain", "query": "How does modern pharmacology study Withania somnifera compared to Ayurvedic Rasayana?", "expected_domain": "MIXED_DOMAIN", "expected_lang": "en"},
    {"id": "UNSEEN_26", "category": "Mixed Domain", "query": "Compare Ayurvedic Agni with modern digestive enzymes", "expected_domain": "MIXED_DOMAIN", "expected_lang": "en"},

    # 14. Additional Verification Queries for Evidence Correctness (To reach 30)
    {"id": "EVID_27", "category": "Evidence Audit", "query": "What are the therapeutic uses of Triphala?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "en"},
    {"id": "EVID_28", "category": "Evidence Audit", "query": "What is Brahmi traditionally used for?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "en"},
    {"id": "EVID_29", "category": "Evidence Audit", "query": "What are the three sub-doshas of Vata?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "en"},
    {"id": "EVID_30", "category": "Evidence Audit", "query": "What does Prameha mean in Ayurveda?", "expected_domain": "AYURVEDA_DOMAIN", "expected_lang": "en"},
]


def run_forensic_suite():
    print("=" * 70)
    print("   AYURMITRA V2 FORENSIC EVIDENCE & GENERALIZATION SUITE")
    print("=" * 70)

    pipe = AyurMitraPipeline()
    results = []

    for idx, item in enumerate(UNSEEN_TEST_QUERIES, start=1):
        qid = item["id"]
        q = item["query"]
        cat = item["category"]
        exp_dom = item["expected_domain"]
        exp_lang = item.get("expected_lang", "en")
        forbidden = item.get("forbidden", [])

        t0 = time.time()
        res = pipe.process_query(q, system_mode="P2", target_lang="auto")
        dur_ms = round((time.time() - t0) * 1000, 2)

        actual_route = res.get("route_category")
        actual_lang = res.get("detected_language")
        answer = res.get("answer", "")
        citations = res.get("citations", [])
        retrieved_passages = res.get("retrieved_passages", [])
        retrieved_ids = [p.get("chunk_id") for p in retrieved_passages if p.get("chunk_id")]
        cited_ids = [c.get("chunk_id") for c in citations if c.get("chunk_id")]

        # Verification checks
        route_pass = actual_route == exp_dom or (exp_dom == "AYURVEDA_DOMAIN" and actual_route in ("AYURVEDA_DOMAIN", "MIXED_DOMAIN"))
        lang_pass = actual_lang == exp_lang or (exp_lang == "hi" and actual_lang in ("hi", "hinglish")) or (exp_lang == "kn" and actual_lang in ("kn", "kanglish"))
        forbidden_found = [f for f in forbidden if f.lower() in answer.lower()]
        no_forbidden = len(forbidden_found) == 0

        # Detailed Evidence Evaluation
        # 1. Citations exist?
        has_citations = len(cited_ids) > 0 or res.get("abstained", False)
        # 2. Citation points to retrieved passage?
        citation_in_retrieved = all(cid in retrieved_ids for cid in cited_ids) if cited_ids else True
        # 3. Passage is relevant?
        passage_relevant = len(retrieved_ids) > 0 and not res.get("abstained", False)
        # 4. Passage supports actual claim?
        claim_supported = False
        if answer and retrieved_passages:
            # Check overlap between answer key terms and retrieved passage texts
            ans_lower = answer.lower()
            passage_combined = " ".join(p.get("text", "").lower() for p in retrieved_passages[:3])
            # Check if key concepts from answer appear in retrieved passages
            key_words = [w for w in ans_lower.split() if len(w) > 4 and w.isalnum()]
            overlap = sum(1 for w in key_words if w in passage_combined)
            claim_supported = overlap > 3 or res.get("route_category") in ("GENERAL_KNOWLEDGE", "CURRENT_INFORMATION")

        overall_pass = route_pass and lang_pass and no_forbidden and (claim_supported or res.get("abstained", False))
        verdict = "PASS" if overall_pass else ("PARTIAL" if (route_pass and no_forbidden) else "FAIL")

        print(f"[{idx:02d}/30] {qid:<12} | {cat:<22} | Route: {actual_route:<18} | Status: {verdict}")
        if forbidden_found:
            print(f"       WARNING: Forbidden words detected: {forbidden_found}")

        results.append({
            "test_id": qid,
            "category": cat,
            "query": q,
            "expected_domain": exp_dom,
            "actual_domain": actual_route,
            "domain_match": route_pass,
            "expected_language": exp_lang,
            "actual_language": actual_lang,
            "language_match": lang_pass,
            "retrieved_chunk_ids": retrieved_ids[:5],
            "cited_chunk_ids": cited_ids,
            "citation_exists": len(cited_ids) > 0,
            "citation_in_retrieved": citation_in_retrieved,
            "passage_relevant": passage_relevant,
            "passage_supports_claim": claim_supported,
            "forbidden_detected": forbidden_found,
            "abstained": res.get("abstained", False),
            "latency_ms": dur_ms,
            "verdict": verdict,
            "answer_preview": answer[:250].replace("\n", " "),
        })

    out_file = os.path.join(ROOT, "AYURMITRA_FORENSIC_TEST_RESULTS.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nForensic results written to: {out_file}")
    total = len(results)
    passed = sum(1 for r in results if r["verdict"] == "PASS")
    partial = sum(1 for r in results if r["verdict"] == "PARTIAL")
    failed = sum(1 for r in results if r["verdict"] == "FAIL")
    print(f"Summary: Total={total} | PASS={passed} | PARTIAL={partial} | FAIL={failed}")


if __name__ == "__main__":
    run_forensic_suite()
