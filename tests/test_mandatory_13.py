import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.pipeline.rag_pipeline import AyurMitraPipeline

p = AyurMitraPipeline()

test_queries = [
    ("What is roga?", "en"),
    ("What is disease?", "en"),
    ("What is Roga in Ayurveda?", "en"),
    ("What is Kuru disease?", "en"),
    ("What is Mopacho?", "en"),
    ("रोग मतलब क्या होता है?", "hi"),
    ("आयुर्वेद में रोग का क्या अर्थ है?", "hi"),
    ("मधुमेह क्या होता है?", "hi"),
    ("वात दोष क्या है?", "hi"),
    ("ರೋಗ ಎಂದರೇನು?", "kn"),
    ("ಆಯುರ್ವೇದದಲ್ಲಿ ರೋಗ ಎಂದರೇನು?", "kn"),
    ("ಮಧುಮೇಹ ಎಂದರೇನು?", "kn"),
    ("ವಾತ ದೋಷ ಎಂದರೇನು?", "kn"),
]

print("=" * 80)
print("TESTING 13 MANDATORY REGRESSION QUERIES")
print("=" * 80)

for i, (q, expected_lang) in enumerate(test_queries, 1):
    t0 = time.time()
    res = p.process_query(q, system_mode="P2", target_lang="auto")
    elapsed = (time.time() - t0) * 1000
    route = res.get("route_label")
    lang = res.get("target_language")
    ans = res.get("answer", "")
    ans_one_line = ans[:160].replace("\n", " ")

    # Verification checks
    failed = False
    fail_reason = ""
    if "mopacho" in q.lower():
        if "mopacho" not in ans.lower() or "dance" not in ans.lower():
            failed = True
            fail_reason = "Expected Mopacho explanation"
    elif "kuru" in q.lower():
        if "kuru" not in ans.lower() or "prion" not in ans.lower():
            failed = True
            fail_reason = "Expected Kuru explanation"
    elif "roga" in q.lower() or "रोग" in q or "ರೋಗ" in q or "disease" in q.lower():
        if "mopacho" in ans.lower() or "kuru" in ans.lower():
            failed = True
            fail_reason = "Corrupted with Mopacho or Kuru"

    status = "FAIL" if failed else "PASS"
    print(f"[{i:02d}] {status} | Q: {q}")
    print(f"     Route: {route} | Lang: {lang} | Latency: {elapsed:.1f}ms")
    print(f"     Answer: {ans_one_line}")
    if failed:
        print(f"     FAILED REASON: {fail_reason}")
    print("-" * 80)
