"""
AyurMitra — Independent verification script for target RAG queries
"""
import sys
import os

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from app.pipeline.rag_pipeline import AyurMitraPipeline

pipe = AyurMitraPipeline()

test_queries = [
    "What is Ayurveda?",
    "What is Agni?",
    "What are the three doshas?",
    "What is the role of Vata?",
    "पित्त दोष के कार्य क्या हैं?",
    "ಆಯುರ್ವೇದ ಎಂದರೇನು?",
    "Agni digestion alli enu role ide?"
]

has_issue = False

for q in test_queries:
    print("=" * 70)
    print("QUERY:", q)
    res = pipe.process_query(q, system_mode="P2")
    ans = res.get("answer", "")
    citations = res.get("citations", [])
    abstained = res.get("abstained", False)
    retrieved = res.get("retrieved_passages", [])
    
    print(f"ABSTAINED: {abstained} | REASON: {res.get('abstention_reason')}")
    print("RETRIEVAL QUERY:", res.get("retrieval_query"))
    print("DETECTED TERMS:", res.get("detected_terms"))
    print(f"PASSAGES RETRIEVED: {len(retrieved)}")
    for i, p in enumerate(retrieved[:3]):
        cid = p.get("chunk_id")
        score = p.get("rrf_score", 0.0)
        snippet = (p.get("text", "")[:100]).replace("\n", " ")
        print(f"  [{i+1}] {cid} ({score:.4f}): {snippet}...")
    
    print("\n--- ANSWER ---")
    print(ans)
    print("--- CITATIONS ---")
    print([c.get("chunk_id") for c in citations])
    
    # Verification checks:
    # 1. No URLs
    if "http://" in ans or "https://" in ans or "www." in ans:
        print("FAIL: Promotional URL detected in answer!")
        has_issue = True
    # 2. No clinic promo terms
    for promo in ["contact us", "book an appointment", "call today", "dr. sharda", "specializes in"]:
        if promo in ans.lower():
            print(f"FAIL: Promotional phrase '{promo}' detected in answer!")
            has_issue = True
    # 3. Check citations match retrieved
    retrieved_cids = {p.get("chunk_id") for p in retrieved}
    for c in citations:
        if c.get("chunk_id") not in retrieved_cids:
            print(f"FAIL: Citation {c.get('chunk_id')} not in retrieved passages!")
            has_issue = True
            
    if abstained:
        print("WARNING: Query abstained!")
        has_issue = True
    else:
        print("VERIFICATION CHECK: PASS")

print("=" * 70)
if has_issue:
    print("SOME QUERIES HAD ISSUES")
    sys.exit(1)
else:
    print("ALL 7 TARGET QUERIES PASSED VERIFICATION")
    sys.exit(0)
