import urllib.request
import json
import re

queries = [
    ("Madhumeh kya hota hai?", "hi"),
    ("Pitta badhne par kya hota hai?", "hi"),
    ("Agni mandya andre enu?", "kn"),
    ("ವಾತ ದೋಷ ಎಂದರೇನು?", "kn"),
    ("वात दोष क्या है?", "hi"),
    ("What is Vata dosha?", "en"),
]

print("=== RUNNING CLEAN MULTILINGUAL VERIFICATION ===\n")

for q, exp_lang in queries:
    payload = {"query": q, "mode": "P2", "target_lang": "auto", "web_fallback": False, "generator": "extractive"}
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/ask",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        ans = data.get("answer", "")
        t_lang = data.get("target_language")
        tts = data.get("tts_lang")
        
        # Check corrupted tokens
        corrupted = re.findall(r"(?:__|निः?)\s*(?:AYURTERM|ayurterm|आयुरटर्म|अयुर्तर्म|ಆಯುರ್ಟರ್ಮ್)[\s_]*[0-9०-९೦-೯]+\s*__?|abritA|nadhunehA|prakAra", ans, re.I)
        
        print("=" * 60)
        print(f"QUERY: '{q}'")
        print(f"Language Mode: {t_lang} (expected {exp_lang}), TTS: {tts}")
        print(f"Any Corrupted Tokens Found: {corrupted or 'None (CLEAN)'}")
        print("-" * 60)
        print(ans[:600])
        print("=" * 60 + "\n")
