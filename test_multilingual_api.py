import urllib.request
import json
import re

tests = [
    ("Madhumeh kya hota hai.", "hi", "devanagari"),
    ("वात दोष क्या है?", "hi", "devanagari"),
    ("Pitta badhne par kya hota hai?", "hi", "devanagari"),
    ("ಮಧುಮೇಹ ಎಂದರೇನು?", "kn", "kannada"),
    ("Agni mandya andre enu?", "kn", "kannada"),
    ("What is Vata dosha?", "en", "latin"),
]

print("Starting API Verification against http://127.0.0.1:8000/api/ask ...\n")

all_passed = True
for q, exp_lang, exp_script in tests:
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/ask",
        data=json.dumps({"query": q, "mode": "P2", "target_lang": "auto"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        ans = data.get("answer", "")
        t_lang = data.get("target_language")
        tts = data.get("tts_lang")
        
        # Check corrupted tokens
        corrupted_tokens = ["abritA", "nadhunehA", "prakAra", "kA ", "nen "]
        found_corrupted = [tok for tok in corrupted_tokens if tok in ans]
        
        # Check script
        dev_chars = len(re.findall(r"[\u0900-\u097F]", ans))
        kn_chars = len(re.findall(r"[\u0C80-\u0CFF]", ans))
        
        script_pass = True
        if exp_script == "devanagari" and dev_chars < 15:
            script_pass = False
        elif exp_script == "kannada" and kn_chars < 15:
            script_pass = False
        
        passed = (t_lang == exp_lang) and (not found_corrupted) and script_pass
        if not passed:
            all_passed = False
            
        print(f"QUERY: '{q}'")
        print(f"  Target Lang: {t_lang} (expected {exp_lang}) -> {'PASS' if t_lang == exp_lang else 'FAIL'}")
        print(f"  TTS Code:    {tts}")
        print(f"  Script Chars: Devanagari={dev_chars}, Kannada={kn_chars} -> {'PASS' if script_pass else 'FAIL'}")
        print(f"  Corrupted Tokens: {found_corrupted or 'None (PASS)'}")
        lines = [line.strip() for line in ans.split("\n") if line.strip()]
        first_few = " | ".join(lines[:2])
        print(f"  Sample Output: {first_few[:140]}...")
        print(f"  Result: {'PASS' if passed else 'FAIL'}\n")

print(f"OVERALL API TEST SUITE: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
